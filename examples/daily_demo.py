"""Offline synthetic full-day context and rule-preview demonstration; no model call."""
from pathlib import Path
import importlib.util
import json
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location('daily_demo_adapter', ROOT/'ai-life-management-easy/scripts/daily.py')
daily = importlib.util.module_from_spec(spec)
spec.loader.exec_module(daily)

def main():
    scratch = ROOT/'tmp'
    scratch.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='life-daily-demo-', dir=scratch) as directory:
        assert Path(directory).resolve().is_relative_to(scratch.resolve())
        root = Path(directory)/'records'
        events = [
            {'operation':'goal','record_id':'writing','category':'user_decision','title':'写作练习','status':'active'},
            {'operation':'action','record_id':'paragraph','goal_id':'writing','category':'user_decision','text':'写一个段落','status':'planned','check_at':'2026-10-13T20:00:00+08:00'},
            {'operation':'profile','key':'weekly_minutes','value':30,'category':'user_report'},
            {'operation':'action','record_id':'paragraph','category':'user_report','status':'completed','evidence':'虚构用户报告已写120字'},
        ]
        for revision, event in enumerate(events):
            event.update(source='Synthetic offline demo', as_of=f'2026-10-13T{[8,9,12,21][revision]:02}:00:00+08:00')
            daily.core.commit(root,event,revision,f'demo-{revision+1}')
        context = daily.day_context(root,'2026-10-13','+08:00')
        before = (root/'history.jsonl').read_bytes()
        first = daily.report(root,context,daily.preview(context),'rules',True)
        second = daily.report(root,context,daily.preview(context),'rules',True)
        assert len(context['timeline']) == 4
        assert second['changed'] is False
        assert (root/'history.jsonl').read_bytes() == before
        assert Path(first['path']).is_file()
        print(first['markdown'])
        print('Daily demo passed: events=4, idempotent=True, core_history_unchanged=True, mode=rules')
        print('For contextual guidance, give the complete context to a model and validate its analysis JSON; this demo does not call a model.')

if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
