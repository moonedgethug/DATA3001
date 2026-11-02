"""Independent counters, scalar path review and saved S3 probability/score audit."""
from collections import Counter,defaultdict
import hashlib
import json
import numpy as np
import pandas as pd
import shapely as sh
from shapely.geometry import Point,LineString
from data3001.preprocessing.prep_core import cells
from data3001.modelling.baselines.drifter_shrinkage_e3_audit import region,macro
from data3001.modelling.common.qualified_count_inputs import read_frame
from data3001.modelling.baselines.spatial_borrowing_s3_e1_inputs import FALLBACK, Geometry

MODELS=('B2','Fixed','Adaptive','LocalEndpoint','LocalDisplacement')
METRICS=('brier','region90_cells','region90_hit')


def scalar_transfer(frame,label,target,dx,dy,geo):
    """Literal chronological walk; does not use event arrays or next-event queries."""
    by_key=frame.set_index('source_obs'); start=by_key.loc[int(label.origin_source_obs)]
    start_time=float(start.time); end_time=float(label.target_epoch)
    pieces=frame[(frame.time>=start_time)&(frame.time<=end_time)].sort_values('time')
    previous=None
    for position,r in enumerate(pieces.itertuples(index=False)):
        x=(float(r.lon)+dx+180)%360-180;y=float(r.lat)+dy
        if previous is not None and r.time!=previous[0]+3600: return FALLBACK,5
        valid=bool(r.position_ok) and np.isfinite([x,y]).all() and -90<=y<90
        if not valid: return FALLBACK,1
        point=Point(x,y); inside=geo.domain.intersects(point)
        h=inside and geo.high.intersects(point);m=inside and geo.intermediate.intersects(point)
        cell=int(cells(np.array([x]),np.array([y]))[0])
        why=3 if h!=m else 2 if h else 4 if inside and cell not in geo.states else 0
        if position==0:
            if why: return FALLBACK,why
            if cell!=target: return FALLBACK,9
            if not inside or not geo.region.intersects(point): return FALLBACK,8
        else:
            line=LineString([(previous[1],previous[2]),(x,y)]).intersection(geo.domain)
            hl=geo.high.intersects(line);ml=geo.intermediate.intersects(line)
            if hl or ml: return FALLBACK,10 if hl!=ml else 6
            if why: return FALLBACK,why
            if not inside: return -2,0
        previous=(float(r.time),x,y)
    if previous is None or previous[0]!=end_time: return FALLBACK,7
    return int(cells(np.array([previous[1]]),np.array([previous[2]]))[0]),0


