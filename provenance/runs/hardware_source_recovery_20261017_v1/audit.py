"""Replay the approved source audit. This script never writes active data."""
from collections import Counter, defaultdict
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
import csv
import hashlib
import json
import math

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).resolve().parent
FIELDS = ('DragAreaAboveDrogue', 'DragAreaOfDrogue', 'DragAreaRatio',
          'DrogueBallast', 'DrogueCenterDepth', 'DrogueLength', 'FloatDiameter')
SOURCE_FIELDS = {'DragAreaAboveDrogue': 'Drag Area Above Drogue(m2)',
                 'DragAreaOfDrogue': 'Drag Area of Drogue(m2)',
                 'DragAreaRatio': 'Drag Ratio', 'DrogueBallast': 'Drogue Ballast(kg)',
                 'DrogueCenterDepth': 'Drogue Center Depth(m)',
                 'DrogueLength': 'Drogue Length(m)', 'FloatDiameter': 'Float Diameter(cm)'}


def sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(8 << 20), b''):
            digest.update(chunk)
    return digest.hexdigest()


def load_source(name, expected_width):
    with (RUN/'sources'/name).open(newline='') as stream:
        reader = csv.DictReader(stream); header = reader.fieldnames
        assert len(header) == expected_width
        data = [row for row in reader if row['DirFL ID'].strip().isdigit()]
    result = defaultdict(list)
    for row in data:
        assert None not in row
        result[row['DirFL ID'].strip()].append(row)
    return header, result


def number(text):
    try:
        value = float(text.strip())
    except (TypeError, ValueError):
        return None
    return value if math.isfinite(value) else None


def norm(text):
    return str(text or '').strip().casefold()


def usable_key(text):
    return norm(text) not in ('', 'unknown', 'na', 'nan', 'none', '?')


def write_csv(path, columns, rows):
    with path.open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader(); writer.writerows(rows)


