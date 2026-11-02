"""Semantic tests for the approved E3 v2 target, before empirical selection."""
import copy
import json
from pathlib import Path
import unittest
from unittest.mock import patch
from types import SimpleNamespace

import numpy as np
import pandas as pd

from data3001.modelling.baselines.drifter_shrinkage_e3 import (
    fit_bases, vector, candidate_units, select_parameters, summarize_units,
    diagnostic_scores, score_units, attach_primary_weights, uncertainty, GRID, METRICS,
)
from data3001.modelling.baselines.drifter_shrinkage_e3_audit import rebuild, audit_candidates, macro
from data3001.modelling.baselines.run_drifter_shrinkage_e3 import expected_config, validate_config, source_hashes


def fixture():
    rows = []
    for h in (7, 30):
        rows += [[1,h,10,10,6], [1,h,10,-2,2], [2,h,10,-2,2], [2,h,20,20,4],
                 [3,h,10,30,2], [3,h,10,-2,1], [4,h,10,10,5], [3,h,20,20,2], [3,h,30,30,7]]
    return pd.DataFrame(rows, columns=["id","horizon_days","origin_cell_1","destination_cell_1","pair_count"])


class E3Tests(unittest.TestCase):
    def base(self, counts=None, ids=(1,2)):
        return fit_bases(fixture() if counts is None else counts, ids, [10,20,30], [-2,10,20,30])

    def test_equal_id_hand_example_and_exit(self):
        b = self.base()
        np.testing.assert_allclose(b.rows[(7,10)], [.4,.6,0,0], atol=1e-15)
        np.testing.assert_allclose(b.equal_rows[(7,10)], [.625,.375,0,0], atol=1e-15)
        g = b.contributions[(b.contributions.horizon_days == 7) & (b.contributions.origin_cell_1 == 10)]
        np.testing.assert_allclose(g.raw_share, [.8,.2])
        np.testing.assert_allclose(g.equal_share, [.5,.5])
        self.assertEqual(set(g.id), {1,2})
        self.assertTrue(b.local_distributions.pair_count.dtype.kind in "iu")

    def test_replication_invariance_and_no_mutation(self):
        counts = fixture(); untouched = counts.copy()
        a = self.base(counts)
        pd.testing.assert_frame_equal(counts, untouched)
        counts.loc[(counts.id == 1) & (counts.origin_cell_1 == 10), "pair_count"] *= 20
        b = self.base(counts)
        for key in a.equal_rows:
            np.testing.assert_allclose(a.equal_rows[key], b.equal_rows[key], rtol=0, atol=1e-15)
        self.assertFalse(np.allclose(a.rows[(7,10)], b.rows[(7,10)]))

    def test_degenerate_rows_and_order(self):
        b = self.base()
        np.testing.assert_array_equal(b.equal_rows[(7,20)], b.rows[(7,20)])
        single = self.base(ids=(1,))
        np.testing.assert_array_equal(single.equal_rows[(7,10)], single.rows[(7,10)])
        changed = fixture()
        changed.loc[changed.id.eq(2) & changed.origin_cell_1.eq(10), "pair_count"] = 8
        equal = self.base(changed)
        np.testing.assert_array_equal(equal.equal_rows[(7,10)], equal.rows[(7,10)])
        reverse = self.base(fixture().iloc[::-1])
        for key in b.equal_rows:
            np.testing.assert_array_equal(b.equal_rows[key], reverse.equal_rows[key])

    def test_horizon_and_origin_specific_counts(self):
        data = fixture()
        data.loc[(data.id == 1) & (data.horizon_days == 30), "pair_count"] *= 3
        base = self.base(data)
        self.assertEqual(base.contributions[(base.contributions.id == 2) & (base.contributions.origin_cell_1 == 20)].row_id_count.tolist(), [1,1])
        np.testing.assert_array_equal(base.equal_rows[(7,10)], base.equal_rows[(30,10)])

    def test_true_zero_support_and_no_fallback(self):
        b = self.base()
        self.assertIsNone(vector(b,7,30,"Fixed",1))
        for key in b.rows:
            np.testing.assert_array_equal(b.rows[key] > 0, b.equal_rows[key] > 0)
        scores,_ = diagnostic_scores(b, b.rows, fixture(), [3,4], "B2")
        unseen = scores[(scores.horizon_days == 7) & (scores.origin_cell_1 == 10) & (scores.destination_cell_1 == 30)].iloc[0]
        self.assertAlmostEqual(unseen.brier,1.52)
        self.assertEqual(unseen.zero_true_probability,1)
        self.assertTrue(scores.loc[scores.origin_cell_1.eq(30),"brier"].isna().all())

    def test_holdout_cannot_change_fit_and_overlap_rejected(self):
        a = self.base(); data = fixture()
        data.loc[data.id.isin([3,4]), "pair_count"] *= 1000
        b = self.base(data)
        for key in a.equal_rows:
            np.testing.assert_array_equal(a.equal_rows[key],b.equal_rows[key])
        for h in (7,30):
            np.testing.assert_array_equal(a.references[h],b.references[h])
        with self.assertRaises(ValueError):
            candidate_units(a, fixture(), [1,3])
        with self.assertRaises(ValueError):
            self.base(data[data.horizon_days.eq(7)])

    def test_fixed_endpoints_and_full_grid(self):
        b = self.base()
        for key in b.rows:
            np.testing.assert_array_equal(vector(b,*key,"Fixed",0),b.rows[key])
            np.testing.assert_array_equal(vector(b,*key,"Fixed",1),b.references[key[0]])
        c = candidate_units(b, fixture(), [3,4])
        table = summarize_units(c, ("horizon_days","model","parameter_a"))
        self.assertEqual(len(table),46)
        chosen,_ = select_parameters(c)
        self.assertEqual(len(chosen),2)

    def test_compressed_candidate_matches_case_weighted_evaluation(self):
        b = self.base()
        candidates = candidate_units(b, fixture(), [3,4])
        for model,a in [("B2",0),("EqualID",0),("Fixed",.35)]:
            vectors = {key:vector(b,*key,model,a) for key in b.rows}
            scores,_ = diagnostic_scores(b,vectors,fixture(),[3,4],model)
            units = score_units(scores)
            expected = summarize_units(units).set_index("horizon_days")
            actual = summarize_units(candidates[(candidates.model == model)&(candidates.parameter_a == a)]).set_index("horizon_days")
            np.testing.assert_allclose(expected[list(METRICS)],actual[list(METRICS)],rtol=0,atol=1e-12)

    def test_three_level_mean_and_explicit_case_weights(self):
        rows=[]
        for origin,ident,n,b in [(10,3,100,.2),(10,4,10,.8),(20,3,2,.3)]:
            rows.append(dict(horizon_days=7,model="B2",origin_cell_1=origin,id=ident,
                             eligible_pairs=n,supported=True,brier=b,region90_cells=10,region90_hit=.9))
        units=pd.DataFrame(rows)
        primary=summarize_units(units).iloc[0]
        pair=summarize_units(units,pair_weighted=True).iloc[0]
        self.assertAlmostEqual(primary.brier,.4)
        self.assertNotAlmostEqual(primary.brier,pair.brier)
        self.assertAlmostEqual(macro(rows)["brier"],.4)
        cases=pd.DataFrame([{**r,"pair_count":r["eligible_pairs"],"destination_cell_1":10,"status":"evaluable"} for r in rows])
        weights=attach_primary_weights(cases)
        np.testing.assert_allclose(weights.primary_group_weight,[.25,.25,.5],atol=1e-15)
        self.assertAlmostEqual(weights.primary_group_weight.sum(),1.)

    def test_metric_conditioning_keeps_original_base_weights(self):
        units=pd.DataFrame([
            dict(horizon_days=7,model="B2",origin_cell_1=10,id=3,eligible_pairs=10,supported=True,D_region_hit=.5,D_region_hit__mass=.5),
            dict(horizon_days=7,model="B2",origin_cell_1=10,id=4,eligible_pairs=2,supported=True,D_region_hit=0,D_region_hit__mass=1)])
        r=summarize_units(units,metrics=("D_region_hit",)).iloc[0]
        self.assertAlmostEqual(r.D_region_hit,1/3)

    def test_independent_macro_stable_for_many_IDs(self):
        rows=[dict(origin_cell_1=cell,id=ident,eligible_pairs=ident+1,supported=True,
                   brier=.7,region90_cells=200.,region90_hit=.9)
              for cell,n in [(10,700),(20,233),(30,91)] for ident in range(n)]
        result=macro(rows)
        self.assertLessEqual(abs(result["region90_cells"]-200),1e-12)

    def test_id_mean_invariant_to_evaluation_record_replication(self):
        b=self.base(); data=fixture()
        s,_=diagnostic_scores(b,b.equal_rows,data,[3,4],"EqualID")
        expected=summarize_units(score_units(s))
        data.loc[data.id.eq(3)&data.origin_cell_1.eq(10),"pair_count"]*=20
        t,_=diagnostic_scores(b,b.equal_rows,data,[3,4],"EqualID")
        actual=summarize_units(score_units(t))
        np.testing.assert_allclose(expected[list(METRICS)],actual[list(METRICS)],rtol=0,atol=1e-12)

    def selector_fixture(self, identical=False):
        rows=[]
        for h in (7,30):
            for model,a in [("B2",0),("EqualID",0),*[("Fixed",a) for a in GRID]]:
                for cell,ident,n,target in [(10,3,100,0),(10,4,1,1),(20,3,1,1)]:
                    loss=1 if identical else (a-target)**2
                    rows.append(dict(horizon_days=h,model=model,parameter_a=a,origin_cell_1=cell,id=ident,
                                     eligible_pairs=n,supported=True,brier=loss,region90_cells=10+10*a,region90_hit=1-a/5))
        return pd.DataFrame(rows)

    def test_primary_selector_disagrees_with_pair_selector_and_ignores_region(self):
        units=self.selector_fixture()
        chosen,pool=select_parameters(units)
        self.assertTrue(chosen.parameter_a.eq(.75).all())
        pair=summarize_units(units,("horizon_days","model","parameter_a"),pair_weighted=True)
        best=pair[pair.model.eq("Fixed")].sort_values("brier").iloc[0].parameter_a
        self.assertEqual(best,0.)
        self.assertTrue(chosen.region90_cells.gt(10).all())
        self.assertTrue(chosen.region90_hit.lt(1).all())

    def test_ties_and_duplicate_pool_rejected(self):
        selected,_=select_parameters(self.selector_fixture(True))
        self.assertTrue(selected.parameter_a.eq(0).all())
        data=self.selector_fixture()
        with self.assertRaises(ValueError):
            select_parameters(pd.concat([data,data],ignore_index=True))
        with self.assertRaises(ValueError):
            select_parameters(data[~data.parameter_a.eq(.5)])

    def test_availability_and_empty_supported_pool(self):
        b=self.base()
        units=candidate_units(b,fixture(),[3,4])
        table=summarize_units(units,("horizon_days","model","parameter_a"))
        self.assertTrue(np.allclose(table.target_availability,2/3))
        self.assertTrue(table.unsupported_id_cells.eq(1).all())
        absent=units[units.origin_cell_1.eq(30)]
        with self.assertRaises(ValueError):
            select_parameters(absent)

    def test_brier_minimizer_identity(self):
        b=self.base(); q=b.equal_rows[(7,10)]
        optimum=1-np.dot(q,q)
        for p in [b.rows[(7,10)],b.references[7],np.ones(4)/4]:
            loss=1+np.dot(p,p)-2*np.dot(q,p)
            self.assertAlmostEqual(loss-optimum,np.dot(p-q,p-q))

    def test_independent_candidate_reconstruction(self):
        data=fixture(); b=self.base(ids=(1,2,5))
        roles={"outer_0_inner_1":dict(training_ids=[1,2,5],evaluation_ids=[3],outer_fold=0,inner_fold=1)}
        folds=pd.DataFrame(dict(id=[1,2,3,4,5],outer_fold=[2,3,1,0,4]))
        units=candidate_units(b,data,[3]).assign(fit_role="outer_0_inner_1",selection_role="outer_0")
        table=summarize_units(units,("fit_role","horizon_days","model","parameter_a"))
        rebuilt=rebuild(data,folds,roles,b.states)
        result=audit_candidates(data,roles,b.states,rebuilt,units,table)
        self.assertEqual(result["candidate_identities_checked"],46)
        broken=units.copy();broken.loc[broken.supported,"brier"]+=.01
        with self.assertRaises(AssertionError):
            audit_candidates(data,roles,b.states,rebuilt,broken,table)

    def test_positive_ID_resampling_paired_and_reproducible(self):
        b=self.base(); parts=[]
        for model in ("B2","EqualID","Fixed"):
            vectors={key:vector(b,*key,model,.2) for key in b.rows}
            s,_=diagnostic_scores(b,vectors,fixture(),[3,4],model);parts.append(s)
        units=score_units(pd.concat(parts,ignore_index=True))
        first=uncertainty(units,[1,2,3,4,5],30,3)
        second=uncertainty(units,[5,4,3,2,1],30,3)
        pd.testing.assert_frame_equal(first[0],second[0])
        self.assertEqual(first[-1],second[-1])
        w=np.random.Generator(np.random.PCG64(3)).exponential(size=(30,5))
        g=units[units.supported&units.horizon_days.eq(7)&units.model.eq("EqualID")]
        vals=[]
        for t in range(30):
            by_cell=[]
            for cell, group in g.groupby("origin_cell_1"):
                by_cell.append(sum(w[t,r.id-1]*r.brier for r in group.itertuples())/sum(w[t,r.id-1] for r in group.itertuples()))
            vals.append(np.mean(by_cell))
        actual=first[0][first[0].horizon_days.eq(7)&first[0].model.eq("EqualID")].brier
        np.testing.assert_allclose(vals,actual,rtol=0,atol=1e-12)
        self.assertEqual(len(first[3]),4)

    def test_locked_config_and_plan(self):
        expected=expected_config()
        validate_config(expected)
        root=Path(__file__).resolve().parents[1]
        self.assertEqual(expected,json.loads((root/"configs/drifter_shrinkage_e3.json").read_text()))
        for key,value in [("gamma",.5),("primary_weighting","equal_pairs"),("final_test_access",True),("bootstrap_replicates",100)]:
            wrong=copy.deepcopy(expected);wrong[key]=value
            with self.assertRaises(ValueError):
                validate_config(wrong)

    def test_source_receipt_includes_main_entrypoint(self):
        root=Path(__file__).resolve().parents[1]
        with patch("data3001.modelling.baselines.run_drifter_shrinkage_e3.sys.modules", {}):
            hashes=source_hashes(SimpleNamespace(root=root))
        self.assertIn("src/data3001/modelling/baselines/run_drifter_shrinkage_e3.py",hashes)


if __name__=="__main__":
    unittest.main()
