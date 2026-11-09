"""A bounded, explicitly partial report for the E9 engineering pilot."""
import base64
import html
import json
import sys
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from data3001.modelling.baselines import seasonal_exact_position_s4_e9_inputs as inputs
from data3001.modelling.common.runtime import save_json
from data3001.paths import file_sha256


def main(name):
    paths,run,cfg,approval,guard=inputs.context(name)
    budget=inputs.Budget(run,cfg,'audit');completed=False
    folder=run['results']/'report_v3';folder.mkdir()
    try:
        gate=json.loads((run['provenance']/'pilot_gate.json').read_text())
        review=json.loads((run['provenance']/'pilot_independent_review.json').read_text())
        assert review['review_passed'] and not gate['pilot_passed']
        summary=pd.read_csv(run['results']/'pilot_audit/inner_pilot_summary.csv')
        levels=gate['levels'];last=levels[-1]
        resources=[json.loads(p.read_text()) for p in run['provenance'].glob('*_resources.json')]
        pilot_seconds=sum(r['elapsed_seconds'] for r in resources if r['phase']=='pilot')
        peak=max(r['peak_rss_bytes'] for r in resources)/2**30
        counts=[r['energy_count'] for r in levels]
        errors=[1000*r['energy_projection']['SeasonalEndpointCI']['three_se_km'] for r in levels]
        limits=[1000*r['energy_projection']['SeasonalEndpointCI']['threshold_km'] for r in levels]
        times=[r['formal_projected_seconds']/60 for r in levels]
        reserve=[2*t for t in times]
        plt.rcParams.update({'font.family':'DejaVu Sans','font.size':11,'axes.spines.top':False,
                             'axes.spines.right':False,'svg.fonttype':'none'})
        fig,axes=plt.subplots(1,2,figsize=(12.5,5.5),layout='constrained')
        for ax in axes:
            ax.set_xscale('log',base=2);ax.set_xticks(counts,[f'{n:,}' for n in counts])
            ax.set_xlabel('ES donor pairs per query')
            ax.grid(axis='y',alpha=.18);ax.tick_params(axis='x',labelsize=9)
        axes[0].plot(counts,errors,'o-',color='#b54c35',label='Seasonal CI minus annual CI: projected 3 SE')
        axes[0].plot(counts,limits,'--',color='#303b47',label='Precision limit (pilot reference)')
        axes[0].set(title='Numerical precision gate: not passed',ylabel='Projected aggregate 3 SE (metres)')
        axes[0].text(.98,.62,f'65,536 pairs: {errors[-1]:.1f} m > {limits[-1]:.1f} m',
                     transform=axes[0].transAxes,ha='right',color='#93402e',fontsize=10)
        axes[0].legend(loc='upper right',fontsize=8,frameon=False)
        axes[1].plot(counts,times,'o-',color='#376f91',label='Formal runtime projection')
        axes[1].plot(counts,reserve,'s--',color='#b54c35',label='Required 2x time reserve')
        axes[1].axhline(120,color='#303b47',linestyle=':',label='120-minute phase cap')
        axes[1].set(title='Resource gate: not passed',ylabel='Projected minutes (not an actual full run)')
        axes[1].legend(loc='upper left',fontsize=8,frameon=False)
        axes[0].set_ylim(0,max(errors)*1.2)
        axes[1].set_ylim(0,max(reserve)*1.15)
        fig.suptitle('Step 4 E9 | Stopped at the pilot gate',fontsize=16,fontweight='bold')
        fig.savefig(folder/'pilot_gates.png',dpi=170)
        fig.savefig(folder/'pilot_gates.svg')
        plt.close(fig)
        display=summary[['model','energy_km','h90','area90_km2']].copy()
        display.columns=['Model','Energy Score (km)','Actual hit rate (%)','90% area (km2)']
        display['Actual hit rate (%)']*=100
        formatters={'Energy Score (km)':lambda x:f'{x:.6f}',
                    'Actual hit rate (%)':lambda x:f'{x:.3f}',
                    '90% area (km2)':lambda x:f'{x:,.2f}'}
        table=display.to_html(index=False,border=0,formatters=formatters)
        scope='128 fixed internal pilot cases, 44 distinct drifter IDs, 64 cases per training role. These are not the 33,971 outer validation cases.'
        plot64=base64.b64encode((folder/'pilot_gates.png').read_bytes()).decode()
        markdown_rows='\n'.join(f"| {r.model} | {r.energy_km:.6f} | {100*r.h90:.3f}% | {r.area90_km2:,.2f} |" for r in summary.itertuples())
        ac=summary.loc[summary.model.eq('AnnualEndpointCI')].iloc[0]
        sc=summary.loc[summary.model.eq('SeasonalEndpointCI')].iloc[0]
        interpretation=("The pilot is inconclusive about the seasonal scientific hypothesis. "
            "The seasonal pilot scores are worse, but this fixed engineering roster is not the full validation population. "
            "No scientific rejection, model selection, or seasonal stopping conclusion follows from this table.")
        checks=(f"24 semantic/regression tests passed. The review independently reconstructed the 128 neighbour selections "
            f"using full WGS84 distance scans, recomputed UTC quarter overlaps and all five gate calculations, "
            f"and verified {review['protected_file_count']} protected file hashes. "
            "The original seasonal donor vectors were not retained by the pilot; this is a deterministic reconstruction audit. "
            "Formal forecast freeze, whole-population score audit, bootstrap inference and six outer example maps were not performed.")
        explanation=("The new seasonal-minus-annual comparison involves different donor distributions. "
            "Their Monte Carlo self-distance uncertainty is much larger than the tiny CI-minus-point perturbation assessed in E8. "
            "The current pilot uses separate annual and seasonal numerical streams and includes uncertainty from both. "
            "The 3-SE projection applies each pilot season's largest observed per-case variance to the full query weights. "
            "It is a conservative planning estimate, not a measured outer error or a guaranteed mathematical upper bound. "
            "Runtime uses the pilot's 95th-percentile case time, all 33,971 cases, fixed overhead and 10% allowance; "
            "the contract additionally requires a factor-of-two reserve. A full support/storage inventory was not started after these preliminary gates failed.")
        fallback=(f"Season-to-annual fallback: 0/128 pilot queries for both seasonal arms. "
            f"Missing-error point fallback appears in {int(ac.error_fallback_queries)}/128 annual-CI cases and "
            f"{int(sc.error_fallback_queries)}/128 seasonal-CI cases. Its ID-weighted probability mass is "
            f"{100*ac.error_fallback_mass:.4f}% and {100*sc.error_fallback_mass:.4f}%, respectively. "
            "These are two different fallback definitions. Neither deletes observations or changes their vote. "
            f"All four seasons are represented; {review['cross_season_queries']} cases cross a season boundary and "
            f"{review['ties']} are exact ties. Tie behaviour passed synthetic tests. Outer fallback rates remain unmeasured.")
        region=last['region_checks']
        region_text=(f"Region stability passed at 16,384 quadrature points: maximum independent mass discrepancy "
            f"{100*max(x['max_mass_error'] for x in region.values()):.4f} percentage points "
            "(limit 0.5); weighted hit disagreement 0 percentage points (limit 0.1); "
            f"largest weighted absolute area change {100*max(x['weighted_area_change'] for x in region.values()):.4f}% "
            "(limit 0.5%). These are numerical repeatability checks, not evidence of predictive coverage.")
        report=f'''# Step 4 E9 — stopped at the pilot gate

Status: PARTIAL; formal experiment not started. Run: `{name}`.

The four approved model definitions are implemented. No fusion, new weights, endpoint translation, CI rescaling, radius adjustment or scientific-definition amendment was made. No outer endpoints or locked final-test records were read by this E9 run.

## Decision and resources

- Highest registered ES budget: 65,536 donor pairs per query.
- Projected aggregate 3-SE uncertainty: {errors[-1]:.3f} m; required threshold: {limits[-1]:.3f} m. Both seasonal comparisons fail.
- Projected formal time: {times[-1]:.2f} min; with required twofold reserve: {reserve[-1]:.2f} min; formal cap: 120 min. These are projections, not consumed runtime.
- Actual cumulative pilot/check runtime: {pilot_seconds:.2f} s of 600 s. Peak observed process RSS through review: {peak:.3f} GiB.
- Formal four-model results, acceptance tests, and formal fallback rates: unavailable.

{region_text}

![Pilot engineering gates](pilot_gates.png)

## Why this is an engineering stop

{explanation}

## Internal pilot values only

{scope} ES, hit and area average times within each ID and then average IDs. No bootstrap significance or acceptance claim is made. Numeric ES uses 65,536 pairs; CI region quadrature uses 16,384 points. The table is supplied for traceability, not as a substitute for formal results.

| Model | ES (km) | Actual hit rate | Mean 90% area (km2) |
|---|---:|---:|---:|
{markdown_rows}

{interpretation}

## Fallback and support

{fallback}

## Independent verification and limits

{checks}

The majority-season definition is seven elapsed UTC days, with ties assigned to the departure season. Season filtering precedes the 100-km/8,000-neighbour selection; all kth-distance ties remain. Every selected historical pair retains the same vote. CI unavailable records remain point components. No nonempty low-support seasonal pool was blended with annual data.

## Next decision

Stop under the approved contract. A continuation would first need a reviewed computational plan for reducing ES estimator variance and repeated work while preserving all four probability laws and the original scores. This report does not authorize or implement that change, a larger budget, extra sampling levels, or a weaker threshold.

Evidence: `../pilot/`, `../pilot_audit/`, and the matching provenance run's `pilot_gate.json`, `pilot_independent_review.json`, `semantic_tests.txt` and resource receipts. Approved contract SHA256: `{cfg['contract_sha256']}`.
'''
        paths.publish(folder/'REPORT.md',lambda f:f.write(report.encode()))
        page=f'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Step 4 E9 — Pilot review</title><style>
