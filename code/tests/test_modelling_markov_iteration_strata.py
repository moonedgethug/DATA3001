import itertools
import unittest
import numpy as np
from data3001.modelling.markov_iteration_strata import weights_for,allocations,stratified_scores,stratified_forecast


class StrataTests(unittest.TestCase):
    def test_every_lambda_is_a_normalized_binomial_mixture(self):
        for m in [5,6,9,10,13,15,30]:
            w=weights_for(m,np.arange(11)/10);n=allocations(w,32)
            np.testing.assert_allclose(w.sum(axis=1),1,atol=3e-15,rtol=0)
            self.assertTrue((n[w.max(axis=0)>0]>=2).all())
            self.assertTrue((n[None,:]>=32*w-1e-12).all())
            self.assertLess(int(n.sum()),11*32)

    def test_weighted_collision_formula_is_unbiased_not_renormalized(self):
        # Two independent strata, two particles each; enumerate their exact law.
        probs=[.2,.8];w=np.array([[.3,.7]]);values=[];mass=[]
        for a in itertools.product([43000,43001],repeat=4):
            score=stratified_scores(np.array([a]),np.array([43000]),np.array([2,2]),w)
            values.append(score['S_integration'][0,0]);mass.append(np.prod([
                probs[i//2] if v==43000 else 1-probs[i//2] for i,v in enumerate(a)]))
        p=.3*.2+.7*.8;expected=1-2*p+p*p+(1-p)**2
        self.assertAlmostEqual(np.dot(values,mass),expected,places=14)

    def test_single_stratum_recovers_original_score_and_U_mass(self):
        from data3001.modelling.markov_iteration import fast_scores
        a=np.array([[43000,43001,-3,-2],[43000]*4]);y=np.array([43001,43000])
        s=stratified_scores(a,y,np.array([4]),np.array([[1.]]));old=fast_scores(a,y)
        for key in old:np.testing.assert_allclose(s[key][:,0],old[key],atol=3e-16,rtol=0)

    def test_uniform_count_conditioning_recovers_ordered_noncommuting_kernel(self):
        # Each substep has different local/pooled transition matrices.
        L=[np.array([[.8,.2],[.1,.9]]),np.array([[.3,.7],[.4,.6]])]
        B=[np.array([[.2,.8],[.7,.3]]),np.array([[.9,.1],[.6,.4]])]
        conditional=[]
        for k in range(3):
            outcomes=[]
            for pattern in itertools.product([0,1],repeat=2):
                if sum(pattern)!=k:continue
                p=np.array([1.,0.])
                for t,b in enumerate(pattern):p=p@(B[t] if b else L[t])
                outcomes.append(p)
            conditional.append(np.mean(outcomes,axis=0))
        for lam,w in zip(np.arange(11)/10,weights_for(2,np.arange(11)/10)):
            direct=np.array([1.,0.])
            for l,b in zip(L,B):direct=direct@((1-lam)*l+lam*b)
            np.testing.assert_allclose(w@conditional,direct,atol=2e-16,rtol=0)


if __name__=='__main__':unittest.main()
