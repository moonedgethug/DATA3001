import importlib
import hashlib
import json
import tempfile
import unittest
from contextlib import ExitStack, contextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
import pandas as pd


def signed(value):
    value = {key: item for key, item in value.items() if key != 'identity_sha256'}
    value['identity_sha256'] = hashlib.sha256(json.dumps(
        value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()
    return value


@contextmanager
def synthetic_release(module):
    from data3001.paths import file_sha256
    from data3001.modelling.continuous_models import conditional_mdn_s5_e3_inputs as inputs
    from data3001.modelling.continuous_models import conditional_mdn_s5_e3_formal_scoring as scoring
    from data3001.modelling.continuous_models.conditional_mdn_s5_e3 import CONTRACT_SHA256
    with tempfile.TemporaryDirectory() as directory, ExitStack() as stack:
        root = Path(directory)
        run = {name: root/name/'conditional_mdn_s5_e3_synthetic' for name in ('results', 'provenance')}
        for folder in run.values():
            folder.mkdir(parents=True)
        query = pd.DataFrame({'id': [10, 20], 'origin_source_obs': [100, 200],
                              'horizon_days': [7, 7], 'lon': [-75., -74.], 'lat': [35., 36.]})
        targets = query[inputs.KEY].assign(endpoint_lon=[-75.1, -74.1], endpoint_lat=[35.1, 36.1], outside=False)
        source = root/'outer_targets.parquet'; source.write_bytes(b'synthetic sealed source')
        protected = root/'training_coordinates.parquet'; protected.write_bytes(b'synthetic protected source')
        approval = {'protected_files': {protected.name: file_sha256(protected)}}
        source_code = root/'scorer.py'; source_code.write_text('# synthetic dependency\n')
        cfg = dict(contract_sha256=CONTRACT_SHA256, e7_run='synthetic')
        auth = dict(status='approved', contract_sha256=CONTRACT_SHA256,
                    full_experiment_authorized=True, scientific_definition_unchanged=True,
                    final_test_access=False, deferred_target_path=source.name,
                    deferred_target_sha256=file_sha256(source))
        auth_path = run['provenance']/'formal_v1/authorization.json'
        auth_path.parent.mkdir(); auth_path.write_text(json.dumps(auth))
        base = run['results']/'formal_v1'; base.mkdir()

        def forecast_models(role):
            models = {}
            for k in module.CANDIDATES:
                folder = base/f'{role}/K{k}'; folder.mkdir(parents=True)
                parameters = folder/'parameters.npz'
                np.savez(parameters, query_keys=query[inputs.KEY].to_numpy(np.int64),
                         origins=query[['lon', 'lat']].to_numpy(np.float64),
                         pi=np.full((2, k), 1/k), mu=np.zeros((2, k, 2)),
                         cov=np.tile(np.eye(2), (2, k, 1, 1)), target_scale=np.ones(2))
                manifest = folder/'manifest.json'
                manifest.write_text(json.dumps(dict(status='complete', role=role, k=k,
                    query_key_sha256=inputs.key_digest(query),
                    parameters=dict(path=str(parameters.relative_to(base)), sha256=file_sha256(parameters)))))
                models[str(k)] = dict(parameters=str(parameters.relative_to(base)),
                                       parameters_sha256=file_sha256(parameters),
                                       manifest=str(manifest.relative_to(base)), manifest_sha256=file_sha256(manifest))
            return models

        evidence = {}
        for role in ('C_T0', 'C_T1'):
            inner_models = forecast_models(role)
            for suffix in ('forecast_freeze.json', 'inner_energy/N65536_M65536/complete.json'):
                path = run['provenance']/'formal_v1'/role/suffix
                path.parent.mkdir(parents=True, exist_ok=True)
                receipt = dict(status='complete', role=role, query_count=2, query_id_count=2)
                if path.name == 'complete.json':
                    scores = path.parent/'scores.parquet'
                    pd.DataFrame([dict(id=i, K=k) for i in (10, 20) for k in module.CANDIDATES]).to_parquet(scores)
                    receipt.update(mode='inner_energy', k_values=list(module.CANDIDATES),
                                   scores_sha256=file_sha256(scores), row_count=12, excluded_queries=0)
                else:
                    receipt.update(models=inner_models, outer_targets_read=False,
                                   query_key_sha256=inputs.key_digest(query))
                path.write_text(json.dumps(receipt))
                evidence[str(path)] = file_sha256(path)
        selection = dict(status='complete', selected_k=1, provisional_k=1,
                         contract_sha256=CONTRACT_SHA256, source_run_name=run['results'].name,
                         selection_inputs_sha256=evidence)
        selection_path = base/'selection.json'; selection_path.write_text(json.dumps(selection))
        models = forecast_models('C_outer')
        forecast = dict(status='complete', role='C_outer', query_count=len(query),
                        query_key_sha256=inputs.key_digest(query), models=models,
                        outer_targets_read=False, selected_k=1, selection_sha256=file_sha256(selection_path))
        forecast_path = run['provenance']/'formal_v1/C_outer/forecast_freeze.json'
        forecast_path.parent.mkdir(); forecast_path.write_text(json.dumps(forecast))
        streams = scoring.stream_manifest(query, 'C_outer', 'outer_score', 65536, 65536)
        receipt = signed(dict(status='complete', role='C_outer', mode='outer_score', query_count=len(query),
                              query_key_sha256=inputs.key_digest(query), k_values=list(module.CANDIDATES),
                              count=65536, region_count=65536,
                              parameter_hashes={k: record['parameters_sha256'] for k, record in models.items()},
                              source_hashes={source_code.name: file_sha256(source_code)},
                              forecast_freeze_sha256=file_sha256(forecast_path),
                              node_key_sha256=streams['node_key_sha256'], streams=streams))
        stream_path = run['provenance']/'formal_v1/C_outer/outer_score/inputs_N65536_M65536.json'
        stream_path.parent.mkdir(); stream_path.write_text(json.dumps(receipt))
        guard = SimpleNamespace(outer_allowed=False, outer_read=False, denied=[])
        stack.enter_context(patch.object(module, 'ROOT', root))
        stack.enter_context(patch.object(module, '_TARGETS', {}))
        stack.enter_context(patch.object(module, 'context', return_value=(None, run, cfg, approval, guard)))
        stack.enter_context(patch.object(module.inp, 'cohorts', return_value={'C_outer': {'query': query}}))
        stack.enter_context(patch.object(module.inp, 'EXPECTED',
                                         {role: (2, 2, 2, 2) for role in ('C_T0', 'C_T1', 'C_outer')}))
        yield dict(root=root, run=run, receipt=receipt, stream_path=stream_path, targets=targets,
                   guard=guard, auth=auth, auth_path=auth_path, selection_path=selection_path,
                   selection=selection, protected=protected)


class FormalAuthorizationTests(unittest.TestCase):
    def module(self):
        return importlib.import_module('data3001.modelling.continuous_models.conditional_mdn_s5_e3_formal_context')

    def test_formal_execution_requires_explicit_amendment_and_unchanged_contract(self):
        m = self.module()
        with tempfile.TemporaryDirectory() as d:
            run = {'provenance': Path(d)}
            cfg = {'contract_sha256': 'original'}
            with self.assertRaises(PermissionError):
                m.authorization(run, cfg)
            p = Path(d) / 'formal_v1/authorization.json'
            p.parent.mkdir()
            value = dict(status='approved', contract_sha256='original',
                         full_experiment_authorized=True, resource_time_limit_seconds=None,
                         scientific_definition_unchanged=True, final_test_access=False)
            p.write_text(json.dumps(value))
            self.assertEqual(m.authorization(run, cfg), value)
            value['contract_sha256'] = 'modified'
            p.write_text(json.dumps(value))
            with self.assertRaises(ValueError):
                m.authorization(run, cfg)

    def test_complete_selection_is_required_before_outer_release(self):
        m = self.module()
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'selection.json'
            with self.assertRaises(PermissionError):
                m.completed_selection(path)
            path.write_text(json.dumps(dict(status='provisional', selected_k=4)))
            with self.assertRaises(PermissionError):
                m.completed_selection(path)
            path.write_text(json.dumps(dict(status='complete', selected_k=4)))
            self.assertEqual(m.completed_selection(path)['selected_k'], 4)
            path.write_text(json.dumps(dict(status='complete', selected_k=3)))
            with self.assertRaises(ValueError):
                m.completed_selection(path)

    def test_tampered_streams_are_rejected_before_any_raw_target_read(self):
        m = self.module()
        mutations = (
            lambda r: r.pop('identity_sha256'),
            lambda r: r.update(node_key_sha256='0'*64),
            lambda r: r.update(source_hashes={}),
            lambda r: r.update(forecast_freeze_sha256='0'*64),
            lambda r: r['streams'].update(all_streams=[]),
            lambda r: r['streams'].update(all_node_key_sha256='0'*64),
        )
        for index, mutate in enumerate(mutations):
            with self.subTest(mutation=index), synthetic_release(m) as fixture:
                receipt = fixture['receipt']; mutate(receipt)
                # Re-sign all but the first two cases: a checksum alone must not
                # authorize a malformed schedule or a different forecast.
                if index >= 2:
                    receipt = signed(receipt)
                fixture['stream_path'].write_text(json.dumps(receipt))
                with patch.object(m.inp, 'read_frame', side_effect=AssertionError('Raw target read before rejection')):
                    with self.assertRaises(ValueError):
                        m.release_targets(fixture['run']['results'].name, 'C_outer', 'outer_score',
                                          m.CANDIDATES, 65536, 65536)
                self.assertFalse(fixture['guard'].outer_allowed)

    def test_outer_selection_binding_is_checked_before_raw_target_read(self):
        m = self.module()
        with synthetic_release(m) as fixture:
            choice = fixture['selection']; choice['selected_k'] = 2
            fixture['selection_path'].write_text(json.dumps(choice))
            with patch.object(m.inp, 'read_frame', side_effect=AssertionError('Raw target read before selection check')):
                with self.assertRaises(ValueError):
                    m.release_targets(fixture['run']['results'].name, 'C_outer', 'outer_score',
                                      m.CANDIDATES, 65536, 65536)
            self.assertFalse(fixture['guard'].outer_allowed)

    def test_outer_source_failure_and_success_both_restore_sealed_permission(self):
        m = self.module()
        with synthetic_release(m) as fixture:
            auth = fixture['auth']; auth['deferred_target_sha256'] = '0'*64
            fixture['auth_path'].write_text(json.dumps(auth))
            with self.assertRaises(ValueError):
                m.release_targets(fixture['run']['results'].name, 'C_outer', 'outer_score',
                                  m.CANDIDATES, 65536, 65536)
            self.assertFalse(fixture['guard'].outer_allowed)
        with synthetic_release(m) as fixture:
            with patch.object(m.inp, 'read_frame', return_value=fixture['targets']):
                result = m.release_targets(fixture['run']['results'].name, 'C_outer', 'outer_score',
                                           m.CANDIDATES, 65536, 65536)
            self.assertEqual(result.id.tolist(), [10, 20])
            self.assertFalse(fixture['guard'].outer_allowed)

    def test_protected_input_drift_is_rechecked_before_target_release(self):
        m = self.module()
        with synthetic_release(m) as fixture:
            fixture['protected'].write_bytes(b'changed values with the same roster')
            with patch.object(m.inp, 'read_frame', side_effect=AssertionError('Raw target read after source drift')):
                with self.assertRaises(ValueError):
                    m.release_targets(fixture['run']['results'].name, 'C_outer', 'outer_score',
                                      m.CANDIDATES, 65536, 65536)
            self.assertFalse(fixture['guard'].outer_allowed)


if __name__ == '__main__':
    unittest.main()
