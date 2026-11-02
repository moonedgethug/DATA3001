"""Post-run handoff checks for a sealed S3 benchmark and independent replay."""
import argparse
from datetime import datetime, timezone
from html.parser import HTMLParser
import json
from pathlib import Path
import numpy as np
import pandas as pd
from data3001.paths import project_paths, file_sha256
from data3001.modelling.common.runtime import verified_run


class Links(HTMLParser):
    def __init__(self):
        super().__init__(); self.targets=[]

    def handle_starttag(self, tag, attrs):
        for name,value in attrs:
            if (tag,name) in [('a','href'),('img','src')]: self.targets.append(value)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--primary',required=True);parser.add_argument('--replay',required=True)
    parser.add_argument('--visually-reviewed-run',required=True)
    args=parser.parse_args();paths=project_paths()
    for name in [args.primary,args.replay,args.visually_reviewed_run]:
        assert Path(name).name==name and name.startswith('spatial_borrowing_s3_e1_')
    root=paths.root/'results/runs'/args.primary;replay=paths.root/'results/runs'/args.replay
    receipts=[]
    for name in [args.primary,args.replay]:
        verified_run(paths,name)
        p=paths.root/'provenance/runs'/name
        v=json.loads((p/'verification.json').read_text());receipts.append(v)
        assert v['passed'] and v['final_test_trajectories_read']==0 and not v['denied_operations']
        assert v['elapsed_seconds']<1800 and v['max_rss_bytes']<8*1024**3 and v['artifact_bytes']<5*1024**3
        code=json.loads((p/'source_sha256.json').read_text())
        assert any(k.endswith('/run_spatial_borrowing_s3_e1.py') for k in code)
        for rel,digest in code.items():
            assert file_sha256(paths.root/rel)==digest
            assert file_sha256(p/'code_snapshot'/rel)==digest
    assert receipts[1]['replay']['passed'] and receipts[1]['replay']['reference_run']==args.primary
    for name in ['source_sha256.json','input_inventory.json','environment.json']:
        a=paths.root/'provenance/runs'/args.primary/name;b=paths.root/'provenance/runs'/args.replay/name
        assert json.loads(a.read_text())==json.loads(b.read_text())

    scores=pd.read_parquet(root/'heldout_scores.parquet')
    common=['id','horizon_days','origin_cell_1','destination_cell_1']
    assert scores.pivot(index=common,columns='model',values='primary_group_weight').nunique(axis=1).eq(1).all()
    weight_error=0.
    for (h,m),g in scores.groupby(['horizon_days','model']):
        supported=g[g.status.eq('evaluable')]
        n=supported.groupby(['id','origin_cell_1']).pair_count.transform('sum')
        per_cell=supported.groupby('origin_cell_1').id.nunique()
        expected=supported.pair_count/n/supported.origin_cell_1.map(per_cell)/len(per_cell)
        weight_error=max(weight_error,float(np.max(np.abs(expected-supported.primary_group_weight))))
        assert abs(supported.primary_group_weight.sum()-1)<1e-12
    assert weight_error<1e-12

    summary=pd.read_csv(root/'summary.csv').set_index(['horizon_days','model'])
    diffs=pd.read_csv(root/'paired_differences.csv')
    for r in diffs.itertuples(index=False):
        expected=summary.loc[(r.horizon_days,r.model),r.metric]-summary.loc[(r.horizon_days,r.reference),r.metric]
        assert abs(expected-r.difference)<1e-12
    decisions=pd.read_csv(root/'decisions.csv')
    for r in decisions.itertuples(index=False):
        d=diffs[(diffs.horizon_days==r.horizon_days)&(diffs.model==r.model)&(diffs.reference==r.reference)].set_index('metric')
        brier=d.loc['brier','difference']<-1e-12
        supported=brier and d.loc['brier','adjusted_directional_bound']<-1e-12
        quality=supported and d.loc['region90_hit','adjusted_directional_bound']>=-1e-12 and d.loc['region90_cells','adjusted_directional_bound']<=1e-12
        assert bool(r.point_Brier_gain)==bool(brier)
        assert bool(r.conditional_Brier_support)==bool(supported)
        assert bool(r.conditional_quality_preserving)==bool(quality)
        assert bool(r.conditional_smaller_region)==bool(quality and d.loc['region90_cells','adjusted_directional_bound']<-1e-12)

    intervals=pd.read_csv(root/'bootstrap_intervals.csv');draws=pd.read_csv(root/'bootstrap_draws.csv')
    for r in intervals.itertuples(index=False):
        values=draws[(draws.horizon_days==r.horizon_days)&(draws.model==r.model)][r.metric]
        assert len(values)==5000 and r.undefined_replicates==0
        np.testing.assert_allclose(np.quantile(values,[.025,.975]),[r.lower_95,r.upper_95],rtol=0,atol=1e-12)
    for field in ['support_stratum','boundary_stratum']:
        strata=pd.read_csv(root/f'{field}.csv')
        for key,g in strata.groupby(['horizon_days','model']):
            assert abs(g.primary_weight_mass.sum()-1)<1e-12
            for metric in ['brier','region90_cells','region90_hit']:
                assert abs(np.dot(g.primary_weight_mass,g[metric])-summary.loc[key,metric])<1e-12

    visual=paths.root/'results/runs'/args.visually_reviewed_run
    pngs=sorted(root.glob('*.png'));assert len(pngs)==11
    for p in pngs:
        assert file_sha256(p)==file_sha256(visual/p.name)==file_sha256(replay/p.name)
    links=Links();links.feed((root/'review.html').read_text())
    assert all((root/target).is_file() for target in links.targets)
    roster=json.loads((root/'illustration_roster.json').read_text())['roster']
    frozen=json.loads((paths.root/'provenance/reviews/spatial_borrowing_s3_e1_illustration_roster.json').read_text())
    assert roster==frozen['roster']

    support=pd.read_csv(root/'row_support.csv')
    data=scores[scores.model.eq('LocalDisplacement')].merge(support[support.model.eq('LocalDisplacement')],
        on=['role','outer_fold','model','horizon_days','origin_cell_1'],validate='many_to_one')
    fields=['fallback_fraction','effective_borrowing_weight','neighbour_ids']+[c for c in support if c.startswith('reason_')]
    safeguards={str(h):{f:float(np.dot(g.primary_group_weight,g[f])) for f in fields} for h,g in data.groupby('horizon_days')}
    result=dict(passed=True,primary=args.primary,replay=args.replay,checked_utc=datetime.now(timezone.utc).isoformat(),
        audit_script_sha256=file_sha256(Path(__file__)),numerical_tables_replayed=len(receipts[1]['replay']['numerical_tables_compared']),
        complete_source_snapshots_match_live_code=True,common_case_weights_independently_verified=True,maximum_weight_error=weight_error,
        decision_rules_and_intervals_verified=True,strata_recompose_primary_scores=True,
        reviewed_pngs=[p.name for p in pngs],rendered_images_match_visually_reviewed_and_replayed_files=True,
        reviewed_image_source=args.visually_reviewed_run,html_links_valid=True,pre_result_roster_verified=True,
        heldout_weighted_transfer_safeguards=safeguards,final_test_trajectories_read=0,
        scientific_retention='pending user review; no automatic stage closure')
    output=paths.root/'provenance/reviews'/f'{args.primary}_audit.json'
    with output.open('x') as stream:json.dump(result,stream,indent=2,sort_keys=True)
    print(json.dumps(dict(receipt=str(output),passed=True,numerical_tables=result['numerical_tables_replayed'])))


if __name__=='__main__':main()
