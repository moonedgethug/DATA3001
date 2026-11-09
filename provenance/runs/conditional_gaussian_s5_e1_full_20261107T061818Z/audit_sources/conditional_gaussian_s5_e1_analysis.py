"""Fixed whole-ID aggregation, paired intervals and prespecified decisions."""
import numpy as np
import pandas as pd

FIELDS=['energy_km','h90','area90_km2','land_mass','outside_D_mass','auxiliary_loss',
        'model_mass90','ci_unavailable_mass','largest_id_share','independent_ids','pairs']


def auxiliary(energy,mean1,mean2,truth):
    return float(energy/100+np.dot(np.asarray(mean1)-truth,np.asarray(mean2)-truth)/10000)


def summarize(table):
    fields=[f for f in FIELDS if f in table]
    per_id=table.groupby(['id','model'],sort=True)[fields].mean().reset_index()
    return per_id.groupby('model')[fields].mean(),per_id


def decision(*,es_delta,es_relative,es_upper,hit_delta,hit_lower,area_ratio,area_upper,
             land_delta,outside_delta,numerical):
    es_benefit=bool(es_upper<0 and es_relative<=-.001 and numerical)
    quality=bool(hit_delta>=0 and area_ratio<=1)
    statistical=bool(hit_lower>=-.01 and area_upper<=1.02)
    geography=bool(land_delta<=.01 and outside_delta<=.01)
    return dict(es_benefit=es_benefit,quality_preserved=quality,statistical_guardrails=statistical,
                geographic_guardrails=geography,eligible=bool(es_benefit and quality and statistical and geography))


def compare(table,numerical_pass=True):
    summary,per_id=summarize(table)
    ids=sorted(per_id.id.unique());g=per_id[per_id.model.eq('LocalGaussian')].set_index('id').loc[ids]
    draw=np.random.Generator(np.random.PCG64(20261109)).integers(len(ids),size=(10000,len(ids)))
    comparisons=[];loo=[]
    for baseline in ['ExactPoint','EndpointCI']:
        b=per_id[per_id.model.eq(baseline)].set_index('id').loc[ids]
        es=(g.energy_km-b.energy_km).to_numpy();hit=(g.h90-b.h90).to_numpy()
        area_g=g.area90_km2.to_numpy();area_b=b.area90_km2.to_numpy()
        es_ci=np.quantile(es[draw].mean(axis=1),[.025,.975]);hit_ci=np.quantile(hit[draw].mean(axis=1),[.025,.975])
        ratio_ci=np.quantile(area_g[draw].mean(axis=1)/area_b[draw].mean(axis=1),[.025,.975])
        row=dict(baseline=baseline,es_delta=float(es.mean()),es_relative=float(es.mean()/b.energy_km.mean()),
            es_lower=float(es_ci[0]),es_upper=float(es_ci[1]),hit_delta=float(hit.mean()),
            hit_lower=float(hit_ci[0]),hit_upper=float(hit_ci[1]),area_ratio=float(area_g.mean()/area_b.mean()),
            area_lower=float(ratio_ci[0]),area_upper=float(ratio_ci[1]),
            land_delta=float((g.land_mass-b.land_mass).mean()),outside_delta=float((g.outside_D_mass-b.outside_D_mass).mean()))
        row.update(decision(**{k:row[k] for k in ['es_delta','es_relative','es_upper','hit_delta','hit_lower','area_ratio','area_upper','land_delta','outside_delta']},numerical=numerical_pass))
        comparisons.append(row)
        for i,id_ in enumerate(ids):
            keep=np.arange(len(ids))!=i
            loo.append(dict(omitted_id=int(id_),baseline=baseline,es_delta=float(es[keep].mean()),hit_delta=float(hit[keep].mean()),area_ratio=float(area_g[keep].mean()/area_b[keep].mean())))
    return summary,per_id,pd.DataFrame(comparisons),pd.DataFrame(loo)