def main():
    inventory = json.loads((RUN/'inventory.json').read_text())
    manifest_path = ROOT/'configs/dataset_manifest.json'
    manifest = json.loads(manifest_path.read_text())
    assert sha(manifest_path) == inventory['manifest_sha256']
    assert sha(ROOT/'docs/contract/data_contract_v1.0.xlsx') == inventory['contract_sha256']
    # Source receipts must identify the actual inspected bytes, not just URLs.
    sources = {}
    for receipt_path in sorted((RUN/'sources').glob('*.receipt.json')):
        receipt = json.loads(receipt_path.read_text()); stem = receipt_path.name[:-13]
        candidates = [RUN/'sources'/(stem+ext) for ext in ('.html', '.txt', '.pdf')]
        content = next(p for p in candidates if p.exists())
        assert sha(content) == receipt['sha256']
        sources[stem] = receipt
    dh, drifters = load_source('drifter_specifications_csv_retry.txt', 10)
    gh, drogues = load_source('drogue_specifications_csv.txt', 13)
    assert set(SOURCE_FIELDS.values()).issubset(gh)
    # Compare CSV columns/order/rows to an independently parsed HTML snapshot.
    html_consistency = {}
    for label, header, source in [('drifter', dh, drifters), ('drogue', gh, drogues)]:
        html = json.loads((RUN/'sources'/f'{label}_specifications.rows.json').read_text())
        hindex = defaultdict(list)
        for row in html:
            hindex[row[0]].append(row)
        for item in inventory['records']:
            sid = item['id']
            assert [[r[c] for c in header] for r in source.get(sid, [])] == hindex.get(sid, [])
        html_consistency[label] = True
    directory = defaultdict(list)
    for line in unescape((RUN/'sources/directory.html').read_text()).splitlines():
        tokens = line.split()
        if len(tokens) >= 21 and tokens[0].isdigit() and tokens[1].isdigit():
            directory[tokens[0]].append(line.strip())
    outcomes = []; field_rows = []; evidence = []
    exact = conflicts = aliases = 0
    for item in inventory['records']:
        sid = item['id']; local = item['values']; errors = []; checks = []
        manufacturer = local['BuoyTypeManufacturer_text'].strip()
        model = local['BuoyTypeSensorArray_text'].strip()
        drows = drifters.get(sid, []); grows = drogues.get(sid, [])
        exact_match = len(drows) == len(grows) == 1
        candidate_sid = sid
        if exact_match:
            exact += 1; checks.append('exact_ID_in_both_official_specification_tables')
        else:
            # Suffix matches are search candidates only; they are NEVER a join rule.
            candidate_sid = str(int(sid[-8:]))
            drows = drifters.get(candidate_sid, []); grows = drogues.get(candidate_sid, [])
            aliases += 1; errors.append('no_explicit_cross_identifier_mapping; suffix_not_accepted')
        if len(drows) != 1:
            errors.append('official_drifter_candidate_row_count:'+str(len(drows)))
        if len(grows) != 1:
            errors.append('official_drogue_candidate_row_count:'+str(len(grows)))
        drow = drows[0] if len(drows) == 1 else None
        grow = grows[0] if len(grows) == 1 else None
        if drow and grow:
            if local['WMO'] > 0:
                observed = str(local['WMO'])
                if drow['WMO'].strip() == grow['WMO'].strip() == observed:
                    checks.append('positive_WMO_agrees_in_both_tables')
                else:
                    errors.append('WMO_disagreement:' + observed + '/' + drow['WMO'] + '/' + grow['WMO'])
            else:
                errors.append('native_WMO_unavailable_as_independent_identity_evidence')
            for name, current, official in [('manufacturer', manufacturer, drow['Manufacturer']),
                                            ('model', model, drow['Sensor Type'])]:
                if not usable_key(current):
                    errors.append('native_'+name+'_not_recorded')
                elif norm(current) == norm(official):
                    checks.append(name+'_agrees')
                else:
                    errors.append(name+'_disagreement:'+str(current)+'/'+str(official))
            for field in FIELDS:
                current = local[field]; source = number(grow[SOURCE_FIELDS[field]])
                if current is not None and source is not None:
                    if not math.isclose(current, source, rel_tol=1e-5, abs_tol=1e-4):
                        errors.append('known_'+field+'_disagreement:'+str(current)+'/'+str(source))
            present = norm(grow['Subsurface Float Presence'])
            if present in ('yes', 'no'):
                official_presence = int(present == 'yes')
                if local['SubsfcFloatPresence'] != official_presence:
                    errors.append('SubsfcFloatPresence_disagreement:'+str(local['SubsfcFloatPresence'])+'/'+str(official_presence))
        if exact_match and any('disagreement' in e for e in errors):
            conflicts += 1
        status = 'official_target_fields_empty' if exact_match else 'cross_identifier_candidate_not_accepted'
        native_row = {'id': sid, 'pool': item['pool'], 'manufacturer': manufacturer, 'model': model,
                      'drogue_type': local['DrogueType_text'], 'WMO': local['WMO'],
                      'missing_fields': ';'.join(item['missing_fields']), 'exact_source_ID_match': exact_match,
                      'candidate_source_ID': candidate_sid, 'official_manufacturer': drow['Manufacturer'] if drow else '',
                      'official_model': drow['Sensor Type'] if drow else '',
                      'official_configuration_code': drow['Buoy Type'] if drow else '',
                      'disposition': status, 'identity_and_configuration_checks': ';'.join(checks),
                      'unresolved_evidence': ';'.join(errors), 'restored_fields': 0}
        outcomes.append(native_row)
        for field in item['missing_fields']:
            raw = grow[SOURCE_FIELDS[field]] if grow else ''
            value = number(raw)
            if not exact_match:
                reason = 'unverified_cross_identifier_candidate'
            elif not raw.strip():
                reason = 'official_per_ID_value_also_empty'
            elif value is None or value < 0:
                reason = 'official_value_unusable'
            elif value == 0:
                reason = 'zero_not_accepted_without_explicit_applicable_semantics'
            elif errors:
                reason = 'identity_or_configuration_unresolved'
            else:
                raise AssertionError('A newly recoverable positive value needs a reviewed restoration step')
            field_rows.append({'id': sid, 'pool': item['pool'], 'feature': field, 'current_value': 'NA',
                               'candidate_source_ID': candidate_sid, 'source_raw_value': raw,
                               'source_value_positive': value is not None and value > 0,
                               'decision': 'retain_NA', 'reason': reason,
                               'identity_and_configuration_notes': ';'.join(errors)})
        evidence.append({'id': sid, 'native_record': item, 'source_candidate_ID': candidate_sid,
                         'exact_ID_match': exact_match, 'drifter_rows': drows, 'drogue_rows': grows,
                         'directory_rows': directory.get(candidate_sid, []), 'checks': checks, 'unresolved': errors})
    assert len(outcomes) == 210 and len(field_rows) == 481
    assert all(r['decision'] == 'retain_NA' for r in field_rows)
    assert sum(r['source_value_positive'] for r in field_rows) == 7
    assert exact == 191 and aliases == 19
    write_csv(RUN/'per_ID_audit.csv', list(outcomes[0]), outcomes)
    write_csv(RUN/'per_field_audit.csv', list(field_rows[0]), field_rows)
    (RUN/'evidence.json').write_text(json.dumps(evidence, indent=2, allow_nan=False)+'\n')
    # No publication step: accepted restoration set is empty. Verify every active
    # trajectory and current manifest still refer to precisely the original bytes.
    for n, record in enumerate(manifest['records'].values(), 1):
        assert sha(ROOT/record['path']) == record['sha256']
        if n % 1000 == 0:
            print(f'Preserved current file hashes {n}/{manifest["IDs"]}', flush=True)
    summary = {'complete': True, 'release_unchanged': manifest['version'], 'IDs_audited': 210,
               'ID_field_missing_cases': 481, 'exact_ID_specification_matches': exact,
               'exact_ID_matches_with_a_disagreement': conflicts,
               'nonexact_ID_candidates_not_accepted': aliases,
               'accepted_restoration_IDs': 0, 'accepted_restoration_fields': 0,
               'all_missing_cases_remain_NA': True, 'new_feature_columns': [],
               'all_3741_current_file_hashes_unchanged': True, 'active_rows': manifest['rows'],
               'active_columns': manifest['fields'],
               'field_dispositions': dict(Counter(r['reason'] for r in field_rows)),
               'source_CSV_HTML_checks': html_consistency,
               'source_receipts': sources, 'contract_sha256': inventory['contract_sha256'],
               'forecast_accuracy_evaluated': False,
               'no_universal_absence_claim': 'No accepted values in inspected sources; this does not prove no records exist elsewhere.'}
    (RUN/'summary.json').write_text(json.dumps(summary, indent=2)+'\n')
    print(json.dumps({k: v for k, v in summary.items() if k != 'source_receipts'}, indent=2), flush=True)


if __name__ == '__main__':
    main()
