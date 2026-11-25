#!/usr/bin/env python3
"""Offline core nf-test review. Only explicit ingest/promote can write expectations.

Expected values live in test/core/expected/<N>_<sample_id>.yaml (one file per
sample, matched by sample_id). Check titles and value types come from
test/core/schema.yaml. Workflow outputs are evaluated only by
CoreAssertions.groovy; this tool reads its JSON evidence.
"""
import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import html
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import tempfile
from urllib.parse import quote
import xml.etree.ElementTree as ET

import yaml

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent.parent
EXPECTED = ROOT / 'expected'
SELENIUM = ROOT.parent / 'selenium/expected'
STATUSES = {'passed', 'failed', 'error', 'unbaselined', 'delegated', 'not_checked'}
FLAGS = ('A', 'B', 'C', 'D', 'E', 'NA', 'ERR')
STATES = ('assessed', 'not_assessed', 'null', 'NA')


# ---------------------------------------------------------------- shared data

def digest(path):
    path = Path(path)
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None


def ownership_digest():
    value = hashlib.sha256()
    for path in sorted(SELENIUM.glob('*.yaml')):
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


def load_schema(path=ROOT / 'schema.yaml'):
    schema = yaml.safe_load(Path(path).read_text())
    if not isinstance(schema, dict) or schema.get('schema_version') != 2:
        raise ValueError('Unsupported test/core/schema.yaml')
    schema['by_id'] = {c['id']: c for c in schema['components']}
    schema['check_component'] = {check: c['id'] for c in schema['components'] for check in (c.get('checks') or {})}
    return schema


SCHEMA = load_schema()


def key(component, group, name, assertion):
    return f'{component}/{group}/{name}/{assertion}' if group else f'{component}/{assertion}'


def value_valid(kind, value):
    if kind == 'membership':
        return (isinstance(value, list) and all(isinstance(x, str) and x for x in value)
                and len(value) == len(set(value)))
    if kind == 'fingerprints':
        return isinstance(value, dict) and all(
            isinstance(k, str) and k and isinstance(v, str) and re.fullmatch(r'[0-9a-f]{16}', v)
            for k, v in value.items())
    if kind == 'flag':
        return value in FLAGS
    if kind == 'state':
        return value in STATES
    return False


def check_title(row):
    """Plain-language label and rule for a row (invariant or data value)."""
    component = SCHEMA['by_id'].get(row.get('component'), {})
    if row.get('kind') is None:
        check = (component.get('checks') or {}).get(row['id'], {})
        return check.get('title', row['id']), check.get('rule', row.get('rule', ''))
    definition = (component.get('assertions') or {}).get(row.get('assertion'), {})
    title = definition.get('title', row.get('assertion', row['id']))
    if row.get('group'):
        title = f"{title} — {row['group']} {row['name']}"
    return title, SCHEMA['types'].get(row.get('kind'), '')


def evidence(path):
    data = read_json(path)
    if not isinstance(data, dict) or data.get('schema_version') != 2:
        raise ValueError('Unsupported assertion evidence schema (expected version 2; re-evaluate older runs)')
    run = data.get('run', {})
    if not isinstance(run, dict) or not all(isinstance(run.get(k), str) and run[k] for k in ('id', 'source_test', 'evaluated_at')):
        raise ValueError('Missing run identity/provenance')
    if type(run.get('execution_success')) is not bool or type(run.get('complete')) is not bool:
        raise ValueError('Missing execution/completeness state')
    for name in ('contract_sha256', 'schema_sha256', 'ownership_sha256'):
        val = data.get(name)
        if name not in data or (val is not None and (not isinstance(val, str) or len(val) != 64)):
            raise ValueError(f'Invalid {name}')
    files = data.get('expectations')
    if not isinstance(files, dict) or not all(
            v is None or isinstance(v, dict) and isinstance(v.get('sha256'), str) for v in files.values()):
        raise ValueError('Invalid per-sample expectation digests')
    rows = data.get('rows')
    if not isinstance(rows, list) or not rows:
        raise ValueError('No assertion rows: evaluation is incomplete')
    seen = set()
    for row in rows:
        if not isinstance(row, dict) or not all(isinstance(row.get(k), str) and row[k] for k in ('sample', 'id', 'field', 'owner', 'component')):
            raise ValueError('Missing sample/assertion/field/owner/component')
        ident = (row['sample'], row['id'])
        if ident in seen:
            raise ValueError(f'Duplicate assertion key: {ident}')
        seen.add(ident)
        if row.get('status') not in STATUSES or type(row.get('promotable')) is not bool:
            raise ValueError(f'Invalid assertion status: {ident}')
        if not isinstance(row.get('artifacts'), list) or not all(isinstance(x, str) for x in row['artifacts']):
            raise ValueError(f'Invalid artifacts: {ident}')
        if row['promotable']:
            component = SCHEMA['by_id'].get(row['component'], {})
            definition = (component.get('assertions') or {}).get(row.get('assertion'))
            group = row.get('group')
            group_ok = (group in (component.get('groups') or []) and bool(row.get('name'))) if group else not row.get('name')
            if (row['owner'] != 'core' or not definition or definition.get('stored') is False
                    or definition['type'] != row.get('kind') or not group_ok
                    or row['id'] != key(row['component'], row.get('group'), row.get('name'), row['assertion'])):
                raise ValueError(f'Only defined core data expectations are promotable: {ident}')
            if row['status'] not in {'passed', 'failed', 'unbaselined'}:
                raise ValueError(f'Incomplete/malformed observation: {ident}')
            if row.get('absent'):
                if row['status'] != 'failed' or row.get('observed') is not None:
                    raise ValueError(f'Incomplete/malformed observation: {ident}')
            elif 'observed' not in row or not value_valid(row['kind'], row['observed']):
                raise ValueError(f'Incomplete/malformed observation: {ident}')
    return data


# ---------------------------------------------------------- per-sample files

def sample_files(expected_dir):
    """sample_id -> path for every YAML file in expected_dir."""
    found = {}
    for path in sorted(Path(expected_dir).glob('*.yaml')):
        doc = yaml.safe_load(path.read_text()) or {}
        sid = doc.get('sample_id') if isinstance(doc, dict) else None
        if not isinstance(sid, str) or not sid:
            raise ValueError(f'{path.name}: missing sample_id')
        if sid in found:
            raise ValueError(f'{path.name}: duplicate sample_id {sid} (also {found[sid].name})')
        found[sid] = path
    return found


