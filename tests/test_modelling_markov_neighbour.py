"""Independent checks of displacement borrowing, not an endpoint-copy model."""
import unittest
import numpy as np
from pyproj import Geod
from shapely.geometry import box
from data3001.modelling.markov_position import OBS_DTYPE, fit_pool, step
from data3001.modelling.neighbourhood import EndpointMapper
from data3001.preprocessing.prep_core import cells


def fixtures():
    tracks=[];bins=[];origins=[];ends=[]
    # Three eligible hourly donor pairs: two in the west neighbour, one east.
    for sid,(x0,x1,b) in enumerate([(-77.7,-77.5,1),(-77.6,-77.4,2),(-75.7,-75.3,1)],1):
        a=np.zeros(25,dtype=OBS_DTYPE);a['id']=sid;a['source_obs']=np.arange(25)
        a['time']=np.arange(25)*3600;a['lon']=np.linspace(x0,x1,25);a['lat']=33.2
        a['cell']=cells(a['lon'],a['lat'])
        _,_,d=Geod(ellps='WGS84').inv(a['lon'][:-1],a['lat'][:-1],a['lon'][1:],a['lat'][1:])
        a['length']=np.r_[0,np.cumsum(d)];origins.append(len(tracks)*25);ends.append(len(tracks)*25+24)
        tracks.append(a);v=np.full(25,b,dtype='int8');v[-1]=8;bins.append(v)
    obs=np.concatenate(tracks);bins=np.concatenate(bins)
    return fit_pool(obs,np.array(origins),np.array(ends),bins,{1,2,3},1),EndpointMapper(box(-81,20,-8,55))


class NeighbourMarkovTests(unittest.TestCase):
    def test_alpha_zero_is_bitwise_existing_step(self):
        from data3001.modelling.markov_neighbour import neighbour_step
        p,m=fixtures();x=np.full(100,-77.5);y=np.full(100,33.2);c=cells(x,y);v=np.ones(100,dtype='int8')
        rng=np.random.default_rng(7);u=rng.random(100);d=rng.random(100)
        old=step(p,x,y,c,v,.4,u,d,m,precise=True)
        new=neighbour_step(p,x,y,c,v,np.zeros(100,dtype=bool),u<.4,d,m)
        for a,b in zip(old[:4],new[:4]):np.testing.assert_array_equal(a,b)

    def test_neighbour_donors_are_equal_pairs_not_equal_cells(self):
        from data3001.modelling.markov_neighbour import donor_selection
        p,_=fixtures();n=3000;x=np.full(n,-76.5);y=np.full(n,33.2);c=cells(x,y);v=np.ones(n,dtype='int8')
        # Force pooled velocity; uniform ranks enumerate all three donor pairs equally.
        source,uniform,unsupported,backoff=donor_selection(p,c,v,np.ones(n,dtype=bool),np.ones(n,dtype=bool),(np.arange(n)+.5)/n)
        unique,count=np.unique(source,return_counts=True)
        expected=np.array([int(cells(np.array([-77.5]),np.array([33.2]))[0]),int(cells(np.array([-75.5]),np.array([33.2]))[0])])
        np.testing.assert_array_equal(unique,np.sort(expected))
        self.assertEqual(sorted(count.tolist()),[1000,2000]);self.assertFalse(unsupported.any())

    def test_conditional_neighbour_pool_preserves_velocity_and_exact_anchor(self):
        from data3001.modelling.markov_neighbour import neighbour_step
        p,m=fixtures();x=np.array([-76.5,-76.5]);y=np.array([33.2,33.2]);c=cells(x,y);v=np.array([1,1])
        code,nx,ny,b,record=neighbour_step(p,x,y,c,v,np.ones(2,dtype=bool),np.zeros(2,dtype=bool),np.array([.1,.9]),m)
        self.assertTrue((nx>x).all());self.assertTrue((nx<-76).all())
        np.testing.assert_array_equal(b,[8,8]);self.assertEqual(record['neighbour_active'],2)
        # Original west/east endpoints must not replace target anchors.
        self.assertTrue((nx>-77).all())

    def test_missing_neighbour_stays_U_and_missing_velocity_uses_neighbour_pooled(self):
        from data3001.modelling.markov_neighbour import neighbour_step
        p,m=fixtures();x=np.array([-76.5,-65.5,np.nan]);y=np.array([33.2,33.2,np.nan])
        c=np.r_[cells(x[:2],y[:2]),-2];v=np.array([7,7,-2])
        code,*_,record=neighbour_step(p,x,y,c,v,np.ones(3,dtype=bool),np.zeros(3,dtype=bool),np.full(3,.5),m)
        self.assertGreaterEqual(code[0],0);np.testing.assert_array_equal(code[1:],[-3,-2])
        self.assertEqual(record['neighbour_unsupported'],1);self.assertEqual(record['neighbour_backoff'],1)
        self.assertEqual(record['active'],2)

    def test_schedules_and_grid_include_zero_borrowing_without_historical_choices(self):
        from data3001.modelling.markov_neighbour import schedules,candidates
        for h,n in [(7,8),(30,9)]:
            paths=schedules(h);self.assertEqual(len(paths),n)
            self.assertTrue(all(sum(s)==h for s in paths.values()))
            grid=candidates(h);self.assertEqual(len(grid),n*121)
            self.assertEqual(sum(a==0 for _,a,l in grid),n*11)

    def test_precomputed_neighbour_counts_preserve_every_selected_donor(self):
        from data3001.modelling.markov_neighbour import donor_selection,prepare_neighbours
        p,_=fixtures();rng=np.random.default_rng(180);n=1000
        x=rng.uniform(-78,-74,n);c=cells(x,np.full(n,33.2));b=rng.integers(0,9,n)
        borrow=rng.random(n)<.8;pooled=rng.random(n)<.4;u=rng.random(n)
        a=donor_selection(p,c,b,borrow,pooled,u);prepare_neighbours({1:p});z=donor_selection(p,c,b,borrow,pooled,u)
        for original,cached in zip(a,z):np.testing.assert_array_equal(original,cached)

    def test_donor_support_reports_pairs_and_independent_IDs_separately(self):
        from data3001.modelling.markov_neighbour import donor_support
        p,_=fixtures();cell=int(cells(np.array([-76.5]),np.array([33.2]))[0])
        t=donor_support(p,[(cell,1)]).set_index(['scope','conditioning'])
        self.assertEqual(t.loc[('self','conditional'),'pair_count'],0)
        self.assertEqual(t.loc[('neighbour','conditional'),'pair_count'],2)
        self.assertEqual(t.loc[('neighbour','pooled'),'independent_donor_ids'],3)


if __name__=='__main__':unittest.main()
