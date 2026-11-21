import itertools
import unittest
import numpy as np


class NeighbourIntegrationTests(unittest.TestCase):
    def test_importance_denominator_uses_joint_proposals_and_includes_all_corners(self):
        from data3001.modelling.markov_neighbour_integration import likelihood_weights
        proposal=[(0.,0.),(.2,.8),(1.,1.)];target=[(.2,.8),(0.,0.),(1.,1.)]
        k=np.array([[0,1,2]]);l=np.array([[0,0,2]])
        got=likelihood_weights(2,k,l,proposal,target)
        for i,(a,b) in enumerate(target):
            num=a**k*(1-a)**(2-k)*b**l*(1-b)**(2-l)
            den=sum(c**k*(1-c)**(2-k)*d**l*(1-d)**(2-l) for c,d in proposal)/len(proposal)
            np.testing.assert_allclose(got[:,:,i],num/den,rtol=1e-14)
        self.assertTrue((got<=len(proposal)+1e-12).all())

    def test_smaller_proposal_grid_covers_every_target_without_dropping_candidates(self):
        from data3001.modelling.markov_neighbour_integration import weight_table
        from data3001.modelling.markov_neighbour import GRID
        p=tuple((a,b) for a in [0,.1,.3,.5,.7,.9,1] for b in [0,.1,.3,.5,.7,.9,1])
        t=tuple((a,b) for a in GRID for b in GRID)
        for steps in range(1,31):
            table=weight_table(steps,p,t)
            self.assertEqual(table.shape,(steps+1,steps+1,121));self.assertTrue(np.isfinite(table).all())
            self.assertLessEqual(table.max(),92.173873823)

    def test_centered_stratified_score_exactly_unbiased_by_enumeration(self):
        from data3001.modelling.markov_neighbour_integration import weighted_scores
        proposal=[.2,.8];targets=[.4,.9];expect=np.zeros(2)
        for state in itertools.product([0,1],repeat=4):
            draw=np.array([state]);mass=np.prod([proposal[i//2] if x==0 else 1-proposal[i//2] for i,x in enumerate(state)])
            w=np.array([[[p/.5 if x==0 else (1-p)/.5 for p in targets] for x in state]])
            score=weighted_scores(draw,np.array([0]),w,2)
            expect+=mass*score['S_integration'][0]
        np.testing.assert_allclose(expect,[2*(1-p)**2 for p in targets],atol=1e-14,rtol=0)

    def test_deterministic_correct_destination_has_exact_zero_residual_even_with_weights(self):
        from data3001.modelling.markov_neighbour_integration import weighted_scores
        w=np.array([[[.2,1],[3,2],[1,.1],[4,.2]]])
        got=weighted_scores(np.full((1,4),44000),np.array([44000]),w,2)
        np.testing.assert_allclose(got['S_integration'],0,atol=1e-13)

    def test_unit_weights_recover_stratified_unbiased_score_including_E_U(self):
        from data3001.modelling.markov_neighbour_integration import weighted_scores
        from data3001.modelling.markov_iteration_strata import stratified_scores
        x=np.array([[44000,-3,44001,-2],[44000]*4]);y=np.array([44001,44000])
        a=weighted_scores(x,y,np.ones((2,4,1)),2)
        b=stratified_scores(x,y,np.array([2,2]),np.array([[.5,.5]]))
        np.testing.assert_allclose(a['S_integration'],b['S_integration'],rtol=0,atol=2e-16)

    def test_independent_target_selection_does_not_inherit_neighbour_or_history(self):
        from data3001.modelling.markov_neighbour_integration import choose
        import pandas as pd
        t=pd.DataFrame({'candidate':[0,1,2],'path':['D1','D7','D7'],'alpha':[0,.5,0],
                        'lambda_value':[.1,.8,.7],'S':[.9,.7,.8],'MC_SE':[0,0,0]})
        self.assertEqual(choose(t,7,'self')['candidate'],2)
        self.assertEqual(choose(t,7,'neighbour')['candidate'],1)

    def test_production_sampler_scores_agree_with_independent_two_step_law(self):
        from test_modelling_markov_neighbour import fixtures
        from data3001.modelling.markov_position import fit_pool
        from data3001.modelling.markov_neighbour_integration import proposal_forecast,query_seeds
        from data3001.modelling.markov_neighbour_native import score_counts
        from data3001.preprocessing.prep_core import cells
        p,mapper=fixtures();extra=p.obs[:25].copy();extra['id']=4;extra['lon']+=1.1
        extra['cell']=cells(extra['lon'],extra['lat']);obs=np.r_[p.obs,extra]
        bins=np.r_[p.bins,p.bins[:25]]
        pool=fit_pool(obs,np.array([0,25,50,75]),np.array([24,49,74,99]),bins,{1,2,3,4},1)
        target=[(0.,0.),(0.,1.),(1.,0.),(1.,1.),(.5,.5)];n=5000
        seeds=query_seeds('independent_two_step',np.ones(n),np.arange(n),0,'five_proposals')
        draw,k,l,_=proposal_forecast({1:pool},np.full(n,-76.5),np.full(n,33.2),np.ones(n),
                                    (1,1),target,4,seeds,mapper)
        truth=np.full(n,int(cells(np.array([-76.5]),np.array([33.2]))[0]))
        score=score_counts(draw,truth,k,l,2,target,4)
        expected=[]
        for a,b in target:
            p1=a*((1-b)/2+b/3);p2=a/3;prob=(1-p1)*(1-p2)
            expected.append(2*(1-prob)**2)
        for name in ['S_integration','S_uncentred']:
            s=score[name];se=s.std(axis=0,ddof=1)/np.sqrt(n)
            self.assertTrue((np.abs(s.mean(axis=0)-expected)<5*se+1e-4).all(),(name,s.mean(axis=0),expected,se))

    def test_transferred_step_causes_keep_exact_days_and_absorption(self):
        from test_modelling_markov_neighbour import fixtures
        from data3001.modelling.markov_neighbour_integration import proposal_forecast
        p,m=fixtures();seen=[]
        def trace(day,draw,record):seen.append((day,draw.copy(),dict(record)))
        proposal_forecast({1:p},np.array([-65.5]),np.array([33.2]),np.array([1]),(1,1),[(0.,0.)],
                          2,np.array([123],dtype='uint64'),m,trace=trace)
        self.assertEqual([x[0] for x in seen],[1,2])
        self.assertTrue(all((x[1]==-3).all() for x in seen))


if __name__=='__main__':unittest.main()
