"""Export geography and already-published aggregate audits; never reads drifter test records."""
import ast,csv,json,hashlib
from pathlib import Path
from shapely.geometry import shape,box,Polygon,mapping,LineString
ROOT=Path('/Users/moonedgethug/Documents/UNSW/DATA3001/work_place')
SITE=Path(__file__).resolve().parents[1]
out=SITE/'dist/assets/pt2'
base=json.loads((SITE/'dist/assets/pt1/geography-wide.json').read_text())
geo=json.loads(Path('/tmp/data3001-ne-land.json').read_text())
land=[]
for f in geo['features']:
 p=shape(f['geometry']).intersection(box(-180,-60,180,78)).simplify(.055,preserve_topology=True)
 for q in (p.geoms if hasattr(p,'geoms') else [p]):
  if q.geom_type=='Polygon' and q.area>.02: land.append([[round(x,4),round(y,4)] for x,y in q.exterior.coords])
# Read region definitions from the audit's AST, without importing or executing its analysis.
tree=ast.parse((ROOT/'archive/region_screening_6h/region_data_audit.py').read_text())
expr=next(x.value for x in tree.body if isinstance(x,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='REGIONS' for t in x.targets))
regions=eval(compile(ast.Expression(expr),'regions','eval'),{'__builtins__':{},'box':box,'Polygon':Polygon})
corridor=regions['Gulf Stream Corridor']
windows=[(-82,30,-73,35.5),(-78,35.5,-66,38.5),(-74,38.5,-60,42.5)]
segments=[list(corridor.intersection(box(*w)).exterior.coords) for w in windows]
r_polygon=Polygon(base['region'])
grid=[]
for line in [LineString([(x,30),(x,35.5)]) for x in range(-82,-72)]+[LineString([(-82,y),(-73,y)]) for y in range(30,36)]:
 clipped=line.intersection(r_polygon)
 for part in (clipped.geoms if hasattr(clipped,'geoms') else [clipped]):
  if part.geom_type=='LineString' and not part.is_empty: grid.append(list(part.coords))
annualpath=ROOT/'provenance/reviews/seasonal_temporal_support_20261102/annual_support.csv'
rows=[r for r in csv.DictReader(annualpath.open()) if int(r['horizon_days'])==7]
byyear={int(r['year']):{k:int(r[k]) for k in ['year','ids','pairs']} for r in rows}
annual=[byyear.get(y,dict(year=y,ids=0,pairs=0)) for y in range(1990,2023)]
assert sum(r['pairs'] for r in annual)==303288
payload={'land':land,'region':base['region'],'regions':{k:list(v.exterior.coords) for k,v in regions.items()},'segments':segments,'rGrid':grid,'D':[[-81,20],[-8,20],[-8,55],[-81,55],[-81,20]],'annual':annual,'final':{'fit':{'years':'2001–2019','ids':338,'pairs':265393},'validation':{'years':'2020–2022','ids':45,'pairs':33971}},'sources':{'land':base['source'],'region_sha256':base['region_sha256'],'annual_csv_sha256':hashlib.sha256(annualpath.read_bytes()).hexdigest(),'annual_scope':'Historical eligible 1-degree stopped labels in development pool, before final split exclusions; by origin year. 2022 incomplete.'}}
(out/'data.json').write_text(json.dumps(payload,separators=(',',':')))
for name in ['region-audit-summary.csv','gulf-stream-segment-summary.csv']:
 (out/name).write_bytes((ROOT/'archive/region_screening_6h/outputs'/name).read_bytes())
(out/'annual_support.csv').write_bytes(annualpath.read_bytes())
print(json.dumps({'land_rings':len(land),'land_points':sum(map(len,land)),'annual_pairs':303288,'bytes':(out/'data.json').stat().st_size}))