def audit_preparation(paths,input_root,states):
    geo=Geometry.load(paths,states);sample=read_frame(input_root/'audit_sample.csv');checked=0
    combined=[];all_reasons=set();extra=[];all_outcomes=set()
    for p in sorted((input_root/'transfers').glob('*.parquet')):
        t=read_frame(p); labels=read_frame(input_root/'labels'/p.name)
        assert not t.duplicated(['horizon_days','origin_source_obs','origin_cell_1']).any()
        assert (t.destination_cell_1.eq(FALLBACK)==t.reason_code.gt(0)).all()
        assert t.id.eq(int(p.stem)).all()
        expected_counts=labels.groupby(['horizon_days','origin_cell_1']).size()
        for (h,target,donor),g in t.groupby(['horizon_days','origin_cell_1','donor_cell_1']):
            assert len(g)==expected_counts.loc[(h,donor)]
            y,x=divmod(int(target),360);yy,xx=divmod(int(donor),360)
            assert max(abs(y-yy),abs(((x-xx+180)%360)-180))==1
        combined.append(t.groupby(['id','horizon_days','origin_cell_1','donor_cell_1','destination_cell_1','reason_code']).size().rename('pair_count').reset_index())
        all_reasons.update(zip(t.horizon_days,t.reason_code))
        t['outcome_class']=np.where(t.destination_cell_1.eq(FALLBACK),'fallback',np.where(t.destination_cell_1.eq(-2),'exit','in_D'))
        all_outcomes.update(t[['horizon_days','reason_code','outcome_class']].itertuples(index=False,name=None))
        # Resolved E and resolved D share reason zero; both require a real path audit.
        extra.append(t.sort_values(['id','origin_source_obs','origin_cell_1']).groupby(['horizon_days','reason_code','outcome_class']).head(3))
    cols=['id','horizon_days','origin_cell_1','donor_cell_1','destination_cell_1','reason_code']
    actual=pd.concat(combined,ignore_index=True).sort_values(cols).reset_index(drop=True)
    saved=read_frame(input_root/'transfer_counts_by_id.parquet').sort_values(cols).reset_index(drop=True)
    pd.testing.assert_frame_equal(actual,saved,check_dtype=False,check_exact=True)
    assert all_reasons <= set(zip(sample.horizon_days,sample.reason_code))
    extra=pd.concat(extra,ignore_index=True).sort_values(['id','origin_source_obs','origin_cell_1']).groupby(['horizon_days','reason_code','outcome_class']).head(3)
    sample=pd.concat([sample,extra],ignore_index=True).drop_duplicates(['id','horizon_days','origin_source_obs','origin_cell_1'])
    sample['outcome_class']=np.where(sample.destination_cell_1.eq(FALLBACK),'fallback',np.where(sample.destination_cell_1.eq(-2),'exit','in_D'))
    assert all_outcomes<=set(sample[['horizon_days','reason_code','outcome_class']].itertuples(index=False,name=None))
    for ident,g in sample.groupby('id'):
        f=read_frame(input_root/'paths'/f'{ident}.parquet')
        labels=read_frame(input_root/'labels'/f'{ident}.parquet').set_index(['horizon_days','origin_source_obs'])
        for r in g.itertuples(index=False):
            label=labels.loc[(r.horizon_days,r.origin_source_obs)].copy();label['origin_source_obs']=r.origin_source_obs
            actual=scalar_transfer(f,label,r.origin_cell_1,r.dx,r.dy,geo)
            assert actual==(r.destination_cell_1,r.reason_code),(r,actual)
            checked+=1
    return dict(independent_scalar_paths=checked,all_observed_reasons_covered=True,all_observed_outcome_classes_covered=True,
                resolved_exit_paths_checked=int(sample.destination_cell_1.eq(-2).sum()),transfer_count_rows_reconciled=len(saved))


def rebuild(counts,transfers,folds,roles,states):
    index={int(c):k for k,c in enumerate(states)};result={}
    for role,spec in roles.items():
        excluded=[spec[k] for k in ('outer_fold','inner_fold') if spec[k]>=0]
        train=set(spec['training_ids']);evaluation=set(spec['evaluation_ids'])
        assert train==set(folds.loc[~folds.outer_fold.isin(excluded),'id']) and not train&evaluation
        expected=set() if spec['outer_fold']<0 else set(folds.loc[folds.outer_fold.eq(spec['inner_fold'] if spec['inner_fold']>=0 else spec['outer_fold']),'id'])
        assert evaluation==expected
        raw=defaultdict(Counter);moved=defaultdict(Counter)
        for r in counts.itertuples(index=False):
            if r.id in train: raw[(r.horizon_days,r.origin_cell_1)][r.destination_cell_1]+=r.pair_count
        for r in transfers.itertuples(index=False):
            if r.id in train: moved[(r.horizon_days,r.origin_cell_1)][r.destination_cell_1]+=r.pair_count
        p={};q={h:np.zeros(len(states)) for h in (7,30)};qe={};qd={};ns={}
        for (h,i),c in sorted(raw.items()):
            z=np.zeros(len(states));n=sum(c.values());ns[(h,i)]=n
            for j,v in c.items():z[index[j]]=v/n;q[h][index[j]]+=v
            p[(h,i)]=z
        for h in q:q[h]/=q[h].sum()
        for (h,i),prob in p.items():
            y,x=divmod(i,360);neigh=[]
            for (hh,k),c in raw.items():
                yy,xx=divmod(k,360)
                if hh==h and k!=i and abs(y-yy)<=1 and abs(((x-xx+180)%360)-180)<=1:neigh.append(c)
            local=Counter()
            for c in neigh:local.update(c)
            n=sum(local.values());shift=moved[(h,i)]
            assert n==sum(shift.values())
            a=np.zeros(len(states));b=np.zeros(len(states))
            if n:
                for j,v in local.items():a[index[j]]=v/n
                for j,v in shift.items():
                    if j==FALLBACK:b+=(v/n)*prob
                    else:b[index[j]]+=v/n
            else:a=prob.copy();b=prob.copy()
            qe[(h,i)]=a;qd[(h,i)]=b
        med={h:float(np.median([n for (hh,i),n in ns.items() if hh==h])) for h in (7,30)}
        result[role]=dict(p=p,q=q,qe=qe,qd=qd,n=ns,m=med)
    return result


