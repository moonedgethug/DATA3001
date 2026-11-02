"""Source-backed E5 resource-gate report; never substitutes pilot scores for CV."""
import html
import json
import re
from io import BytesIO
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from data3001.modelling.common.runtime import save_json,save_frame


def write_capacity_report(paths,run,pilot,result,timings,workload,roster,verification):
    """Report a stopped resource gate, without fabricated prediction comparisons."""
    if result['capacity_passed'] or result['full_experiment_started']:
        raise ValueError('This report is only for a failed resource gate before full CV')
    projection=[]
    if len(timings):
        for (h,cell),group in timings.groupby(['horizon_days','origin_cell_1']):
            total=int(workload[(workload.horizon_days==h)&(workload.origin_cell_1==cell)].iloc[0].outer_query_donor_combinations)
            planned=int(((roster.horizon_days==h)&(roster.origin_cell_1==cell)).sum())
            rates=group.seconds/group.donors
            projection.append(dict(horizon_days=int(h),origin_cell_1=int(cell),sample_queries=len(group),
                planned_queries=planned,completed_stratum=len(group)==planned,outer_combinations=total,
                mean_query_seconds=float(group.seconds.mean()),mean_seconds_per_donor=float(group.seconds.sum()/group.donors.sum()),
                diagnostic_hours_mean=float(group.seconds.sum()/group.donors.sum()*total/3600),
                diagnostic_hours_min=float(rates.min()*total/3600),diagnostic_hours_max=float(rates.max()*total/3600)))
    save_frame(paths,run['results']/'diagnostic_resource_projection.csv',pd.DataFrame(projection))
    save_frame(paths,run['results']/'completed_query_timings.csv',timings)
    save_frame(paths,run['results']/'pilot_roster.csv',roster)
    save_frame(paths,run['results']/'workload.csv',workload)
    fig,axes=plt.subplots(1,3,figsize=(15,4.6),layout='constrained')
    fig.suptitle('Step 3 E5 v2 — resource gate, not prediction performance',fontsize=15)
    if len(timings):
        axes[0].bar(np.arange(1,len(timings)+1),timings.seconds,color='#28638a')
        axes[0].set(xlabel='Completed pilot query',ylabel='Geometry time (seconds)',title='Measured query cost')
        cert=int(timings.certified.sum());literal=int(timings.literal_pairs.sum());total=cert+literal
        axes[1].barh(['Completed donor transfers'],[cert/total],color='#318c78',label='Exact rectangle certificate')
        axes[1].barh(['Completed donor transfers'],[literal/total],left=[cert/total],color='#d68a3b',label='Hourly path checks')
        axes[1].set(xlim=(0,1),xlabel='Fraction of donor transfers',title=f'{total:,} fully timed donor transfers')
        axes[1].legend(loc='lower center',bbox_to_anchor=(.5,-.35),frameon=False)
    else:
        for ax in axes[:2]:ax.text(.5,.5,'No completed query timing',ha='center',transform=ax.transAxes)
    axes[2].bar(['Pilot elapsed','Pilot limit'],[result['elapsed_seconds'],300],color=['#b9554f','#a6b3bd'])
    axes[2].set(ylabel='Seconds',title='Approved 300-second gate')
    for spine in ('top','right'):
        for ax in axes:ax.spines[spine].set_visible(False)
    for suffix in ('png','svg'):
        data=BytesIO();fig.savefig(data,format=suffix,dpi=160,metadata={'Creator':'DATA3001 E5 resource audit'})
        paths.publish(run['results']/f'capacity_comparison.{suffix}',lambda f,data=data:f.write(data.getvalue()))
    plt.close(fig)
    rows='\n'.join(f'| {label} | Not run | Not run | Not run |' for label in
                    ['Fixed grid','Fixed analytic','Adaptive grid','Adaptive continuous'])
    mean=float(timings.seconds.mean()) if len(timings) else 0.
    total=int(timings.donors.sum()) if len(timings) else 0
    certified=int(timings.certified.sum()) if len(timings) else 0
    projection_text='No completed-stratum runtime projection was available at the stop.'
    if projection:
        p=projection[0]
        projection_text=(f'Timing-only diagnostic for the measured {p["horizon_days"]}-day cell '
          f'{p["origin_cell_1"]}: {p["diagnostic_hours_mean"]:.2f} hours for that cell across outer '
          f'query/donor pairs, using the observed mean rate, a factor-of-two reserve and ideal '
          f'two-worker speedup. Only {p["sample_queries"]}/{p["planned_queries"]} planned queries '
          f'in this stratum completed. This is an incomplete-sample extrapolation, not a full-run '
          f'forecast, confidence interval, lower bound or measured total runtime; unmeasured '
          f'strata and scoring are excluded. The actual stop is determined by the sealed capacity receipt.')
    report=f'''# Step 3 E5 v2 — Resource-Gate Result

**Status: {result['status']}. Full E5 prediction experiment has not run.**

The approved resource gate stopped this attempt: `{result['reason']}`. There is no basis to claim that analytic or continuous weights improved or worsened Brier, 90% region size or actual hit rate. Pilot examples are capacity measurements, not held-out scientific results.

## What was implemented

The actual-start displacement kernel, complete donor-mass/B2 fallback, conservative exact geometry certificates, standard query-level Brier, Fixed grid/analytic solvers, Adaptive grid/bounded continuous solvers, and declared finite quality search are implemented. Semantic verification covers geometry, probability conservation, objective/gradient identities and bounded selection. Full nested-CV orchestration, model comparison and complete fresh-run replay were not completed after the capacity gate failed.

## Measured resources

| Quantity | Observed |
|---|---:|
| Pilot wall time | {result['elapsed_seconds']:.3f} seconds |
| Approved pilot cap | 300 seconds |
| Peak RSS | {result['peak_rss_bytes']/1024**3:.3f} GiB |
| Completed / frozen pilot queries | {result['completed_queries']} / {result['frozen_queries']} |
| Fully timed donor transfers | {total:,} |
| Mean completed-query geometry time | {mean:.3f} seconds |
| Exact rectangle-certified transfers | {certified:,} |
| Independent scalar transfer checks | {result['independent_transfer_checks']} |
| Final-test reads / canonical training trajectory reads | 0 / {result['canonical_train_reads']} |

The last interrupted query is excluded from completed-query means and donor totals. Measurements include the extra donor-fold block needed by the outer cache; the inner forecast would only combine its three permitted fitting blocks. No donor sampling, rounded starts, smaller probability region or reduced CV was substituted.

{projection_text}

![Resource measurements](capacity_comparison.png)

## Requested prediction comparison

| Procedure | Outer Brier | Outer mean K90 | Outer H90 |
|---|---|---|---|
{rows}

The full five-outer/four-inner CV, six-control regression, 72-contrast screen, 50,000 multiplier draws and prediction maps remain unperformed. No candidate was accepted or rejected on scientific quality. A resource failure does not show that displacement or off-grid weight optimisation is ineffective.

## Verification and decision

The independent audit receipt accompanies this report. Completed pilot transfers were compared with a scalar chronological geometry implementation. Synthetic tests establish implementation behaviour, not ocean prediction accuracy. The planned 5,000-real-transfer full-experiment audit and complete geometry/scoring replay were not run. Original source files and the approved plan remain protected; the stage ledger is unchanged.

The current implementation did not establish feasibility within the approved budget. Preserve the four solver implementations and measured bottleneck. The next discussion should address exact geometry acceleration or a separately approved computational design; do not rerun with wider limits, change the estimator, or proceed to full CV automatically.

## Provenance

- Approved plan: `docs/actual_origin_displacement_s3_e5_plan.md`, SHA256 `{result.get('plan_sha256','67afaa77db68bb66e924741cda3c760188be96b4b1843aa78309df11bf4d3fe3')}`.
- Pilot run: `{pilot.name}`.
- Review run: `{run['results'].name}`.
- [Pilot capacity receipt]({pilot/'capacity.json'}).
- [Completed query timings](completed_query_timings.csv).
- [Frozen pilot roster](pilot_roster.csv).
- [Input workload](workload.csv).
- [Diagnostic resource projection](diagnostic_resource_projection.csv).
- [Independent review receipt](verification.json).
'''
    paths.publish(run['results']/'REPORT.md',lambda f:f.write(report.encode()))
    paths.publish(run['results']/'verification.json',lambda f:f.write((json.dumps(verification,indent=2,sort_keys=True)+'\n').encode()))
    body=''
    def inline(text):
        text=html.escape(text)
        text=re.sub(r'\*\*(.+?)\*\*',r'<strong>\1</strong>',text)
        text=re.sub(r'`([^`]+)`',r'<code>\1</code>',text)
        text=re.sub(r'\[([^\]]+)\]\(([^)]+)\)',r'<a href="\2">\1</a>',text)
        return text
    # Render the small controlled report with escaped text, table blocks and links.
    in_table=False
    for line in report.splitlines():
        if line.startswith('|'):
            if not in_table:body+='<table>';in_table=True
            if set(line.replace('|','').replace(' ',''))<={'-',':'}:continue
            body+='<tr>'+''.join('<td>'+inline(c.strip())+'</td>' for c in line.strip('|').split('|'))+'</tr>'
        else:
            if in_table:body+='</table>';in_table=False
            if line.startswith('![Resource'):body+='<img src="capacity_comparison.png" alt="Measured resource use">'
            elif line.startswith('### '):body+='<h3>'+html.escape(line[4:])+'</h3>'
            elif line.startswith('## '):body+='<h2>'+html.escape(line[3:])+'</h2>'
            elif line.startswith('# '):body+='<h1>'+html.escape(line[2:])+'</h1>'
            elif line:body+='<p>'+inline(line)+'</p>'
    body+='''<p><a href="REPORT.md">Full report</a> · <a href="verification.json">Audit receipt</a> ·
<a href="completed_query_timings.csv">Timings</a> · <a href="pilot_roster.csv">Pilot roster</a> ·
<a href="capacity_comparison.svg">Vector figure</a></p>'''
    page='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>E5 v2 resource gate</title><style>body{max-width:1150px;margin:40px auto;padding:0 24px;font:16px/1.6 system-ui;color:#183044;background:#f8fafb}h1{line-height:1.2}h2{margin-top:38px}table{width:100%;border-collapse:collapse;background:white}td{padding:9px 12px;border-bottom:1px solid #d6e0e6}tr:first-child{font-weight:650;background:#e6edf2}img{width:100%;height:auto}p{overflow-wrap:anywhere}a{color:#166889}</style><body>'''+body+'</body></html>'
    paths.publish(run['results']/'review.html',lambda f:f.write(page.encode()))
    return report
