import unittest
import numpy as np
import pandas as pd
from shapely.geometry import box
from data3001.preprocessing.prep_core import cells
from data3001.modelling.markov_position import OBS_DTYPE,fit_pool
from data3001.modelling.neighbourhood import EndpointMapper
from data3001.modelling.markov_iteration_outer import precise_outer


class OuterIterationTests(unittest.TestCase):
    def test_matched_arms_same_cases_duplicate_settings_and_threads(self):
        a=np.zeros(27,dtype=OBS_DTYPE);a['lon']=-75.5;a['lat']=33.2;a['time'][:25]=np.arange(25)*3600
        a['id'][:25]=1;a['id'][25:]=[2,3];a['source_obs']=np.arange(27)
        a['cell']=cells(a['lon'],a['lat']);bins=np.ones(27,dtype='int8')
        pools={1:fit_pool(a,np.array([0]),np.array([24]),bins,{1},1)}
        part=pd.DataFrame({'id':[2,3],'origin_source_obs':[25,26],'origin':[25,26],
            'origin_cell_1':a['cell'][25:],'origin_velocity_bin':[1,1],
            'destination_cell_1':a['cell'][25:],'horizon_days':[30,30]})
        variants={'position-CV':('D1',.2),'position-frozen':('D1',.2)}
        mapper=EndpointMapper(box(-81,20,-8,55))
        one,trace,_=precise_outer(pools,a,bins,part,variants,0,mapper,particles=16,workers=1,batch_size=1)
        two,_,_=precise_outer(pools,a,bins,part,variants,0,mapper,particles=16,workers=2,batch_size=1)
        pd.testing.assert_frame_equal(one,two)
        self.assertEqual(len(one),8);self.assertTrue(one.S_integration.eq(0).all())
        self.assertEqual(one.groupby(['model','repeat']).size().tolist(),[2,2,2,2])
        self.assertIn('step_unsupported_cell',trace.columns)
        self.assertIn('step_endpoint_geometry_U',trace.columns)

    def test_outer_MC_error_is_separate_and_reproducible(self):
        from data3001.modelling.markov_iteration_outer import outer_MC
        rows=[]
        for model,rep,values in [('fine',0,[.9,1.1]),('fine',1,[1.,1.]),('coarse',0,[.8,1.2])]:
            rows.extend((i,100+i,model,rep,value) for i,value in enumerate(values))
        f=pd.DataFrame(rows,columns=['id','origin_source_obs','model','repeat','S_integration'])
        result=outer_MC(f,[('fine','coarse')]).iloc[0]
        self.assertAlmostEqual(result.delta_S,0)
        self.assertAlmostEqual(result.MC_SE,np.sqrt(.02)/4)
        with self.assertRaises(ValueError):outer_MC(f.iloc[:-1],[('fine','coarse')])


if __name__=='__main__':unittest.main()
