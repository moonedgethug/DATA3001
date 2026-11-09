"""Acquire public metadata only. Never writes to data or model outputs."""
from pathlib import Path
import datetime
import ftplib
import hashlib
import json

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
sources = OUT / 'sources'
sources.mkdir(exist_ok=True)
names = ['dirfl_1_5000.dat', 'dirfl_5001_10000.dat',
         'dirfl_10001_15000.dat', 'dirfl_15001_current.dat']
receipts = []
with ftplib.FTP('ftp.aoml.noaa.gov', timeout=30) as ftp:
    ftp.login()
    for name in names:
        path = sources / name
        if path.exists():
            raise RuntimeError(f'Refusing to overwrite source snapshot: {path}')
        remote = '/phod/pub/buoydata/' + name
        chunks = []
        ftp.retrbinary('RETR ' + remote, chunks.append)
        raw = b''.join(chunks)
        path.write_bytes(raw)
        digest = hashlib.sha256(raw).hexdigest()
        old = json.loads((ROOT / 'provenance/runs/drogue_boundary_20261016' / (name+'.json')).read_text())
        receipt = dict(name=name, url='ftp://ftp.aoml.noaa.gov'+remote,
                       retrieved_UTC=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                       server_mtime=ftp.sendcmd('MDTM '+remote), bytes=len(raw), sha256=digest,
                       matches_20261016_source=digest==old['full_response_sha256'])
        receipts.append(receipt)
        print(json.dumps(receipt), flush=True)
(OUT / 'source_receipts.json').write_text(json.dumps(receipts,indent=2)+'\n')