body{{font:16px/1.6 system-ui,sans-serif;color:#253440;background:#f4f6f7;margin:0}}main{{max-width:1080px;margin:auto;padding:40px 22px 70px}}
h1{{font-size:34px;line-height:1.2}}h2{{font-size:22px;margin-top:32px}}.label{{font-size:12px;letter-spacing:.12em;text-transform:uppercase;color:#8e3c2c;font-weight:750}}
.card{{background:white;padding:22px;border:1px solid #dce2e6;border-radius:8px;margin:20px 0}}.alert{{border-left:5px solid #b54c35;background:#fff8f5}}
.metrics{{display:grid;grid-template-columns:repeat(3,1fr);gap:18px}}.value{{font-size:27px;font-weight:650}}.small{{font-size:13px;color:#586873}}
img{{max-width:100%;height:auto}}table{{width:100%;border-collapse:collapse;font-size:14px}}th,td{{text-align:right;padding:11px;border-bottom:1px solid #dce2e6;white-space:nowrap}}th:first-child,td:first-child{{text-align:left}}.scroll{{overflow:auto}}
a{{color:#245f89}}@media(max-width:640px){{main{{padding:24px 14px}}h1{{font-size:28px}}.metrics{{grid-template-columns:1fr}}.card{{padding:16px}}}}
</style><main><div class="label">Partial · Formal experiment not started</div><h1>Step 4 E9: pilot gate review</h1>
<p>The approved four-model implementation is ready for further engineering review. The precision and resource gates did not pass; no formal validation was run.</p>
<div class="card alert"><strong>This does not decide whether seasons help.</strong><p>{interpretation}</p></div>
<div class="metrics"><div class="card"><div class="small">Projected ES contrast 3 SE</div><div class="value">{errors[-1]:.1f} m</div><div>Limit: {limits[-1]:.1f} m</div></div>
<div class="card"><div class="small">Formal runtime projection</div><div class="value">{times[-1]:.0f} min</div><div>{reserve[-1]:.0f} min with required reserve</div></div>
<div class="card"><div class="small">Actual pilot/check runtime</div><div class="value">{pilot_seconds:.0f} s</div><div>Within the 600-second pilot cap</div></div></div>
<div class="card"><img alt="Both gates fail at every tested Energy Score budget. The highest projected uncertainty is 20.3 metres versus 15.1 metres allowed; reserved runtime is 401 minutes versus 120 allowed." src="data:image/png;base64,{plot64}"><p class="small">128 fixed internal cases; both seasonal comparisons have almost identical uncertainty. Runtime and outer numerical uncertainty are projections.</p></div>
<h2>What passed</h2><p>{region_text}</p><p>{checks}</p>
<h2>Why the pilot stopped</h2><p>{explanation}</p>
<div class="card"><h2>Internal pilot values — not formal results</h2><p>{scope}</p><p class="small">Equal time weights within each ID, then equal IDs. ES: 65,536 numerical pairs; CI region: 16,384 quadrature points. No full-population or significance claim.</p><div class="scroll">{table}</div></div>
<h2>Fallback and support in the pilot</h2><p>{fallback}</p>
<h2>Scope preserved</h2><p>Seven elapsed UTC days; majority season; departure season for exact ties. Season selection before the same 100-km/8,000-neighbour rule with cutoff ties retained. Equal votes for selected historical pairs. Missing CI remains the original point. No fusion or scientific changes. Outer validation endpoints and locked final-test data remained unread.</p>
<h2>Next decision</h2><p>Execution is stopped. Any continuation first requires review of a computational plan that preserves the probability laws, scores and experimental definitions. No larger budget, extra sampling level or weaker threshold has been applied.</p>
<p><a href="REPORT.md">Full written report</a> · <a href="../pilot_audit/inner_pilot_summary.csv">Pilot values (CSV)</a> · <a href="../pilot_audit/support.csv">Support review (CSV)</a> · <a href="pilot_gates.svg">Vector figure</a></p>
<p class="small">Source run: {html.escape(name)}<br>Contract SHA256: {cfg['contract_sha256']}<br>Formal metrics, intervals, fallback rates and outer example maps remain unavailable.</p></main></html>'''
        paths.publish(folder/'review.html',lambda f:f.write(page.encode()))
        inputs.verify(approval)
        save_json(paths,run['provenance']/'partial_delivery_v3.json',dict(status='STOPPED_AT_PILOT_GATE',
            formal_completed=False,review_passed=True,outer_targets_read=guard.outcomes_read,
            presentation_revision='Corrected plot axes and label placement; pilot data and models unchanged.',
            final_test_access=False,report_source_sha256=file_sha256(__file__),
            output_sha256={str(p.relative_to(inputs.ROOT)):file_sha256(p) for p in folder.iterdir()}))
        completed=True
        print(folder/'review.html')
    finally:budget.finish(paths,'pilot_report_v3',completed,guard)


if __name__=='__main__':main(sys.argv[1])
