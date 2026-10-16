"""Clock, full-day context, gentle due checks and versioned daily reports."""
from __future__ import annotations
import argparse
from datetime import date, datetime, timedelta, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import sys

EASY = Path(__file__).resolve().parents[1]
LEGACY = EASY.parent / 'ai-life-management'
sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location('life_core', LEGACY/'scripts/life_store.py')
core = importlib.util.module_from_spec(spec)
spec.loader.exec_module(core)

def offset_zone(text):
    match = re.fullmatch(r'([+-])(\d{2}):(\d{2})', text)
    if not match: raise ValueError('UTC offset must be explicit, for example +08:00.')
    hours, minutes = int(match[2]), int(match[3])
    if hours > 14 or minutes > 59 or (hours == 14 and minutes):
        raise ValueError('UTC offset is outside the supported range.')
    return timezone((1 if match[1] == '+' else -1)*timedelta(hours=hours, minutes=minutes))

def instant(text):
    value = datetime.fromisoformat(text.replace('Z', '+00:00'))
    if value.tzinfo is None: raise ValueError('Timestamp requires a UTC offset.')
    return value

def clock(offset, at=None):
    zone = offset_zone(offset)
    now = instant(at) if at else datetime.now(timezone.utc)
    return {'local_time': now.astimezone(zone).isoformat(), 'utc_time': now.astimezone(timezone.utc).isoformat(),
            'offset': offset, 'source': 'provided_timestamp' if at else 'system_clock'}

def data_root(value):
    requested = Path(value).expanduser()
    if requested.is_symlink(): raise ValueError('Use a non-symlink data directory.')
    root = requested.resolve()
    if root == Path(root.anchor) or any(root == p or p in root.parents for p in (EASY, LEGACY)):
        raise ValueError('Data must be outside the skill directories and filesystem root.')
    return root

def event_day(item, zone):
    stamp = item['event'].get('as_of')
    if stamp:
        parsed = core.temporal(stamp, legacy=True)
        if isinstance(parsed, datetime): return parsed.astimezone(zone).date()
        return parsed
    return instant(item['recorded_at']).astimezone(zone).date()

def record_key(event):
    return (event['operation'], event.get('key') or event['record_id'])

def day_context(root, day, offset):
    selected = date.fromisoformat(day); zone = offset_zone(offset)
    source_state, history = core.load(root)
    before = core.empty(); state = core.empty(); timeline = []; latest_before = {}; included = []
    for item in history:
        effective = event_day(item, zone)
        if effective > selected: continue
        included.append(item)
        state = core.apply(state, item['event'], item['revision'])
        if effective < selected:
            before = core.apply(before, item['event'], item['revision'])
            latest_before[record_key(item['event'])] = item
        else:
            timeline.append({**item, 'date_basis': 'as_of' if item['event'].get('as_of') else 'recorded_at'})
    touched = {record_key(item['event']) for item in timeline}
    related_goals = {item['event'].get('goal_id') for item in timeline}
    related_goals |= {item['event'].get('record_id') for item in timeline if item['event']['operation'] == 'goal'}
    baseline = [item for key,item in latest_before.items()
                if key[0] == 'profile' or key in touched or
                (key[0] == 'goal' and (key[1] in related_goals or state['goals'].get(key[1],{}).get('status') == 'active'))]
    relevant_goals={key:value for key,value in state['goals'].items() if value['status']=='active' or key in related_goals}
    relevant_actions={key:value for key,value in state['actions'].items()
                      if ('action',key) in touched or (value.get('status') in {'planned','in_progress'} and
                      (not value.get('goal_id') or relevant_goals.get(value['goal_id'],{}).get('status')=='active'))}
    metadata = core.validity(state, included)
    retired = {item['event_id'] for item in included
               if metadata['current_sources'].get(':'.join(record_key(item['event']))) != item['event_id']}
    retired |= {metadata['current_sources'][key] for key in metadata['invalidated']}
    return {'date': day, 'offset': offset, 'context_revision': state['revision'],
            'source_revision': source_state['revision'],
            'timeline': timeline, 'baseline_sources': baseline,
            **metadata, 'historical_only_evidence': sorted(retired),
            'profile': state['profile'], 'goals': relevant_goals, 'actions': relevant_actions,
            'coverage': {'events': len(timeline), 'recording_order_preserved': True,
                         'explicit_event_dates': sum('as_of' in t['event'] for t in timeline),
                         'limit': '仅覆盖提供的管理记录，未记录不等于未发生；不包含其他聊天。'}}

