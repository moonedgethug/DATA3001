import json,stat,time
import numpy as np
import pandas as pd
from runtime import *
from diagnostic import KEY

def main():
    s,roster=start()
    try:
      with stage('preflight') as check:
        approval=json.loads((OUT/'approval.json').read_text());assert approval['approved']
        assert sha(OUT/'contract_snapshot.md')==sha(ROOT/'docs/coastal_grounding_diagnostic_contract.md')
        for name in ['manifest','verification']:
            digest=(FREEZE/(name+'.sha256')).read_text().split()[0]
            s.verified(FREEZE/(name+'.json'),digest)
        freeze=s.json(FREEZE/'manifest.json')
        t=time.monotonic()
        for i,r in enumerate(freeze['files']):
            p=s.verified(ROOT/r['path'],r['sha256'])
            assert p.stat().st_size==r['bytes']
            assert stat.S_IMODE(p.stat().st_mode)==int(r['expected_mode'],8)
            if i%2500==0:check();print('Frozen checked',i,flush=True)
        data=s.json(ROOT/'configs/dataset_manifest.json')
        qual=s.json(ROOT/'configs/qualification_manifest.json')
        assets=s.json(ROOT/'configs/assets.json')
        assert data['version']=='per-drifter-cleaned-20261017-v7'
        assert qual['dataset_manifest_sha256']==sha(ROOT/'configs/dataset_manifest.json')
        for n in ['release_R','transport_D','land_mask_high']:
            a=assets['assets'][n];s.verified(ROOT/a['path'],a['sha256'])
        for p in [E7/'training_coordinates.parquet',E7/'query_coordinates.parquet',E7/'outer_targets.parquet',E7/'roles.parquet']:
            s.verified(p)
        train=s.frame(E7/'training_coordinates.parquet');valid=s.frame(E7/'query_coordinates.parquet')
        assert (len(train),train.id.nunique(),len(valid),valid.id.nunique())==(265393,338,33971,45)
        assert set(train.id)==set(roster[roster.cohort=='train'].id)
        assert set(valid.id)==set(roster[roster.cohort=='validation'].id)
        assert not set(train.id)&set(valid.id)
        for f in [train,valid]:assert not f.duplicated(KEY).any() and f.horizon_days.eq(7).all()
        assert not train.outside.any()
        summary=s.frame(MDN/'summary.csv')
        scores=s.frame(MDN/'outer_complete.parquet',columns=KEY+['model','energy_km','h90','area90_km2','land_mass','outside_D_mass'])
        five=['MDN22','MDN1','LocalGaussian','ExactPoint','EndpointCI']
        expected=valid[KEY].sort_values(KEY).reset_index(drop=True)
        for m in five:
            f=scores[scores.model==m]
            pd.testing.assert_frame_equal(f[KEY].sort_values(KEY).reset_index(drop=True),expected)
            for metric in ['energy_km','h90','area90_km2','land_mass','outside_D_mass']:
                actual=f.groupby('id')[metric].mean().mean();ref=summary.set_index('model').loc[m,metric]
                assert np.isclose(actual,ref,atol=1e-8,rtol=1e-10),(m,metric,actual,ref)
        receipt=s.json(ROOT/'provenance/runs/markov_input_20261025T095949_830292Z/outputs.json')
        for row in roster.itertuples(index=False):
            sid=str(row.id)
            for manifest in [data,qual]:
                r=manifest['records'][sid];assert r['pool']=='train';s.verified(ROOT/r['path'],r['sha256'])
            p=LABELS/(sid+'.parquet');s.verified(p,receipt['output_sha256'][str(p.relative_to(ROOT))])
            check()
        s.frame(AUDIT/'boundary_ledger.csv');s.frame(AUDIT/'boundary_assessment.csv')
        for p in sorted((AUDIT/'sources').glob('*')):
            if p.is_file():s.verified(p)
        json_write(LOG/'preflight.json',{'passed':True,'frozen_files':len(freeze['files']),
            'protected_bytes':sum(r['bytes'] for r in freeze['files']), 'train_ids':338,'validation_ids':45,
            'train_pairs':265393,'validation_pairs':33971,'five_models_global_summary_reproduced':True,
            'elapsed_seconds':time.monotonic()-t,'final_test_access':False})
        print('PREFLIGHT PASSED',flush=True)
    finally:s.save()

if __name__=='__main__':main()