def new_file_name(sample, expected_dir):
    """Reuse the Selenium fixture number for the same sample, else the next unused number."""
    safe = re.sub(r'[\s/\\]+', '_', sample)
    for path in sorted(SELENIUM.glob('*.yaml')):
        doc = yaml.safe_load(path.read_text()) or {}
        number = re.match(r'(\d+)_', path.name)
        if doc.get('sample_id') == sample and number:
            return f'{number.group(1)}_{safe}.yaml'
    used = [int(m.group(1)) for d in (SELENIUM, Path(expected_dir)) for p in d.glob('*.yaml')
            if (m := re.match(r'(\d+)_', p.name))]
    return f'{max(used, default=0) + 1}_{safe}.yaml'


def resolve_target(target, expected_dir):
    """Selenium-style target: number prefix, file stem/name, or sample_id."""
    files = sample_files(expected_dir)
    for sid, path in files.items():
        if (target.isdigit() and path.name.startswith(target + '_')) or target in (path.name, path.stem, sid):
            return sid
    raise ValueError(f'No expectation file for {target!r} in {expected_dir}')


def set_value(doc, row):
    """Insert or replace one value, keeping schema order for components and assertions."""
    order = [c['id'] for c in SCHEMA['components']]
    components = doc.setdefault('components', [])
    comp = next((c for c in components if c.get('id') == row['component']), None)
    if comp is None:
        comp = {'id': row['component']}
        components.append(comp)
        components.sort(key=lambda c: order.index(c['id']))
    if row.get('group'):
        items = comp.setdefault(row['group'], [])
        item = next((i for i in items if i.get('name') == row['name']), None)
        if item is None:
            item = {'name': row['name'], 'assertions': []}
            items.append(item)
            items.sort(key=lambda i: i['name'])
        target = item.setdefault('assertions', [])
    else:
        target = comp.setdefault('assertions', [])
    value = row['observed']
    if row['kind'] == 'membership':
        value = sorted(value)
    entry = {'id': row['assertion'], 'type': row['kind'], 'value': value}
    names = list((SCHEMA['by_id'][row['component']].get('assertions') or {}))
    target[:] = [a for a in target if a.get('id') != row['assertion']] + [entry]
    target.sort(key=lambda a: names.index(a['id']) if a['id'] in names else len(names))
    # Keep `assertions` before group keys for readability.
    ordered = {'id': comp['id']}
    if 'assertions' in comp:
        ordered['assertions'] = comp['assertions']
    ordered.update({k: v for k, v in comp.items() if k not in ordered})
    comp.clear()
    comp.update(ordered)


def remove_value(doc, row):
    for comp in doc.get('components', []):
        if comp.get('id') != row['component']:
            continue
        if row.get('group'):
            for item in comp.get(row['group'], []):
                if item.get('name') == row['name']:
                    item['assertions'] = [a for a in item.get('assertions', []) if a.get('id') != row['assertion']]
            comp[row['group']] = [i for i in comp.get(row['group'], []) if i.get('assertions')]
            if not comp[row['group']]:
                del comp[row['group']]
        else:
            comp['assertions'] = [a for a in comp.get('assertions', []) if a.get('id') != row['assertion']]
            if not comp['assertions']:
                del comp['assertions']
    doc['components'] = [c for c in doc.get('components', []) if len(c) > 1]


class _Dumper(yaml.SafeDumper):
    pass


# SnakeYAML (Groovy side) reads e.g. 12345e678 as a float even where PyYAML would not.
_NUMBER_LIKE = re.compile(r'[-+]?(\.[0-9]+|[0-9_]+(\.[0-9_]*)?)([eE][-+]?[0-9]+)?|[0-9a-f]{16}')


def _represent_str(dumper, value):
    style = "'" if _NUMBER_LIKE.fullmatch(value) else None
    return dumper.represent_scalar('tag:yaml.org,2002:str', value, style=style)


_Dumper.add_representer(str, _represent_str)


def dump(doc):
    return yaml.dump(doc, Dumper=_Dumper, sort_keys=False, allow_unicode=True, width=4096, default_flow_style=False)


# ------------------------------------------------------------ ingest/promote

def describe_change(row):
    """Short old -> new description used by prompts and the review page."""
    old, new, kind = row.get('expected'), row.get('observed'), row.get('kind')
    if row.get('absent'):
        return 'expected entry no longer observed → remove it'
    if old is None:
        if kind == 'membership':
            return f'new list of {len(new)}: {", ".join(new[:20])}{" …" if len(new) > 20 else ""}'
        if kind == 'fingerprints':
            return f'new fingerprints for {len(new)} sequences'
        return f'new value {new!r}'
    if kind == 'membership':
        added, removed = sorted(set(new) - set(old)), sorted(set(old) - set(new))
        return '; '.join(p for p in (
            f'+{len(added)} added: {", ".join(added[:20])}{" …" if len(added) > 20 else ""}' if added else '',
            f'−{len(removed)} removed: {", ".join(removed[:20])}{" …" if len(removed) > 20 else ""}' if removed else '') if p)
    if kind == 'fingerprints':
        changed = sorted(k for k in set(old) & set(new) if old[k] != new[k])
        added, removed = sorted(set(new) - set(old)), sorted(set(old) - set(new))
        parts = [f'{len(changed)} sequences changed: {", ".join(changed[:20])}' if changed else '',
                 f'+{len(added)} added' if added else '', f'−{len(removed)} removed' if removed else '']
        return '; '.join(p for p in parts if p)
    return f'{old!r} → {new!r}'


def _sample_blockers(rows, sample):
    return [r for r in rows if r['sample'] in (sample, '_run') and r.get('kind') is None
            and r['status'] in ('failed', 'error')]


