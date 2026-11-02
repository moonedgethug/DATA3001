"""Post-run audit of persisted E1 artifacts; no fitting or raw trajectory reads."""
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
PRIMARY = 'adaptive_b2_b1_20261030T044950_931787Z'
REPLAY = 'adaptive_b2_b1_20261030T045122_466415Z'
S1 = 'empirical_b2_20261029T121555_976173Z'


def verify_receipt(run_id):
    receipt = json.loads((ROOT/'provenance/runs'/run_id/'outputs.json').read_text())
    assert receipt['completed'] and receipt['final_test_access'] is False
    for name, expected in receipt['output_sha256'].items():
        assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest() == expected, name
    return len(receipt['output_sha256'])


def main():
    sealed = {name: verify_receipt(name) for name in (PRIMARY, REPLAY, S1)}
    root = ROOT/'results/runs'/PRIMARY
    counts = pd.read_parquet(root/'counts_by_id.parquet')
    roles = json.loads((root/'fit_roles.json').read_text())
    parameters = pd.read_csv(root/'selected_parameters.csv').set_index(['role','horizon_days','model']).parameter_a
    states = pd.read_csv(root/'destination_index.csv').destination_cell_1.to_numpy()
    index = {int(c): i for i,c in enumerate(states)}
    errors = {'probability':0.,'brier':0.,'region_mass':0.,'summary':0.}
    reconstructed = {}
    for role, spec in roles.items():
        assert not set(spec['training_ids']) & set(spec['evaluation_ids'])
        fit = counts[counts.id.isin(spec['training_ids'])]
        grouped = fit.groupby(['horizon_days','origin_cell_1','destination_cell_1']).pair_count.sum()
        persisted = pd.read_parquet(root/'bases'/f'{role}_b2.parquet').set_index(
            ['horizon_days','origin_cell_1','destination_cell_1'])
        pd.testing.assert_series_equal(grouped,persisted.pair_count,check_names=False)
        if '_inner_' in role:
            continue
        for model in ('B2','Fixed','Adaptive'):
            stored = pd.read_parquet(root/'matrices'/f'{role}_{model}.parquet')
            expected_keys = set()
            for h in (7,30):
                rows = fit.loc[fit.horizon_days.eq(h)].groupby(['origin_cell_1','destination_cell_1']).pair_count.sum()
                n = rows.groupby(level=0).sum()
                median = float(np.median(n))
                q = np.zeros(len(states))
                dest_counts = rows.groupby(level=1).sum()
                for c, value in dest_counts.items():
                    q[index[c]] = value/dest_counts.sum()
                a = 0. if model == 'B2' else float(parameters.loc[(role,h,model)])
                for origin,total in n.items():
                    raw = np.zeros(len(states))
                    for dest,value in rows.loc[origin].items():
                        raw[index[dest]] = value
                    if model == 'B2' or a == 0:
                        p = raw/total
                    elif a == 1:
                        p = q.copy()
                    elif model == 'Fixed':
                        p = raw/total*(1-a)+a*q
                    else:
                        tau = median*a/(1-a)
                        p = (raw+tau*q)/(total+tau)
                    actual = stored[stored.horizon_days.eq(h)&stored.origin_cell_1.eq(origin)]
                    vector = np.zeros(len(states))
                    for r in actual.itertuples(index=False):
                        vector[index[r.destination_cell_1]] = r.probability
                        expected_keys.add((h,origin,r.destination_cell_1))
                    assert set(actual.destination_cell_1) == set(states[p>0])
                    errors['probability'] = max(errors['probability'],float(np.max(np.abs(vector-p))))
                    reconstructed[(role,model,h,origin)] = p
            assert len(expected_keys) == len(stored)

    scores = pd.read_parquet(root/'heldout_scores.parquet')
    for (role,model,h,origin),group in scores.groupby(['role','model','horizon_days','origin_cell_1']):
        p = reconstructed.get((role,model,h,origin))
        if p is None:
            assert group.status.eq('unsupported_origin').all() and group.brier.isna().all()
            continue
        ranked = sorted((v for v in p if v>0),reverse=True)
        mass=0.
        for threshold in ranked:
            mass += threshold
            if mass>=.9-1e-12:
                break
        included = (p>0)&(p>=threshold-1e-12)
        count = int(np.sum(included&(states>=0)))
        assert group.region90_cells.eq(count).all()
        errors['region_mass'] = max(errors['region_mass'],float(np.max(np.abs(group.region90_mass-p[included].sum()))))
        ys=np.array([index[c] for c in group.destination_cell_1])
        expected = np.square(p).sum()+1-2*p[ys]
        errors['brier'] = max(errors['brier'],float(np.max(np.abs(expected-group.brier))))
        assert np.array_equal(group.region90_hit.to_numpy(),included[ys].astype(float))

    summary = pd.read_csv(root/'summary.csv').set_index(['horizon_days','model'])
    for key,group in scores.groupby(['horizon_days','model']):
        good=group[group.status.eq('evaluable')]
        assert group.pair_count.sum()==summary.loc[key,'eligible_pairs']
        assert good.pair_count.sum()==summary.loc[key,'evaluable_pairs']
        for metric in ('brier','region90_cells','region90_hit'):
            actual=float(np.average(good[metric],weights=good.pair_count))
            errors['summary']=max(errors['summary'],abs(actual-summary.loc[key,metric]))
    assert max(errors.values())<=1e-12, errors
    replay=json.loads((ROOT/'provenance/runs'/REPLAY/'verification.json').read_text())
    assert replay['replay']['passed']
    result={'primary_run':PRIMARY,'replay_run':REPLAY,'passed':True,
            'sealed_artifacts_verified':sealed,'fit_role_count':len(roles),
            'replay_numerical_tables':len(replay['replay']['tables_compared']),
            'persisted_matrix_support_verified':True,'persisted_region_hits_verified':True,
            'maximum_absolute_errors':errors,'raw_trajectory_reads':0,
            'visual_review_completed':['candidate_comparison_7d.png','candidate_comparison_30d.png',
                                       'weights_by_support.png','budget_hit_curves.png'],
            'visual_review_note':'Plots inspected by the assistant; full report distinguishes candidate maps from held-out scores.',
            'scientific_closure':'pending_user_review'}
    output=ROOT/'provenance/reviews'/f'{PRIMARY}_audit.json'
    if output.exists():
        raise FileExistsError(output)
    output.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    print(json.dumps(result,indent=2))


if __name__=='__main__':
    main()