def probability(base,h,o,model,a):
    key=(h,o)
    if key not in base['p']:return None
    p=base['p'][key]
    if model=='B2':return p
    if model=='Adaptive':
        tau=base['m'][h]*a/(1-a) if 0<a<1 else None
        w=a if a in (0,1) else tau/(base['n'][key]+tau)
        q=base['q'][h]
    else:w=a;q=base['q'][h] if model=='Fixed' else base['qe'][key] if model=='LocalEndpoint' else base['qd'][key]
    return p+w*(q-p)


def independent_audit(paths,run,counts,transfers,folds,roles,states):
    root=run['results'];bases=rebuild(counts,transfers,folds,roles,states);index={int(c):k for k,c in enumerate(states)}
    errors={'probability':0.,'candidate':0.,'score':0.,'summary':0.}; cache={}
    obs={}
    for r in counts.itertuples(index=False):obs.setdefault((r.horizon_days,r.origin_cell_1,r.id),Counter())[r.destination_cell_1]+=r.pair_count
    selected=read_frame(root/'selected_parameters.csv')
    units=read_frame(root/'candidate_id_cells.parquet');scores=read_frame(root/'candidate_scores.csv').set_index(['fit_role','horizon_days','model','parameter_a'])
    expected_ident={('B2',0.),*[(m,k/20) for m in MODELS[1:] for k in range(21)]}
    for role,g in units.groupby('fit_role'):
        keys=set(obskey for obskey in obs if obskey[2] in roles[role]['evaluation_ids'])
        assert set(g[['model','parameter_a']].itertuples(index=False,name=None))==expected_ident
        for ident,z in g.groupby(['model','parameter_a']):
            assert not z.duplicated(['horizon_days','origin_cell_1','id']).any()
            assert set(z[['horizon_days','origin_cell_1','id']].itertuples(index=False,name=None))==keys
    last_role=None
    for r in units.itertuples(index=False):
        if r.fit_role!=last_role: cache.clear();last_role=r.fit_role
        key=(r.fit_role,r.horizon_days,r.origin_cell_1,r.model,r.parameter_a)
        if key not in cache:
            p=probability(bases[r.fit_role],*key[1:]);cache[key]=None if p is None else (p,region(p),float(p@p))
        item=cache[key];c=obs[(r.horizon_days,r.origin_cell_1,r.id)];n=sum(c.values())
        assert n==r.eligible_pairs and r.supported==(item is not None)
        if item is None:continue
        p,reg,norm=item
        expect=(sum(v*(1+norm-2*p[index[j]]) for j,v in c.items())/n,int(np.sum(reg&(states>=0))),sum(v for j,v in c.items() if reg[index[j]])/n)
        errors['candidate']=max(errors['candidate'],*(abs(x-getattr(r,m)) for x,m in zip(expect,METRICS)))
    for key,g in units.groupby(['fit_role','horizon_days','model','parameter_a']):
        independent=macro(g.to_dict('records'));saved=scores.loc[key]
        for m in METRICS: errors['summary']=max(errors['summary'],abs(independent[m]-saved[m]))
    for role,choice in selected.groupby('role'):
        pool=units[units.selection_role.eq(role)]
        for h in (7,30):
            for model in MODELS[1:]:
                vals=[]
                for a,g in pool[pool.horizon_days.eq(h)&pool.model.eq(model)].groupby('parameter_a'):
                    vals.append((a,macro(g.to_dict('records'))['brier']))
                best=min(v for a,v in vals);expected=min(a for a,v in vals if v<=best+1e-12)
                row=choice[choice.horizon_days.eq(h)&choice.model.eq(model)].iloc[0]
                assert expected==row.parameter_a
        for model in MODELS:
            saved=read_frame(root/'matrices'/f'{role}_{model}.parquet')
            for key,p0 in bases[role]['p'].items():
                h,o=key;a=0. if model=='B2' else float(choice[choice.horizon_days.eq(h)&choice.model.eq(model)].parameter_a.iloc[0])
                p=probability(bases[role],h,o,model,a);v=np.zeros(len(states))
                for r in saved[saved.horizon_days.eq(h)&saved.origin_cell_1.eq(o)].itertuples(index=False):v[index[r.destination_cell_1]]=r.probability
                assert abs(v.sum()-1)<1e-12 and (v>=0).all()
                errors['probability']=max(errors['probability'],float(np.max(np.abs(p-v))))
    held=read_frame(root/'heldout_scores.parquet');heldcache={}
    for r in held.itertuples(index=False):
        key=(r.role,r.horizon_days,r.origin_cell_1,r.model)
        if key not in heldcache:
            a=0. if r.model=='B2' else float(selected[selected.role.eq(r.role)&selected.horizon_days.eq(r.horizon_days)&selected.model.eq(r.model)].parameter_a.iloc[0])
            p=probability(bases[r.role],r.horizon_days,r.origin_cell_1,r.model,a);heldcache[key]=None if p is None else (p,region(p))
        item=heldcache[key]
        assert (item is not None)==(r.status=='evaluable')
        if item is None:continue
        p,reg=item;j=index[r.destination_cell_1]
        values=(1+float(p@p)-2*p[j],int(np.sum(reg&(states>=0))),float(reg[j]))
        errors['score']=max(errors['score'],*(abs(x-getattr(r,m)) for x,m in zip(values,METRICS)))
    hu=read_frame(root/'heldout_id_cells.parquet');sm=read_frame(root/'summary.csv').set_index(['horizon_days','model'])
    for key,g in hu.groupby(['horizon_days','model']):
        for m,v in macro(g.to_dict('records')).items():
            if m in METRICS:errors['summary']=max(errors['summary'],abs(v-sm.loc[key,m]))
    assert max(errors.values())<=1e-12,errors
    return dict(passed=True,fitting_roles_checked=len(roles),candidate_id_cells_checked=len(units),candidate_identities_checked=len(scores),heldout_grouped_cases_checked=len(held),maximum_absolute_errors=errors)