def update(mode, assertions, expected_dir=EXPECTED, target=None, all_samples=False, sample=None,
           component=None, assertion=None, dry_run=False, reason=None, ask=input):
    expected_dir = Path(expected_dir)
    data = evidence(assertions)
    rows = data['rows']
    if not data['run']['complete'] or not data['run']['execution_success'] or any(r['status'] == 'error' for r in rows):
        raise ValueError('Execution failure or incomplete evaluation cannot supply expectations')
    if data['contract_sha256'] != digest(ROOT / 'CoreAssertions.groovy'):
        raise ValueError('Stale assertion code; evaluate again before accepting data')
    if data['schema_sha256'] != digest(ROOT / 'schema.yaml'):
        raise ValueError('Stale schema; evaluate again before accepting data')
    if data['ownership_sha256'] != ownership_digest():
        raise ValueError('Stale Selenium ownership; evaluate again before accepting data')

    files = sample_files(expected_dir) if expected_dir.exists() else {}
    if mode == 'promote':
        samples = sorted(files) if all_samples else [resolve_target(target, expected_dir)]
    else:
        samples = [s for s in data['expectations']] if all_samples else [sample]
    explicit = not all_samples
    selected = {}
    for sid in samples:
        if sid not in data['expectations']:
            raise ValueError(f'Sample {sid} was not evaluated in this run')
        blockers = _sample_blockers(rows, sid)
        if blockers:
            message = (f'Invariant failures for {sid} cannot supply an accepted baseline '
                       f'({", ".join(sorted({b["id"] for b in blockers}))}); resolve them and evaluate again')
            if explicit:
                raise ValueError(message)
            print('Skipping: ' + message)
            continue
        recorded = (data['expectations'][sid] or {}).get('sha256')
        current = digest(files[sid]) if sid in files else None
        if current != recorded:
            raise ValueError(f'Stale expectations for {sid}: its file changed since evaluation; evaluate again')
        matching = [r for r in rows if r['sample'] == sid and r['promotable']
                    and (component is None or r['component'] == component)
                    and (assertion is None or assertion in (r['id'], r['assertion']))]
        if assertion is not None and explicit:
            if mode == 'ingest' and any(r['status'] != 'unbaselined' for r in matching):
                raise ValueError('Existing key: use promote instead of ingest')
            if mode == 'promote' and any(r['status'] == 'unbaselined' for r in matching):
                raise ValueError('Missing key: use ingest instead of promote')
        if matching:
            selected[sid] = [r for r in matching if r['status'] == ('unbaselined' if mode == 'ingest' else 'failed')]
    if not selected:
        raise ValueError('No matching promotable core observations')

    accepted = defaultdict(list)
    quit_all = False
    for sid, candidates in selected.items():
        accept_rest = False
        for row in candidates:
            title, _ = check_title(row)
            print(f"{sid} / {row['id']}  ({title})\n  {describe_change(row)}")
            if dry_run:
                continue
            if quit_all:
                break
            choice = 'y' if accept_rest else ask('Accept? [y]es / [n]o / [a]ll in this sample / [q]uit ').strip().lower()
            if choice == 'a':
                accept_rest, choice = True, 'y'
            if choice == 'q':
                quit_all = True
                break
            if choice == 'y':
                accepted[sid].append(row)
        print(f"  source run: {data['run']['id']} evaluated: {data['run']['evaluated_at']}")
    if dry_run or not accepted:
        return 0
    reason = (reason or ask('Reason for accepting these changes: ')).strip()
    if not reason:
        raise ValueError('A review reason is required; nothing written')

    expected_dir.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc)
    writes = []
    for sid, changes in accepted.items():
        path = files.get(sid) or expected_dir / new_file_name(sid, expected_dir)
        doc = yaml.safe_load(path.read_text()) if path.exists() else {'sample_id': sid}
        for row in changes:
            (remove_value if row.get('absent') else set_value)(doc, row)
        doc['date'] = data['run']['evaluated_at']
        doc['provenance'] = {'source_run': data['run']['id'], 'source_test': data['run']['source_test'],
                             'evaluated_at': data['run']['evaluated_at'], 'accepted_at': now.isoformat(),
                             'reason': reason}
        ordered = {'sample_id': sid, 'date': doc['date'], 'provenance': doc['provenance'],
                   'components': doc.get('components', [])}
        writes.append((path, (data['expectations'][sid] or {}).get('sha256'), dump(ordered)))
    # Check freshness of every file immediately before replacing any of them.
    for path, original, _ in writes:
        if digest(path) != original:
            raise ValueError('Expectations changed during review; nothing written')
    stamp = now.strftime('%Y%m%dT%H%M%S.%fZ')
    backups = expected_dir / '.backups'
    for path, _, encoded in writes:
        with tempfile.NamedTemporaryFile(mode='w', dir=expected_dir, prefix='.expected-', delete=False) as stream:
            temporary = Path(stream.name)
            try:
                stream.write(encoded)
                stream.flush()
                os.fsync(stream.fileno())
                if path.exists():
                    backups.mkdir(exist_ok=True)
                    shutil.copy2(path, backups / f'{path.stem}.{stamp}.yaml')
                os.replace(temporary, path)
            finally:
                temporary.unlink(missing_ok=True)
        for old in sorted(backups.glob(f'{path.stem}.*.yaml'))[:-3]:
            old.unlink()
        print(f'Wrote {path}')
    return sum(len(v) for v in accepted.values())


# -------------------------------------------------------------------- render

CSS = """
*{box-sizing:border-box}body{font-family:-apple-system,system-ui,sans-serif;margin:0;color:#1f2937;background:#f9fafb;line-height:1.45}
header{background:#111827;color:#f9fafb;padding:1.25rem 2rem}header h1{margin:0 0 .25rem;font-size:1.3rem}
header .meta{font-size:.85rem;opacity:.8}main{padding:1.5rem 2rem;max-width:1300px;margin:0 auto}
h2{font-size:1.1rem;margin:2rem 0 .6rem}h3{font-size:.95rem;margin:1rem 0 .3rem}p.hint{color:#6b7280;font-size:.85rem;margin:.2rem 0 .8rem}
.verdict{display:inline-block;padding:.2rem .7rem;border-radius:999px;font-weight:700;margin-left:.5rem;font-size:.95rem}
.v-PASSED{background:#16a34a}.v-FAILED,.v-INVALID{background:#dc2626}.v-DRIFT{background:#d97706}
.v-NEEDS{background:#2563eb}.v-INCOMPLETE{background:#ea580c}
.health{display:flex;gap:.6rem;flex-wrap:wrap}.health div{background:#fff;border-radius:6px;padding:.55rem .8rem;
box-shadow:0 1px 2px rgba(0,0,0,.06);font-size:.85rem;border-left:4px solid #16a34a;max-width:24rem}
.health div.bad{border-left-color:#dc2626}.health div.warn{border-left-color:#d97706}.health b{display:block}
table{width:100%;border-collapse:collapse;background:#fff;box-shadow:0 1px 2px rgba(0,0,0,.05);font-size:.85rem}
th,td{text-align:left;padding:.45rem .7rem;border-bottom:1px solid #e5e7eb;vertical-align:top}th{background:#f3f4f6}
td small,.id{color:#6b7280;font-size:.75rem;font-family:ui-monospace,monospace}
tr.s-error td:first-child{border-left:3px solid #ea580c}tr.s-failed td:first-child{border-left:3px solid #dc2626}
tr.s-drift td:first-child{border-left:3px solid #d97706}tr.s-unbaselined td:first-child{border-left:3px solid #2563eb}
.badge{display:inline-block;padding:.1rem .5rem;border-radius:999px;font-size:.72rem;font-weight:600;text-transform:uppercase}
.b-error{background:#ffedd5;color:#9a3412}.b-failed{background:#fee2e2;color:#991b1b}.b-drift{background:#fef3c7;color:#92400e}
.b-unbaselined{background:#dbeafe;color:#1e40af}.b-passed{background:#dcfce7;color:#166534}
table.matrix td,table.matrix th{text-align:center;white-space:nowrap}table.matrix td:first-child,table.matrix th:first-child{text-align:left}
.c-bad{background:#fee2e2}.c-new{background:#dbeafe}.c-ok{color:#166534}.c-none{color:#d1d5db}
details{background:#fff;margin:.75rem 0;padding:0 1rem;border-radius:6px;box-shadow:0 1px 2px rgba(0,0,0,.06)}
details summary{cursor:pointer;padding:.7rem 0;font-weight:600}details table{box-shadow:none;margin-bottom:.8rem}
details.tech{box-shadow:none;padding:0;margin:.3rem 0;background:transparent}details.tech summary{font-weight:400;font-size:.75rem;color:#6b7280;padding:.1rem 0}
pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#f3f4f6;padding:.5rem .7rem;margin:.3rem 0;font-size:.8rem;border-radius:4px}
.links a{color:#2563eb;margin-right:.8rem;font-size:.82rem}.missing{color:#9ca3af;font-size:.8rem}
.area{background:#fff;border-radius:6px;padding:.6rem 1rem;margin:.6rem 0;box-shadow:0 1px 2px rgba(0,0,0,.06)}
.area ul{margin:.3rem 0 .3rem 1.1rem;padding:0;font-size:.85rem}.area .files{font-size:.8rem;color:#4b5563}
"""

