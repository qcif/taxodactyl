#!/usr/bin/env python3
"""Offline core nf-test review. Only explicit ingest/promote can write expectations."""
import argparse
from datetime import datetime, timezone
from collections import Counter
import hashlib
import html
import json
import os
import re
from pathlib import Path
import shlex
import shutil
import tempfile
from urllib.parse import quote
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent
STATUSES = {'passed', 'failed', 'error', 'unbaselined', 'delegated'}
KINDS = {'membership', 'sequence', 'count', 'flag', 'state'}
DATA_RULES = {
    'membership': r'(H\.membership|C\.phylogeny\.membership|M\.membership|S\.membership/.+|D\.membership/(candidate|toi|pmi)(/.+/(related|country))?)',
    'sequence': r'H\.sequence/[^/]+',
    'count': r'D\.count/(candidate|toi|pmi)/.+/(target|(related|country)/.+)',
    'state': r'D\.state/(candidate|toi|pmi)/.+/(target|related|country)',
    'flag': r'(C\.flag\.[127]\.value|S\.flag/.+|F\.value/5\.[123]/(candidate|toi|pmi)/.+)',
}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None


def ownership_digest():
    value = hashlib.sha256()
    for path in sorted((ROOT.parent/'selenium/expected').glob('*.yaml')):
        value.update(path.name.encode())
        value.update(path.read_bytes())
    return value.hexdigest()


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f'Duplicate JSON key: {key}')
        result[key] = value
    return result


def read_json(path):
    return json.loads(Path(path).read_text(), object_pairs_hook=unique_object,
                      parse_constant=lambda x: (_ for _ in ()).throw(ValueError(x)))


def value_valid(kind, value):
    if kind == 'count':
        return value is None or type(value) is int and value >= 0
    if kind == 'flag':
        return value in ('A', 'B', 'C', 'D', 'E', 'NA', 'ERR')
    if kind == 'state':
        return value in ('missing', 'null', 'NA', 'assessed', 'not_assessed', 'empty')
    if kind == 'membership':
        return (isinstance(value, list) and all(isinstance(x, str) and x for x in value)
                and len(value) == len(set(value)))
    if kind == 'sequence':
        return isinstance(value, str) and bool(value) and all(c in 'ACGTURYSWKMBDHVN-.' for c in value.upper())
    return False


def evidence(path):
    data = read_json(path)
    if not isinstance(data, dict) or data.get('schema_version') != 1:
        raise ValueError('Unsupported assertion evidence schema')
    run = data.get('run', {})
    if not isinstance(run, dict) or not all(isinstance(run.get(k), str) and run[k] for k in ('id', 'source_test', 'evaluated_at')):
        raise ValueError('Missing run identity/provenance')
    if type(run.get('execution_success')) is not bool or type(run.get('complete')) is not bool:
        raise ValueError('Missing execution/completeness state')
    for key in ('expectations_sha256', 'contract_sha256', 'ownership_sha256'):
        val = data.get(key)
        if key not in data or (val is not None and (not isinstance(val, str) or len(val) != 64)):
            raise ValueError(f'Invalid {key}')
    rows = data.get('rows')
    if not isinstance(rows, list) or not rows:
        raise ValueError('No assertion rows: evaluation is incomplete')
    seen = set()
    for row in rows:
        if not isinstance(row, dict) or not all(isinstance(row.get(k), str) and row[k] for k in ('sample', 'id', 'field', 'owner')):
            raise ValueError('Missing sample/assertion/field/owner')
        key = (row['sample'], row['id'])
        if key in seen:
            raise ValueError(f'Duplicate assertion key: {key}')
        seen.add(key)
        if row.get('status') not in STATUSES or type(row.get('promotable')) is not bool:
            raise ValueError(f'Invalid assertion status: {key}')
        if not isinstance(row.get('artifacts'), list) or not all(isinstance(x, str) for x in row['artifacts']):
            raise ValueError(f'Invalid artifacts: {key}')
        if row['promotable']:
            if (row['owner'] != 'core' or row.get('kind') not in KINDS
                    or not re.fullmatch(DATA_RULES[row['kind']], row['id'])):
                raise ValueError(f'Only defined core data expectations are promotable: {key}')
            if row['status'] not in {'passed', 'failed', 'unbaselined'} or 'observed' not in row or not value_valid(row['kind'], row['observed']):
                raise ValueError(f'Incomplete/malformed observation: {key}')
    return data


def expectations(path):
    if not path.exists():
        return {'schema_version': 1, 'entries': {}}
    result = read_json(path)
    if not isinstance(result, dict) or result.get('schema_version') != 1 or not isinstance(result.get('entries'), dict):
        raise ValueError('Malformed expectation file')
    for sample, entries in result['entries'].items():
        if not isinstance(entries, dict):
            raise ValueError(f'Malformed expectation entries for {sample}')
        for key, entry in entries.items():
            if not isinstance(entry, dict) or 'value' not in entry:
                raise ValueError(f'Malformed expectation entry: {sample}/{key}')
    return result


