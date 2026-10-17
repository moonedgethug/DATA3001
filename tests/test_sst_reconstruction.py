"""Scientific semantics of sourced SST reconstruction (not forecast accuracy)."""
import importlib
import unittest
import numpy as np
import tempfile
from pathlib import Path
import hashlib

try:
    m = importlib.import_module('data3001.sst_reconstruction')
except ModuleNotFoundError:
    m = None


class SSTReconstructionTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(m, 'SST reconstruction is not implemented')

    def test_bilinear_uses_four_weights_and_kelvin_conversion(self):
        value, w = m.bilinear(0.25, 0.5, np.array([20., 24., 28., 32.]))
        self.assertAlmostEqual(value + 273.15, 298.15)
        np.testing.assert_allclose(w, [.375, .125, .375, .125])

    def test_incomplete_stencil_is_not_renormalized(self):
        self.assertTrue(np.isnan(m.bilinear(.5, .5, [20., np.nan, 22., 24.])[0]))

    def test_outside_stencil_fails(self):
        with self.assertRaises(ValueError):
            m.bilinear(1.1, .5, [20., 21., 22., 23.])

    def test_longitude_normalization_and_grid_wrap(self):
        i, j, u, v = m.stencil(np.array([-79.75, -.01]), np.array([30.25, 0.]))
        np.testing.assert_array_equal(i, [1120, 1439])
        np.testing.assert_array_equal(j, [480, 359])
        np.testing.assert_allclose(u, [.5, .46])
        np.testing.assert_allclose(v, [.5, .5])

    def test_source_poles_are_not_extrapolated(self):
        with self.assertRaises(ValueError):
            m.stencil(np.array([0.]), np.array([89.99]))

    def test_three_missing_hours_use_native_brackets(self):
        t = np.arange(5) * 3600.
        y = np.array([298.15, np.nan, np.nan, np.nan, 300.15])
        got, left, right = m.short_linear(t, y, np.isfinite(y), np.ones(5, bool), np.isnan(y), 3)
        np.testing.assert_allclose(got[1:4], [298.65, 299.15, 299.65])
        np.testing.assert_array_equal(left[1:4], [0, 0, 0])
        np.testing.assert_array_equal(right[1:4], [4, 4, 4])
        self.assertTrue(np.isnan(got[0]) and np.isnan(got[4]))

    def test_gap_limit_and_missing_positions_prevent_bridge(self):
        for t, ok in [(np.arange(6) * 3600., np.ones(6, bool)),
                      (np.array([0, 3600, 10800, 14400.]), np.ones(4, bool)),
                      (np.arange(4)*3600., np.array([1, 1, 0, 1], bool))]:
            y = np.full(len(t), np.nan); y[0] = 298.; y[-1] = 300.
            got, _, _ = m.short_linear(t, y, np.isfinite(y), ok, np.isnan(y), 3)
            self.assertTrue(np.isnan(got).all())

    def test_no_extrapolation_or_imputed_anchor(self):
        y = np.array([np.nan, 298., np.nan, 300., np.nan])
        got, _, _ = m.short_linear(np.arange(5)*3600., y, np.array([0,1,0,0,0], bool),
                                    np.ones(5, bool), np.isnan(y), 3)
        self.assertTrue(np.isnan(got).all())

    def test_rejected_finite_record_is_not_a_routine_missing_gap(self):
        y = np.array([298., np.nan, 999., 300.])
        got, _, _ = m.short_linear(np.arange(4)*3600., y, np.array([1,0,0,1], bool),
                                    np.ones(4, bool), ~np.isfinite(y), 3)
        self.assertTrue(np.isnan(got).all())

    def test_error_bound_does_not_assume_independent_errors(self):
        # Perfect positive correlation attains this upper bound. No model-error claim.
        self.assertAlmostEqual(m.error_bound([.5,.5], [.2,.4]), .3)
        self.assertTrue(np.isnan(m.error_bound([.5,.5], [.2,np.nan])))

    def test_two_sided_interpolation_is_retrospective(self):
        self.assertEqual(m.AVAILABILITY, 'retrospective_only')

    def test_unresolved_motion_flags_block_optional_interpolation(self):
        np.testing.assert_array_equal(m.interpolation_path_ok([1,1,1],[1,0,1],[0,0,1]),[1,0,0])

    def test_resume_enforces_frozen_target_and_configuration_hashes(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);(p/'input').write_bytes(b'original')
            h=hashlib.sha256(b'original').hexdigest()
            m.verify_frozen(p,{'input':h})
            (p/'input').write_bytes(b'changed')
            with self.assertRaises(ValueError):m.verify_frozen(p,{'input':h})

    def test_cache_is_bound_to_request_and_source_metadata(self):
        b=b'bytes';h=hashlib.sha256(b).hexdigest()
        good={'url':'correct','response_sha256':h,'metadata_sha256':'meta'}
        m.verify_cached(b,good,'correct','meta')
        with self.assertRaises(ValueError):m.verify_cached(b,good,'other','meta')
        with self.assertRaises(ValueError):m.verify_cached(b,good,'correct','changed')
        with self.assertRaises(ValueError):m.verify_cached(b'bad',good,'correct','meta')

    def test_packed_zarr_fill_is_masked_before_scale_and_offset(self):
        import numcodecs
        codec=numcodecs.Blosc(cname='lz4',clevel=5,shuffle=2)
        raw=codec.encode(np.array([[-999,2964],[100,200]],dtype='<i2'))
        spec={'dtype':'<i2','shape':[2,2],'chunks':[2,2],'compressor':codec.get_config(),
              'fill_value':-999,'order':'C','filters':None}
        attrs={'scale_factor':.01,'add_offset':0.,'valid_min':-300,'valid_max':4500}
        out=m.decode_zarr_chunk(raw,spec,attrs)
        self.assertTrue(np.isnan(out[0,0]));self.assertAlmostEqual(out[0,1],29.64)

    def test_masked_validation_compares_the_same_cases(self):
        out=m.paired_metrics([10.,20.,30.],[11.,np.nan,31.],[12.,22.,np.nan])
        self.assertEqual(out['n_common'],1)
        self.assertAlmostEqual(out['a_MAE'],1.)
        self.assertAlmostEqual(out['b_MAE'],2.)

    def test_source_fallback_is_only_for_absent_cloud_objects(self):
        self.assertTrue(m.source_fallback_allowed(404))
        self.assertFalse(m.source_fallback_allowed(429))
        self.assertFalse(m.source_fallback_allowed(500))

if __name__ == '__main__':
    unittest.main()
