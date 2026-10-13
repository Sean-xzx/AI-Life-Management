"""Offline synthetic lifecycle; no personal records or external service."""
from pathlib import Path
import json
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / 'ai-life-management/scripts/life_store.py'

def main():
    scratch=ROOT/'tmp';scratch.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='life-demo-',dir=scratch) as folder:
        assert Path(folder).resolve().is_relative_to(scratch.resolve())
        base = Path(folder); data = base / 'records'
        events = [
            {'operation':'profile','key':'weekly_minutes','value':90,'category':'user_report','source':'Synthetic user: 90 minutes per week'},
            {'operation':'goal','record_id':'g-speaking','title':'Record a 60-second speech','status':'active','category':'user_decision','source':'Synthetic user chose the goal'},
            {'operation':'action','record_id':'a-speaking','goal_id':'g-speaking','text':'Try a short recording','status':'planned','category':'ai_suggestion','source':'Synthetic suggestion, not completion'},
            {'operation':'profile','key':'weekly_minutes','value':30,'category':'user_report','source':'Synthetic correction: 30 minutes, not 90'},
            {'operation':'goal','record_id':'g-speaking','status':'paused','category':'user_decision','source':'Synthetic user requests pause'},
            {'operation':'action','record_id':'a-speaking','status':'cancelled','category':'user_decision','source':'Synthetic user requests no further speaking tasks'},
        ]
        for revision,event in enumerate(events):
            file = base / 'event.json'; file.write_text(json.dumps(event),encoding='utf-8')
            result = subprocess.run([sys.executable,'-X','utf8',str(HELPER),'--root',str(data),'entry','--event-file',str(file),'--expected-revision',str(revision),'--event-id',f'demo-{revision}'],capture_output=True,text=True,encoding='utf-8')
            if result.returncode: raise RuntimeError(result.stderr)
        state = json.loads((data/'state.json').read_text(encoding='utf-8'))
        history = [json.loads(line) for line in (data/'history.jsonl').read_text(encoding='utf-8').splitlines()]
        assert state['revision'] == 6
        assert state['profile']['weekly_minutes']['value'] == 30
        assert history[0]['event']['value'] == 90
        assert state['goals']['g-speaking']['status'] == 'paused'
        assert state['actions']['a-speaking']['status'] == 'cancelled'
        print('Demo passed: revision=6, weekly_minutes=30, goal_status=paused, action_status=cancelled')

if __name__ == '__main__': main()
