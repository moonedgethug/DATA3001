"""Read-only project inspection and explicit, separate derived-data runs."""
import argparse
import json
import os
from pathlib import Path
from data3001.paths import project_paths, file_sha256


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, help='Project checkout containing configs/assets.json')
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('inspect', help='Read the catalog without opening large data')
    commands.add_parser('verify-migration', help='Read-only full audit of the active layout, retained bytes and labels')
    commands.add_parser('verify-data', help='Verify downloaded tracks and portable qualification evidence')
    pairs = commands.add_parser('pair', help='Generate independent endpoint/stopped labels; stdout by default')
    pairs.add_argument('--id', type=int, required=True)
    pairs.add_argument('--days', type=int, required=True)
    pairs.add_argument('--scenario', choices=['drogued','undrogued','pooled'], default='drogued')
    pairs.add_argument('--population', choices=['R','D'], default='R')
    pairs.add_argument('--tolerance', type=int, choices=[0,1,2,3,6], default=0)
    pairs.add_argument('--run-id', help='Save derived labels in a new, non-overwritable results run')
    args = parser.parse_args()
    if args.root:
        os.environ['DATA3001_PROJECT_ROOT'] = str(args.root)
        project_paths.cache_clear()
    paths = project_paths()
    if args.command == 'inspect':
        print(json.dumps({'research_contract_version':paths.catalog['research_contract_version'],
                          'status':paths.catalog.get('current_data_status'),
                          'assets':{key:{'path':value['path'],'role':value.get('role'),'split':value.get('split')}
                                    for key,value in paths.catalog['assets'].items()}},indent=2))
    elif args.command == 'verify-data':
        from data3001.dataset import verify_current_data
        print(json.dumps(verify_current_data(), indent=2))
    elif args.command == 'verify-migration':
        from data3001.migration import verify_all
        report = verify_all()
        print(json.dumps(report,indent=2,default=str))
        if not report['passed']:
            raise SystemExit(1)
    else:
        if not 1 <= args.days <= 365:
            parser.error('--days must be an integer from 1 through 365')
        from data3001.preprocessing.prep_io import Source, parquet, code_hash
        from data3001.preprocessing.prep_pairs import load_track, origin_indices, generate
        if 'current_dataset_manifest' in paths.catalog['assets']:
            from data3001.dataset import PreparedSource
            source = PreparedSource()
        else:
            source = Source()
        if source.cohort.loc[args.id,'split'] == 'test':
            parser.error('Final-test trajectories remain locked for this development entry point')
        frame, track, events = load_track(source,args.id)
        origins = origin_indices(frame,track,args.population)
        labels = generate(frame,track,events,args.id,origins,args.days,args.scenario,args.tolerance)
        summary = {'id':args.id,'split':source.cohort.loc[args.id,'split'],
                   'days':args.days,'scenario':args.scenario,'population':args.population,
                   'tolerance_hours':args.tolerance,'candidates':len(origins),
                   'eligible':{name:int((label.reason_code==0).sum())
                               for name,label in zip(['endpoint','stopped'],labels)},
                   'forecast_accuracy_evaluated':False}
        if args.run_id:
            from data3001.preprocessing.drogue_correction import prepared_track_path
            config = {**summary, 'contract_sha256':paths.catalog['contract_sha256'],
                      'source_snapshot_sha256':file_sha256(paths.asset('source_snapshot')),
                      'source_track_sha256':file_sha256(prepared_track_path(args.id,source.cohort.loc[args.id,'split'])),
                      'code_sha256':code_hash(),
                      'environment_lock_sha256':file_sha256(paths.root/'configs/requirements.lock.txt')}
            if 'current_dataset_manifest' in paths.catalog['assets']:
                from data3001.dataset import manifest
                config['dataset_release_version'] = manifest()['version']
                config['dataset_manifest_sha256'] = file_sha256(paths.asset('current_dataset_manifest',verify=True))
                config['recovery_cutoff_policy'] = 'typedeath=2: time <= numeric official end_date; recovery is censoring'
                config['recovery_cutoff_code_sha256'] = file_sha256(paths.root/'src/data3001/model_input_cleaning.py')
                if 'current_qualification_manifest' in paths.catalog['assets']:
                    config['qualification_manifest_sha256'] = file_sha256(
                        paths.asset('current_qualification_manifest', verify=True))
            if 'preparation_correction_version' in track:
                config['preparation_correction_version']=track['preparation_correction_version']
                correction_asset=track.get('preparation_correction_asset','official_drogue_correction')
                config['correction_manifest_sha256']=file_sha256(paths.asset(correction_asset))
                if correction_asset=='official_drogue_boundary':
                    overlay_asset='drogue_boundary_test' if source.cohort.loc[args.id,'split']=='test' else 'drogue_boundary_development'
                    if 'current_dataset_manifest' in paths.catalog['assets']:
                        # Labels are already materialized and bound by the current
                        # track hash. Keep the historical receipt without loading
                        # an unused old overlay from the private preparation cache.
                        config['historical_regime_overlay_sha256'] = paths.catalog['assets'][overlay_asset]['sha256']
                        config['regime_labels_source'] = 'materialized_current_track'
                    else:
                        config['regime_overlay_sha256']=file_sha256(paths.asset(overlay_asset))
            run = paths.create_run(args.run_id,config)
            for name,label in zip(['endpoint','stopped'],labels):
                parquet(label,run['results']/(name+'.parquet'))
            summary['run_id'] = args.run_id
        print(json.dumps(summary,indent=2))


if __name__ == '__main__':
    main()
