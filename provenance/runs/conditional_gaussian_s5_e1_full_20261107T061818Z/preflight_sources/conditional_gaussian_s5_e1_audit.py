"""Independent arithmetic audit of saved pilot cases; never opens outer truth."""
import time
STARTED = time.monotonic()
import hashlib
import json
import sys

import numpy as np
import pandas as pd
from pyproj import Geod, Transformer

from data3001.modelling.common.runtime import save_frame, save_json
from data3001.modelling.continuous_models import conditional_gaussian_s5_e1_inputs as inputs

GEOD = Geod(ellps='WGS84')
PROJECTION = Transformer.from_crs('EPSG:4326',
    '+proj=laea +lat_0=35 +lon_0=-75 +datum=WGS84 +units=m', always_xy=True)


def xyz(points):
    """Independent ellipsoid formula, kilometres; no production ECEF helper."""
    lon, lat = np.deg2rad(np.asarray(points)).T
    a, flattening = 6378.137, 1/298.257223563
    e2 = flattening*(2-flattening)
    n = a/np.sqrt(1-e2*np.sin(lat)**2)
    return np.column_stack((n*np.cos(lat)*np.cos(lon),
                            n*np.cos(lat)*np.sin(lon), n*(1-e2)*np.sin(lat)))


def geographic(origin, vectors):
    lon, lat, _ = GEOD.fwd(np.full(len(vectors), origin[0]), np.full(len(vectors), origin[1]),
        np.rad2deg(np.arctan2(vectors[:, 0], vectors[:, 1])), np.hypot(*vectors.T)*1000)
    return np.column_stack((lon, lat))


