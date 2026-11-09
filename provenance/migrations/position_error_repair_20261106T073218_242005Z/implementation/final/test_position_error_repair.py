"""Source-semantic and identity fixtures for the approved error-only repair."""
import tempfile
import unittest
from pathlib import Path

import netCDF4
import h5py
import numpy as np
import pandas as pd

from data3001.preprocessing.position_error_repair import (
    classify_axis, coordinate_match, decode_values, epoch_values,
    identity_basis, numeric_attribute, read_reference, build_overlay,
)


class ErrorRules(unittest.TestCase):
    def test_missing_mask_precedes_scaling(self):
        a,m=decode_values(np.array([-999999,100],dtype='int32'),
                          {'missing_value':-999999,'scale_factor':1e-5})
        self.assertTrue(m[0] and np.isnan(a[0])); self.assertEqual(a[1],.001)

    def test_string_missing_marker_uses_storage_dtype(self):
        v=np.array([-1e34,.001],dtype='float32')
        decoded,mask=decode_values(v,{'missing_value':'-1.e+34f'})
        self.assertTrue(mask[0] and np.isnan(decoded[0])); self.assertEqual(decoded[1],float(v[1]))

    def test_no_undeclared_scaling(self):
        x=np.array([.01107,.00166]);y,_=decode_values(x,{})
        np.testing.assert_array_equal(x,y)

    def test_negative_zero_and_partial_axis(self):
        values,status=classify_axis([1e-8,-9.99999,np.nan,np.nan],[.001,0,-1,np.nan],[False,False,False,True],'lat',[35]*4)
        self.assertEqual(status.tolist(),['restored_scale','zero_unresolved','reference_invalid','reference_missing'])
        self.assertEqual(values[0],.001); self.assertTrue(np.isnan(values[1:]).all())

    def test_reference_recovery_and_unchanged(self):
        v,s=classify_axis([np.nan,-1,.00166],[.002,.003,.00166],[False]*3,'lon',[30]*3)
        self.assertEqual(s.tolist(),['recovered_from_reference']*2+['verified_unchanged'])
        np.testing.assert_array_equal(v,[.002,.003,.00166])

    def test_unknown_positive_change_not_accepted(self):
        v,s=classify_axis([.001],[.003],[False],'lon',[30])
        self.assertTrue(np.isnan(v[0])); self.assertEqual(s[0],'unexplained_difference')

    def test_geometry_not_clipped(self):
        for axis,ref,lat in [('lon',180,30),('lat',10,85)]:
            v,s=classify_axis([ref],[ref],[False],axis,[lat])
            self.assertTrue(np.isnan(v[0])); self.assertEqual(s[0],'geometry_review_required')

    def test_coordinates_periodic_and_precision_only(self):
        self.assertTrue(coordinate_match(-75,35,285,35))
        self.assertFalse(coordinate_match(-75,35,-75.001,35))
        v=float(np.float32(35.12345));self.assertTrue(coordinate_match(-75,v,-75,35.12345))

    def test_explicit_imei_mapping_only(self):
        self.assertEqual(identity_basis(7647,7647,{}),'native_id_exact')
        self.assertEqual(identity_basis(300234066710170,66710170,{'imei':'300234066710170'}),'official_imei_exact')
        with self.assertRaises(ValueError): identity_basis(300234066710170,66710170,{'imei':'wrong'})

    def test_no_attribute_execution(self):
        with self.assertRaises(ValueError): numeric_attribute('__import__("os")')

    def test_time_conversion_and_calendar(self):
        z=epoch_values([0,1],{'units':'hours since 2001-01-01 00:00:00 UTC'})
        self.assertEqual(z[1]-z[0],3600)
        with self.assertRaises(ValueError):epoch_values([0],{'units':'days since 2001-01-01','calendar':'360_day'})


