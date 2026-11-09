"""Resume the completed E9 inventory after the explicit storage-margin waiver."""
import json
import sys
import time
import traceback
import numpy as np
import pandas as pd
from data3001.paths import project_paths, file_sha256
from data3001.modelling.common.runtime import save_json, save_frame
from data3001.modelling.baselines import seasonal_exact_position_s4_e9_formal_io as fio
from data3001.modelling.baselines import seasonal_exact_position_s4_e9_inputs as inputs
from data3001.modelling.baselines import seasonal_exact_position_s4_e9_esopt as opt
from data3001.modelling.baselines.position_error_s4_e8_geometry import Geography
from data3001.modelling.baselines.position_error_s4_e8_audit import mass_in_frozen


def approve(name):
    paths=project_paths();run=dict(results=fio.ROOT/'results/runs'/name,provenance=fio.ROOT/'provenance/runs'/name)
    old=json.loads((run['provenance']/'approval.json').read_text())
    fio.verify({**old['protected_files'],**old['new_source_sha256']})
    checkpoint=json.loads((run['provenance']/'storage_gate_review.json').read_text())
    assert checkpoint['complete_support_inventory'] and not checkpoint['outer_targets_read']
    source=fio.ROOT/'src/data3001/modelling/baselines/seasonal_exact_position_s4_e9_formal_resume.py'
    paths.publish(run['provenance']/'sources'/source.name,lambda f:f.write(source.read_bytes()))
    receipt=dict(user_reply='批准继续，保留 5 GiB 硬上限',storage_precheck_2_5_gib_waived=True,
        hard_storage_gib=5,scientific_definitions_unchanged=True,prior_work_charged_to_existing_budget=True,
        resume_source_sha256=fio.hashes([source]),reused_inventory_sha256=fio.hashes([p for p in run['results'].rglob('*') if p.is_file()]),
        action='Reuse completed donor inventory and continue the outstanding preflight, forecasts, scoring and audit; no inventory rerun.')
    save_json(paths,run['provenance']/'storage_waiver_approval.json',receipt)
    print('Explicit storage waiver recorded; complete inventory preserved.',flush=True)


def resume(paths,run,cfg,approval,guard,budget):
    waiver=json.loads((run['provenance']/'storage_waiver_approval.json').read_text())
    assert waiver['storage_precheck_2_5_gib_waived'] and waiver['hard_storage_gib']==5
    fio.verify(waiver['resume_source_sha256']);fio.verify(waiver['reused_inventory_sha256'])
    preliminary=json.loads((run['provenance']/'support_inventory.json').read_text())
    assert preliminary['projected_storage_bytes']<=5*2**30
    assert preliminary['projected_peak_rss_bytes']<=4*2**30
    train,ledger=inputs.load(cfg);fit,query,_=inputs.role(cfg,'C_outer',train,ledger)
    roster=inputs.read(run['results']/'roster.parquet')
    pd.testing.assert_frame_equal(roster[fio.KEY],query.sort_values(fio.KEY).reset_index(drop=True)[fio.KEY])
    offsets=inputs.read(run['results']/'lineage_offsets.parquet');selected={}
    with (run['results']/'donor_lineage.zst').open('rb') as stream:
        for i in fio.AUDIT:
            row=offsets.iloc[i];stream.seek(int(row.offset));selected[i]=fio.decode_selection(stream.read(int(row.length)))
    geo=Geography(paths);cache=opt.cache(fit,geo)
    region_count=preliminary['region_count'];mass_checks=[];levels=[];started=time.monotonic()
    while True:
        audit_timings=[];level_checks=[]
        for j,i in enumerate(fio.AUDIT):
            budget.check();q=roster.iloc[i];a,s,fallback=selected[i];audit_seconds=0.
            for pool,choice in [('Annual',a),('Seasonal',s)]:
                if pool=='Seasonal' and fallback:continue
                p=cache.take(choice[0]);f,c=opt.regions(p,fio.key(q,pool,0),region_count)
                cal=opt.calibration(p,fio.key(q,pool));timer=time.monotonic()
                f1,c1=opt.regions(p,fio.key(q,pool,1),region_count)
                # Outcome-free timing placeholder; these synthetic scores are discarded.
                opt.score(p,f1,[q.lon,q.lat],fio.key(q,pool,1),16384,cal)
                for ci in [False,True]:
                    integrated=mass_in_frozen(*c1[ci],f[ci]['region'])
                    area=f[ci]['region']['area_km2'];area1=f1[ci]['region']['area_km2']
                    level_checks.append(dict(query_position=int(i),pool=pool,ci=ci,region_count=region_count,
                        mass_discrepancy=abs(integrated-f[ci]['region']['attained_mass']),
                        relative_area_difference=abs(area1-area)/area if area else 0.))
                audit_seconds+=time.monotonic()-timer
            audit_timings.append(audit_seconds)
            if (j+1)%32==0:fio.progress('outcome-blind final checks',j+1,128,started)
        maximum=max(r['mass_discrepancy'] for r in level_checks)
        levels.append(dict(region_count=region_count,max_mass_discrepancy=maximum));mass_checks.extend(level_checks)
        if maximum<=.005:break
        remaining=[n for n in cfg['region_ladder'] if n>region_count]
        if not remaining:raise ValueError('Registered region ladder exhausted without required precision')
        region_count=remaining[0]
    audit_projection=float(np.percentile(audit_timings,95))*len(roster)*1.1+120
    save_frame(paths,run['results']/'outer_geometry_checks_v2.csv',pd.DataFrame(mass_checks))
    save_json(paths,run['provenance']/'preflight.json',dict(**preliminary,chosen_region_count=region_count,
        energy_count=16384,region_precision_levels=levels,audit_projected_seconds=audit_projection,
        outcome_blind_resume_seconds=time.monotonic()-started,time_margin_waived=True,
        storage_precheck_passed=False,storage_precheck_explicitly_waived=True,hard_storage_budget_passed=True,memory_precheck_passed=True))
    assert audit_projection+cfg['prior_audit_seconds']<=1800,'Projected audit exceeds its actual budget'
    assert not guard.outcomes_read and not guard.denied
    print('Preflight complete; audit estimate',round(audit_projection,2),'seconds; region points',region_count,flush=True)


def main():
    action,name=sys.argv[1:3]
    if action=='approve':approve(name);return
    if action!='resume':raise ValueError('Unknown action')
    args=fio.context(name,'formal');paths,run,cfg,approval,guard,budget=args;completed=False
    try:
        resume(*args);budget.check(storage=True);completed=True
    except BaseException as error:
        save_json(paths,run['provenance']/'inventory_resume_v2_failure.json',dict(type=type(error).__name__,message=str(error),traceback=traceback.format_exc()))
        raise
    finally:budget.finish('inventory_resume_v2',completed)


if __name__=='__main__':main()