def due_context(root, offset, at=None):
    check = clock(offset, at); now = instant(check['local_time'])
    state, history = core.load(root); profile = state['profile']
    paused = profile.get('reminders_paused',{}).get('value') is True
    quiet = profile.get('quiet_until',{}).get('value')
    if quiet: paused = paused or now < instant(quiet)
    due = []; checkpoints = []
    invalidated = core.validity(state, history)['invalidated']
    if not paused:
        for identifier, record in state['actions'].items():
            if record.get('status') not in {'planned','in_progress'}: continue
            if record['category'] not in {'user_decision','user_report','observed_result'}: continue
            goal = state['goals'].get(record.get('goal_id'))
            if goal and goal['status'] != 'active': continue
            if 'action:' + identifier in invalidated: continue
            stamp = record.get('check_at')
            if stamp:
                parsed = core.temporal(stamp, legacy=True)
                if not isinstance(parsed, datetime):
                    if parsed <= now.date():
                        checkpoints.append({'record_id': identifier, 'text': record['text'],
                                            'check_date': parsed.isoformat(), 'time_unknown': True})
                elif parsed <= now:
                    due.append({'record_id': identifier, 'text': record['text'], 'check_at': stamp})
    due.sort(key=lambda value: instant(value['check_at']))
    return {**check, 'quiet': paused, 'due': due, 'date_checkpoints': checkpoints,
            'message': '当前不打扰。' if paused else ('你接受的安排已到检查时间：是否已完成，还是需要调整？' if due else '没有已接受且到点的待办。'),
            'notification_service': False}

def preview(context):
    timeline = context['timeline']
    retired = set(context.get('historical_only_evidence', []))
    sources = [t['event_id'] for t in timeline if t['event_id'] not in retired]
    if not sources: sources = [t['event_id'] for t in context['baseline_sources'] if t['event_id'] not in retired]
    latest = {}
    for item in timeline: latest[record_key(item['event'])] = item
    progress = []
    for item in latest.values():
        if item['event_id'] in retired: continue
        event = item['event']; op = event['operation']; status = event.get('status')
        if op == 'action' and status == 'completed':
            final = context['actions'][event['record_id']]
            progress.append({'text': '你报告完成：'+final['text'] if event['category']=='user_report' else '已观察结果：'+final['text'],
                             'kind': event['category'], 'evidence':[item['event_id']]})
        elif op == 'goal' and status in {'paused','stopped'}:
            progress.append({'text':'目标已'+('暂停' if status=='paused' else '停止')+'：'+context['goals'][event['record_id']]['title'],
                             'kind':'decision','evidence':[item['event_id']]})
    active = [(key,r) for key,r in context['goals'].items() if r['status']=='active']
    tomorrow = [{'text':'明天先确认可用时间，再选一个能留下结果的小步骤。','kind':'suggestion','evidence':sources[:1]}]
    if active:
        gid,goal = active[0]
        candidates = [t['event_id'] for t in timeline+context['baseline_sources']
                      if t['event'].get('record_id')==gid and t['event_id'] not in retired]
        tomorrow = [{'text':'围绕“'+goal['title']+'”，按实际精力选一个小步骤并保存结果。','kind':'suggestion','goal_id':gid,'evidence':candidates[-1:]}]
    return {'overview': {'text':f'已提供{len(timeline)}条当天记录；这是规则预览，未进行模型综合分析。', 'evidence':sources[:1]},
            'progress':progress[:3], 'interpretation':[], 'tomorrow':tomorrow}