class NativeFileRules(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.path=Path(self.tmp.name)/'native.nc'
        with netCDF4.Dataset(self.path,'w') as d:
            d.createDimension('obs',3);d.createDimension('traj',1)
            d.createVariable('ID','i8',('traj',))[:]=7647
            d.createVariable('typedeath','i4',('traj',))[:]=3
            v=d.createVariable('end_date','f8',('traj',));v.units='seconds since 1970-01-01 00:00:00 UTC';v[:]=1e9
            d.history='Version 2.00. Metadata';d.location_type='Argos';d.time_coverage_end='2002-01-01T00:00:00Z'
            for k,vals in {'time':[1000,4600,8200],'longitude':[-75]*3,'latitude':[35]*3,'err_lon':[.001,.00166,.003],'err_lat':[.002,0,.003]}.items():
                v=d.createVariable(k,'f8',('obs',));v[:]=vals
                if k=='time':v.units='seconds since 1970-01-01 00:00:00 UTC'
                if k.startswith('err_'):
                    v.units='degrees_east' if k=='err_lon' else 'degrees_north'
                    v.long_name='95% confidence interval'
        self.t=pd.DataFrame({'source_obs':[1,2,3], 'id':[7647]*3,'time':[1000.,4600.,8200.],
           'lon':[-75.]*3,'lat':[35.]*3,'original_err_lon':[1e-8,.00166,3e-8],
           'original_err_lat':[2e-8,-9.99999,3e-8]})

    def tearDown(self):self.tmp.cleanup()

    def test_native_and_overlay(self):
        f,m=read_reference(self.path,7647,self.t)
        o=build_overlay(self.t,[(f,m)],'test')
        self.assertEqual(o.status_lon.tolist(),['restored_scale','verified_unchanged','restored_scale'])
        self.assertEqual(o.ci_2d_usable.tolist(),[True,False,True])
        self.assertTrue(np.isnan(o.repaired_err_lat.iloc[1]))

    def test_independent_reference_reader(self):
        from data3001.preprocessing.verify_position_error_repair import reference_rows,axis_result
        rows=reference_rows(self.path,7647,self.t)
        self.assertEqual(rows[1]['lon'][1],.001)
        self.assertEqual(rows[2]['lat'][1],0)
        self.assertEqual(axis_result(-9.99999,rows[2]['lat'],'lat',35)[1],'zero_unresolved')

    def test_independent_reader_masks_before_unpacking(self):
        from data3001.preprocessing.verify_position_error_repair import unpack
        path=Path(self.tmp.name)/'packed.h5'
        with h5py.File(path,'w') as h:
            d=h.create_dataset('error',data=np.array([-999999,100],dtype='int32'))
            d.attrs['missing_value']='-999999';d.attrs['scale_factor']=1e-5
        with h5py.File(path,'r') as h:
            raw,value,missing,_=unpack(h['error'])
        self.assertTrue(np.isnan(value[0]) and missing[0]);self.assertEqual(value[1],.001)

    def test_wrong_id_rejected(self):
        with self.assertRaises(ValueError):read_reference(self.path,9999,self.t)

    def test_wrong_time_and_coordinate_not_repaired(self):
        t=self.t.copy();t.loc[0,'time']+=86400;t.loc[1,'lon']+=.01
        f,m=read_reference(self.path,7647,t);o=build_overlay(t,[(f,m)],'test')
        self.assertEqual(o.match_status.tolist(),['time_unmatched','coordinate_changed','matched'])
        self.assertTrue(o.repaired_err_lon.iloc[:2].isna().all())

    def test_unknown_units_and_version_rejected(self):
        with netCDF4.Dataset(self.path,'a') as d:d['err_lon'].units='radians'
        f,m=read_reference(self.path,7647,self.t);self.assertFalse(m['eligible'])

    def test_active_old_version_rejected(self):
        with netCDF4.Dataset(self.path,'a') as d:
            d['typedeath'][:]=0
            d['end_date'][:]=np.nan
        f,m=read_reference(self.path,7647,self.t)
        self.assertFalse(m['eligible']);self.assertTrue(f.match_status.eq('estimation_version_unresolved').all())

    def test_post_cutoff_source_rejected_before_missing_end_date(self):
        from data3001.preprocessing.verify_position_error_repair import reference_rows
        with netCDF4.Dataset(self.path,'a') as d:
            d.time_coverage_end='2021-01-01T00:00:00Z'
            d['end_date'][:]=np.nan
        frame,meta=read_reference(self.path,7647,self.t)
        expected=reference_rows(self.path,7647,self.t)
        self.assertFalse(meta['eligible'])
        self.assertTrue(frame.match_status.eq('estimation_version_unresolved').all())
        self.assertTrue(all(row['status']=='estimation_version_unresolved' for row in expected.values()))

    def test_unaudited_version_with_matching_positions_rejected(self):
        from data3001.preprocessing.verify_position_error_repair import reference_rows
        with netCDF4.Dataset(self.path,'a') as d:d.history='Version 2.01. Metadata'
        frame,meta=read_reference(self.path,7647,self.t)
        expected=reference_rows(self.path,7647,self.t)
        self.assertFalse(meta['eligible'])
        self.assertTrue(frame.match_status.eq('version_unresolved').all())
        self.assertTrue(all(row['status']=='version_unresolved' for row in expected.values()))

    def test_conflicting_references_not_selected(self):
        f,m=read_reference(self.path,7647,self.t);other=f.copy();other.loc[0,'ref_err_lon']*=2
        o=build_overlay(self.t,[(f,m),(other,m)],'test')
        self.assertEqual(o.match_status.iloc[0],'reference_conflict');self.assertFalse(o.ci_2d_usable.iloc[0])

    def test_duplicate_conflict_and_exact_duplicate(self):
        with netCDF4.Dataset(self.path,'a') as d:d['time'][:]=[1000,1000,8200]
        f,m=read_reference(self.path,7647,self.t)
        self.assertEqual(f.match_status.iloc[0],'duplicate_conflict')
        with netCDF4.Dataset(self.path,'a') as d:
            for k in ['err_lon','err_lat']:d[k][1]=d[k][0]
        f,m=read_reference(self.path,7647,self.t);self.assertEqual(f.match_status.iloc[0],'matched')


if __name__=='__main__':unittest.main()
