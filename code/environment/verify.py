"""Run the unchanged scientific test suite in an isolated original-layout view."""
from pathlib import Path
import argparse
import json
import subprocess
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from reproduction.workspace import ExecutionWorkspace
from reproduction.runner import run_command


def run(root, run_id=None):
    view = ExecutionWorkspace(root, run_id)
    try:
        view.materialize_sources()
        view.bind('docs')
        # Two development-only regression fixtures; sealed ID 60350 stays absent.
        for sid in ['43869', '132499']:
            view.bind('data/train/' + sid + '.parquet')
        view.bind_assets(['corpus_time_coverage', 'land_mask_high', 'land_mask_intermediate',
                          'release_R', 'transport_D', 'english_contract', 'development_folds'])
        exact = 'results/runs/exact_origin_s4_e7_primary_20261105T074326_829211Z'
        for name in ['training_coordinates.parquet', 'query_coordinates.parquet', 'roles.parquet']:
            view.bind(exact + '/' + name)
        parent = 'conditional_mdn_s5_e3_20261108T055830_797628Z'
        view.bind('results/runs/' + parent + '/formal_v1/C_T0/K1')
        view.bind('provenance/runs/' + parent + '/formal_v1/final_audit.json')
        (view.path / 'results').mkdir(exist_ok=True)
        native = view.path / '.superpowers/native'
        native.mkdir(parents=True, exist_ok=True)
        command = ['clang++', '-O3', '-std=c++17', '-shared', '-fPIC', '-ffp-contract=off',
                   str(view.path / 'src/data3001/modelling/markov_models/_neighbour_scoring.cpp'),
                   '-o', str(native / 'neighbour_scoring.dylib')]
        compiled = subprocess.run(command, capture_output=True, text=True, timeout=60)
        (view.directory / 'native_build.json').write_text(json.dumps(dict(command=command, returncode=compiled.returncode,
            stdout=compiled.stdout, stderr=compiled.stderr), indent=2) + '\n')
        compiled.check_returncode()
        view.save_inventory()
        run_command(view, ['-B', '-m', 'unittest', 'discover', '-s', 'tests', '-q'],
                    label='Unmodified scientific test suite', timeout=600)
        return view.finish('complete', task='verification.scientific_tests', final_test_access=False)
    except BaseException as error:
        view.finish('failed', task='verification.scientific_tests', error=str(error))
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-id')
    args = parser.parse_args()
    print(json.dumps(run(Path(__file__).resolve().parents[2], args.run_id), indent=2))
