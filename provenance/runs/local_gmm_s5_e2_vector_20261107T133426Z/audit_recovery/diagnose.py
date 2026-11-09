import json
import numpy as np
from pathlib import Path
from data3001.modelling.continuous_models import local_gmm_s5_e2_pipeline as p
from data3001.modelling.continuous_models import local_gmm_s5_e2_audit as a
root=Path(__file__).resolve().parent
run={'results':p.ROOT/'results/runs'/root.parent.name}
t=p.collect(run,'C_outer','score');r=p.collect(run,'C_outer','audit')
g=t[t.model.eq('LocalGMM')]
q=r[r.model.eq('LocalGMM') & r.iid_energy_km.notna()]
fields=['energy_km','variance','iid_energy_km','iid_variance']
result={'selected_rows':len(q),'dtypes':{f:str(q[f].dtype) for f in fields},'types':{f:sorted(set(type(x).__name__ for x in q[f])) for f in fields}}
for f in fields:np.testing.assert_array_equal(q[f].to_numpy(),q[f].to_numpy(dtype=np.float64))
try:a.verify_iid_alignment(g,q)
except TypeError as e:result['reproduced_error']=str(e)
else:raise AssertionError('Expected original type failure')
result['numeric_conversion_changes_values']=False
(root/'diagnosis.json').write_text(json.dumps(result,indent=2))
print(json.dumps(result,indent=2))
