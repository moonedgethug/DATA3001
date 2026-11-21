import unittest
import numpy as np


class NativeScoreTests(unittest.TestCase):
    def test_compiled_score_matches_independent_numpy_formula(self):
        from data3001.modelling.markov_neighbour_native import score_counts
        from data3001.modelling.markov_neighbour_integration import likelihood_weights,weighted_scores
        rng=np.random.default_rng(1701);proposal=[(0.,0.),(.2,.8),(.7,.3),(1.,1.)]
        for r in [2,4,8,16]:
            n=7;m=len(proposal)*r;draw=rng.choice([-3,-2,44000,44001,44002],(n,m)).astype('int32')
            k=rng.integers(0,6,(n,m),dtype='uint8');l=rng.integers(0,6,(n,m),dtype='uint8');y=rng.choice([-2,44000,44001],n).astype('int32')
            w=likelihood_weights(5,k,l,proposal,proposal);reference=weighted_scores(draw,y,w,r)
            actual=score_counts(draw,y,k,l,5,proposal,r)
            for key in reference:np.testing.assert_allclose(actual[key],reference[key],rtol=0,atol=2e-13)

    def test_proposal_count_is_distinct_from_target_count(self):
        from data3001.modelling.markov_neighbour_native import score_counts
        from data3001.modelling.markov_neighbour_integration import likelihood_weights,weighted_scores
        p=[(0.,0.),(.3,.7),(1.,1.)];t=p+[(.4,.6)]
        rng=np.random.default_rng(9);r=4;d=rng.choice([-3,-2,44000],(5,len(p)*r)).astype('int32')
        k=rng.integers(0,4,d.shape,dtype='uint8');l=rng.integers(0,4,d.shape,dtype='uint8');y=np.full(5,44000,dtype='int32')
        ref=weighted_scores(d,y,likelihood_weights(3,k,l,p,t),r)
        actual=score_counts(d,y,k,l,3,p,r,targets=t)
        for name in ref:np.testing.assert_allclose(actual[name],ref[name],rtol=0,atol=2e-13)


if __name__=='__main__':unittest.main()