def update(mode, assertions, target=ROOT / 'expectations.json', sample=None,
           assertion=None, dry_run=False, reason=None, ask=input):
    target = Path(target)
    data = evidence(assertions)
    if not data['run']['complete'] or not data['run']['execution_success'] or any(r['status'] == 'error' for r in data['rows']):
        raise ValueError('Execution failure or incomplete evaluation cannot supply expectations')
    if data['contract_sha256'] != digest(ROOT / 'CoreAssertions.groovy'):
        raise ValueError('Stale assertion code; evaluate again before accepting data')
    if any(not r['promotable'] and r['status'] in ('failed', 'error') for r in data['rows']):
        raise ValueError('Invariant failures cannot supply an accepted baseline; resolve them and evaluate again')
    if data['ownership_sha256'] != ownership_digest():
        raise ValueError('Stale Selenium ownership; evaluate again before accepting data')
    original_digest = digest(target)
    if data['expectations_sha256'] != original_digest:
        raise ValueError('Stale expectations digest; evaluate again before accepting data')
    current = expectations(target)
    selected = [r for r in data['rows'] if r['promotable']
                and (sample is None or r['sample'] == sample)
                and (assertion is None or r['id'] == assertion)]
    if not selected:
        raise ValueError('No matching promotable core observations')
    changes = []
    for row in selected:
        old = current['entries'].get(row['sample'], {}).get(row['id'])
        if mode == 'ingest' and old is not None:
            if assertion is not None:
                raise ValueError('Existing key: use promote instead of ingest')
            continue
        if mode == 'promote' and old is None:
            if assertion is not None:
                raise ValueError('Missing key: use ingest instead of promote')
            continue
        if old is not None and old['value'] == row['observed']:
            continue
        print(f"{row['sample']} / {row['id']} ({row['field']})\n  {old['value'] if old else '<absent>'!r} -> {row['observed']!r}")
        print(f"  source run: {data['run']['id']} evaluated: {data['run']['evaluated_at']}")
        if not dry_run and ask('Accept this value? [y/N] ').strip().lower() == 'y':
            changes.append(row)
    if dry_run or not changes:
        return 0
    reason = reason or ask('Reason for accepting these changes: ').strip()
    if not reason or not reason.strip():
        raise ValueError('A review reason is required; nothing written')
    for row in changes:
        current['entries'].setdefault(row['sample'], {})[row['id']] = {
            'value': row['observed'], 'kind': row['kind'], 'field': row['field'],
            'reason': reason, 'run': data['run'],
            'accepted_at': datetime.now(timezone.utc).isoformat(),
        }
    target.parent.mkdir(parents=True, exist_ok=True)
    # Serialize first, then check freshness again immediately before replacing.
    encoded = json.dumps(current, indent=2, ensure_ascii=False, allow_nan=False) + '\n'
    with tempfile.NamedTemporaryFile(mode='w', dir=target.parent, prefix='.expectations-', delete=False) as stream:
        temporary = Path(stream.name)
        try:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
            if digest(target) != original_digest:
                raise ValueError('Expectations changed during review; nothing written')
            if target.exists():
                backups = target.parent / '.backups'
                backups.mkdir(exist_ok=True)
                name = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')
                shutil.copy2(target, backups / f'{target.stem}-{name}.json')
            os.replace(temporary, target)
        finally:
            temporary.unlink(missing_ok=True)
    backups = target.parent / '.backups'
    if backups.exists():
        for old in sorted(backups.glob(f'{target.stem}-*.json'))[:-3]:
            old.unlink()
    return len(changes)