VERDICT_TEXT = {
    'PASSED': 'Every core check passed.',
    'FAILED': 'A rule check failed. This suggests a workflow bug: find the cause; rule failures cannot be promoted.',
    'DRIFT': 'Some stored values differ from test/core/expected/. This is only a suggestion of drift: the tool cannot '
             'tell why a value changed. Check each change; promote it only if it is expected.',
    'NEEDS BASELINE': 'Some samples or values have no stored expectations yet. Review them, then ingest.',
    'INCOMPLETE': 'The run or its evaluation did not complete; results are partial.',
    'INVALID EVIDENCE': 'The assertion evidence is missing or unreadable; nothing can be trusted as passed.',
}
# How a problem is labelled. The label comes only from the kind of check, never from why it broke.
LABEL_NOTE = ('Labels are a suggestion, not a diagnosis. "Rule failed" means a rule check broke (structure, routing, '
              'valid values): these must always hold, so a workflow bug is the likely cause. "Possible drift" means a '
              'stored value differs from test/core/expected/: new reference data (GenBank, BOLD, GBIF) is a common cause, '
              'but a regression looks the same. The tool cannot tell which; check each change before promoting.')
BADGE = {'unbaselined': 'needs baseline', 'drift': 'possible drift', 'failed': 'rule failed'}
HIDDEN = ('delegated', 'not_checked')   # owned by Selenium: shown in the Selenium review, not here
DATA_NEXT = {'failed': 'The stored value no longer matches (possible drift, not confirmed). Compare with the reference run '
                       'or the linked file: promote only if the change is expected (for example new reference data), '
                       'otherwise treat it as a regression.',
             'unbaselined': 'No stored value yet. Check the observed value, then ingest it.',
             'absent': 'The stored value is no longer produced. If that is expected, promote to remove it.'}


def _esc(value):
    return html.escape(str(value), quote=True)


def _slug(text):
    return 'sample-' + re.sub(r'[^A-Za-z0-9_-]+', '-', text)


def _short(value, limit=160):
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    return text if len(text) <= limit else text[:limit] + '…'


def split_diagnostic(text):
    """(message, technical detail): Groovy power asserts append '. Expression: …' to the message."""
    text = str(text or '').strip()
    for marker in ('. Expression:', '\nExpression:'):
        if marker in text:
            head, tail = text.split(marker, 1)
            return head.rstrip(), 'Expression:' + tail
    return text, ''


def parse_message(text):
    """Split '<where>: <rule>\nExpected: …\nActual: …[\nDifference: …]' into parts."""
    message, technical = split_diagnostic(text)
    if re.fullmatch(r'Expression: ok\. Values: ok = false\.?', technical.strip()):
        technical = ''                     # holds() boilerplate: Expected/Actual already say everything
    parts = {'headline': '', 'expected': None, 'actual': None, 'difference': None, 'technical': technical}
    lines = message.splitlines()
    for line in lines[1:]:
        for label in ('Expected', 'Actual', 'Difference'):
            if line.startswith(label + ': '):
                parts[label.lower()] = line[len(label) + 2:]
    if parts['expected'] is None and parts['actual'] is None:
        parts['actual'] = message          # older or unexpected message: show it whole
    else:
        parts['headline'] = lines[0] if lines else ''
    return parts


def check_info(row):
    """Plain-language fields for a row from schema.yaml."""
    component = SCHEMA['by_id'].get(row.get('component'), {})
    if row.get('kind') is None:
        check = (component.get('checks') or {}).get(row['id'], {})
        return {'title': check.get('title', row['id']), 'explain': check.get('explain') or check.get('rule', row.get('rule', '')),
                'on_fail': check.get('on_fail', '')}
    definition = (component.get('assertions') or {}).get(row.get('assertion'), {})
    title = definition.get('title', row.get('assertion', row['id']))
    if row.get('group'):
        title = f"{title} — {row['group']} {row['name']}"
    return {'title': title, 'explain': definition.get('explain', ''),
            'on_fail': DATA_NEXT['absent' if row.get('absent') else row['status']] if row['status'] in DATA_NEXT else ''}


def _value(value, limit=200):
    """Print a value as it is: strings quoted, lists/maps as JSON."""
    if value is None:
        return 'null'
    text = json.dumps(value, ensure_ascii=False) if not isinstance(value, (int, float)) else str(value)
    return text if len(text) <= limit else text[:limit] + '…'


def difference(row):
    """'missing …; unexpected …' for lists, changed accessions for fingerprints, else None."""
    old, new, kind = row.get('expected'), row.get('observed'), row.get('kind')
    if old is None or new is None:
        return None
    if kind == 'membership':
        return f'missing {_value(sorted(set(old) - set(new)), 120)}; unexpected {_value(sorted(set(new) - set(old)), 120)}'
    if kind == 'fingerprints':
        changed = sorted(k for k in set(old) & set(new) if old[k] != new[k])
        return (f'changed {_value(changed, 120)}; missing {_value(sorted(set(old) - set(new)), 80)}; '
                f'unexpected {_value(sorted(set(new) - set(old)), 80)}')
    return None