def audit_uncertainty(root,folds,replicates=5000,seed=20261030):
    units=read_frame(root/'heldout_id_cells.parquet');draws=read_frame(root/'bootstrap_draws.csv');diffs=read_frame(root/'paired_differences.csv')
    ids=sorted(folds.id.tolist());w=np.random.Generator(np.random.PCG64(seed)).exponential(size=(replicates,len(ids)))
    meta=json.loads((root/'multiplier_identity.json').read_text());assert hashlib.sha256(w.astype('<f8').tobytes()).hexdigest()==meta['little_endian_float64_sha256']
    ix={d:k for k,d in enumerate(ids)};error=0.
    for (h,model),g in units[units.supported].groupby(['horizon_days','model']):
        agg=np.zeros((replicates,3));nc=g.origin_cell_1.nunique()
        for o,z in g.groupby('origin_cell_1'):
            mass=w[:,[ix[d] for d in z.id]];mass=mass/mass.sum(axis=1)[:,None]
            agg+=mass@z[list(METRICS)].to_numpy()/nc
        saved=draws[draws.horizon_days.eq(h)&draws.model.eq(model)].sort_values('replicate')[list(METRICS)].to_numpy()
        error=max(error,float(np.max(np.abs(agg-saved))))
    for r in diffs.itertuples(index=False):
        h=draws[draws.horizon_days.eq(r.horizon_days)].set_index(['model','replicate'])
        delta=h.xs(r.model,level='model')[r.metric]-h.xs(r.reference,level='model')[r.metric]
        for q,v in [(0.025,r.lower_95),(.975,r.upper_95)]:error=max(error,abs(float(np.quantile(delta,q))-v))
        if r.primary_comparison:
            q=.05/6 if r.metric=='region90_hit' else 1-.05/6
            error=max(error,abs(float(np.quantile(delta,q))-r.adjusted_directional_bound))
    assert error<1e-12,error
    return dict(passed=True,max_error=error,replicates=replicates,draw_identity_verified=True)
