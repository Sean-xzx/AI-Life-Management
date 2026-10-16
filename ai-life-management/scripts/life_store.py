"""Local, append-only life-management records. Standard library only."""
from __future__ import annotations
import argparse
import copy
from datetime import date, datetime, timezone
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import uuid

CATEGORIES = {'confirmed_fact', 'user_report', 'user_preference', 'estimate',
              'ai_suggestion', 'user_decision', 'observed_result'}
OPERATIONS = {'profile', 'goal', 'action', 'decision', 'review', 'note'}
CATEGORY_LABELS = {'confirmed_fact': '已核实事实', 'user_report': '用户报告',
                   'user_preference': '个人偏好', 'estimate': '估计',
                   'ai_suggestion': 'AI 建议', 'user_decision': '用户决定',
                   'observed_result': '实际观察'}
STATUS_LABELS = {'active': '推进中', 'paused': '已暂停', 'stopped': '已停止',
                 'planned': '计划中', 'in_progress': '进行中',
                 'completed': '已完成', 'cancelled': '已取消'}
ID = re.compile(r'^[a-zA-Z0-9][a-zA-Z0-9_-]{0,79}$')
SKILL_ROOT = Path(__file__).resolve().parents[1]

class StoreError(ValueError):
    pass

def empty():
    return {'schema_version': 1, 'revision': 0, 'profile': {}, 'goals': {},
            'actions': {}, 'decisions': {}, 'reviews': {}, 'notes': {}}

def identifier(value, label):
    if not isinstance(value, str) or not ID.fullmatch(value):
        raise StoreError(f'Invalid {label}; use letters, digits, underscores or hyphens.')

def temporal(value, *, legacy=False):
    """Return a date or aware instant without inventing time precision.

    Only the known historical date-with-zone spelling is accepted on replay.
    New events must use an ISO date or timestamp with an explicit UTC offset.
    """
    if not isinstance(value, str):
        raise StoreError('Dates must be ISO dates or offset timestamps.')
    if legacy and re.fullmatch(r'\d{4}-\d{2}-\d{2} Asia/Shanghai', value):
        return date.fromisoformat(value[:10])
    if re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
        return date.fromisoformat(value)
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        raise StoreError('Timestamp requires a UTC offset; use YYYY-MM-DD if only the date is known.')
    return parsed


def record_key(event):
    return (event['operation'], event.get('key') or event.get('record_id'))


def validity(state, history):
    """Find current records whose declared source versions were superseded.

    This is derived metadata: it never rewrites the authoritative log/snapshot.
    Absence of dependencies is explicitly untracked, not proof of validity.
    """
    events = {item['event_id']: item for item in history}
    positions = {item['event_id']: index for index, item in enumerate(history)}
    latest = {record_key(item['event']): item['event_id'] for item in history}
    records = {('profile', key): record for key, record in state['profile'].items()}
    for bucket, op in [('goals', 'goal'), ('actions', 'action'), ('decisions', 'decision'),
                       ('reviews', 'review'), ('notes', 'note')]:
        records.update({(op, key): record for key, record in state[bucket].items()})
    stale = {}; visited = set()

    def check(key, stack):
        label = ':'.join(key)
        if label in stale: return True
        if key in stack:
            stale[label] = ['Dependency cycle']; return True
        if key in visited: return False
        reasons = []
        goal_key = ('goal', records[key].get('goal_id'))
        needs_goal_review = (records[key]['category'] == 'ai_suggestion' or
                             (key[0] == 'action' and records[key].get('status') in {'planned', 'in_progress'}))
        if (needs_goal_review and goal_key in latest and
                positions[latest[goal_key]] > positions[latest[key]]):
            reasons.append('Linked goal changed: ' + goal_key[1])
        for source in records[key].get('depends_on', []):
            item = events.get(source)
            if not item:
                reasons.append('Missing source: ' + source); continue
            source_key = record_key(item['event'])
            if latest.get(source_key) != source:
                reasons.append('Superseded source: ' + source)
            elif source_key in records and check(source_key, stack | {key}):
                reasons.append('Invalidated source: ' + source)
        visited.add(key)
        if reasons: stale[label] = reasons
        return bool(reasons)

    for key in records: check(key, set())
    return {'current_sources': {':'.join(key): value for key, value in latest.items()},
            'invalidated': stale,
            'untracked_derived': [':'.join(key) for key, record in records.items()
                                  if record['category'] in {'estimate', 'ai_suggestion'}
                                  and not record.get('depends_on')]}