def expected_actual(row):
    """Expected / Actual / Difference / technical detail for any row."""
    if row.get('kind') is None:
        return parse_message(row.get('diagnostic') or 'Check failed.')
    parts = {'headline': f"{row['id']}: stored value", 'technical': ''}
    parts['expected'] = 'no stored value' if row['status'] == 'unbaselined' else _value(row.get('expected'))
    parts['actual'] = 'not produced' if row.get('absent') else _value(row.get('observed'))
    parts['difference'] = difference(row)
    if row['kind'] == 'fingerprints' and row['status'] == 'failed':
        parts['technical'] = _sequence_diff(row)
    return parts


def one_line(row):
    p = expected_actual(row)
    text = f"expected {p['expected']}, actual {p['actual']}" if p['expected'] is not None else p['actual']
    if p['difference']:
        text += f" ({p['difference']})"
    rule = p['headline'].split(': ', 1)[-1] if p['headline'] else ''
    return _short(f'{rule} — {text}' if rule else text, 300)


def _sequence_diff(fingerprint_row, limit=5):
    """Observed sequences behind changed fingerprints (old sequences are not stored, only their fingerprints)."""
    old, new, detail = fingerprint_row.get('expected') or {}, fingerprint_row.get('observed') or {}, fingerprint_row.get('detail') or {}
    lines = []
    for accession in sorted(set(new) | set(old)):
        if old.get(accession) == new.get(accession):
            continue
        if len(lines) >= limit:
            lines.append('…')
            break
        sequence = detail.get(accession, '')
        lines.append(f"{accession}: {old.get(accession, 'absent')} → {new.get(accession, 'absent')}"
                     + (f"  (observed length {len(sequence)}: {sequence[:80]}{'…' if len(sequence) > 80 else ''})" if sequence else ''))
    return '\n'.join(lines)


def _junit(junit):
    """(health entry, diagnostics, invalid) for the native JUnit file."""
    try:
        root = ET.parse(junit).getroot()
        if root.tag not in {'testsuites', 'testsuite', 'testcase'}:
            raise ET.ParseError('Not a JUnit document')
        cases = [root] if root.tag == 'testcase' else list(root.iter('testcase'))
        if not cases:
            return ('bad', 'JUnit XML', 'No executed test cases'), [], True
        for suite in root.iter('testsuite'):
            if suite.get('tests') is not None and int(suite.get('tests')) != len(list(suite.iter('testcase'))):
                return ('bad', 'JUnit XML', 'Declared test count differs from retained cases'), [], True
        diagnostics, failed = [], False
        for case in cases:
            if case.get('status', '').upper() in {'FAILED', 'ERROR', 'SKIPPED'}:
                failed = True
            for tag in ('failure', 'error', 'skipped'):
                for node in case.findall(tag):
                    failed = True
                    diagnostics.append(f"{tag}: {case.get('name', '<unnamed>')}\n" + node.get('message', '') + '\n' + ''.join(node.itertext()))
        return (('warn' if failed else 'ok'), 'JUnit XML', 'nf-test reported a failure' if failed else 'nf-test reported success'), diagnostics, False
    except (OSError, ET.ParseError, ValueError) as exc:
        return ('bad', 'JUnit XML', f'Missing/invalid: {exc}'), [], True


def _analyse(junit, assertions):
    """Everything the page and the summary need, independent of output format."""
    junit_health, diagnostics, junit_invalid = _junit(junit)
    health = [junit_health]
    data, rows, run, evidence_error = None, [], {}, None
    if assertions is None:
        evidence_error = 'Structured assertion evidence unavailable (legacy run)'
    else:
        try:
            data = evidence(assertions)
            run = data['run']
            rows = [r for r in data['rows'] if r['status'] not in HIDDEN]
        except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
            evidence_error = f'Missing/invalid assertion evidence: {exc}'
    statuses = Counter(r['status'] for r in rows)
    invariant_failed = any(r.get('kind') is None and r['status'] == 'failed' for r in rows)
    drift = any(r.get('kind') and r['status'] == 'failed' for r in rows)
    incomplete = bool(data) and (not run['complete'] or not run['execution_success'] or statuses['error'] > 0)
    if evidence_error:
        verdict = 'INVALID EVIDENCE'
    elif incomplete or junit_invalid:
        verdict = 'INCOMPLETE'
    elif invariant_failed or junit_health[0] == 'warn' and not (drift or statuses['unbaselined']):
        verdict = 'FAILED'
    elif drift:
        verdict = 'DRIFT'
    elif statuses['unbaselined']:
        verdict = 'NEEDS BASELINE'
    else:
        verdict = 'PASSED'
    if evidence_error:
        health.insert(0, ('bad', 'Assertion evidence', evidence_error))
    else:
        ok = run['complete'] and not statuses['error']
        health.insert(0, ('ok' if run['execution_success'] else 'bad', 'Workflow execution',
                          'Succeeded' if run['execution_success'] else 'Workflow failed'))
        health.insert(1, ('ok' if ok else 'bad', 'Evaluation', f'{len(rows)} core checks evaluated'
                          + ('' if ok else f"; {statuses['error']} could not be evaluated")))
        files = data['expectations']
        with_file = sum(1 for v in files.values() if v)
        health.append(('ok' if with_file == len(files) else 'warn', 'Expectation files',
                       f'{with_file} of {len(files)} samples have test/core/expected/*.yaml'))
    samples = (['_run'] + list(run.get('samples') or [])) if rows else []
    samples += sorted({r['sample'] for r in rows} - set(samples))

    attention = []   # (level, sample, title, id, label, message)
    for r in rows:
        if r['status'] == 'error' or r['status'] == 'failed' and r.get('kind') is None:
            attention.append((0 if r['status'] == 'error' else 1, r['sample'], check_info(r)['title'], r['id'],
                              'error' if r['status'] == 'error' else 'failed', one_line(r)))
    by_drift = defaultdict(list)
    for r in rows:
        if r.get('kind') and r['status'] == 'failed':
            by_drift[(r['sample'], r['component'])].append(r)
    for (sid, comp), items in by_drift.items():
        summary = '; '.join(f"{check_info(r)['title']}: {one_line(r)}" for r in items[:2])
        attention.append((2, sid, SCHEMA['by_id'][comp]['title'], comp, 'drift',
                          _short(f'{len(items)} stored value(s) changed. {summary}', 300)))
    baseline = Counter(r['sample'] for r in rows if r['status'] == 'unbaselined')
    for sid, count in baseline.items():
        has_file = bool((data or {}).get('expectations', {}).get(sid))
        attention.append((3, sid, 'Stored expectations', '', 'unbaselined',
                          f'{count} value(s) have no stored expectation yet'
                          + ('.' if has_file else ' (this sample has no expectation file).')))
    attention.sort(key=lambda a: (a[0], samples.index(a[1]) if a[1] in samples else 0, a[2]))
    return dict(verdict=verdict, health=health, diagnostics=diagnostics, run=run, rows=rows, samples=samples,
                statuses=statuses, attention=attention, groups=_failure_groups(rows, samples),
                invalid=junit_invalid or bool(evidence_error))