def validate_analysis(context, analysis, layout='short'):
    if layout not in {'short', 'detailed'}: raise ValueError('Unknown report layout.')
    required = {'overview','progress','interpretation','tomorrow'}
    optional = {'action_plan'} if layout == 'detailed' else set()
    if not isinstance(analysis,dict) or not required <= set(analysis) or set(analysis) - required - optional:
        raise ValueError('Analysis needs overview, progress, interpretation and tomorrow.')
    evidence = {item['event_id']:item['event'] for item in context['timeline']+context['baseline_sources']}
    day_ids = {item['event_id'] for item in context['timeline']}
    detailed = layout == 'detailed'
    sections = [('overview',[analysis['overview']],1),('progress',analysis['progress'],16 if detailed else 3),
                ('interpretation',analysis['interpretation'],10 if detailed else 2),
                ('tomorrow',analysis['tomorrow'],6 if detailed else 3)]
    if detailed: sections.append(('action_plan', analysis.get('action_plan', []), 16))
    retired = set(context.get('historical_only_evidence', []))
    total = 0
    for name,rows,limit in sections:
        if not isinstance(rows,list) or len(rows)>limit: raise ValueError('Too many rows in '+name)
        for row in rows:
            if not isinstance(row,dict) or set(row)-{'text','kind','evidence','goal_id','historical','area'}:
                raise ValueError('Invalid report row.')
            if 'historical' in row and (not isinstance(row['historical'], bool) or name != 'interpretation'):
                raise ValueError('Historical comparisons belong in interpretation only.')
            if 'area' in row and (name != 'action_plan' or not isinstance(row['area'], str)
                                  or not row['area'].strip() or len(row['area']) > 40):
                raise ValueError('area is a short label for action_plan only.')
            text = row.get('text'); citations = row.get('evidence')
            if not isinstance(text,str) or not text.strip() or len(text)>(600 if detailed else 180):
                raise ValueError('Report rows need short, nonempty text.')
            total += len(text)
            if not isinstance(citations,list) or any(not isinstance(c,str) or c not in evidence for c in citations):
                raise ValueError('Unknown or invalid evidence ID.')
            if evidence and not citations: raise ValueError('Nonempty context requires evidence references.')
            if retired.intersection(citations) and not row.get('historical'):
                raise ValueError('Superseded or invalidated evidence requires an explicit historical interpretation.')
            categories = {evidence[c]['category'] for c in citations}
            if name=='progress':
                if not day_ids.intersection(citations): raise ValueError('Progress must reference a day event.')
                allowed={'fact':{'confirmed_fact','observed_result'},'observed_result':{'observed_result'},
                         'user_report':{'user_report'},'decision':{'user_decision'},
                         'estimate':core.CATEGORIES,'suggestion':core.CATEGORIES}
                if row.get('kind') not in allowed or not categories<=allowed[row['kind']]:
                    raise ValueError('Progress evidence category does not match its claim.')
            if name=='interpretation' and row.get('kind')!='estimate': raise ValueError('Interpretation must be an estimate.')
            if name in {'tomorrow', 'action_plan'}:
                if row.get('kind')!='suggestion': raise ValueError('Tomorrow guidance is a suggestion.')
                if row.get('goal_id'):
                    goal=context['goals'].get(row['goal_id'])
                    if not goal or goal['status']!='active': raise ValueError('Cannot schedule a paused or unavailable goal.')
    if total>(8000 if detailed else 600): raise ValueError('Report content exceeds the selected layout budget.')

def render_report(context, analysis, mode, layout='short'):
    def clean(value):
        value=re.sub(r'\s+',' ',value).strip()
        return re.sub(r'([\\`*_\[\]<>#|])',r'\\\1',value)
    lines=['# '+context['date']+' 日报','', '## 今日概况',clean(analysis['overview']['text'])]
    headings=[('progress','进展与偏差'),('interpretation','关键解释'),('tomorrow','明日指引')]
    labels={'fact':'观察','observed_result':'观察','user_report':'报告','decision':'决定','estimate':'推断','suggestion':'建议'}
    for key,label in headings:
        if not analysis[key]: continue
        lines.extend(['','## '+label])
        for row in analysis[key]:
            prefix = '历史复盘／' if row.get('historical') else ''
            lines.append('- '+prefix+labels[row['kind']]+'：'+clean(row['text']))
    if layout == 'detailed' and analysis.get('action_plan'):
        lines.extend(['', '## 全天行动建议（尚未执行）'])
        for row in analysis['action_plan']:
            area = clean(row.get('area', '行动'))
            lines.append('- '+area+'：'+clean(row['text']))
    lines.extend(['','## 资料覆盖',f'使用{context["coverage"]["events"]}条当天事件及{len(context["baseline_sources"])}条相关背景，时区偏移{context["offset"]}。',
                  context['coverage']['limit'], '分析方式：'+('模型分析，经结构与引用检查；含义仍需核对。' if mode=='model' else '规则预览，不是模型综合分析。')])
    if context.get('invalidated'):
        lines.append('待重算：'+clean(', '.join(context['invalidated']))+'；旧估算仅供历史回查。')
    if context.get('untracked_derived'):
        lines.append('部分旧建议或估算未声明依赖版本，不能据自动检查认定仍然有效。')
    return '\n'.join(lines)+'\n'