def audit(name):
    paths, run, cfg, approval, guard = inputs.context(name)
    budget = inputs.Budget(run, cfg, 'audit', STARTED)
    inputs.freeze_sources(paths, run, 'audit')
    contexts, _, outer = inputs.load(cfg)
    root = run['results']
    roster = pd.read_parquet(root/'pilot_roster.parquet')
    energy = pd.read_parquet(root/'pilot_energy.parquet')
    regions = pd.read_parquet(root/'pilot_regions.parquet')
    gates = json.loads((root/'pilot_gates.json').read_text())
    support = pd.read_csv(root/'pilot_support.csv')
    timing = pd.read_csv(root/'pilot_timings.csv')
    expected_weights = roster.id.map(roster.id.value_counts()).rdiv(1/roster.id.nunique()).to_numpy()
    np.testing.assert_allclose(roster.evaluation_weight, expected_weights, rtol=0, atol=1e-15)
    assert len(roster) == 128 and len(energy) == 128*3*4 and len(regions) == 128*3*3
    assert not gates['formal_started'] and not gates['passed']
    rows, metrics = [], []
    for row in roster.itertuples(index=False):
        budget.check()
        context = contexts[row.role]
        fit = context['fit']
        origin = np.array([row.lon, row.lat])
        with np.load(root/'lineage'/f'{row.pilot_position:03d}.npz') as f:
            indices, saved_distance = f['indices'], f['distances_m']
        # Exhaustive geodesic audit does not use the production spatial index.
        _, _, distances = GEOD.inv(np.full(len(fit), row.lon), np.full(len(fit), row.lat),
                                   fit.lon.to_numpy(), fit.lat.to_numpy())
        eligible = np.flatnonzero(distances <= 100000+1e-6)
        order = np.lexsort((eligible, distances[eligible]))
        selected = eligible[order]
        if len(selected)>8000:
            selected = selected[distances[selected] <= distances[selected[7999]]+1e-6]
        np.testing.assert_array_equal(indices, selected)
        np.testing.assert_allclose(saved_distance, distances[indices], rtol=0, atol=1e-8)
        donor = fit.iloc[indices]
        frozen = json.loads((root/'parameters'/f'{row.pilot_position:03d}.json').read_text())
        assert hashlib.sha256(donor[inputs.KEY].to_numpy(dtype=np.int64).tobytes()).hexdigest() == frozen['donor_digest']
        packet = frozen['gaussian']
        endpoint = donor[['endpoint_lon','endpoint_lat']].to_numpy()
        angle, _, distance = GEOD.inv(np.full(len(donor),row.lon), np.full(len(donor),row.lat), *endpoint.T)
        vectors = np.array([distance*np.sin(np.deg2rad(angle)),distance*np.cos(np.deg2rad(angle))]).T/1000
        mean = np.array([np.sum(vectors[:, i], dtype=np.longdouble)/len(vectors) for i in range(2)], float)
        covariance = np.cov(vectors, rowvar=False, bias=True)
        mean_error = float(np.max(np.abs(mean-packet['mean'])))
        covariance_error = float(np.max(np.abs(covariance-packet['covariance'])))
        np.testing.assert_allclose(mean, packet['mean'], rtol=1e-11, atol=1e-9)
        np.testing.assert_allclose(covariance, packet['covariance'], rtol=1e-11, atol=1e-8)
        truth = context['target'].iloc[row.query_position][['endpoint_lon','endpoint_lat']].to_numpy(float)
        truth_xy = np.array(PROJECTION.transform(*truth))/1000
        selected_regions = json.loads((root/'regions'/f'{row.pilot_position:03d}_{gates["selected_region_count"]}.json').read_text())
        for model, item in selected_regions.items():
            reg = item['region']
            assert reg['rank'] == 2
            delta = truth_xy-reg['centre']
            d2 = float(delta @ np.linalg.solve(np.asarray(reg['covariance']), delta))
            area = float(np.pi*reg['cutoff']*np.sqrt(np.linalg.det(reg['covariance'])))
            saved = regions[regions.pilot_position.eq(row.pilot_position)&regions.model.eq(model)&regions.level.eq(gates['selected_region_count'])].iloc[0]
            assert float(d2 <= reg['cutoff']+1e-12) == saved.h90
            np.testing.assert_allclose(area, saved.area90_km2, rtol=1e-10)
            if model == 'ExactPoint':
                xy = np.column_stack(PROJECTION.transform(*endpoint.T))/1000
                c = xy.mean(axis=0)
                s = np.cov(xy, rowvar=False, bias=True)
                mahal = np.sum((xy-c)*np.linalg.solve(s, (xy-c).T).T, axis=1)
                # Integer CDF threshold, including all exact ties.
                cutoff = np.sort(mahal)[(9*len(xy)+9)//10-1]
                np.testing.assert_allclose(c, reg['centre'], rtol=1e-10, atol=1e-9)
                np.testing.assert_allclose(cutoff, reg['cutoff'], rtol=1e-10, atol=1e-10)
                assert item['mass_check']['discrepancy'] <= 1e-12
            metrics.append(dict(pilot_position=row.pilot_position, id=row.id, role=row.role,
                model=model, energy_km=float(energy[energy.pilot_position.eq(row.pilot_position)&energy.model.eq(model)&energy.level.eq(gates['selected_energy_count'])].iloc[0].energy_km),
                h90=float(d2<=reg['cutoff']+1e-12), area90_km2=area,
                land_mass=item['land_mass'], outside_D_mass=item['outside_D_mass']))
        # Independent IID, eigensquare-root sampling and a separate ECEF formula.
        key = ('s5_e1_v1', row.role, row.id, row.origin_source_obs, 7, 'audit_iid', 0)
        seed = int.from_bytes(hashlib.sha256(json.dumps(key,separators=(',',':')).encode()).digest()[:16],'little')
        rng = np.random.Generator(np.random.PCG64(seed))
        values, axes = np.linalg.eigh(covariance)
        root_cov = axes*np.sqrt(values)
        normal = rng.standard_normal((65536,4))
        a = xyz(geographic(origin, mean+normal[:,:2]@root_cov.T))
        b = xyz(geographic(origin, mean+normal[:,2:]@root_cov.T))
        integrand = np.sqrt(np.sum((a-xyz(truth[None,:])[0])**2, axis=1))-.5*np.sqrt(np.sum((a-b)**2,axis=1))
        reference = energy[energy.pilot_position.eq(row.pilot_position)&energy.model.eq('LocalGaussian')&energy.level.eq(65536)].iloc[0]
        rows.append(dict(pilot_position=row.pilot_position, id=row.id, role=row.role,
            mean_max_abs_km=mean_error, covariance_max_abs_km2=covariance_error,
            iid_energy_km=float(integrand.mean()), rqmc_energy_km=float(reference.energy_km),
            independent_difference_km=float(integrand.mean()-reference.energy_km),
            independent_difference_variance=float(integrand.var(ddof=1)/len(integrand)+reference.variance)))
        if (row.pilot_position+1)%16==0:
            print('AUDIT',row.pilot_position+1,'/128',round(budget.check()['elapsed_seconds'],1),'seconds',flush=True)
    audit_rows = pd.DataFrame(rows)
    iid_difference = float(expected_weights@audit_rows.independent_difference_km)
    iid_three_se = float(3*np.sqrt(expected_weights**2@audit_rows.independent_difference_variance))
    assert abs(iid_difference) <= iid_three_se
    per_case = pd.DataFrame(metrics)
    summaries = []
    fields = ['energy_km','h90','area90_km2','land_mass','outside_D_mass']
    for scope in ['all_pilot','C_T0','C_T1']:
        subset = per_case if scope=='all_pilot' else per_case[per_case.role.eq(scope)]
        for model, group in subset.groupby('model',sort=False):
            by_id = group.groupby('id')[fields].mean()
            summaries.append(dict(scope=scope,model=model,cases=len(group),ids=len(by_id),**by_id.mean().to_dict()))
    summary = pd.DataFrame(summaries)
    # Independent direct arithmetic of pilot ES projection, without assess().
    outer_counts = outer.id.value_counts()
    outer_square = float(np.sum(1/outer_counts)/(len(outer_counts)**2))
    for level in cfg['energy_levels']:
        v = energy[energy.level.eq(level)].pivot(index='pilot_position',columns='model',values='variance')
        for base in ['ExactPoint','EndpointCI']:
            recomputed = 3*np.sqrt(float((v.LocalGaussian+v[base]).max())*outer_square)
            np.testing.assert_allclose(recomputed,gates['energy_checks'][str(level)]['contrasts'][base]['projected_three_se_km'],rtol=1e-12)
    projection = gates['resource_projection']
    assert projection['formal_with_twofold_reserve_seconds']>7200
    assert projection['audit_seconds']>1800 and projection['storage_bytes']>2.5*2**30
    receipt = dict(status='PILOT_AUDIT_PASSED_FORMAL_BLOCKED', cases=128,
        donor_search_exhaustive_cases=128, independently_recomputed_parameters=128,
        independently_checked_regions=384, mean_max_abs_km=float(audit_rows.mean_max_abs_km.max()),
        covariance_max_abs_km2=float(audit_rows.covariance_max_abs_km2.max()),
        gaussian_iid_draws_per_case=65536, iid_minus_rqmc_km=iid_difference, iid_three_se_km=iid_three_se,
        pilot_ids=int(roster.id.nunique()), support_pairs_min=int(support.pairs.min()),
        support_pairs_max=int(support.pairs.max()), donor_ids_min=int(support.independent_ids.min()),
        donor_ids_max=int(support.independent_ids.max()), max_covariance_condition=float(support.covariance_condition.max()),
        weighted_ci_fallback_mass=float(expected_weights@support.ci_unavailable_mass),
        maximum_single_id_share=float(support.largest_id_share.max()),
        outer_targets_read=False, final_test_access=False, formal_started=False,
        formal_quality_conclusion='NOT_EVALUATED', scientific_definitions_changed=False,
        storage_projection_is_conservative=True,
        storage_projection_note='Pilot retained bytes include all refinement levels and checkpoints. Scaling these bytes with a factor of two is a screening estimate, not measured full-run storage.',
        audit_scope='All 128 pilot cases only. No outer support scan, outer parameter freeze, outer scoring, formal bootstrap or formal examples were performed.')
    save_frame(paths,root/'audit_pilot_parameters_energy.csv',audit_rows)
    save_frame(paths,root/'audit_pilot_metrics.csv',per_case)
    save_frame(paths,root/'pilot_summary.csv',summary)
    save_json(paths,run['provenance']/'pilot_independent_audit.json',receipt)
    inputs.verify(approval)
    budget.finish(paths,'independent_pilot_audit',True,guard)
    print(json.dumps(receipt),flush=True)


if __name__ == '__main__': audit(sys.argv[1])