def _base_title(row):
    """Check title without the per-taxon/per-file suffix, so the same check groups across samples."""
    if row.get('kind') is None:
        return check_info(row)['title']
    definition = (SCHEMA['by_id'].get(row.get('component'), {}).get('assertions') or {}).get(row.get('assertion'), {})
    return definition.get('title', row.get('assertion', row['id']))


def _failure_groups(rows, samples):
    """Problems grouped by kind and area across samples (e.g. drift in Database coverage), most serious first."""
    groups = {}
    for r in rows:
        if r['status'] not in ('error', 'failed', 'unbaselined'):
            continue
        label = 'drift' if r.get('kind') and r['status'] == 'failed' else r['status']
        g = groups.setdefault((label, r.get('component')), dict(
            level={'error': 0, 'failed': 1, 'drift': 2, 'unbaselined': 3}[label], label=label,
            area=SCHEMA['by_id'].get(r.get('component'), {}).get('title', r.get('component') or 'Run'),
            samples=[], checks=Counter(), count=0, example=None))
        g['count'] += 1
        g['checks'][_base_title(r)] += 1
        if r['sample'] not in g['samples']:
            g['samples'].append(r['sample'])
        if g['example'] is None:
            g['example'] = (r['sample'], one_line(r))
    for g in groups.values():
        g['samples'].sort(key=lambda s: samples.index(s) if s in samples else len(samples))
    return sorted(groups.values(), key=lambda g: (g['level'], -len(g['samples']), -g['count'], g['area']))


def _what_is_checked():
    """Static reference: what each area checks (from schema.yaml; no per-run results)."""
    parts = ['<details><summary>What this test checks</summary>',
             '<p class="hint">One core workflow run over the samples in test/core/metadata.csv. <b>Rule checks</b> must always '
             'hold; a failure is a bug and cannot be promoted. <b>Stored values</b> are compared with '
             'test/core/expected/&lt;N&gt;_&lt;sample&gt;.yaml and can be promoted after review. A value belongs to Selenium for a '
             'sample when that sample\'s Selenium fixture (test/selenium/expected/) has a non-empty expected value for it; core '
             'then neither compares it nor re-checks that it exists and is valid.</p>']
    for comp in SCHEMA['components']:
        parts.append(f'<div class="area"><h3>{_esc(comp["title"])} <small class="id">{_esc(comp["channel"])}</small></h3>'
                     f'<div>{_esc(comp.get("description", ""))}</div>'
                     f'<div class="files">Files: {_esc(comp.get("files", ""))} — written by {_esc(comp.get("producer", ""))}</div>')
        checks = comp.get('checks') or {}
        if checks:
            parts.append('<b style="font-size:.85rem">Rule checks</b><ul>' + ''.join(
                f'<li><b>{_esc(c["title"])}</b>: {_esc(c.get("explain", c.get("rule", "")))}</li>' for c in checks.values()) + '</ul>')
        stored = [a for a in (comp.get('assertions') or {}).values() if a.get('stored') is not False]
        if stored:
            parts.append('<b style="font-size:.85rem">Stored values compared</b><ul>' + ''.join(
                f'<li><b>{_esc(a["title"])}</b>: {_esc(a.get("explain", ""))}</li>' for a in stored) + '</ul>')
        parts.append('</div>')
    parts.append('</details>')
    return ''.join(parts)


