from pathlib import Path
from datetime import datetime, timezone
import importlib.util
import copy
import json
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.dont_write_bytecode=True
spec=importlib.util.spec_from_file_location('daily_adapter',ROOT/'ai-life-management-easy/scripts/daily.py')
daily=importlib.util.module_from_spec(spec);spec.loader.exec_module(daily)

class DailyTests(unittest.TestCase):
    def setUp(self):
        scratch=ROOT/'tmp';scratch.mkdir(exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(prefix='daily-test-',dir=scratch)
        assert Path(self.temp.name).resolve().is_relative_to(scratch.resolve())
        self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)/'records';self.rev=0
    def add(self,operation,record_id=None,**fields):
        event={'operation':operation,'category':'user_report','source':'Synthetic fixture','as_of':'2026-10-13',**fields}
        if record_id:event['record_id']=record_id
        self.rev+=1;daily.core.commit(self.root,event,self.rev-1,f'e-{self.rev}')
        return f'e-{self.rev}'
    def seed(self):
        self.add('goal','g-speaking',title='口语练习',status='active',category='user_decision',as_of='2026-10-12')
        self.add('action','a-first',goal_id='g-speaking',text='保存一次试录',status='planned',category='ai_suggestion',as_of='2026-10-13T09:00:00+08:00')
        self.add('action','a-first',status='completed',evidence='用户报告已保存30秒试录',as_of='2026-10-13T21:00:00+08:00')
        self.add('profile',key='weekly_minutes',value=30,as_of='2026-10-13T12:00:00+08:00')
    def context(self,day='2026-10-13'):
        return daily.day_context(self.root,day,'+08:00')
    def model_analysis(self):
        return {'overview':{'text':'今天完成一次试录并调整了时间预算。','evidence':['e-3','e-4']},
                'progress':[{'text':'你报告保存了30秒试录，尚未独立检查。','kind':'user_report','evidence':['e-3']}],
                'interpretation':[{'text':'较小的时间预算可能需要缩小练习，仍需确认实际余量。','kind':'estimate','evidence':['e-4']}],
                'tomorrow':[{'text':'按实际精力补一个例子，再保存一次试录。','kind':'suggestion','goal_id':'g-speaking','evidence':['e-1','e-3']}]}
    def test_clock_is_live_and_source_explicit(self):
        before=datetime.now(timezone.utc);result=daily.clock('+08:00');after=datetime.now(timezone.utc)
        self.assertLessEqual(before,daily.instant(result['utc_time']));self.assertLessEqual(daily.instant(result['utc_time']),after)
        self.assertEqual(result['source'],'system_clock')
    def test_manual_clock_does_not_claim_system(self):
        result=daily.clock('+08:00','2026-10-12T16:30:00Z')
        self.assertTrue(result['local_time'].startswith('2026-10-13T00:30:00'))
        self.assertEqual(result['source'],'provided_timestamp')
    def test_timezone_is_not_guessed(self):
        with self.assertRaises(ValueError):daily.instant('2026-10-13T12:00:00')
        with self.assertRaises(ValueError):daily.offset_zone('+14:30')
    def test_empty_day_is_honest_and_nonwriting(self):
        c=self.context();self.assertEqual(c['timeline'],[]);self.assertFalse(self.root.exists())
        result=daily.report(self.root,c,daily.preview(c),'rules',False)
        self.assertIn('0条',result['markdown']);self.assertIn('规则预览',result['markdown'])
        with self.assertRaises(ValueError):daily.report(self.root,c,daily.preview(c),'rules',True)
    def test_full_day_includes_early_plan_and_late_result(self):
        self.seed();c=self.context()
        self.assertEqual([t['event_id'] for t in c['timeline']],['e-2','e-3','e-4'])
        self.assertEqual(c['timeline'][0]['event']['status'],'planned')
        self.assertEqual(c['actions']['a-first']['status'],'completed')
    def test_recorded_utc_converts_to_local_day(self):
        self.add('note','n-first',text='late UTC record',as_of='2026-10-12T17:00:00Z')
        self.assertEqual(len(self.context()['timeline']),1)
    def test_backdated_correction_and_future_exclusion(self):
        self.add('profile',key='weekly_minutes',value=90,as_of='2026-10-12')
        self.add('profile',key='weekly_minutes',value=30,as_of='2026-10-12')
        self.add('profile',key='weekly_minutes',value=999,as_of='2026-10-14')
        c=self.context('2026-10-12');self.assertEqual(c['profile']['weekly_minutes']['value'],30)
        self.assertEqual(len(c['timeline']),2)
    def test_prior_background_does_not_become_today_progress(self):
        self.seed();c=self.context('2026-10-14');self.assertEqual(c['timeline'],[])
        result=daily.report(self.root,c,daily.preview(c),'rules',False);self.assertIn('0条',result['markdown'])
        analysis=self.model_analysis();analysis['progress'][0]['evidence']=['e-3']
        with self.assertRaises(ValueError):daily.validate_analysis(c,analysis)
    def test_unknown_evidence_is_rejected(self):
        self.seed();a=self.model_analysis();a['overview']['evidence']=['invented']
        with self.assertRaises(ValueError):daily.validate_analysis(self.context(),a)
    def test_unrelated_old_completed_action_is_not_exported(self):
        self.seed();self.add('action','a-old',goal_id='g-speaking',text='old private detail',status='completed',evidence='Synthetic past report',as_of='2026-10-12')
        self.assertNotIn('a-old',self.context()['actions'])
    def test_user_report_cannot_be_claimed_observed_fact(self):
        self.seed();a=self.model_analysis();a['progress'][0]['kind']='fact'
        with self.assertRaises(ValueError):daily.validate_analysis(self.context(),a)
    def test_report_refuses_paused_goal_guidance(self):
        self.seed();self.add('goal','g-speaking',status='paused',category='user_decision')
        with self.assertRaises(ValueError):daily.validate_analysis(self.context(),self.model_analysis())
    def test_report_is_short_and_revisions_preserve_original(self):
        self.seed();c=self.context();a=self.model_analysis();raw=(self.root/'history.jsonl').read_bytes()
        first=daily.report(self.root,c,a,'model',True);self.assertTrue(first['changed'])
        self.assertFalse(daily.report(self.root,c,a,'model',True)['changed'])
        amended=copy.deepcopy(a);amended['interpretation'][0]['text']='时间预算下降，需要先确认明日可用精力。'
        self.assertTrue(daily.report(self.root,c,amended,'model',True)['changed'])
        self.assertEqual(len(list((self.root/'reports/history').glob('*.md'))),1)
        self.assertEqual((self.root/'history.jsonl').read_bytes(),raw)
        self.assertLess(len(first['markdown']),700)
    def test_manual_report_is_not_overwritten(self):
        self.seed();c=self.context();a=self.model_analysis();daily.report(self.root,c,a,'model',True)
        p=self.root/'reports/2026-10-13.md';p.write_text('user edit',encoding='utf-8')
        with self.assertRaises(ValueError):daily.report(self.root,c,a,'model',True)
        self.assertEqual(p.read_text(),'user edit')
    def test_only_accepted_due_actions_are_reminded(self):
        self.add('goal','g-speaking',title='口语练习',status='active',category='user_decision')
        self.add('action','a-unaccepted',goal_id='g-speaking',text='建议练习',status='planned',check_at='2026-10-13T09:00:00+08:00',category='ai_suggestion')
        self.assertEqual(daily.due_context(self.root,'+08:00','2026-10-13T10:00:00+08:00')['due'],[])
        self.add('action','a-unaccepted',category='user_decision')
        self.assertEqual(len(daily.due_context(self.root,'+08:00','2026-10-13T10:00:00+08:00')['due']),1)
        self.add('goal','g-speaking',status='paused',category='user_decision')
        self.assertEqual(daily.due_context(self.root,'+08:00','2026-10-13T10:00:00+08:00')['due'],[])
    def test_quiet_window_and_no_background_claim(self):
        self.add('profile',key='quiet_until',value='2026-10-13T11:00:00+08:00',category='user_preference')
        result=daily.due_context(self.root,'+08:00','2026-10-13T10:00:00+08:00')
        self.assertTrue(result['quiet']);self.assertFalse(result['notification_service'])
    def test_excessive_report_and_naive_due_time_are_rejected(self):
        self.seed();a=self.model_analysis();a['overview']['text']='字'*181
        with self.assertRaises(ValueError):daily.validate_analysis(self.context(),a)
        self.add('action','a-date',goal_id='g-speaking',text='检查',status='planned',category='user_decision',check_at='2026-10-13T09:00:00')
        with self.assertRaises(ValueError):daily.due_context(self.root,'+08:00','2026-10-13T10:00:00+08:00')

if __name__=='__main__':unittest.main()
