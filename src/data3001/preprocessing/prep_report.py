"""English readiness artifacts and development-only scientific figures."""
from data3001.paths import legacy_path, asset_path, project_paths, ensure_output_path, frozen_action
import json,csv
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon as PlotPolygon
from data3001.preprocessing.prep_io import BASE, OUT, sha, save_json, now
from data3001.preprocessing.prep_geometry import region_R

@frozen_action
def figures():
    r=pd.read_csv(legacy_path('preparation', 'support/R_seasonal_IDs.csv'));seasons=['DJF','MAM','JJA','SON']
    fig,axes=plt.subplots(1,2,figsize=(12,4.5),layout='constrained')
    for ax,tgt in zip(axes,['endpoint','stopped']):
        for split,color,off in [('train','#2878a1',-.18),('validation','#de7b37',.18)]:
            z=r[(r.scenario=='drogued')&(r.horizon_days==365)&(r.target==tgt)&(r.split==split)].set_index('season')
            y=[int(z.loc[i,'eligible_IDs']) if i in z.index else 0 for i in range(4)]
            bars=ax.bar(np.arange(4)+off,y,.34,label=split,color=color)
            ax.bar_label(bars,padding=3,fontsize=9)
        ax.set_xticks(range(4),seasons);ax.set_ylabel('Distinct eligible drifter IDs');ax.set_title(f'365-day fixed drogued: {tgt}');ax.set_ylim(0,15);ax.grid(axis='y',alpha=.2);ax.set_axisbelow(True);ax.legend(frameon=False)
    fig.suptitle('R-development support: hourly windows are not independent trajectories',fontsize=12)
    fig.savefig(legacy_path('preparation', 'figures/R_365_seasonal_ID_support.png'),dpi=180);plt.close(fig)
    x=pd.read_parquet(legacy_path('preparation', 'support/cell_support.parquet'));fig,axes=plt.subplots(1,2,figsize=(12,5),layout='constrained')
    for ax,res in zip(axes,[1,.5]):
        z=x[(x.population=='R')&(x.resolution==res)&(x.scenario=='drogued')&(x.horizon_days==365)&(x.target=='stopped')].groupby('cell')[['eligible','candidates']].sum()
        xs=np.arange(-82,-72,res);ys=np.arange(29,37,res);a=np.full((len(ys),len(xs)),np.nan);nx=int(360/res)
        for cell,v in z.iterrows():
            lon=(int(cell)%nx)*res-180;lat=(int(cell)//nx)*res-90;i=int(round((lon+82)/res));j=int(round((lat-29)/res))
            if 0<=i<len(xs) and 0<=j<len(ys):a[j,i]=v.eligible/v.candidates
        im=ax.imshow(a,origin='lower',extent=[-82,-72,29,37],vmin=0,vmax=.3,cmap='viridis',interpolation='nearest',aspect='auto')
        ax.add_patch(PlotPolygon(np.asarray(region_R().exterior.coords),fill=False,edgecolor='red',linewidth=1.2));ax.set_title(f'{res:g} degree grid, 365-day stopped availability');ax.set_xlabel('Longitude');ax.set_ylabel('Latitude');fig.colorbar(im,ax=ax,label='Eligible / candidate hourly origins')
    fig.suptitle('Development only; no grid promotion or predictive accuracy claim',fontsize=12)
    fig.savefig(legacy_path('preparation', 'figures/R_365_grid_availability.png'),dpi=180);plt.close(fig)
    candidates=json.loads((legacy_path('preparation', 'audit/domain_selection.json')).read_text())['candidates'];cells=pd.read_csv(legacy_path('audit/development_observed_path_cells.csv'))
    fig,ax=plt.subplots(figsize=(10,5.5),layout='constrained');ax.scatter(cells.cell_west_longitude+.5,cells.cell_south_latitude+.5,s=4,alpha=.4,label='Observed development R-window cells')
    for z,col in zip(candidates,['#c53a2b','#379343','#967ac5']):
        x0,y0,x1,y1=z['bounds'];ax.plot([x0,x1,x1,x0,x0],[y0,y0,y1,y1,y0],color=col,label=f"D candidate {z['candidate']} ({z['grid_cells_1deg']} interior cells)")
    ax.add_patch(PlotPolygon(np.asarray(region_R().exterior.coords),facecolor='#f1a22d',edgecolor='black',linewidth=.8,label='Frozen R'));ax.set_xlim(-88,0);ax.set_ylim(13,62);ax.set_xlabel('Longitude');ax.set_ylabel('Latitude');ax.set_title('Nested domains: observed intermediate paths through 365 days');ax.legend(fontsize=8,loc='upper left');ax.grid(alpha=.2)
    fig.savefig(legacy_path('preparation', 'figures/development_domain_candidates.png'),dpi=180);plt.close(fig)

@frozen_action
def report():
    v=json.loads((legacy_path('preparation', 'audit/preparation_verification.json')).read_text());assert v['status']=='PASS_WITH_REPORTED_SUPPORT_LIMITATIONS'
    co=json.loads((legacy_path('preparation', 'audit/cohort_reconciliation.json')).read_text());domain=json.loads((legacy_path('preparation', 'audit/domain_selection.json')).read_text());peer=json.loads((legacy_path('preparation', 'audit/speed_event_diagnostics.json')).read_text())
    r=pd.read_csv(legacy_path('preparation', 'support/R_seasonal_IDs.csv'));annual=pd.read_csv(legacy_path('preparation', 'support/R_annual_counts_and_IDs.csv'));primary=annual[(annual.scenario=='drogued')&(annual.horizon_days==365)]
    seasonal=[]
    for i,name in enumerate(['DJF','MAM','JJA','SON']):
        values=[]
        for split in ['train','validation']:
            for target in ['endpoint','stopped']:
                z=r[(r.split==split)&(r.season==i)&(r.scenario=='drogued')&(r.horizon_days==365)&(r.target==target)].iloc[0];values.append(f"{int(z.eligible):,} / {int(z.eligible_IDs)}")
        seasonal.append('| '+name+' | '+' | '.join(values)+' |')
    text=f'''# Data preparation readiness report

Status: **prepared with explicit observational-support limitations**. Integrity, source preservation, field-specific cleaning, distinct target eligibility and count reconciliation passed. Predictive modelling and predictive acceptance have not been performed.

## Authority and source

The authoritative Excel remains unchanged: SHA-256 `6cfa91471a1399a9c3a1a8edfeb2e18cea17e0f4031ef0f8ca604ca4565a2446`. The authorized stage prompt is preserved in `docs/AUTHORIZED_STAGE_PROMPT.txt`; all 31 aspects are mapped in `docs/contract_crosswalk.csv`. Neither this report nor the rule register creates a new research contract.

Official NOAA hourly v2.01.1, DOI [10.25921/x46c-3620](https://doi.org/10.25921/x46c-3620), is pinned through metadata, object receipts and checksums. A `latest` URL is not an immutable release guarantee. Fresh verification checked {v['source_objects_reverified']:,} downloaded source objects and all {v['source_subset_fields_reverified']} source field value hashes. Original values of all 20 observation fields were also compared against every cleaned row. The 40 source trajectory metadata fields and two provenance fields remain in the read-only raw subset.

The measured full source spans 1987-10-02 13:00 UTC to 2022-10-31 00:00 UTC; public release prose reports 1987-10-03 13:00 to 2022-10-31 23:00. Stored attributes and the measured source timestamps are preserved separately. Maturity uses the measured global cutoff. Downloaded cohort coverage is {co['downloaded_start']} to {co['downloaded_cutoff']}.

The [NOAA hourly documentation](https://www.aoml.noaa.gov/phod/gdp/hourly_data.php) describes processed estimates following QC. These are not independent hourly instrument fixes. [Position/velocity methods](https://doi.org/10.1002/2016JC011716), [SST methods](https://www.nature.com/articles/s41597-022-01670-2), and [GSHHG documentation](https://www.soest.hawaii.edu/pwessel/gshhg/) are saved with retrieval receipts. Current ERDDAP documentation supplied conventions, never substitute trajectory records.

## Cohort and preservation

- {co['IDs']:,} IDs and {co['hourly_records']:,} source hourly estimates retained, with complete available trajectories and all original observation values.
- 463 R-visiting IDs: 323 train, 73 validation, 67 locked test; R-track records total {co['R_hourly_records']:,}.
- Actual R origins: train 249,125, validation 68,983; locked-test products stay under `restricted_test/`.
- {co['non_hourly_intervals']:,} non-hourly intervals and {co['missing_hours']:,} absent expected hours remain explicit. They are not physical exits.
- {v['counts']['missing_SST_position_retained']:,} missing-SST records keep their usable positions. {v['counts']['negative_position_uncertainty']:,} rows with negative position uncertainty are retained and isolated from uncertainty use.

The frozen whole-ID assignment uses full SHA-256 of ASCII `20261004:<canonical GDP ID>` with exact integer thresholds. The auxiliary Markdown uses a different `DATA3001-v1|20261004|<ID>` construction and the first 13 hex digits. That discrepancy is documented; the existing global manifest was preserved and all 19,396 assignments verified. No six-hour records or ID whitelist entered this hourly preparation.

## Domain, states and targets

Frozen R is the corridor/window intersection polygon, not its rectangle. D is {domain['selected_bounds']}, selected from three documented development candidates. All {domain['candidates'][0]['R_365_intermediate_positions']:,} observed intermediate R-development positions within the union of 365-day windows are covered. Candidate 0 uses the smallest covered interior grid. Downstream adjacent exits/returns were also audited. The selected product is explicitly a **finite stopped-domain product**; no model boundary-map stability or unrestricted one-year transport has been established.

The 1-degree grid remains primary; aligned 0.5-degree diagnostics use identical eligibility. GSHHG 2.3.7 high-resolution L1 provides ocean/land mapping, with high/intermediate disagreement isolated. Wet cell areas, disconnected component counts and checksums are saved. Actual points decide R/D membership. Inclusive north/east D boundaries require adjacent half-open grid cells; the state inventory includes them, including boundary-only intersections. No point was snapped or recoded as outside because of a coastline mismatch.

Endpoint occupancy and stopped-first-exit ledgers are separate. Endpoint pairs can survive a position gap if recorded metadata independently confirms regime constancy. Stopped labels require every expected usable hour and the scenario through the first eligible observed exit or the nominal horizon. An outside observation after a gap cannot shorten that requirement. A qualified exit absorbs later death, loss, return or cutoff. Unknown and recorded-switch/mismatched-scenario predicates remain separate secondary evidence. Missingness never becomes physical outside or an observed unresolved-support destination.

Real training example: ID 7706157, origin 1990-09-06 05:00 UTC, eligible observed exit 1990-09-07 02:00 UTC, track termination 1991-01-09 19:00 UTC. It supplies a 365-day stopped-outside label while its 365-day endpoint is unavailable. The contiguous path to exit was independently checked. This D-source example is not presented as an R-origin case.

## 365-day evidence and limitations

Values below are **eligible hourly pairs / distinct eligible IDs**. Distinct IDs overlap across seasons and cells; they must not be summed as independent trajectories.

| UTC departure season | Train endpoint | Train stopped | Validation endpoint | Validation stopped |
|---|---:|---:|---:|---:|
{chr(10).join(seasonal)}

DJF has no fixed-drogued 365-day validation endpoints or stopped labels. MAM has no such stopped labels. Other seasonal supports depend on few IDs and overlapping windows. These data cannot certify seasonal one-year predictive accuracy. Whole-ID grouped five-fold development assignments and refitting instructions are prepared; the locked test split is unchanged. Annual pooling, uncertainty intervals, scoring and any decision to change the research definition belong to modelling/architecture.

![Distinct seasonal ID support]({OUT}/figures/R_365_seasonal_ID_support.png)

![Aligned grid support diagnostics]({OUT}/figures/R_365_grid_availability.png)

The main distribution remains conditional on usable observed constant-regime pairs. Available records do not identify the destinations of every missing or terminated trajectory. No universal adequate-count threshold or effective sample size was invented.

## Field and diagnostic results

Temperature components, official velocity, interval-net velocity, each uncertainty, geometry and regime have separate flags. Absolute SST converts Kelvin to Celsius; anomalies remain unchanged. Total/non-diurnal SST uses flags 4/5 and the declared range; diurnal use requires flag 5. Source ID17503 has a negative legitimate anomaly but source flag2, so it remains preserved and is unavailable to that temperature extension. Missing or rejected SST never removes an otherwise usable position.

Zero loss dates are documented as uncertain from the beginning. Generic NaN conversion origin is not proven universally; affected fixed-regime uses stay isolated and pooled records remain. Negative uncertainty codes and upstream `gap` interpretation remain documented questions. No absolute-value repair or uncertainty-to-zero replacement occurred.

Development speed review flagged {peer['flagged_rows']:,} rows in {peer['representative_events']:,} contiguous review events; {sum(e['reference_IDs']>0 for e in peer['events']):,} events had comparable contemporaneous peers. Training-only thresholds prioritize review, never deletion. Other-ID selection, actual distance/time, known regime, recorded depth/hardware, bounded wet connectivity, vector/circular statistics and source context are preserved. No peer absence/disagreement generated an observation or removed a position. Global screening statistics are retrospective diagnostics and cannot be reused as held-out-fold fitted features.

## Verification and remaining work

The consequential suite includes native invalid coordinates, duplicate provenance, zero velocity, missing uncertainty, tolerance ties/late selected endpoints, independent regime confirmation, early exit/termination, gap-before-exit, inclusive grid boundaries, simultaneous secondary predicates, and randomized comparison with an independent chronological scanner. Five named real source cases and integer-day generation through 365 were verified. Every candidate reconciles to eligible or exactly one primary exclusion; secondary predicates remain nonexclusive.

Routine implementation corrections were versioned: exact tiled water-area computation; inclusive boundary cell inventory; independent secondary predicates; and nominal-window retention after an unqualified outside observation. Historical code hashes are recoverable. Raw acquisition objects and receipts remain unchanged. Corrected candidate and eligible totals are compared with pre-correction totals, and frozen rules are reapplied to separated test partitions.

A checkpoint ownership audit also corrected an overbroad filename prefix: ID7647 must not claim ID107647's ledger files. Only checkpoint metadata was repaired; all original checkpoint versions and actual data-generation signatures are retained. No Parquet source or scientific label values changed in that repair. All corrected owned output hashes passed the final audit.

Optional reconstruction was deferred; no reconstructed primary endpoint, exit, independent drifter or transition was created. No transport model, forecast, predictive score, bootstrap interval or regional transfer claim has been produced. Preparation is usable for the next modelling stage subject to the reported support and isolated-semantics limits.

## Package navigation

- `metadata/`, `docs/QC_RULE_REGISTER.csv`, `config/`: source conventions, decisions, unresolved uses and frozen implementation.
- `cleaned/`: all development hourly source fields plus annotations; source linkage through `source_obs`, original within-trajectory index and frozen manifest.
- `origins/`, `events/`: all D-source origins, R membership and compact retrospective bounds.
- `ledgers/endpoint/`, `ledgers/stopped/`: exact R anchor ledgers, distinct targets and all scenarios.
- `support/`: development cell/season support, attrition, destinations, concentration, lag/remainder support, endpoint sensitivities and vector descriptions.
- `geometry/`, `figures/`: R/D/grid/water states and development-only support figures.
- `restricted_test/`: frozen test application; keep separate from tuning and illustrations.
- `audit/preparation_verification.json`: final source preservation, frozen settings, reference isolation and candidate reconciliation.

See `docs/REPRODUCIBILITY.md` and `docs/MODELLING_HANDOVER.md` before modelling.
'''
    (legacy_path('preparation', 'READINESS_REPORT.md')).write_text(text)
    cross=pd.read_csv(legacy_path('preparation', 'docs/contract_crosswalk.csv')).fillna('')
    deferred={4,7,15,17,18,20,24,25,27,28,29,30}
    for i,row in cross.iterrows():
        n=int(row.aspect[:2]);cross.loc[i,'status']='deferred to modelling' if n in deferred else 'implemented'
        cross.loc[i,'verification']='audit/preparation_verification.json; '+row.verification
        if n in deferred:cross.loc[i,'deferred_detail']='Preparation inputs implemented; model fitting/scoring/propagation/transfer part deferred. '+row.deferred_detail
        elif n==8:cross.loc[i,'deferred_detail']='Source zero semantics resolved; NaN-loss fixed uses isolated under U01; pooled retained.'
        elif n==23:cross.loc[i,'deferred_detail']='Field-specific rules implemented; U01/U02/U03 isolate their affected uses.'
    cross.to_csv(legacy_path('preparation', 'docs/contract_crosswalk.csv'),index=False)
    save_json(legacy_path('preparation', 'metadata/readiness_status.json'),{'utc':now(),'stage':'prepared with reported limitations','integrity':'passed','eligibility_implementation':'passed','observational_support':'limited, especially seasonal365 fixed drogued','predictive_accuracy':'not evaluated','research_contract_changed':False,'test_used_for_tuning':False})

if __name__=='__main__':figures();report()