def _page(a, linker, assertions_arg):
    run, rows, samples, statuses = a['run'], a['rows'], a['samples'], a['statuses']
    components = [c['id'] for c in SCHEMA['components']]
    verdict = a['verdict']
    parts = ['<!doctype html><html lang="en"><meta charset="utf-8">',
             '<meta name="viewport" content="width=device-width,initial-scale=1"><title>Core nf-test review</title>',
             f'<style>{CSS}</style><header><h1>Core nf-test review <span class="verdict v-{verdict.split()[0]}">{_esc(verdict)}</span></h1>',
             f'<div class="meta">{_esc(VERDICT_TEXT[verdict])}<br>Run {_esc(run.get("id", "unavailable"))} · '
             f'evaluated {_esc(run.get("evaluated_at", "unavailable"))} · revision {_esc(run.get("revision", "unknown"))} · '
             f'references {_esc(", ".join(f"{k}={v}" for k, v in (run.get("references") or {}).items()) or "unknown")}</div></header><main>',
             '<h2>Run health</h2><div class="health">']
    parts += [f'<div class="{"bad" if s == "bad" else "warn" if s == "warn" else ""}"><b>{_esc(t)}</b>{_esc(m)}</div>' for s, t, m in a['health']]
    parts.append('</div>')

    attention = a['attention']
    parts.append(f'<h2>Needs attention ({len(attention)})</h2>')
    if attention:
        parts.append('<p class="hint">Most serious first: errors, rule failures (fix the cause), possible drift (review, then promote '
                     'if expected), missing expectations (review, then ingest). Click a sample for the full explanation.</p>'
                     f'<p class="hint"><b>How labels are chosen:</b> {_esc(LABEL_NOTE)}</p>')
        parts.append('<table><tr><th>Sample</th><th>Check</th><th>What went wrong</th></tr>')
        for _level, sid, title, _ident, label, message in attention:
            badge = BADGE.get(label, label)
            parts.append(f'<tr class="s-{label}"><td><a href="#{_slug(sid)}">{_esc(sid)}</a></td>'
                         f'<td><span class="badge b-{label}">{_esc(badge)}</span> {_esc(title)}</td><td>{_esc(message)}</td></tr>')
        parts.append('</table>')
    else:
        parts.append('<p class="hint">Nothing to review.</p>')

    groups = a['groups']
    if groups:
        parts.append(f'<h2>Failure analysis ({len(groups)})</h2><p class="hint">The same problems grouped by kind and area across '
                     'samples, most serious first, then by how many samples share them. Use it to spot one cause behind many '
                     'rows above.</p>')
        parts.append('<table><tr><th>Problem</th><th>Samples</th><th>Checks involved</th><th>Example</th></tr>')
        for g in groups:
            badge = BADGE.get(g['label'], g['label'])
            shown = ', '.join(f'<a href="#{_slug(s)}">{_esc(s)}</a>' for s in g['samples'][:20])
            more = f' … and {len(g["samples"]) - 20} more' if len(g['samples']) > 20 else ''
            checks = '<br>'.join(f'{_esc(t)} <small>×{n}</small>' for t, n in g['checks'].most_common(8))
            if len(g['checks']) > 8:
                checks += f'<br><small>… and {len(g["checks"]) - 8} more checks</small>'
            sid, example = g['example']
            parts.append(f'<tr class="s-{g["label"]}"><td><span class="badge b-{g["label"]}">{_esc(badge)}</span> {_esc(g["area"])}'
                         f'<br><small>{g["count"]} result(s) in {len(g["samples"])} sample(s)</small></td>'
                         f'<td>{shown}{more}</td><td>{checks}</td><td><small>{_esc(sid)}:</small> {_esc(_short(example, 200))}</td></tr>')
        parts.append('</table>')

    if rows:
        parts.append('<h2>Samples × checks</h2><p class="hint">✔ passed · ✖ failed · ? needs a baseline. '
                     'Click a highlighted sample to jump to its details.</p>')
        parts.append('<table class="matrix"><tr><th>Sample</th>' + ''.join(
            f'<th title="{_esc(SCHEMA["by_id"][c]["channel"])}">{_esc(SCHEMA["by_id"][c]["title"])}</th>' for c in components) + '</tr>')
        cells = defaultdict(Counter)
        for r in rows:
            cells[(r['sample'], r['component'])][r['status']] += 1
        problem_samples = {r['sample'] for r in rows if r['status'] in ('failed', 'error', 'unbaselined')}
        for sid in samples:
            name = f'<a href="#{_slug(sid)}">{_esc(sid)}</a>' if sid in problem_samples else _esc(sid)
            row_html = [f'<tr><td>{name}</td>']
            for comp in components:
                c = cells.get((sid, comp))
                if not c:
                    row_html.append('<td class="c-none">·</td>')
                    continue
                bad, new, ok = c['failed'] + c['error'], c['unbaselined'], c['passed']
                text = ' '.join(t for t in (f'✖ {bad}' if bad else '', f'? {new}' if new else '', f'✔ {ok}' if ok else '') if t)
                row_html.append(f'<td class="{"c-bad" if bad else "c-new" if new else "c-ok"}">{_esc(text)}</td>')
            parts.append(''.join(row_html) + '</tr>')
        parts.append('</table>')

        parts.append('<h2>Sample details</h2><p class="hint">Only samples with something to review are shown.</p>')
        for sid in samples:
            problems = [r for r in rows if r['sample'] == sid and r['status'] in ('failed', 'error', 'unbaselined')]
            if not problems:
                continue
            problems.sort(key=lambda r: ({'error': 0, 'failed': 1, 'unbaselined': 2}[r['status']] + (0 if r.get('kind') is None else 0.5),
                                         components.index(r['component']) if r['component'] in components else 99, r['id']))
            parts.append(f'<details open id="{_slug(sid)}"><summary>{_esc(sid)} — {len(problems)} to review</summary>')
            parts.append('<table><tr><th>Check</th><th>Expected</th><th>Actual</th><th>Next step</th></tr>')
            shown = 0
            for r in problems:
                if r['status'] == 'unbaselined' and shown >= 40:
                    continue
                shown += r['status'] == 'unbaselined'
                info = check_info(r)
                status = 'drift' if r.get('kind') and r['status'] == 'failed' else r['status']
                badge = BADGE.get(status, status)
                p = expected_actual(r)
                actual = _esc(p['actual'])
                if p['difference']:
                    actual += f'<div class="id">Difference: {_esc(p["difference"])}</div>'
                if p['technical']:
                    actual += f'<details class="tech"><summary>Technical detail</summary><pre>{_esc(p["technical"])}</pre></details>'
                parts.append(f'<tr class="s-{status}"><td><span class="badge b-{status}">{_esc(badge)}</span> {_esc(info["title"])}'
                             f'<br><span class="id">{_esc(p["headline"] or r["id"])}</span></td>'
                             f'<td><code>{_esc(p["expected"] if p["expected"] is not None else info["explain"])}</code></td>'
                             f'<td><code>{actual}</code></td><td>{_esc(info["on_fail"])}</td></tr>')
            hidden = sum(1 for r in problems if r['status'] == 'unbaselined') - shown
            if hidden > 0:
                parts.append(f'<tr><td colspan="4" class="missing">… and {hidden} more values without expectations (use ingest --dry-run to list them all).</td></tr>')
            parts.append('</table>')
            links, missing = [], set()
            for artifact in sorted({x for r in problems for x in r['artifacts']}):
                href = linker(sid, artifact)
                (links.append(f'<a href="{_esc(href)}">{_esc(Path(artifact).name)}</a>') if href else missing.add(Path(artifact).name))
            if links:
                parts.append('<div class="links">Files: ' + ''.join(links) + '</div>')
            if missing:
                parts.append(f'<div class="missing">Not in this bundle (unavailable in bundle): {_esc(", ".join(sorted(missing)))}</div>')
            if sid != '_run':
                if any(r['promotable'] and r['status'] == 'failed' for r in problems):
                    parts.append('<pre>' + _esc(shlex.join(['python', 'test/core/testkit.py', 'promote', sid, '--assertions', assertions_arg, '--dry-run'])) + '</pre>')
                if any(r['status'] == 'unbaselined' for r in problems):
                    parts.append('<pre>' + _esc(shlex.join(['python', 'test/core/testkit.py', 'ingest', '--sample', sid, '--assertions', assertions_arg, '--dry-run'])) + '</pre>')
            parts.append('</details>')

    parts.append('<h2>Reference</h2>')
    parts.append('<details><summary>Commands</summary><pre>'
                 + _esc('# Rerun core (see test/core/README.md for the core nf-test.config):\n'
                        'nf-test test -c <core.nf-test.config> test/core/taxodactyl.assertions.nf.test --ci --junitxml <run>/nf-test.xml\n'
                        f"python test/core/testkit.py render --junit <run>/nf-test.xml --assertions {assertions_arg} --output <run>/nf-test-review.html\n"
                        f'python test/core/testkit.py promote --all --assertions {assertions_arg} --dry-run\n'
                        f'python test/core/testkit.py ingest --all --assertions {assertions_arg} --dry-run')
                 + '</pre></details>')
    parts.append(_what_is_checked())
    parts.append('<details><summary>Channel legend</summary><table>' + ''.join(
        f'<tr><td><b>{_esc(k)}</b></td><td>{_esc(v)}</td></tr>' for k, v in SCHEMA['channels'].items()) + '</table></details>')
    if a['diagnostics']:
        parts.append('<details><summary>Native nf-test diagnostics</summary>' + ''.join(f'<pre>{_esc(d)}</pre>' for d in a['diagnostics']) + '</details>')
    parts.append(f'<p class="hint">Rendering never changes test results or expectations. Totals: '
                 f'{_esc(" · ".join(f"{n} {s}" for s, n in sorted(statuses.items())) or "none")}</p></main></html>')
    return '\n'.join(parts) + '\n'