def validate(event, state, *, historical=False):
    if not isinstance(event, dict):
        raise StoreError('Event must be a JSON object.')
    allowed = {'operation', 'record_id', 'key', 'value', 'title', 'text', 'status',
               'goal_id', 'category', 'source', 'evidence', 'check_at', 'as_of', 'depends_on'}
    unknown = set(event) - allowed
    if unknown:
        raise StoreError('Unknown fields: ' + ', '.join(sorted(unknown)))
    op = event.get('operation')
    if op not in OPERATIONS:
        raise StoreError('Unsupported operation.')
    if event.get('category') not in CATEGORIES:
        raise StoreError('A valid category is required.')
    if not isinstance(event.get('source'), str) or not event['source'].strip():
        raise StoreError('A concrete source is required.')
    for key in ('title', 'text', 'evidence', 'check_at', 'as_of', 'goal_id'):
        if key in event and (not isinstance(event[key], str) or not event[key].strip()):
            raise StoreError(f'{key} must be a nonempty string.')
    for key in ('as_of', 'check_at'):
        if key in event: temporal(event[key], legacy=historical)
    if 'depends_on' in event:
        sources = event['depends_on']
        if (not isinstance(sources, list) or any(not isinstance(source, str) for source in sources)
                or len(sources) != len(set(sources))):
            raise StoreError('depends_on must be a list of unique event IDs.')
        for source in sources: identifier(source, 'source event ID')
    if op == 'profile':
        identifier(event.get('key'), 'profile key')
        if 'value' not in event:
            raise StoreError('Profile value is required.')
        if set(event) & {'record_id', 'status', 'goal_id'}:
            raise StoreError('Profile cannot carry record_id, status or goal_id.')
    else:
        identifier(event.get('record_id'), 'record_id')
        bucket = 'goals' if op == 'goal' else op + 's'
        previous = state[bucket].get(event['record_id'])
        if op == 'goal':
            if not previous and not event.get('title'):
                raise StoreError('A new goal requires a title.')
            status = event.get('status', previous.get('status') if previous else 'active')
            if status not in {'active', 'paused', 'stopped', 'completed'}:
                raise StoreError('Invalid goal status.')
            if 'status' in event or 'title' in event or not previous:
                if event['category'] != 'user_decision':
                    raise StoreError('Goal creation or status changes require user_decision.')
            if status == 'completed' and not event.get('evidence', (previous or {}).get('evidence')):
                raise StoreError('Completed goals require evidence.')
        elif op == 'action':
            if not previous and not event.get('text'):
                raise StoreError('A new action requires text.')
            goal_id = event.get('goal_id', (previous or {}).get('goal_id'))
            if goal_id:
                identifier(goal_id, 'goal_id')
                if goal_id not in state['goals']:
                    raise StoreError('Referenced goal does not exist.')
                if not previous and state['goals'][goal_id]['status'] != 'active':
                    raise StoreError('Cannot add actions to an inactive goal.')
            status = event.get('status', previous.get('status') if previous else 'planned')
            if status not in {'planned', 'in_progress', 'completed', 'cancelled'}:
                raise StoreError('Invalid action status.')
            if status == 'completed':
                if event['category'] not in {'user_report', 'observed_result'}:
                    raise StoreError('Completion must be reported or observed, not suggested.')
                if not event.get('evidence', (previous or {}).get('evidence')):
                    raise StoreError('Completed actions require evidence.')
        elif not event.get('text'):
            raise StoreError('This operation requires text.')
    return copy.deepcopy(event)

def apply(state, event, revision):
    state = copy.deepcopy(state)
    if event['operation'] == 'profile':
        state['profile'][event['key']] = copy.deepcopy(event)
    else:
        op = event['operation']; bucket = 'goals' if op == 'goal' else op + 's'
        previous = state[bucket].get(event['record_id'], {})
        record = {**previous, **copy.deepcopy(event)}
        if op == 'goal': record.setdefault('status', 'active')
        if op == 'action': record.setdefault('status', 'planned')
        state[bucket][event['record_id']] = record
    state['revision'] = revision
    return state

