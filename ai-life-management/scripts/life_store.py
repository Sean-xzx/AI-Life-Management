"""Local, append-only life-management records. Standard library only."""
from __future__ import annotations
import argparse
import copy
from datetime import datetime, timezone
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

def validate(event, state):
    if not isinstance(event, dict):
        raise StoreError('Event must be a JSON object.')
    allowed = {'operation', 'record_id', 'key', 'value', 'title', 'text', 'status',
               'goal_id', 'category', 'source', 'evidence', 'check_at', 'as_of'}
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
            if 'status' in event or not previous:
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
            validate(item['event'], state)
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

def journal(state):
    lines = ['# 人生管理当前记录', '', f'资料版本：{state["revision"]}', '',
             '本文件为 history.jsonl 的可读视图。修改资料请追加事件，不直接编辑此视图。', '']
    labels = [('profile', '背景与约束'), ('goals', '目标'), ('actions', '行动'),
              ('decisions', '决定'), ('reviews', '复盘'), ('notes', '补充记录')]
    for bucket, title in labels:
        if not state[bucket]: continue
        lines.extend(['## ' + title, ''])
        for key, record in state[bucket].items():
            content = record.get('value', record.get('title', record.get('text', '')))
            if not isinstance(content, str): content = json.dumps(content, ensure_ascii=False)
            # Escape Markdown control punctuation to keep untrusted record text as content.
            clean = lambda value: re.sub(r'([\\`*_\[\]<>#|])', r'\\\1', str(value)).replace('\n', ' / ')
            lines.append(f'- {clean(key)}：{clean(content)}')
            category = CATEGORY_LABELS[record['category']]
            status = STATUS_LABELS.get(record.get('status'), '不适用')
            lines.append(f'  - 分类：{category}；状态：{status}')
            lines.append(f'  - 来源：{clean(record["source"])}')
            for field, label in [('goal_id', '关联目标'), ('evidence', '证据'), ('check_at', '检查时间'), ('as_of', '信息日期')]:
                if field in record: lines.append(f'  - {label}：{clean(record[field])}')
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
                atomic_text(root / 'journal.md', journal(state))
                return state, False
        if state['revision'] != expected:
            raise StoreError(f'Stale revision: expected {expected}, current {state["revision"]}. Re-read first.')
        event = validate(event, state)
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
        atomic_text(root / 'journal.md', journal(next_state))
        return next_state, True
    finally:
        lock.unlink(missing_ok=True)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', required=True, help='Explicit user data directory')
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('show')
    entry = sub.add_parser('entry')
    entry.add_argument('--event-file', required=True)
    entry.add_argument('--expected-revision', type=int, required=True)
    entry.add_argument('--event-id', default=None)
    args = parser.parse_args(); root = Path(args.root).expanduser().resolve()
    try:
        if args.command == 'show': state, _ = load(root)
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
