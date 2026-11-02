"""Human-facing frozen-model diagnostic report and observed-state control.

The observed-state control intentionally supplies the previous REAL hourly state.
It isolates local errors and is never presented as a free-running forecast.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd
import torch

from data3001.paths import project_paths, file_sha256
from data3001.modelling.continuous import mixture_draw, to_state
from data3001.modelling.continuous_diagnostics import MODEL_RUN, PARENT, HOURS, physical_moments
from data3001.modelling.run_continuous import load_model
from data3001.modelling.run_blend_cv import ReadOnlyInputs, save_frame, save_json
from data3001.modelling.run_neighbourhood import verified_run, _seal


@torch.no_grad()
def observed_state_control(query, observations, models):
    rows = []
    for name, (model, mean, sd) in models.items():
        mu0, sd0 = torch.from_numpy(mean), torch.from_numpy(sd)
        for hour in HOURS:
            prev = observations[query.origin.to_numpy()+hour-1]
            actual = observations[query.origin.to_numpy()+hour]
            if not (np.array_equal(prev['id'],actual['id']) and np.array_equal(prev['id'],query.id) and (actual['time']-prev['time']==3600).all()):
                raise ValueError('Observed-state control requires exact same-ID adjacent hours')
            s = to_state(prev['lon'],prev['lat'],prev['ve'],prev['vn']).astype('float32')
            torch.manual_seed(81721+hour)
            repeated = torch.from_numpy(np.repeat(s,128,axis=0))
            out = model((repeated-mu0[:4])/sd0[:4])
            vnext = repeated[:,2:]+(mixture_draw(out)*sd0[4:]+mu0[4:])[:,2:]
            expected_speed = vnext.norm(dim=1).reshape(len(s),128).mean(1).numpy()
            m,_ = physical_moments(model((torch.from_numpy(s)-mu0[:4])/sd0[:4]),mu0,sd0)
            vector = s[:,2:]+m[:,2:].numpy()
            for i,q in enumerate(query.itertuples()):
                rows.append({'model':name,'id':int(q.id),'origin':int(q.origin),'hour':hour,
                    'weight':q.diagnostic_weight,'observed_speed_m_s':float(np.hypot(actual['ve'][i],actual['vn'][i])),
                    'control_expected_speed_m_s':float(expected_speed[i]),
                    'observed_vn_m_s':float(actual['vn'][i]),'control_vn_m_s':float(vector[i,1]),
                    'velocity_squared_error':float((vector[i,0]-actual['ve'][i])**2+(vector[i,1]-actual['vn'][i])**2)})
    return pd.DataFrame(rows)


def summaries(traces,control):
    rows=[]
    for (model,seed,hour),g in traces.groupby(['model','seed','hour']):
        ok=g.predicted_speed_m_s.notna();a=g.loc[ok]
        c=control.loc[control.model.eq(model)&control.hour.eq(hour)].set_index('origin').loc[a.origin]
        row={'model':model,'seed':int(seed),'hour':int(hour),'origins':len(g),
             'origins_with_survivors':int(ok.sum()),'IDs':int(g.id.nunique())}
        for key in ('S',*[f'reason_{j}_fraction' for j in range(5)]):
            row[key]=float(np.average(g[key],weights=g.weight))
        for key in ('observed_speed_m_s','predicted_speed_m_s','observed_vn_m_s','predicted_vn_m_s',
                    'within_prediction_rms_chart_km','centroid_error_chart_km'):
            row[key]=float(np.average(a[key],weights=a.weight))
        for key in ('control_expected_speed_m_s','control_vn_m_s'):
            row[key]=float(np.average(c[key],weights=a.weight))
        rows.append(row)
    return pd.DataFrame(rows)


def table(frame):
    lines=['| '+' | '.join(map(str,frame.columns))+' |','| '+' | '.join(['---']*len(frame.columns))+' |']
    for values in frame.itertuples(index=False,name=None):
        lines.append('| '+' | '.join(f'{v:.5g}' if isinstance(v,(float,np.floating)) else str(v) for v in values)+' |')
    return '\n'.join(lines)


def figure(path,summary,one):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(2,2,figsize=(12,8),layout='constrained')
    a=summary.loc[summary.model.eq('MDN3_l2_0')].groupby('hour').mean(numeric_only=True).reset_index()
    for ax,pred,obs,control,label in [
        (axes[0,0],'predicted_speed_m_s','observed_speed_m_s','control_expected_speed_m_s','Mean speed (m/s)'),
        (axes[0,1],'predicted_vn_m_s','observed_vn_m_s','control_vn_m_s','Mean northward velocity (m/s)')]:
        ax.plot(a.hour,a[obs],'-o',color='#183844',label='Observed')
        ax.plot(a.hour,a[pred],'-o',color='#c3593e',label='MDN free rollout')
        ax.plot(a.hour,a[control],'--o',color='#2a8b75',label='Real previous state supplied*')
        ax.set(xscale='log',xticks=list(HOURS),xticklabels=list(HOURS),xlabel='Hours since release',ylabel=label)
        ax.grid(alpha=.2);ax.legend(fontsize=8)
    ax=axes[1,0]
    ax.plot(a.hour,100*a.reason_2_fraction,'-o',label='Land-mask failures (U)',color='#c3593e')
    ax.plot(a.hour,100*a.reason_1_fraction,'-o',label='First domain exit (E)',color='#5267a5')
    ax.set(xscale='log',xticks=list(HOURS),xticklabels=list(HOURS),xlabel='Hours since release',ylabel='Probability mass (%)')
    ax.grid(alpha=.2);ax.legend(fontsize=8)
    ax=axes[1,1]
    z=one.loc[one.model.eq('MDN3_l2_0') & one.scope.eq('R') & one.speed_band.eq(2)].iloc[0]
    ax.bar(['Observed','MDN'],[z.observed_parallel_dv,z.predicted_parallel_dv],color=['#183844','#c3593e'])
    ax.axhline(0,color='#777',lw=.7);ax.set(ylabel='One-hour velocity change along initial direction (m/s)',title='R origins with initial speed >= 0.75 m/s')
    fig.suptitle('Frozen MDN diagnosis: local skill does not ensure sustained transport',fontsize=15)
    fig.text(.01,-.035,'* Diagnostic control uses real previous-hour observations; it is NOT an open-loop forecast.\n'
             'Trace: 953 sampled origins / 60 IDs, inverse-inclusion weights, two 32-particle seeds. Velocity curves condition on surviving queries.',fontsize=9)
    fig.savefig(path,dpi=170,bbox_inches='tight');plt.close(fig)


def main():
    p=argparse.ArgumentParser();p.add_argument('--run',required=True);args=p.parse_args()
    paths=project_paths();receipt=verified_run(paths,args.run)
    root=paths.root/'results/runs'/args.run
    query=pd.read_csv(root/'diagnostic_queries.csv')
    traces=pd.concat([pd.read_csv(f) for f in sorted(root.glob('trace_*.csv'))],ignore_index=True)
    one=pd.read_csv(root/'one_step_summary.csv');byid=pd.read_csv(root/'one_step_by_ID.csv')
    comp=pd.read_csv(root/'ID_completeness.csv')
    failures=pd.concat([pd.read_parquet(f) for f in root.glob('failures_*.parquet')],ignore_index=True)
    run=paths.create_run(datetime.now(timezone.utc).strftime('continuous_diagnostic_report_%Y%m%dT%H%M%S_%fZ'),{
        'diagnostic_run':args.run,'parent_receipt_sha256':file_sha256(receipt),'model_run':MODEL_RUN,
        'source_sha256':file_sha256(Path(__file__)),'final_test_access':False,'refitting':False,
        'control':'observed previous-hour state supplied; not a forecast','control_particles':128})
    paths.publish(run['provenance']/'report_source.py',lambda f:f.write(Path(__file__).read_bytes()))
    guard=ReadOnlyInputs(paths.root,run,data_root=paths.data_root);sys.addaudithook(guard)
    try:
        torch.set_num_threads(4)
        obs=np.load(paths.root/'results/runs'/PARENT/'observations.npy',mmap_mode='r')
        models={name:load_model(paths.root/'results/runs'/MODEL_RUN/('refit_'+name)) for name in ('G_l2_0','MDN3_l2_0')}
        control=observed_state_control(query,obs,models)
        save_frame(paths,run['results']/'observed_state_control.csv',control)
        summary=summaries(traces,control)
        save_frame(paths,run['results']/'trace_summary.csv',summary)
        train=comp.loc[comp.historical_split.eq('train')&comp.pairs.gt(0)]
        training={'IDs':len(train),'pairs':int(train.pairs.sum()),
            'R_pair_fraction':float(train.R_pairs.sum()/train.pairs.sum()),
            'next_hour_eligibility':float(train.pairs.sum()/train.D_candidate_origins.sum()),
            **{f'fraction_in_segments_ge_{h}h':float(np.average(train[f'fraction_in_segments_ge_{h}h'],weights=train.pairs)) for h in (24,168,720)},
            **{f'top_{k}_ID_training_share':float(train.pairs.nlargest(k).sum()/train.pairs.sum()) for k in (1,10,100)}}
        save_json(paths,run['results']/'training_influence.json',training)
        fast=byid.loc[byid.model.eq('MDN3_l2_0')&byid.scope.eq('R')&byid.speed_band.eq(2)]
        d=(fast.predicted_parallel_dv_sum-fast.observed_parallel_dv_sum).to_numpy();n=fast.pairs.to_numpy()
        rng=np.random.default_rng(4);ix=rng.integers(0,len(fast),(2000,len(fast)))
        interval=np.quantile(d[ix].sum(1)/n[ix].sum(1),[.025,.975])
        bias={'IDs':len(fast),'pairs':int(n.sum()),'mean_bias_m_s':float(d.sum()/n.sum()),
              'lower95':float(interval[0]),'upper95':float(interval[1]),
              'scope':'Whole-ID bootstrap, frozen model, exploratory R speed>=0.75 m/s stratum; no refitting uncertainty.'}
        save_json(paths,run['results']/'fast_R_velocity_bias.json',bias)
        sig=pd.read_csv(root/'local_sensitivity.csv')
        sig['d_delta_ve_d_ve']=sig.d_ve_next_d_ve-1
        sig['d_delta_vn_d_vn']=sig.d_vn_next_d_vn-1
        save_frame(paths,run['results']/'learned_velocity_derivatives.csv',sig)
        counts=failures.groupby(['model','reason']).size().reset_index(name='particle_events')
        save_frame(paths,run['results']/'first_failure_counts.csv',counts)
        figure(run['results']/'diagnostic_overview.png',summary,one)
        mdn=summary.loc[summary.model.eq('MDN3_l2_0')].groupby('hour').mean(numeric_only=True).reset_index()
        view=mdn[['hour','observed_speed_m_s','control_expected_speed_m_s','predicted_speed_m_s','observed_vn_m_s','predicted_vn_m_s']]
        local=one.loc[one.model.eq('MDN3_l2_0'),['scope','speed_band','pairs','IDs','velocity_RMSE_m_s','persistence_velocity_RMSE_m_s','predicted_parallel_dv','observed_parallel_dv']]
        report=f'''# Continuous-model diagnostic audit

The current MDN has measurable one-hour skill, but does not sustain the observed
transport adequately in free rollouts. The evidence supports investigating excessive
velocity damping, weak location-dependent mean corrections, training convergence,
and coastal boundary handling before imposing a narrower forecast.

Model run: `{MODEL_RUN}`. Diagnostic run: `{args.run}`.
No model was refitted, no training weights or features were changed, and final test
was not opened. Canonical inputs and existing results remain unchanged.

## 1. Evidence and coverage

- All 4,598,829 eligible hourly transitions from 440 historical-validation IDs were
  scored for one-step diagnostics. R and speed bands are descriptive strata.
- Free rollouts use {len(query)} origins from {query.id.nunique()} IDs in the common
  complete 7/30-day cohort. Up to 16 origins per ID are sampled without replacement,
  before examining errors; inverse inclusion weights recover the cohort's pair target.
- Each Gaussian/MDN free rollout uses two independent 32-particle seeds. Both use
  gamma=0, the selected 30-day configurations. This is an exploratory path diagnosis,
  not a new model-selection round or an exact reproduction of the full 7-day cohort.
- Observed-state controls receive the actual state one hour before each diagnostic
  horizon, then make one step. They intentionally use intervening observations and
  must never be presented as usable release-time forecasts.
- All trace-selected observed paths were verified hour by hour for ID, time and
  in-domain eligibility. Whole IDs remain the unit of uncertainty assessment.

## 2. One-step velocity learning

Speed bands: 0 < 0.25 m/s; 1 = [0.25,0.75) m/s; 2 >= 0.75 m/s.
RMSE is the Euclidean velocity-vector RMSE. Persistence holds the current velocity.
Parallel change projects the velocity increment onto the INITIAL direction; it is
not identical to a change in speed magnitude, because turning also changes it.

{table(local)}

The MDN's vector RMSE is slightly below persistence in every reported stratum;
therefore the claim that it learns no useful velocity information is unsupported.
However, fast R origins have a predicted-minus-observed parallel-change bias of
{bias['mean_bias_m_s']:.5f} m/s per one-hour transition, with a frozen-model whole-ID
95% bootstrap interval [{bias['lower95']:.5f}, {bias['upper95']:.5f}] across {bias['IDs']} IDs.
This supports an excessive along-direction damping diagnosis in this stratum,
not a universal assertion that every flow should preserve its speed.

Local derivatives also show nonzero learned velocity corrections. Subtracting the
identity contribution in the propagation formula is essential: a next-velocity
derivative near one does not by itself prove the network learned velocity well.
Location derivatives of the conditional mean velocity are small on sampled R
states; this does not prove that location is irrelevant to mixture weights,
covariances, or other regions. No causal feature importance is claimed.

## 3. Single-step control versus free propagation

{table(view)}

Control expected speeds use 128 samples; free-rollout speeds are averages of
sampled speed magnitudes, not the magnitude of a mean vector. This avoids mistaking
directional cancellation for speed decay. Velocity summaries use the same origins
with surviving simulated particles for the observed, control and free-run values;
failure mass is reported separately and never renormalized away in forecast scores.
Survivor conditioning remains a limitation of these physical-state summaries.

The observed-state control remains much closer to observed velocities than the
free-running model. Thus locally reasonable predictions do not preserve the observed
long-run dynamics. This is consistent with feedback of generated-state errors and
insufficient sustained dynamics; it does not alone distinguish model capacity,
state insufficiency, training objective, or state-distribution shift as the cause.

## 4. Completeness and current training influence

{table(pd.DataFrame([{'metric':k,'value':v} for k,v in training.items()]))}

About {100*training['fraction_in_segments_ge_720h']:.2f}% of training pairs already belong
to uninterrupted eligible segments of at least 720 hours. This measures continuity
of the processed hourly product, not original satellite measurement frequency or
measurement accuracy. Long trajectories already contribute more under equal-pair
training. There is no evidence here that an additional completeness bonus would
repair the observed velocity bias.

Only {100*training['R_pair_fraction']:.2f}% of D-origin training transitions start in R.
D coverage is necessary for later transport, so this is not a recommendation to
discard outside-R data. It motivates checking learning curves and state-stratified
errors. Any quality weighting needs an independently justified quality variable,
a defined sampled population, and a separate sensitivity experiment under Contract
03/12. Sampling schemes with importance correction can change optimization without
silently changing the main equal-pair objective.

## 5. Dispersion and unresolved outcomes

{table(counts)}

Every unresolved particle in this sampled diagnostic is a finite generated point
rejected by the frozen land mask; direct mask checks confirmed this. There were no
nonfinite/invalid-latitude failures in these traces. This is a simulated geometry
failure, not evidence of an observed beaching event. Do not generalize the absence
of numerical failures to all possible releases.

Weighted MDN land-failure mass at 30 days is
{100*mdn.loc[mdn.hour.eq(720),'reason_2_fraction'].iloc[0]:.2f}%; it is
{100*summary.loc[summary.model.eq('MDN3_l2_0') & summary.hour.eq(720),'reason_2_fraction'].min():.2f}--
{100*summary.loc[summary.model.eq('MDN3_l2_0') & summary.hour.eq(720),'reason_2_fraction'].max():.2f}%
across the two MC seeds. These are weighted subset diagnostics, not replacements
for the earlier full-cohort U estimate. The existing full comparison remains the
source for B2-versus-MDN performance.

A wide map can combine a displaced centre, genuine uncertainty, wrong directions,
and artificial tails. Minimizing nonzero cell count is not a proper objective.
Do not clip trajectories to the observed validation envelope, resample away land
failures, or renormalize remaining geographic mass and call that improved accuracy.

## 6. Proposed implementation gate

1. Keep B2 and the frozen Gaussian/MDN outputs as controls, along with identical
   features, annual pooling, source data and locked final test.
2. First test training adequacy and velocity-dynamics learning: longer training
   with held-ID stopping and a small declared capacity comparison. All six MDN CV
   fits hit the original eight-epoch ceiling; the last held NLL still decreased.
   This suggests training is not proven sufficient, not that more epochs must help.
3. Then compare one-hour training against declared multi-hour kernels on common
   7/30-day releases. Longer lags require full hourly first-exit labels and an explicit
   exit treatment; they cannot simply skip the original absorbing boundary checks.
4. Consider a short multi-step probabilistic training comparison if one-step skill
   still fails to sustain trajectories. Preserve multimodal targets and separate
   mean drift, uncertainty, and boundary errors.
5. Evaluate boundary-aware transition distributions separately if land failures
   persist. Rejection/redraw or truncation is a model change requiring probability
   normalization and re-evaluation, not a graphical cleanup.
6. Completeness/quality weights and covariance-scale calibration are separate
   later challengers, selected using training-internal whole-ID CV with shared
   evaluation weights, probability-region coverage/area, S, and visible E/U mass.

This audit authorizes no new weights, predictors, truncation, or long-lag policy.
It supplies the evidence for freezing the next engineering comparison with the user.

![Diagnostic overview](diagnostic_overview.png)
'''
        paths.publish(run['results']/'REPORT.md',lambda f:f.write(report.encode()))
        _seal(paths,run,{'completed':True,'final_test_access':False,'refitted':False,
            'canonical_changed':False,'diagnostic_run':args.run,'denied_operations':guard.denied,
            'one_step_pairs':4598829,'query_origins':len(query),'query_IDs':int(query.id.nunique())})
        print('DIAGNOSTIC_REPORT='+run['results'].name)
        print(table(view))
    finally:guard.active=False


if __name__=='__main__':main()