def load(root):
    log = root / 'history.jsonl'; state = empty(); history = []; seen = set()
    if log.exists():
        if log.is_symlink(): raise StoreError('Symlink record files are not supported.')
        raw = log.read_text(encoding='utf-8')
        if raw and not raw.endswith('\n'):
            raise StoreError('Incomplete history tail; preserve files and reconcile before writing.')
        for line in raw.splitlines():
            item = json.loads(line)
            if set(item) != {'revision', 'event_id', 'recorded_at', 'event'}:
                raise StoreError('Malformed history entry.')
            if item['revision'] != state['revision'] + 1 or item['event_id'] in seen:
                raise StoreError('History sequence or event ID conflict.')
            identifier(item['event_id'], 'event_id')
            validate(item['event'], state, historical=True)
            state = apply(state, item['event'], item['revision'])
            seen.add(item['event_id']); history.append(item)
    cache = root / 'state.json'
    if cache.exists():
        if cache.is_symlink(): raise StoreError('Symlink record files are not supported.')
        cached = json.loads(cache.read_text(encoding='utf-8'))
        r = cached.get('revision', -1)
        if not isinstance(r, int) or r < 0 or r > state['revision']:
            raise StoreError('Snapshot conflicts with history.')
        replay = empty()
        for item in history[:r]: replay = apply(replay, item['event'], item['revision'])
        if cached != replay:
            raise StoreError('Snapshot was edited outside the helper; reconcile without overwriting.')
    elif root.exists() and not log.exists() and any(p.name != '.life-store.lock' for p in root.iterdir()):
        raise StoreError('Existing nonempty folder has no helper records; use its format or another folder.')
    return state, history

def atomic_text(path, text):
    if path.is_symlink(): raise StoreError('Symlink targets are not supported.')
    with tempfile.NamedTemporaryFile('w', encoding='utf-8', dir=path.parent,
                                     delete=False, prefix='.life-', suffix='.tmp', newline='\n') as stream:
        stream.write(text); stream.flush(); os.fsync(stream.fileno()); temporary = stream.name
    try: os.replace(temporary, path)
    finally:
        if os.path.exists(temporary): os.unlink(temporary)

def journal(state, metadata=None):
    metadata = metadata or {'invalidated': {}, 'untracked_derived': []}
    lines = ['# 人生管理当前记录', '', f'资料版本：{state["revision"]}', '',
             '本文件为 history.jsonl 的可读视图。修改资料请追加事件，不直接编辑此视图。', '']
    labels = [('profile', '背景与约束'), ('goals', '目标'), ('actions', '行动'),
              ('decisions', '决定'), ('reviews', '复盘'), ('notes', '补充记录')]
    for bucket, title in labels:
        if not state[bucket]: continue
        lines.extend(['## ' + title, ''])
        for key, record in state[bucket].items():
            reference = ':'.join(record_key(record))
            content = record.get('value', record.get('title', record.get('text', '')))
            if not isinstance(content, str): content = json.dumps(content, ensure_ascii=False)
            # Escape Markdown control punctuation to keep untrusted record text as content.
            clean = lambda value: re.sub(r'([\\`*_\[\]<>#|])', r'\\\1', str(value)).replace('\n', ' / ')
            warning = '【待重算，不作当前依据】' if reference in metadata['invalidated'] else ''
            lines.append(f'- {warning}{clean(key)}：{clean(content)}')
            if warning:
                lines.append('  - 失效原因：'+clean('; '.join(metadata['invalidated'][reference])))
            elif reference in metadata['untracked_derived']:
                lines.append('  - 依赖未追踪：需人工复核，不代表当前仍有效。')
            category = CATEGORY_LABELS[record['category']]
            status = STATUS_LABELS.get(record.get('status'), '不适用')
            lines.append(f'  - 分类：{category}；状态：{status}')
            lines.append(f'  - 来源：{clean(record["source"])}')
            for field, label in [('goal_id', '关联目标'), ('evidence', '证据'), ('check_at', '检查时间'), ('as_of', '信息日期')]:
                if field in record: lines.append(f'  - {label}：{clean(record[field])}')
            if record.get('depends_on'): lines.append('  - 依赖版本：' + clean(', '.join(record['depends_on'])))
        lines.append('')
    return '\n'.join(lines) + '\n'

