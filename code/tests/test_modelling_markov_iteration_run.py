import unittest
from pathlib import Path
import json
import numpy as np
from data3001.modelling.run_markov_iteration import validate_settings,check_role,cache_rows,checkpoint


class IterationRunTests(unittest.TestCase):
    def test_environment_reports_actual_numeric_workers(self):
        from data3001.modelling.run_markov_iteration import run_environment
        self.assertEqual(run_environment(True,4)['numeric_workers'],1)
        self.assertEqual(run_environment(False,4)['numeric_workers'],4)

    def test_grid_and_test_boundaries_cannot_be_silently_changed(self):
        c=json.loads((Path(__file__).resolve().parents[1]/'configs/markov_m1_iteration.json').read_text())
        validate_settings(c)
        for replacement in [{'lambda_grid':[.2]},{'final_test_access':True},{'candidate_filter':'fixed_lambda_top2'}]:
            with self.assertRaises(ValueError):validate_settings({**c,**replacement})

    def test_role_uses_exact_recorded_fitting_IDs_and_threshold(self):
        th={'roles':{'inner_0_1':{'fitting_ids':[1,2],'threshold_m_s':.2}}}
        self.assertEqual(check_role(th,'inner_0_1',{1,2},{3}),.2)
        with self.assertRaises(ValueError):check_role(th,'inner_0_1',{1},{3})
        with self.assertRaises(ValueError):check_role(th,'inner_0_1',{1,2},{2})

    def test_sparse_geometry_cache_keeps_original_native_ID_ranges(self):
        from data3001.modelling.markov_position import OBS_DTYPE
        a=np.zeros(25,dtype=OBS_DTYPE);a['id']=300534067902500;a['time']=np.arange(25)*3600
        a['lon']=-75.;a['lat']=33.;a['cell']=44385
        result=cache_rows(a,np.array([100]),np.array([124]),1,100)
        self.assertEqual(result['endpoint'][0],124)
        self.assertTrue((result['endpoint'][1:]==-1).all())

    def test_resume_finds_hash_verified_parent_checkpoint_without_writing_it(self):
        from tempfile import TemporaryDirectory
        from types import SimpleNamespace
        import hashlib
        with TemporaryDirectory() as d:
            root=Path(d);old=root/'results/runs/old/inner/role_abc_attempt';old.mkdir(parents=True)
            (old/'scores.csv').write_text('x\n1\n')
            payload={'files':{'scores.csv':hashlib.sha256((old/'scores.csv').read_bytes()).hexdigest()}}
            (old/'COMPLETE.json').write_text(json.dumps(payload))
            run={'results':root/'results/runs/new','provenance':root/'provenance/runs/new'}
            run['results'].mkdir(parents=True);run['provenance'].mkdir(parents=True)
            (run['provenance']/'run.json').write_text(json.dumps({'config':{'resume_from':'old','source_sha256':{}}}))
            p=root/'provenance/runs/old';p.mkdir(parents=True)
            (p/'run.json').write_text(json.dumps({'config':{'source_sha256':{}}}))
            folder,record=checkpoint(SimpleNamespace(root=root),run,'role_abc')
            self.assertEqual(folder,old);self.assertEqual(record,payload)
            self.assertEqual((old/'scores.csv').read_text(),'x\n1\n')


if __name__=='__main__':unittest.main()