def _local_linker(base, output):
    def link(_sample, artifact):
        path = Path(artifact)
        path = path if path.is_absolute() else base / path
        # Lexical check (symlinked retained files stay inside the bundle's tree). Never expose params.
        try:
            Path(os.path.abspath(path)).relative_to(os.path.abspath(base))
        except ValueError:
            return None
        if not path.is_file() or 'params' in path.name.lower():
            return None
        return quote(os.path.relpath(path, output.parent), safe='/')
    return link


def _summary(a, page_name):
    """Short Markdown for the GitHub Actions job summary."""
    cell = lambda t: str(t).replace('|', '\\|').replace('\n', ' ')
    lines = [f"## Core nf-test: {a['verdict']}", '', VERDICT_TEXT[a['verdict']], '']
    if a['groups']:
        lines += [f'> {LABEL_NOTE}', '']
    lines += [f"- **{t}:** {m}" for _s, t, m in a['health']]
    lines += ['', f"### Needs attention ({len(a['attention'])})", '']
    if a['attention']:
        lines += ['| Sample | Check | What went wrong |', '|---|---|---|']
        for _level, sid, title, _ident, label, message in a['attention'][:50]:
            lines.append(f"| {cell(sid)} | {cell(BADGE.get(label, label))}: {cell(title)} | {cell(_short(message, 240))} |")
        if len(a['attention']) > 50:
            lines.append(f"\n… and {len(a['attention']) - 50} more.")
    else:
        lines.append('Nothing to review.')
    if a['groups']:
        lines += ['', f"### Failure analysis ({len(a['groups'])})", '',
                  '| Problem | Samples | Checks involved |', '|---|---|---|']
        for g in a['groups']:
            badge = BADGE.get(g['label'], g['label'])
            names = ', '.join(g['samples'][:10]) + (f" … and {len(g['samples']) - 10} more" if len(g['samples']) > 10 else '')
            checks = '; '.join(f'{t} ×{n}' for t, n in g['checks'].most_common(5))
            lines.append(f"| {cell(badge)}: {cell(g['area'])} ({g['count']}) | {cell(names)} | {cell(checks)} |")
    lines += ['', f'Full explanations: download the `{page_name}` artifact (page only), or the `nf-test-review` '
              f'artifact (zip with copies of the files behind each failure) and open `{page_name}` inside it.', '']
    return '\n'.join(lines)


def _bundle(a, bundle_dir, junit, assertions, include, assertions_arg):
    """Self-contained copy: page, evidence, logs and the files read by failing checks (no symlinks)."""
    bundle_dir = Path(bundle_dir)
    bundle_dir.mkdir(parents=True, exist_ok=True)
    base = Path(assertions).parent if assertions else Path(junit).parent
    copied = {}

    def link(sample, artifact):
        if (sample, artifact) in copied:
            return copied[(sample, artifact)]
        path = Path(artifact)
        path = path if path.is_absolute() else base / path
        if not path.is_file() or 'params' in path.name.lower():
            return None
        # Index prefix keeps names unique even on case-insensitive filesystems.
        target = bundle_dir / 'files' / re.sub(r'[^A-Za-z0-9_.-]+', '_', sample) / f'{len(copied) + 1:03d}-{path.name}'
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)   # follows symlinks: ordinary files only
        copied[(sample, artifact)] = quote(target.relative_to(bundle_dir).as_posix(), safe='/')
        return copied[(sample, artifact)]

    page = _page(a, link, assertions_arg)
    (bundle_dir / 'nf-test-review.html').write_text(page)
    for source in [junit, assertions, *include]:
        if source and Path(source).is_file():
            shutil.copyfile(source, bundle_dir / Path(source).name)
    return bundle_dir / 'nf-test-review.html'


def render(junit, output, assertions=None, summary=None, bundle_dir=None, include=()):
    output = Path(output)
    a = _analyse(junit, assertions)
    base = Path(assertions).parent if assertions else Path(junit).parent
    assertions_arg = os.path.relpath(assertions) if assertions else '<run>/nf-test-assertions.json'
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(_page(a, _local_linker(base, output), assertions_arg))
    if bundle_dir:
        _bundle(a, bundle_dir, junit, assertions, include, assertions_arg)
    if summary:
        Path(summary).write_text(_summary(a, 'nf-test-review.html'))
    # Rendering evidence of a failed test is successful rendering. Invalid input is an error.
    return 2 if a['invalid'] else 0


# ----------------------------------------------------------------------- CLI

def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    subs = parser.add_subparsers(dest='command', required=True)
    p = subs.add_parser('render', help='Write the HTML review page from retained evidence')
    p.add_argument('--junit', type=Path, required=True)
    p.add_argument('--assertions', type=Path)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--summary', type=Path, help='also write a short Markdown summary (e.g. for $GITHUB_STEP_SUMMARY)')
    p.add_argument('--bundle-dir', type=Path, help='also write a self-contained copy (page, evidence, failing files) here')
    p.add_argument('--include', type=Path, nargs='*', default=[], help='extra files (logs) to copy into --bundle-dir')
    for mode in ('ingest', 'promote'):
        p = subs.add_parser(mode, help=('Add missing expectations (new samples or new values)' if mode == 'ingest'
                                        else 'Accept reviewed changes to existing expectations'))
        scope = p.add_mutually_exclusive_group(required=True)
        if mode == 'ingest':
            scope.add_argument('--sample', help='sample_id to ingest')
        else:
            scope.add_argument('target', nargs='?', help='file number (e.g. 1), file stem, or sample_id')
        scope.add_argument('--all', action='store_true', help='every eligible sample')
        p.add_argument('--assertions', type=Path, required=True)
        p.add_argument('--component', help='limit to one component, e.g. database_coverage')
        p.add_argument('--assertion', help='limit to one value: full id or assertion name')
        p.add_argument('--dry-run', action='store_true')
        p.add_argument('--reason')
        p.add_argument('--expected-dir', type=Path, default=EXPECTED, help='Use a disposable directory for toolkit demonstrations')
    args = parser.parse_args()
    try:
        if args.command == 'render':
            return render(args.junit, args.output, args.assertions, args.summary, args.bundle_dir, args.include)
        count = update(args.command, args.assertions, args.expected_dir,
                       target=getattr(args, 'target', None), all_samples=args.all,
                       sample=getattr(args, 'sample', None), component=args.component,
                       assertion=args.assertion, dry_run=args.dry_run, reason=args.reason)
        print(f'{count} reviewed expectation(s) written. Rerun the affected checks; original evidence is unchanged.')
        return 0
    except (OSError, ValueError, TypeError, KeyError, yaml.YAMLError) as exc:
        parser.exit(2, f'Error: {exc}\n')


if __name__ == '__main__':
    raise SystemExit(main())