def report(root, context, analysis, mode, write, layout='short'):
    validate_analysis(context,analysis,layout)
    result={'date':context['date'],'offset':context['offset'],'context_revision':context['context_revision'],
            'analysis_mode':mode,'analysis':analysis,'coverage':context['coverage'],'baseline_count':len(context['baseline_sources'])}
    result['validity'] = {key: context[key] for key in ('invalidated', 'untracked_derived') if key in context}
    if layout != 'short': result['layout'] = layout
    markdown=render_report(context,analysis,mode,layout)
    if not write: return {'report':result,'markdown':markdown,'saved':False}
    if not (root/'history.jsonl').is_file(): raise ValueError('No record store yet; deliver the short report in chat first.')
    directory=root/'reports'
    if directory.is_symlink(): raise ValueError('Report directory must not be a symlink.')
    directory.mkdir(exist_ok=True)
    lock=directory/'.report.lock'
    try: descriptor=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY)
    except FileExistsError: raise ValueError('Another report writer is active.')
    os.close(descriptor)
    source_lock = root / '.life-store.lock'; source_owned = False
    try:
        try: source_fd = os.open(source_lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError: raise ValueError('A record writer is active; re-read context before retrying.')
        os.close(source_fd); source_owned = True
        current, _ = core.load(root)
        if current['revision'] != context.get('source_revision', context['context_revision']):
            raise ValueError('Stale report context; re-read and re-analyze before writing.')
        json_path=directory/(context['date']+'.json');md_path=directory/(context['date']+'.md')
        if json_path.is_symlink() or md_path.is_symlink(): raise ValueError('Report files must not be symlinks.')
        if json_path.exists()!=md_path.exists(): raise ValueError('Partial report pair; reconcile before writing.')
        if json_path.exists():
            old=json.loads(json_path.read_text(encoding='utf-8'))
            old_context={**context,'date':old['date'],'offset':old['offset'],'coverage':old['coverage'],
                         'baseline_sources':[None]*old['baseline_count']}
            # Preserve byte-for-byte verification of reports from older releases.
            old_context.pop('invalidated', None); old_context.pop('untracked_derived', None)
            old_context.update(old.get('validity', {}))
            if md_path.read_text(encoding='utf-8')!=render_report(old_context,old['analysis'],old['analysis_mode'],old.get('layout','short')):
                raise ValueError('Report was edited manually; preserve and reconcile.')
            if old==result:return {'report':result,'markdown':markdown,'saved':True,'changed':False,'path':str(md_path)}
            archive=directory/'history'
            if archive.is_symlink():raise ValueError('History directory must not be a symlink.')
            archive.mkdir(exist_ok=True)
            digest=hashlib.sha256(json_path.read_bytes()).hexdigest()[:16]
            for path in (json_path,md_path):
                target=archive/(context['date']+'.'+digest+path.suffix)
                if target.exists() and target.read_bytes()!=path.read_bytes():raise ValueError('Report archive conflict.')
                if not target.exists():core.atomic_text(target,path.read_text(encoding='utf-8'))
        core.atomic_text(json_path,json.dumps(result,ensure_ascii=False,indent=2)+'\n')
        core.atomic_text(md_path,markdown)
        return {'report':result,'markdown':markdown,'saved':True,'changed':True,'path':str(md_path)}
    finally:
        if source_owned: source_lock.unlink(missing_ok=True)
        lock.unlink(missing_ok=True)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=['clock','context','next','report'])
    parser.add_argument('--root');parser.add_argument('--offset',default='+08:00')
    parser.add_argument('--date');parser.add_argument('--at')
    parser.add_argument('--analysis-file');parser.add_argument('--write',action='store_true')
    parser.add_argument('--layout', choices=['short','detailed'], default='short')
    args=parser.parse_args()
    try:
        if args.command=='clock':result=clock(args.offset,args.at)
        else:
            if not args.root:raise ValueError('--root is required.')
            root=data_root(args.root)
            if args.command=='next':result=due_context(root,args.offset,args.at)
            else:
                day=args.date or clock(args.offset,args.at)['local_time'][:10]
                context=day_context(root,day,args.offset)
                if args.command=='context':result=context
                else:
                    analysis=json.loads(Path(args.analysis_file).read_text(encoding='utf-8-sig')) if args.analysis_file else preview(context)
                    result=report(root,context,analysis,'model' if args.analysis_file else 'rules',args.write,args.layout)
        print(json.dumps(result,ensure_ascii=False,indent=2))
    except (ValueError,OSError,KeyError,TypeError) as error:
        print(json.dumps({'error':str(error)},ensure_ascii=False),file=sys.stderr);sys.exit(2)

if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8');sys.stderr.reconfigure(encoding='utf-8');main()