def render(junit, output, assertions=None):
    output = Path(output)
    problems, diagnostics, rows, run = [], [], [], {}
    try:
        root = ET.parse(junit).getroot()
        if root.tag not in {'testsuites', 'testsuite', 'testcase'}:
            raise ET.ParseError('Not a JUnit document')
        cases = ([root] if root.tag == 'testcase' else list(root.iter('testcase')))
        if not cases:
            problems.append('No executed JUnit test cases')
        for suite in root.iter('testsuite'):
            if suite.get('tests') is not None and int(suite.get('tests')) != len(list(suite.iter('testcase'))):
                problems.append('Missing/invalid JUnit XML: declared test count differs from retained cases')
        for case in cases:
            if case.get('status', '').upper() in {'FAILED', 'ERROR', 'SKIPPED'}:
                problems.append(f"{case.get('status')}: {case.get('name', '<unnamed>')}")
            for tag in ('failure', 'error', 'skipped'):
                for node in case.findall(tag):
                    problems.append(f"{tag}: {case.get('name', '<unnamed>')}")
                    diagnostics.append(node.get('message', '') + '\n' + ''.join(node.itertext()))
    except (OSError, ET.ParseError, ValueError) as exc:
        problems.append(f'Missing/invalid JUnit XML: {exc}')
    if assertions is not None:
        try:
            data = evidence(assertions)
            rows, run = data['rows'], data['run']
            if not run['complete'] or not run['execution_success']:
                problems.append('Execution error or incomplete assertion evaluation')
            if any(r['status'] not in ('passed', 'delegated') for r in rows):
                problems.append('Assertions failed or need reviewed expectations')
        except (OSError, ValueError, TypeError, KeyError) as exc:
            problems.append(f'Missing/invalid assertion evidence: {exc}')
    else:
        problems.append('Structured assertion evidence unavailable (legacy run)')
    esc = lambda x: html.escape(str(x), quote=True)
    status = 'REVIEW REQUIRED' if problems else 'PASSED'
    parts = ['<!doctype html><meta charset="utf-8"><title>Core nf-test review</title>',
             '<style>body{font:16px system-ui;max-width:1200px;margin:2rem auto;padding:1rem}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#f3f4f6;padding:1rem}table{border-collapse:collapse;width:100%}td,th{text-align:left;padding:.7rem;border:1px solid #ddd}summary{cursor:pointer}h1{color:#234}</style>',
             f'<h1>Core nf-test: {status}</h1>', '<p>Expected values require manual review. Rendering never changes test results.</p>',
             f'<p>Run: {esc(run.get("id", "unavailable"))} · Test: {esc(run.get("source_test", "unavailable"))}</p>']
    parts += [f'<p>{esc(p)}</p>' for p in problems]
    parts += [f'<pre>{esc(d)}</pre>' for d in diagnostics]
    base = Path(assertions).parent if assertions else Path(junit).parent
    totals = Counter(row['status'] for row in rows)
    parts.append('<p>' + esc(' · '.join(f'{count} {status}' for status, count in sorted(totals.items()))) + '</p>')
    current_sample = None
    for row in sorted(rows, key=lambda r: (r['sample'], r['id'])):
        if row['sample'] != current_sample:
            if current_sample is not None:
                parts.append('</details>')
            current_sample = row['sample']
            parts.append(f'<details><summary><strong>{esc(current_sample)}</strong></summary>')
        parts.append(f'<details{" open" if row["status"] in ("failed", "error") else ""}><summary>{esc(row["status"])} · {esc(row["sample"])} · {esc(row["id"])}</summary>')
        parts.append(f'<p>{esc(row["field"])} · Owner: {esc(row["owner"])}</p>')
        parts.append(f'<pre>Expected: {esc(json.dumps(row.get("expected"), ensure_ascii=False))}\nObserved: {esc(json.dumps(row.get("observed"), ensure_ascii=False))}\n{esc(row.get("diagnostic", ""))}</pre>')
        for artifact in row['artifacts']:
            path = Path(artifact)
            path = path if path.is_absolute() else base / path
            # Link only retained files inside the evidence bundle. Never expose params.
            try:
                path.resolve().relative_to(base.resolve())
                portable = path.is_file() and 'params' not in path.name.lower()
            except ValueError:
                portable = False
            if portable:
                href = quote(os.path.relpath(path, output.parent), safe='/')
                parts.append(f'<p><a href="{esc(href)}">{esc(path.name)}</a></p>')
            else:
                parts.append(f'<p>Artifact unavailable in bundle: {esc(path.name)}</p>')
        if row['promotable'] and row['status'] in ('unbaselined', 'failed'):
            mode = 'ingest' if row['status'] == 'unbaselined' else 'promote'
            command = ['python', 'test/core/testkit.py', mode]
            command += ['--sample', row['sample']] if mode == 'ingest' else [row['sample']]
            command += ['--assertions', os.path.relpath(assertions), '--assertion', row['id'], '--dry-run']
            parts.append(f'<pre>{esc(shlex.join(command))}</pre>')
        parts.append('</details>')
    if current_sample is not None:
        parts.append('</details>')
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text('\n'.join(parts) + '\n')
    # Rendering evidence of a failed test is successful rendering. Invalid input is an error.
    return 2 if any(p.startswith(('Missing/invalid', 'No executed', 'Structured assertion')) for p in problems) else 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest='command', required=True)
    p = subs.add_parser('render')
    p.add_argument('--junit', type=Path, required=True)
    p.add_argument('--assertions', type=Path)
    p.add_argument('--output', type=Path, required=True)
    for mode in ('ingest', 'promote'):
        p = subs.add_parser(mode)
        if mode == 'ingest':
            p.add_argument('--sample')
        else:
            p.add_argument('sample')
        p.add_argument('--assertions', type=Path, required=True)
        p.add_argument('--assertion')
        p.add_argument('--dry-run', action='store_true')
        p.add_argument('--reason')
        p.add_argument('--expectations', type=Path, default=ROOT / 'expectations.json', help='Use a disposable path for toolkit demonstrations')
    args = parser.parse_args()
    try:
        if args.command == 'render':
            return render(args.junit, args.output, args.assertions)
        count = update(args.command, args.assertions, args.expectations, args.sample,
                       args.assertion, args.dry_run, args.reason)
        print(f'{count} reviewed expectation(s) written. Rerun the affected checks; original evidence is unchanged.')
        return 0
    except (OSError, ValueError, TypeError, KeyError) as exc:
        parser.exit(2, f'Error: {exc}\n')


if __name__ == '__main__':
    raise SystemExit(main())
