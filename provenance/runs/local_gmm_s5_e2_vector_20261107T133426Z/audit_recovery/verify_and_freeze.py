import hashlib,json,shutil,math
from datetime import datetime,timezone
from pathlib import Path
import numpy as np
from data3001.paths import file_sha256
from data3001.modelling.continuous_models import local_gmm_s5_e2_pipeline as pipe
from data3001.modelling.continuous_models import local_gmm_s5_e2_audit as audit
p=Path(__file__).resolve().parent;prov=p.parent;root=pipe.ROOT
run={'results':root/'results/runs'/prov.name,'provenance':prov}
t=pipe.collect(run,'C_outer','score');a=pipe.collect(run,'C_outer','audit')
g=t[t.model.eq('LocalGMM')];q=a[a.model.eq('LocalGMM') & a.iid_energy_km.notna()]
check=audit.verify_iid_alignment(g,q)
assert check['passed'],check
# Independent scalar arithmetic verifies the dtype conversion has not changed the gate.
q=q.sort_values('query_position');gp=g.set_index('query_position').loc[q.query_position].reset_index()
for table,name in [(q,'reference'),(gp,'primary')]:
    ids=table.id.to_list();w=np.array([1/(len(set(ids))*ids.count(i)) for i in ids])
    delta=[float(y)-float(x) for y,x in zip(q.iid_energy_km,table.energy_km)]
    variance=[float(v)+float(u) for v,u in zip(q.iid_variance,table.variance)]
    expected={'mean_difference':math.fsum(float(z)*d for z,d in zip(w,delta)),
        'three_se':3*math.sqrt(math.fsum(float(z*z)*v for z,v in zip(w,variance))),
        'max_standardised_difference':max(abs(d)/math.sqrt(v) for d,v in zip(delta,variance))}
    for key,value in expected.items():np.testing.assert_allclose(check[name][key],value,atol=1e-12,rtol=1e-12)
preserved={}
for receipt in sorted((prov/'batches').rglob('*.json')):
    for source,digest in json.loads(receipt.read_text())['sha256'].items():
        if source in preserved:assert preserved[source]==digest
        preserved[source]=digest
for source,digest in preserved.items():assert file_sha256(root/source)==digest,source
(p/'preserved_outputs.json').write_text(json.dumps(preserved,indent=2)+'\n')
active=json.loads((prov/'source_hashes.json').read_text())
source='src/data3001/modelling/continuous_models/local_gmm_s5_e2_audit.py'
for key,value in active.items():
    if key!=source:assert file_sha256(root/key)==value,key
assert active[source]==file_sha256(p/'audit_before.py')
new_test='tests/test_modelling_local_gmm_s5_e2_audit_dtype.py'
folder=prov/'implementation_revision_5'
for key in [source,new_test]:
    out=folder/key;out.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(root/key,out)
    active[key]=file_sha256(root/key)
(prov/'source_hashes_revision_5.json').write_text(json.dumps(active,indent=2)+'\n')
(prov/'source_hashes.json').write_text(json.dumps(active,indent=2)+'\n')
result={'timestamp_utc':datetime.now(timezone.utc).isoformat(),'source_revision':5,
    'change':'Convert nullable IID numeric columns to float64 at the audit arithmetic boundary',
    'root_cause':'Parquet batches with all-null IID fields leave concatenated IID columns as object dtype; selected values are Python float',
    'scientific_model_changed':False,'training_weights_changed':False,'cohorts_changed':False,
    'precision_changed':False,'resource_caps_changed':False,'thresholds_changed':False,
    'preserved_output_files':len(preserved),'actual_iid_cases':len(q),'iid_check':check,
    'independent_scalar_agreement':True,'final_test_access':False}
(prov/'implementation_amendment_5.json').write_text(json.dumps(result,indent=2)+'\n')
(p/'verification.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
