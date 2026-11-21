"""Canonical release readers preserve validation provenance and locked tests."""
import hashlib,importlib,json,os,tempfile,unittest
from pathlib import Path
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from data3001.paths import ProjectPaths,project_paths,file_sha256


class CurrentDataset(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);(self.root/'configs').mkdir()
        for pool in ['train','test']:(self.root/'data'/pool).mkdir(parents=True)
        records={}
        for id,pool,old in [(1,'train','validation'),(2,'test','test')]:
            table=pa.table({'id':pa.array([id],type=pa.int64()),'ve':pa.array([None],type=pa.float32())})
            table=table.replace_schema_metadata({b'data3001':json.dumps({'id':str(id),'pool':pool,'historical_split':old,'regime_context':{}}).encode()})
            path=self.root/'data'/pool/f'{id}.parquet';pq.write_table(table,path)
            records[str(id)]={'id':str(id),'path':f'data/{pool}/{id}.parquet','pool':pool,'historical_split':old,'rows':1,'sha256':file_sha256(path)}
        manifest={'version':'per-drifter-20261016-v1','IDs':2,'rows':2,'records':records}
        m=self.root/'configs/dataset_manifest.json';m.write_text(json.dumps(manifest))
        assets={'current_dataset_manifest':{'path':'configs/dataset_manifest.json','kind':'file','sha256':file_sha256(m),'split':'all'},'current_train_tracks':{'path':'data/train','kind':'directory','split':'development'},'current_test_tracks':{'path':'data/test','kind':'directory','split':'test'},'test_alias':{'path':'data/test/2.parquet','kind':'file','split':'all'}}
        (self.root/'configs/assets.json').write_text(json.dumps({'schema_version':1,'assets':assets}))
        self.previous=os.environ.get('DATA3001_PROJECT_ROOT');os.environ['DATA3001_PROJECT_ROOT']=str(self.root);project_paths.cache_clear();self.addCleanup(self.restore)
    def restore(self):
        if self.previous is None:os.environ.pop('DATA3001_PROJECT_ROOT',None)
        else:os.environ['DATA3001_PROJECT_ROOT']=self.previous
        project_paths.cache_clear()
    def api(self):
        self.assertIsNotNone(importlib.util.find_spec('data3001.dataset'),'Canonical dataset reader is missing')
        return importlib.import_module('data3001.dataset')
    def test_original_validation_ID_is_available_in_development_pool(self):
        api=self.api();f=api.read_track(1)
        self.assertEqual(f.id.tolist(),[1]);self.assertEqual(api.development_ids(),[1])
        self.assertEqual(f.attrs['data3001']['historical_split'],'validation')
    def test_final_test_ID_requires_explicit_access(self):
        api=self.api()
        with self.assertRaises(PermissionError):api.read_track(2)
        self.assertEqual(api.read_track(2,allow_test=True).id.tolist(),[2])
    def test_hash_mismatch_stops_loading(self):
        api=self.api();(self.root/'data/train/1.parquet').write_bytes(b'changed')
        with self.assertRaises(ValueError):api.read_track(1)
    def test_child_track_symlink_cannot_escape_the_pool(self):
        api=self.api();path=self.root/'data/train/1.parquet'
        outside=self.root/'outside.parquet';outside.write_bytes(path.read_bytes())
        path.unlink();path.symlink_to(outside)
        with self.assertRaises(PermissionError):api.read_track(1)
    def test_development_alias_cannot_expose_new_test_directory(self):
        with self.assertRaises(PermissionError):ProjectPaths(self.root).asset('test_alias')
    def test_archived_test_alias_remains_locked(self):
        p=self.root/'archive/data_before_release_20261016/restricted_test/a.bin';p.parent.mkdir(parents=True);p.write_bytes(b'held')
        catalog=json.loads((self.root/'configs/assets.json').read_text());catalog['assets']['old_alias']={'path':str(p.relative_to(self.root)),'kind':'file','split':'all'}
        (self.root/'configs/assets.json').write_text(json.dumps(catalog))
        with self.assertRaises(PermissionError):ProjectPaths(self.root).asset('old_alias')


if __name__=='__main__':unittest.main()
