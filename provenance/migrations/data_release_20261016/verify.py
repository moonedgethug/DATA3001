from pathlib import Path
import json
from data3001.release_verification import verify_release
r=verify_release(progress=lambda x:print(x,flush=True))
p=Path('provenance/migrations/data_release_20261016/full_verification.json')
with p.open('x') as f:json.dump(r,f,indent=2)
print(json.dumps(r,indent=2),flush=True)
