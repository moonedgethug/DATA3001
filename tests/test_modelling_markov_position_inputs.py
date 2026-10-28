import hashlib
import importlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd


def api():return importlib.import_module('data3001.modelling.markov_position_inputs')


class PositionInputTests(unittest.TestCase):
    def track(self,sid,hours):
        from data3001.preprocessing.prep_core import cells,event_bounds
        t=1600000000+np.arange(hours)*3600;x=-76.5+np.arange(hours)*.0001
        f=pd.DataFrame({'id':sid,'source_obs':np.arange(hours),'time':t,
                        'time_UTC':pd.to_datetime(t,unit='s',utc=True),'lon_normalized':x,
                        'lat':33.2,'cell_1':cells(x,np.full(hours,33.2)),
                        've':1.,'vn':1.,'season':2})
        a={'time':t,'position_ok':np.ones(hours,bool),'mapping_ok':np.ones(hours,bool),
           'inside_D':np.ones(hours,bool),'in_R':np.arange(hours)==0,'visit_cell_1':np.zeros(hours,int),
           'regime':np.ones(hours,np.int8),'loss':float(t[-1]+86400)}
        return f,a,event_bounds(a)

    def test_native_mmap_roundtrip_and_donor_keys(self):
        m=api()
        from data3001.preprocessing.prep_pairs import generate
        f,a,e=self.track(1,49);native=m.native_observations(f,[.5])
        ledger=generate(f,a,e,1,np.array([0,1]),1,'pooled')[1]
        rows=m.donor_rows(ledger,f,100)
        self.assertEqual(rows.origin.tolist(),[100,101]);self.assertEqual(rows.endpoint.tolist(),[124,125])
        with tempfile.TemporaryDirectory() as directory:
            p=Path(directory)/'obs.npy'
            with p.open('wb') as stream:
                np.lib.format.write_array_header_2_0(stream,{'descr':native.dtype.descr,'fortran_order':False,'shape':native.shape})
                stream.write(native.tobytes())
            read=np.load(p,mmap_mode='r',allow_pickle=False)
            np.testing.assert_array_equal(read,native)
        self.assertGreater(native['length'][-1],0)

    def test_source_exit_needs_no_horizon_endpoint_and_bad_time_rejected(self):
        m=api()
        from data3001.preprocessing.prep_pairs import generate
        f,a,e=self.track(1,49);d=generate(f,a,e,1,np.array([0]),1,'pooled')[1]
        d.loc[0,'destination_cell_1']=-2;d.loc[0,'endpoint_source_obs']=-1
        self.assertEqual(m.donor_rows(d,f,0).endpoint.iloc[0],-2)
        d.loc[0,'destination_cell_1']=int(f.cell_1.iloc[24]);d.loc[0,'endpoint_source_obs']=23
        with self.assertRaises(ValueError):m.donor_rows(d,f,0)

    def test_full_synthetic_cache_keeps_zero_eligible_R_and_reconciles(self):
        m=api()
        from data3001.preprocessing.prep_pairs import generate
        from data3001.modelling.markov_inputs import count_pairs
        class Paths:
            def publish(self,path,writer):
                path.parent.mkdir(parents=True,exist_ok=True)
                with path.open('wb') as stream:writer(stream)
        tracks={i:self.track(i,1 if i==1 else 721) for i in [1,2]}
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);parent=root/'parent';(parent/'release_labels').mkdir(parents=True)
            dparts=[];rparts=[];records=[]
            for sid,(f,a,e) in tracks.items():
                digest=hashlib.sha256()
                for h in [1,2,3,5,7]:
                    d=generate(f,a,e,sid,np.arange(len(f)),h,'pooled')[1]
                    dparts.append(count_pairs(d));digest.update(d[['origin_source_obs','horizon_days','destination_cell_1','reason_code']].to_numpy(dtype='<i8').tobytes())
                labels=[]
                for h in [1,2,3,5,7,30]:
                    d=generate(f,a,e,sid,np.array([0]),h,'pooled')[1]
                    labels.append(d);rparts.append(count_pairs(d));digest.update(d[['origin_source_obs','horizon_days','destination_cell_1','reason_code']].to_numpy(dtype='<i8').tobytes())
                pd.concat(labels,ignore_index=True).to_parquet(parent/'release_labels'/f'{sid}.parquet')
                records.append({'id':sid,'target_reason_digest':digest.hexdigest()})
            pd.concat(dparts,ignore_index=True).to_parquet(parent/'transition_counts_by_id.parquet')
            pd.concat(rparts,ignore_index=True).to_parquet(parent/'release_counts_by_id.parquet')
            pd.DataFrame(records).to_csv(parent/'source_ID_summary.csv',index=False)
            data={'records':{str(i):{'pool':'train','rows':len(t[0]),'sha256':'synthetic'} for i,t in tracks.items()}}
            with patch.object(m,'manifest',return_value=data),patch.object(m,'PreparedSource'),patch.object(m,'load_track',side_effect=lambda _,i:tracks[i]):
                result=m.collect_position_inputs(Paths(),{'results':root/'results'},[1,2],parent,[.5],progress=lambda *a,**k:None)
            self.assertTrue(result['all_source_keys_and_parent_counts_identical'])
            obs=np.load(root/'results/observations.npy',mmap_mode='r')
            self.assertEqual(len(obs),722)
            releases=pd.read_parquet(root/'results/releases.parquet')
            self.assertEqual(len(releases.loc[releases.id.eq(1)]),2)
            self.assertFalse(releases.loc[releases.id.eq(1),'reason_code'].eq(0).any())
            donors=pd.read_parquet(root/'results/donors.parquet')
            known=donors.endpoint.ge(0)
            np.testing.assert_array_equal(obs['id'][donors.origin.to_numpy()[known]],obs['id'][donors.endpoint.to_numpy()[known]])


if __name__=='__main__':unittest.main()
