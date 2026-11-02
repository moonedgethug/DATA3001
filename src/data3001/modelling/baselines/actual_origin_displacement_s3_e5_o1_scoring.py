"""Exact case scoring with prevalidated support and vectorised borrowing weights."""
import numpy as np
from data3001.modelling.baselines.actual_origin_displacement_s3_e5_selection import CaseEvaluator,weight_gradient,METRICS


class CachedCaseEvaluator(CaseEvaluator):
    def __init__(self,cases,check=lambda:None):
        super().__init__(cases,check)
        self.case_z=np.array([c.z for c in self.cases])
        self.truth_indices=[int(np.flatnonzero(c.states==c.truth)[0]) for c in self.cases]
        self.geographical=[c.states>=0 for c in self.cases]

    def metrics(self,a,gamma):
        weights=weight_gradient(a,gamma,self.case_z)[0];total=np.zeros(4)
        for n,(c,lam,loc,geographical) in enumerate(zip(self.cases,weights,self.truth_indices,self.geographical)):
            if n%256==0:self.check()
            p=(1-float(lam))*c.p+float(lam)*c.q
            positive=np.sort(p[p>0])[::-1]
            ix=min(int(np.searchsorted(np.cumsum(positive),.9-1e-12)),len(positive)-1)
            region=(p>0)&(p>=float(positive[ix])-1e-12)
            total+=c.weight*np.array([1+p@p-2*p[loc],int(np.sum(region&geographical)),float(region[loc]),float(p[region].sum())])
        if abs(total[0]-self.objective((a,gamma))[0])>1e-12:raise AssertionError('Coefficient/score mismatch')
        return dict(zip((*METRICS,'region90_mass'),map(float,total)))
