"""G3: conservative 32-hour certificates with exact chronological descent."""
import resource,sys
import numpy as np
import shapely as sh
from scipy.ndimage import minimum_filter1d,maximum_filter1d
from data3001.modelling.baselines.actual_origin_displacement_s3_e5_o1_g2 import G2Kernel
from data3001.preprocessing.prep_core import cells
from data3001.modelling.baselines.spatial_borrowing_s3_e1_inputs import FALLBACK
from data3001.modelling.common.qualified_count_inputs import EXIT


class G3Kernel(G2Kernel):
    __slots__=('bounds','bad','gap')

    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs);t=self.tracks;self.bounds={}
        self.bad=np.r_[0,np.cumsum(~t.valid|~np.isfinite(t.lon)|~np.isfinite(t.lat))]
        self.gap=np.r_[0,np.cumsum(np.r_[False,np.diff(t.time)!=3600])]
        for width in (2,4,8,16,32):
            rss=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1 if sys.platform=='darwin' else 1024)
            if rss+4*t.lon.nbytes>8*2**30:raise MemoryError('Time-block indexes exceed approved combined RSS')
            self.bounds[width]=tuple(filt(values,size=width+1,origin=-(width//2),mode='constant',cval=cval)
                for values in (t.lon,t.lat) for filt,cval in ((minimum_filter1d,np.inf),(maximum_filter1d,-np.inf)))
            for a in self.bounds[width]:a.flags.writeable=False
        self.bad.flags.writeable=False;self.gap.flags.writeable=False

    def safe_block(self,q,c,indices,lo,hi):
        t=self.tracks;start=c.start[indices].astype(int)+lo;end=c.start[indices].astype(int)+hi
        last=np.minimum(end,len(t.time)-1)
        complete=((end<c.track_end[indices])&(t.time[start]==c.epoch[indices]+lo*3600)
                  &(t.time[last]==c.epoch[indices]+hi*3600)
                  &((self.bad[last+1]-self.bad[start])==0)&((self.gap[last+1]-self.gap[start+1])==0))
        bx0,bx1,by0,by1=self.bounds[hi-lo]
        xmin=q.lon+(bx0[start]-c.lon[indices]);xmax=q.lon+(bx1[start]-c.lon[indices])
        ymin=q.lat+(by0[start]-c.lat[indices]);ymax=q.lat+(by1[start]-c.lat[indices])
        possible=complete&(xmin>=-180)&(xmax<180)&(ymin>=-90)&(ymax<90)
        xmin=(xmin+180)%360-180;xmax=(xmax+180)%360-180
        xmin-=1e-10;xmax+=1e-10;ymin-=1e-10;ymax+=1e-10
        possible&=(xmin>=-180)&(xmax<180)&(xmin<=xmax)&(ymin>=-90)&(ymax<90)
        return self.rectangle_safe(xmin,xmax,ymin,ymax,possible)

    def classify_context(self,q,c,*,check=lambda:None,certificates=True):
        if c.owner is not self.context_owner:raise ValueError('Stale or foreign context')
        if q.id in c.fitting_ids or q.fold in c.donor_folds:raise PermissionError('Whole-ID leakage')
        if q.horizon!=c.horizon or q.origin!=c.origin:raise ValueError('Wrong context role')
        n=len(c);out=np.full(n,FALLBACK,np.int64);why=np.zeros(n,np.int16)
        profile=dict(donors=n,certified=0,literal_pairs=0,hourly_steps=0,block_certificates=0,proven_hourly_steps=0,block_attempts=0)
        if not self.query_safe(q):why[:]=11;return out,why,profile
        # Endpoints and all intervening segments are covered by every block envelope.
        t=self.tracks;horizon=24*q.horizon
        for first in range(0,n,self.batch_size):
            check();last=min(first+self.batch_size,n);sl=slice(first,last)
            cert=self.certificates_context(q,c,sl) if certificates else np.zeros(last-first,bool)
            ci=first+np.flatnonzero(cert)
            if len(ci):
                x=(q.lon+(c.end_lon[ci]-c.lon[ci])+180)%360-180;y=q.lat+(c.end_lat[ci]-c.lat[ci])
                out[ci]=cells(x,y)
            active=first+np.flatnonzero(~cert);profile['certified']+=int(cert.sum());profile['literal_pairs']+=len(active)
            prevx=np.full(last-first,q.lon);prevy=np.full(last-first,q.lat)

            def visit(active,lo,hi):
                if not len(active):return active
                check()
                if hi-lo>1 and certificates:
                    safe=self.safe_block(q,c,active,lo,hi);profile['block_attempts']+=len(active)
                    good=active[safe];other=active[~safe]
                    if len(good):
                        loc=c.start[good].astype(int)+hi
                        prevx[good-first]=(q.lon+(t.lon[loc]-c.lon[good])+180)%360-180
                        prevy[good-first]=q.lat+(t.lat[loc]-c.lat[good])
                        profile['block_certificates']+=len(good);profile['proven_hourly_steps']+=len(good)*(hi-lo)
                    if len(other):
                        mid=(lo+hi)//2;other=visit(visit(other,lo,mid),mid,hi)
                    return np.sort(np.r_[good,other])
                if hi-lo>1:
                    for step in range(lo+1,hi+1):active=visit(active,step-1,step)
                    return active
                # Exact old hourly rule, including segment-over-point precedence.
                profile['hourly_steps']+=len(active);loc=c.start[active].astype(int)+hi
                present=loc<c.track_end[active];why[active[~present]]=7
                active=active[present];loc=loc[present]
                if not len(active):return active
                timed=t.time[loc]==c.epoch[active]+3600*hi;why[active[~timed]]=5
                active=active[timed];loc=loc[timed]
                if not len(active):return active
                x=(q.lon+(t.lon[loc]-c.lon[active])+180)%360-180;y=q.lat+(t.lat[loc]-c.lat[active])
                valid=t.valid[loc]&np.isfinite(x)&np.isfinite(y)&(y>=-90)&(y<90)
                why[active[~valid]]=1;active=active[valid];x=x[valid];y=y[valid]
                if not len(active):return active
                inside=self.inside_domain(x,y);high=self.land_points('high',x,y,inside);mid=self.land_points('intermediate',x,y,inside)
                code=cells(x,y);reason=np.zeros(len(active),np.int16)
                indexed=np.zeros(len(code),bool);valid_code=(code>=0)&(code<len(self.valid_states));indexed[valid_code]=self.valid_states[code[valid_code]]
                reason[inside&~indexed]=4;reason[high&mid]=2;reason[high^mid]=3
                xy=np.stack((np.column_stack((prevx[active-first],prevy[active-first])),np.column_stack((x,y))),axis=1)
                lines=sh.linestrings(xy);high=self.land_intersects('high_D',lines);mid=self.land_intersects('intermediate_D',lines)
                reason[high&mid]=6;reason[high^mid]=10
                failed=reason>0;why[active[failed]]=reason[failed]
                exited=~failed&~inside;out[active[exited]]=EXIT;remain=~failed&inside
                prevx[active[remain]-first]=x[remain];prevy[active[remain]-first]=y[remain]
                return active[remain]

            for lo in range(0,horizon,32):
                active=visit(active,lo,min(lo+32,horizon))
                if not len(active):break
            if len(active):out[active]=cells(prevx[active-first],prevy[active-first])
        if not np.array_equal(out==FALLBACK,why>0):raise AssertionError('Outcome/reason mismatch')
        return out,why,profile