def commit(root, event, expected, event_id):
    if root == Path(root.anchor) or root == SKILL_ROOT or SKILL_ROOT in root.parents:
        raise StoreError('Select a data directory outside the skill and filesystem root.')
    if root.is_symlink(): raise StoreError('Symlink data directories are not supported.')
    root.mkdir(parents=True, exist_ok=True)
    lock = root / '.life-store.lock'
    try: fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError: raise StoreError('Another writer holds the lock; do not remove it without checking.')
    try:
        os.write(fd, str(os.getpid()).encode('ascii')); os.close(fd)
        state, history = load(root)
        for item in history:
            if item['event_id'] == event_id:
                if item['event'] != event: raise StoreError('Event ID reused with different content.')
                atomic_text(root / 'state.json', json.dumps(state, ensure_ascii=False, indent=2) + '\n')
                atomic_text(root / 'journal.md', journal(state, validity(state, history)))
                return state, False
        if state['revision'] != expected:
            raise StoreError(f'Stale revision: expected {expected}, current {state["revision"]}. Re-read first.')
        event = validate(event, state)
        available = {item['event_id'] for item in history}
        for source in event.get('depends_on', []):
            if source not in available: raise StoreError('Unknown dependency event ID: ' + source)
        candidate = apply(state, event, expected + 1)
        candidate_history = history + [{'event_id': event_id, 'event': event}]
        target = ':'.join(record_key(event))
        if event.get('depends_on') and target in validity(candidate, candidate_history)['invalidated']:
            raise StoreError('Dependency is superseded or invalidated; re-read current sources before writing.')
        item = {'revision': expected + 1, 'event_id': event_id,
                'recorded_at': datetime.now(timezone.utc).isoformat(), 'event': event}
        next_state = apply(state, event, item['revision'])
        log = root / 'history.jsonl'
        if log.is_symlink(): raise StoreError('Symlink record files are not supported.')
        # The log is authoritative; snapshots are recoverable if writing is interrupted.
        with log.open('a', encoding='utf-8', newline='\n') as stream:
            stream.write(json.dumps(item, ensure_ascii=False, separators=(',', ':')) + '\n')
            stream.flush(); os.fsync(stream.fileno())
        atomic_text(root / 'state.json', json.dumps(next_state, ensure_ascii=False, indent=2) + '\n')
        atomic_text(root / 'journal.md', journal(next_state, validity(next_state, history + [item])))
        return next_state, True
    finally:
        lock.unlink(missing_ok=True)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', required=True, help='Explicit user data directory')
    sub = parser.add_subparsers(dest='command', required=True)
    show = sub.add_parser('show')
    show.add_argument('--record-id', action='append', help='Limit output to these record IDs or profile keys')
    show.add_argument('--goal-id', help='Limit output to this goal and linked actions')
    show.add_argument('--with-validity', action='store_true', help='Include source-version validity metadata')
    entry = sub.add_parser('entry')
    entry.add_argument('--event-file', required=True)
    entry.add_argument('--expected-revision', type=int, required=True)
    entry.add_argument('--event-id', default=None)
    args = parser.parse_args(); root = Path(args.root).expanduser().resolve()
    try:
        if args.command == 'show':
            state, history = load(root)
            metadata = validity(state, history)
            if args.record_id or args.goal_id:
                requested = set(args.record_id or [])
                for bucket in ('profile', 'goals', 'actions', 'decisions', 'reviews', 'notes'):
                    state[bucket] = {key: record for key, record in state[bucket].items()
                                     if key in requested or (args.goal_id and
                                        ((bucket == 'goals' and key == args.goal_id) or
                                         record.get('goal_id') == args.goal_id))}
                keys = {':'.join(record_key(record)) for bucket in
                        ('profile', 'goals', 'actions', 'decisions', 'reviews', 'notes')
                        for record in state[bucket].values()}
                metadata = {'current_sources': {k: v for k, v in metadata['current_sources'].items() if k in keys},
                            'invalidated': {k: v for k, v in metadata['invalidated'].items() if k in keys},
                            'untracked_derived': [k for k in metadata['untracked_derived'] if k in keys]}
            if args.with_validity: state = {'state': state, **metadata}
        else:
            event = json.loads(Path(args.event_file).read_text(encoding='utf-8-sig'))
            event_id = args.event_id or 'e-' + uuid.uuid4().hex
            identifier(event_id, 'event_id')
            state, written = commit(root, event, args.expected_revision, event_id)
            print(json.dumps({'written': written, 'revision': state['revision'], 'event_id': event_id,
                              'root': str(root)}, ensure_ascii=False)); return
        print(json.dumps(state, ensure_ascii=False, indent=2))
    except (StoreError, OSError, ValueError, TypeError, KeyError) as error:
        print(json.dumps({'error': str(error)}, ensure_ascii=False), file=sys.stderr); sys.exit(2)

if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'): sys.stdout.reconfigure(encoding='utf-8')
    if hasattr(sys.stderr, 'reconfigure'): sys.stderr.reconfigure(encoding='utf-8')
    main()
