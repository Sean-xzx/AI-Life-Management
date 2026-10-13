from pathlib import Path
import json
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
SKILL=ROOT/'ai-life-management'
HELPER=SKILL/'scripts/life_store.py'

class RecordTests(unittest.TestCase):
    def setUp(self):
        scratch=ROOT/'tmp';scratch.mkdir(exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(prefix='life-test-',dir=scratch)
        assert Path(self.temp.name).resolve().is_relative_to(scratch.resolve())
        self.addCleanup(self.temp.cleanup)
        self.base=Path(self.temp.name);self.data=self.base/'records';self.counter=0
    def call(self,event=None,rev=0,eid=None,root=None):
        root=root or self.data
        args=[sys.executable,'-X','utf8',str(HELPER),'--root',str(root)]
        if event is None:args+=['show']
        else:
            self.counter+=1;file=self.base/f'event-{self.counter}.json'
            file.write_text(json.dumps(event,ensure_ascii=False),encoding='utf-8')
            args+=['entry','--event-file',str(file),'--expected-revision',str(rev),'--event-id',eid or f'e-{self.counter}']
        r=subprocess.run(args,capture_output=True,text=True,encoding='utf-8')
        return r.returncode,json.loads(r.stdout if r.returncode==0 else r.stderr)
    def profile(self,value=90):
        return {'operation':'profile','key':'weekly_minutes','value':value,'category':'user_report','source':'Synthetic user report'}
    def goal(self):
        return {'operation':'goal','record_id':'g-test','title':'Test goal','status':'active','category':'user_decision','source':'Synthetic explicit user goal'}
    def action(self):
        return {'operation':'action','record_id':'a-test','goal_id':'g-test','text':'Small step','status':'planned','category':'ai_suggestion','source':'Synthetic suggestion'}
    def seeded(self):
        self.assertEqual(self.call(self.goal(),0)[0],0)
        self.assertEqual(self.call(self.action(),1)[0],0)
    def test_empty_read_has_no_side_effect(self):
        c,s=self.call();self.assertEqual(c,0);self.assertEqual(s['revision'],0);self.assertFalse(self.data.exists())
    def test_unicode_round_trip(self):
        e=self.profile();e['source']='虚构用户报告，不是真实用户资料'
        self.assertEqual(self.call(e)[0],0);self.assertEqual(self.call()[1]['profile']['weekly_minutes']['source'],e['source'])
    def test_idempotent_retry(self):
        e=self.profile();self.call(e,0,'e-same');c,r=self.call(e,0,'e-same')
        self.assertEqual(c,0);self.assertFalse(r['written']);self.assertEqual(r['revision'],1)
    def test_correction_keeps_history(self):
        self.call(self.profile());self.call(self.profile(30),1)
        self.assertEqual(self.call()[1]['profile']['weekly_minutes']['value'],30)
        logs=[json.loads(l) for l in (self.data/'history.jsonl').read_text(encoding='utf-8').splitlines()]
        self.assertEqual([r['event']['value'] for r in logs],[90,30])
    def test_stale_revision_preserves_log(self):
        self.call(self.profile());old=(self.data/'history.jsonl').read_bytes()
        self.assertEqual(self.call(self.profile(30),0)[0],2);self.assertEqual((self.data/'history.jsonl').read_bytes(),old)
    def test_id_reuse_with_different_content(self):
        self.call(self.profile(),0,'e-same');self.assertEqual(self.call(self.profile(30),1,'e-same')[0],2)
    def test_suggestion_stays_planned(self):
        self.seeded();self.assertEqual(self.call()[1]['actions']['a-test']['status'],'planned')
    def test_completed_suggestion_rejected(self):
        self.seeded();e={**self.action(),'status':'completed','evidence':'Not a report'}
        self.assertEqual(self.call(e,2)[0],2)
    def test_completion_needs_evidence(self):
        self.seeded();e={**self.action(),'status':'completed','category':'user_report'}
        self.assertEqual(self.call(e,2)[0],2)
        e['evidence']='Synthetic user reports saved a paragraph'
        self.assertEqual(self.call(e,2)[0],0);self.assertEqual(self.call()[1]['actions']['a-test']['status'],'completed')
    def test_pause_blocks_new_action(self):
        self.seeded();p={**self.goal(),'status':'paused'};self.assertEqual(self.call(p,2)[0],0)
        self.assertEqual(self.call({**self.action(),'record_id':'a-new'},3)[0],2)
        self.assertEqual(self.call()[1]['goals']['g-test']['status'],'paused')
    def test_candidate_goal_not_user_decision(self):
        self.assertEqual(self.call({**self.goal(),'category':'ai_suggestion'})[0],2)
    def test_existing_lock_is_retained(self):
        self.call(self.profile());lock=self.data/'.life-store.lock';lock.write_text('fixture')
        self.assertEqual(self.call(self.profile(30),1)[0],2);self.assertTrue(lock.exists())
    def test_stale_snapshot_recovery(self):
        e=self.profile();self.call(e,0,'e-first');old=(self.data/'state.json').read_bytes()
        e2=self.profile(30);self.call(e2,1,'e-second');(self.data/'state.json').write_bytes(old)
        self.assertEqual(self.call()[1]['revision'],2)
        c,r=self.call(e2,1,'e-second');self.assertEqual(c,0);self.assertFalse(r['written'])
        self.assertEqual(json.loads((self.data/'state.json').read_text())['revision'],2)
    def test_manual_snapshot_edit_is_preserved(self):
        self.call(self.profile());p=self.data/'state.json';s=json.loads(p.read_text());s['profile']['weekly_minutes']['value']=999
        p.write_text(json.dumps(s));self.assertEqual(self.call()[0],2);self.assertEqual(json.loads(p.read_text())['profile']['weekly_minutes']['value'],999)
    def test_incomplete_history_is_preserved(self):
        self.call(self.profile());p=self.data/'history.jsonl'
        with p.open('ab') as f:f.write(b'{"partial":')
        before=p.read_bytes();self.assertEqual(self.call()[0],2);self.assertEqual(p.read_bytes(),before)
    def test_custom_records_are_not_replaced(self):
        self.data.mkdir();p=self.data/'goals.md';p.write_text('custom goal')
        self.assertEqual(self.call(self.profile())[0],2);self.assertEqual(p.read_text(),'custom goal');self.assertFalse((self.data/'history.jsonl').exists())
    def test_skill_directory_is_not_data_storage(self):
        # Use the skill directory itself: no test folder is written in the source tree.
        self.assertEqual(self.call(self.profile(),root=SKILL)[0],2)

if __name__=='__main__':unittest.main()
