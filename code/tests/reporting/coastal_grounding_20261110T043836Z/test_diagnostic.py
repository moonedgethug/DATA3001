import sys
from pathlib import Path
import numpy as np
import pandas as pd
import unittest
raises=unittest.TestCase().assertRaises

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'code'))
import diagnostic as d

def test_administrative_bit_not_hidden_by_path_reason():
    f=pd.DataFrame({'reason_code':[6,3,0,6], 'secondary_predicates':[130,4,0,128],
        'outside':[False,False,True,False], 'role_excluded':[False]*4,
        'endpoint_available':[False,False,False,True]})
    out=d.availability_flags(f)
    assert out.risk_set.tolist()==[False,True,False,True]
    assert out.missing_endpoint.tolist()==[False,True,False,False]

def test_drifter_equal_is_not_pair_equal():
    f=pd.DataFrame({'id':[1,1,1,2], 'model':['A']*4,'energy_km':[0.,0.,0.,10.]})
    assert d.id_equal_mean(f,'energy_km')==5.

def test_official_death_not_binary_grounding():
    assert d.official_status(1)=='official_grounding'
    assert d.official_status(3)=='transmission_stopped_unknown_cause'
    assert d.official_status(2)=='vessel_recovery'
    assert d.official_status(None)=='unresolved'

def test_event_interval_unknown_and_boundary():
    assert d.window_relation(100,200,None,None)=='event_time_unknown'
    assert d.window_relation(100,200,120,180)=='within_window'
    assert d.window_relation(100,200,90,120)=='possible_overlap'
    assert d.window_relation(100,200,20,100)=='no_overlap'

def test_unique_join_preserves_large_integer_ids():
    ident=300234063731750
    a=pd.DataFrame({'id':[ident], 'origin_source_obs':[123], 'horizon_days':[7]})
    b=a.assign(x=4)
    assert int(d.exact_join(a,b,d.KEY).id.iloc[0])==ident
    with raises(ValueError):d.exact_join(a,pd.concat([b,b]),d.KEY)
    with raises(ValueError):d.exact_join(a,b.iloc[0:0],d.KEY)

def test_zero_denominator_not_zero_missing():
    f=pd.DataFrame({'id':[1,2,2],'risk_set':[False,True,True], 'missing_endpoint':[False,True,False]})
    r=d.availability_by_id(f).set_index('id')
    assert np.isnan(r.loc[1,'missing_rate'])
    assert r.loc[2,'missing_rate']==.5

def test_frozen_and_final_test_paths_rejected():
    out=Path('/supplement')
    assert d.check_write_path(out/'results/x.csv',out)
    with raises(PermissionError):d.check_write_path(Path('/original/results/x'),out)
    with raises(PermissionError):d.check_read_path(Path('/original/data/test/123.parquet'),{123})
    with raises(PermissionError):d.check_read_path(Path('/original/data/train/456.parquet'),{123})

def test_geometry_uses_boundary_before_crop():
    import shapely.geometry as sg
    land=sg.box(0,0,10,10)
    clip=sg.box(5,-1,15,11)
    boundary=d.clipped_real_boundary(land,clip)
    assert boundary.distance(sg.Point(5,5))==5

def test_common_cluster_draws_and_sparse_groups():
    draws=d.bootstrap_draws(45,5000,20261110)
    assert draws.shape==(5000,45)
    assert np.array_equal(draws,d.bootstrap_draws(45,5000,20261110))
    assert d.supports_interval(9) is False
    assert d.supports_interval(10) is True

def test_source_conflict_not_hidden_by_agreeing_death_code():
    assert d.metadata_conflict(1,1,'cross_source_conflict')
    assert not d.metadata_conflict(0,3,'native_end_missing_official_available')

def test_coast_interval_must_not_cross_threshold():
    assert d.distance_class(9990,10010)=='uncertain'
    assert d.distance_class(10001,10010)=='10_50km'
    assert d.distance_class(49999,50001)=='uncertain'
    assert d.distance_class(50001,60000)=='>50km'

def test_association_rates_keep_group_id_denominator():
    from complete_evidence import strata
    f=pd.DataFrame({'id':[1,1,1,2,3],'cohort':['train']*5,
        'risk_set':[True,True,True,True,False],'missing_endpoint':[True,True,False,False,False],
        'used_by_original':[False,False,True,True,False]})
    r=strata(f,['cohort']).iloc[0]
    assert r.risk==4 and r.missing==2 and r.risk_ids==2 and r.missing_ids==1
    assert r.zero_denominator_ids==1 and r.missing_pair_rate==.5
    assert np.isclose(r.missing_id_equal_rate,1/3)

if __name__=='__main__':
    suite=unittest.TestSuite(unittest.FunctionTestCase(v) for k,v in list(globals().items()) if k.startswith('test_'))
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    sys.exit(not result.wasSuccessful())
