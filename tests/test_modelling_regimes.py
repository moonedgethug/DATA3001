"""Regime intervals and matched-case comparisons, using synthetic inputs only."""
import unittest
import numpy as np
import pandas as pd
from data3001.preprocessing import prep_core as c
from data3001.modelling.regimes import qualify_intervals, matched_pooled_scores, paired_regime_intervals, preflight


class RegimeTests(unittest.TestCase):
    def track(self):
        t = 1000000000. + np.arange(1000)*3600.
        a = dict(time=t, regime=np.ones(len(t), np.int8), loss=np.nan,
                 position_ok=np.ones(len(t), bool), mapping_ok=np.ones(len(t), bool),
                 inside_D=np.ones(len(t), bool), loss_status_source='official_fill_attached',
                 official_attached_through_epoch=t[-1])
        return a

    def test_official_proof_is_bounded_and_missing_is_not_undrogued(self):
        a = self.track(); origins=np.array([0, 100]); ends=a['time'][origins]+7*86400
        d,u=qualify_intervals(a,origins,ends)
        self.assertEqual(d.tolist(),[True,True]); self.assertFalse(u.any())
        a['official_attached_through_epoch']=ends[0]
        d,u=qualify_intervals(a,origins,ends)
        self.assertEqual(d.tolist(),[True,False]); self.assertFalse(u.any())
        a.pop('loss_status_source'); a['loss']=0.
        d,u=qualify_intervals(a,origins,ends)
        self.assertFalse(d.any() or u.any())

    def test_internal_unknown_cannot_be_hidden_by_known_endpoints(self):
        a=self.track();a['regime'][50]=-1
        d,u=qualify_intervals(a,np.array([0]),a['time'][[168]])
        self.assertFalse(d.any() or u.any())

    def test_official_loss_crossing_and_mutual_exclusion(self):
        a=self.track();a['loss']=a['time'][200];a['regime'][200:]=0
        a.update(loss_status_source='official_boundary_refinement',official_regime_decision='nominal_loss',official_loss_epoch=a['loss'])
        d,u=qualify_intervals(a,np.array([0,100,300]),a['time'][[168,268,468]])
        self.assertEqual(d.tolist(),[True,False,False]);self.assertEqual(u.tolist(),[False,False,True])
        a.update(official_regime_decision='attached_at_end',official_attached_through_epoch=a['time'][200])
        a['regime'][:]=1
        d,u=qualify_intervals(a,np.array([0,100]),a['time'][[168,268]])
        self.assertEqual(d.tolist(),[True,False]);self.assertFalse(u.any())

    def test_float_precision_boundary_is_not_silently_classified(self):
        a=self.track();a.pop('loss_status_source');a['loss']=a['time'][168]
        d,u=qualify_intervals(a,np.array([0]),a['time'][[168]])
        self.assertFalse(d.any() or u.any())

    def scores(self):
        rows=[]
        for sid in range(1,11):
            for model in ('B2','Local-U-Analytic'):
                rows.append(dict(id=sid,horizon_days=7,origin_cell_1=100,destination_cell_1=101,
                                 outer_fold=sid%5,model=model,pair_count=10,
                                 brier_failure_penalized=.6, true_probability=.4))
        return pd.DataFrame(rows)

    def counts(self):
        return self.scores().query("model=='B2'").drop(columns=['model','outer_fold','brier_failure_penalized','true_probability']).assign(pair_count=3)

    def test_matched_case_reweighting_keeps_frozen_predictions(self):
        pooled=self.scores();fixed=self.counts();matched=matched_pooled_scores(pooled,fixed)
        self.assertEqual(matched.pair_count.tolist(),[3]*20)
        self.assertTrue(matched.true_probability.eq(.4).all())
        self.assertTrue(matched.brier_failure_penalized.eq(.6).all())
        self.assertTrue(pooled.pair_count.eq(10).all())
        with self.assertRaises(ValueError):matched_pooled_scores(pooled,fixed.assign(pair_count=11))
        with self.assertRaises(ValueError):matched_pooled_scores(pooled.iloc[1:],fixed)
        with self.assertRaises(ValueError):matched_pooled_scores(pd.concat([pooled,pooled.iloc[:1]]),fixed)

    def test_paired_intervals_are_same_case_and_constant_difference(self):
        pooled=matched_pooled_scores(self.scores(),self.counts())
        fixed=pooled.assign(brier_failure_penalized=.5)
        out=paired_regime_intervals(fixed,pooled)
        np.testing.assert_allclose(out[['delta_brier','lower','upper']],-.1)
        with self.assertRaises(ValueError):paired_regime_intervals(fixed.assign(pair_count=4),pooled)
        with self.assertRaises(ValueError):paired_regime_intervals(fixed.assign(outer_fold=99),pooled)

    def test_empty_tuning_population_is_not_evaluable(self):
        outer={i:i%5 for i in range(1,41)}
        inner={f:{i:i%4 for i in outer if outer[i]!=f} for f in range(5)}
        good=pd.DataFrame([dict(id=i,horizon_days=h,origin_cell_1=1) for i in outer for h in (7,30)])
        self.assertTrue(preflight(good,outer,inner).evaluable.all())
        with self.assertRaises(ValueError):preflight(good.iloc[:1],outer,inner)

    def test_fixed_nested_models_reproduce_controls_and_pooled_case_join(self):
        from shapely.geometry import box
        from data3001.modelling.experiment import make_nested_folds
        from data3001.modelling.neighbourhood import EndpointMapper
        from data3001.modelling.neighbourhood_cv import evaluate_local_nested, pair_counts
        from data3001.modelling.cv import evaluate_nested
        rows=[]
        for sid in range(1,41):
            for h in (7,30):
                x=.2+sid%2;endx=x+(2 if sid%4 else 0)
                rows.append(dict(id=sid,horizon_days=h,origin_lon=x,origin_lat=.2,
                    endpoint_lon=endx,endpoint_lat=.2,origin_cell_1=32580+sid%2,
                    destination_cell_1=32580+int(endx)))
        pairs=pd.DataFrame(rows);outer,inner=make_nested_folds(range(1,41))
        result=evaluate_local_nested(pairs,outer,inner,{32580,32581},
            EndpointMapper(box(-10,-10,10,10)),integration={'exact_limit':10000},progress=lambda s:None)
        old=evaluate_nested(pair_counts(pairs),outer,inner,progress=lambda s:None)['scores']
        old['model']=old.model.replace({'Grid':'Global-Grid','Analytic':'Global-Analytic'})
        new=result['scores'].loc[result['scores'].model.isin(old.model.unique())]
        keys=['outer_fold','id','horizon_days','origin_cell_1','destination_cell_1','model']
        old=old.sort_values(keys).reset_index(drop=True);new=new.sort_values(keys).reset_index(drop=True)
        pd.testing.assert_frame_equal(old[keys+['pair_count']],new[keys+['pair_count']])
        np.testing.assert_allclose(old.brier_failure_penalized,new.brier_failure_penalized,atol=1e-12)
        counts=pair_counts(pairs).iloc[::2].copy()
        matched=matched_pooled_scores(result['scores'],counts)
        selected=result['scores'].merge(counts[keys[1:-1]],on=keys[1:-1],validate='many_to_one')
        paired=paired_regime_intervals(selected,matched)
        np.testing.assert_allclose(paired[['delta_brier','lower','upper']],0)


if __name__=='__main__':unittest.main()
