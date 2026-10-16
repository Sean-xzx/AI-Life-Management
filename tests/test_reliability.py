"""Synthetic multi-turn regressions; never reads personal records or images."""
from pathlib import Path
import copy
from datetime import date, datetime
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('reliable_daily', ROOT/'ai-life-management-easy/scripts/daily.py')
daily = importlib.util.module_from_spec(spec); spec.loader.exec_module(daily)
core = daily.core


class ReliabilityTests(unittest.TestCase):
    def setUp(self):
        scratch = ROOT/'tmp'; scratch.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix='reliability-', dir=scratch)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)/'records'; self.rev = 0

    def add(self, op='note', key='n-source', **fields):
        event = {'operation': op, 'category': 'user_report', 'source': 'Synthetic fixture',
                 'as_of': '2030-04-03', **fields}
        if op == 'profile': event['key'] = key
        else: event['record_id'] = key
        if op not in {'profile', 'goal', 'action'}: event.setdefault('text', 'Synthetic report')
        eid = f'e-{self.rev+1}'
        state, _ = core.commit(self.root, event, self.rev, eid)
        self.rev = state['revision']; return eid

    def context(self): return daily.day_context(self.root, '2030-04-03', '+08:00')

    def analysis(self, source):
        return {'overview': {'text': 'Current evidence only.', 'evidence': [source]},
                'progress': [], 'interpretation': [], 'tomorrow': []}

    def seed_legacy(self, event):
        self.root.mkdir()
        item = {'revision': 1, 'event_id': 'e-1', 'recorded_at': '2030-04-03T02:00:00+00:00',
                'event': {'operation': 'note', 'record_id': 'n-source', 'text': 'Synthetic legacy',
                          'category': 'user_report', 'source': 'Synthetic old release', **event}}
        (self.root/'history.jsonl').write_text(json.dumps(item)+'\n', encoding='utf-8')
        self.rev = 1

    def test_iso_date_keeps_day_precision(self):
        value = core.temporal('2030-04-03')
        self.assertIs(type(value), date)

    def test_offset_timestamp_converts_local_day(self):
        self.add(as_of='2030-04-02T17:00:00Z')
        self.assertEqual(len(self.context()['timeline']), 1)

    def test_new_named_zone_spelling_is_rejected_before_append(self):
        self.add(); before = (self.root/'history.jsonl').read_bytes()
        with self.assertRaises(ValueError): self.add(as_of='2030-04-03 Asia/Shanghai')
        self.assertEqual((self.root/'history.jsonl').read_bytes(), before)

    def test_new_naive_timestamp_is_rejected(self):
        with self.assertRaises(ValueError): self.add(as_of='2030-04-03T09:00:00')
        self.assertFalse((self.root/'history.jsonl').exists())

    def test_impossible_date_is_rejected(self):
        with self.assertRaises(ValueError): self.add(as_of='2030-02-30')

    def test_legacy_named_zone_log_replays_without_rewrite(self):
        self.seed_legacy({'as_of': '2030-04-03 Asia/Shanghai'})
        before = (self.root/'history.jsonl').read_bytes()
        self.assertEqual(len(self.context()['timeline']), 1)
        self.add(key='n-new')
        self.assertTrue((self.root/'history.jsonl').read_bytes().startswith(before))

    def test_legacy_zone_is_not_silently_guessed(self):
        self.seed_legacy({'as_of': '2030-04-03 Ambiguous/Place'})
        with self.assertRaises(ValueError): self.context()

    def test_day_checkpoint_is_not_a_midnight_alarm(self):
        self.add('action', 'a-check', text='Review', category='user_decision',
                 status='planned', check_at='2030-04-03')
        result = daily.due_context(self.root, '+08:00', '2030-04-03T10:00:00+08:00')
        self.assertEqual(result['due'], [])
        self.assertTrue(result['date_checkpoints'][0]['time_unknown'])
        self.assertNotIn('check_at', result['date_checkpoints'][0])

    def test_legacy_day_checkpoint_replays_without_alarm(self):
        self.seed_legacy({'operation': 'action', 'record_id': 'a-check', 'text': 'Review',
                          'status': 'planned', 'category': 'user_decision',
                          'as_of': '2030-04-03 Asia/Shanghai', 'check_at': '2030-04-03 Asia/Shanghai'})
        result = daily.due_context(self.root, '+08:00', '2030-04-03T10:00:00+08:00')
        self.assertEqual(result['due'], [])
        self.assertEqual(len(result['date_checkpoints']), 1)

    def test_new_checkpoint_requires_valid_date_or_offset(self):
        with self.assertRaises(ValueError):
            self.add('action', 'a-check', text='Review', check_at='2030-04-03T10:00:00')

    def test_unknown_dependency_is_rejected(self):
        with self.assertRaises(ValueError): self.add(category='estimate', depends_on=['missing'])

    def test_duplicate_or_untyped_dependencies_are_rejected(self):
        eid = self.add()
        for sources in ([eid, eid], [42], 'e-1', [{}]):
            with self.subTest(sources=sources), self.assertRaises(ValueError):
                self.add(key='n-estimate', category='estimate', depends_on=sources)

    def test_food_correction_invalidates_estimate(self):
        eid = self.add(text='Serving shown; amount eaten unconfirmed.')
        self.add(key='n-total', text='Conditional total.', category='estimate', depends_on=[eid])
        self.add(text='User ate none of the pictured grain.')
        self.assertIn('note:n-total', self.context()['invalidated'])

    def test_journal_marks_old_estimate_until_recomputed(self):
        original = self.add()
        self.add(key='n-total', text='Old estimate', category='estimate', depends_on=[original])
        correction = self.add(text='Corrected intake')
        journal = (self.root/'journal.md').read_text(encoding='utf-8')
        self.assertIn('【待重算，不作当前依据】n-total', journal)
        self.add(key='n-total', text='New estimate', category='estimate', depends_on=[correction])
        journal = (self.root/'journal.md').read_text(encoding='utf-8')
        self.assertNotIn('【待重算，不作当前依据】n-total', journal)

    def test_invalidation_propagates_to_plan(self):
        original = self.add()
        estimate = self.add(key='n-total', category='estimate', depends_on=[original])
        self.add(key='n-plan', category='ai_suggestion', depends_on=[estimate])
        self.add(text='Correction')
        self.assertIn('note:n-plan', self.context()['invalidated'])

    def test_recomputed_total_uses_latest_source(self):
        original = self.add()
        self.add(key='n-total', category='estimate', depends_on=[original])
        correction = self.add(text='Correction')
        self.add(key='n-total', category='estimate', depends_on=[correction])
        self.assertNotIn('note:n-total', self.context()['invalidated'])

    def test_old_source_cannot_create_new_estimate(self):
        original = self.add(); self.add(text='Correction')
        with self.assertRaises(ValueError):
            self.add(key='n-total', category='estimate', depends_on=[original])

    def test_transitively_invalid_source_cannot_create_plan(self):
        original = self.add()
        estimate = self.add(key='n-total', category='estimate', depends_on=[original])
        self.add(text='Correction')
        with self.assertRaises(ValueError):
            self.add(key='n-plan', category='ai_suggestion', depends_on=[estimate])

    def test_dependency_cycles_are_rejected(self):
        original = self.add()
        estimate = self.add(key='n-total', category='estimate', depends_on=[original])
        with self.assertRaises(ValueError): self.add(category='estimate', depends_on=[estimate])

    def test_undeclared_legacy_estimate_is_not_claimed_valid(self):
        self.add(category='estimate')
        self.assertIn('note:n-source', self.context()['untracked_derived'])

    def test_goal_title_change_needs_user_decision(self):
        self.add('goal', 'g-test', title='Initial goal', category='user_decision')
        with self.assertRaises(ValueError):
            self.add('goal', 'g-test', title='AI alternative', category='ai_suggestion')

    def test_goal_change_retires_linked_unaccepted_plan(self):
        self.add('goal', 'g-test', title='Initial goal', category='user_decision')
        self.add('action', 'a-plan', text='Small step', category='ai_suggestion', goal_id='g-test')
        self.add('goal', 'g-test', title='User changed goal', category='user_decision')
        self.assertIn('action:a-plan', self.context()['invalidated'])

    def test_goal_change_preserves_real_completion(self):
        self.add('goal', 'g-test', title='Initial goal', category='user_decision')
        self.add('action', 'a-done', text='Actual work', category='user_report', goal_id='g-test',
                 status='completed', evidence='Synthetic user completion')
        self.add('goal', 'g-test', title='Updated goal', category='user_decision')
        self.assertNotIn('action:a-done', self.context()['invalidated'])
        self.assertEqual(self.context()['actions']['a-done']['status'], 'completed')

    def test_goal_change_also_retires_old_accepted_reminder(self):
        self.add('goal', 'g-test', title='Initial goal', category='user_decision')
        self.add('action', 'a-plan', text='Accepted old step', category='user_decision',
                 goal_id='g-test', check_at='2030-04-03T09:00:00+08:00')
        self.add('goal', 'g-test', title='Changed goal', category='user_decision')
        result = daily.due_context(self.root, '+08:00', '2030-04-03T10:00:00+08:00')
        self.assertEqual(result['due'], [])

    def test_report_rejects_current_claim_from_superseded_evidence(self):
        original = self.add(); self.add(text='Correction')
        with self.assertRaises(ValueError): daily.validate_analysis(self.context(), self.analysis(original))

    def test_historical_comparison_is_explicit(self):
        original = self.add(); correction = self.add(text='Correction')
        analysis = self.analysis(correction)
        analysis['interpretation'] = [{'text': 'Earlier report was corrected.', 'kind': 'estimate',
                                       'historical': True, 'evidence': [original, correction]}]
        daily.validate_analysis(self.context(), analysis)
        self.assertIn('历史复盘', daily.render_report(self.context(), analysis, 'model'))

    def test_detailed_action_plan_has_explicit_domains(self):
        eid = self.add()
        analysis = self.analysis(eid)
        analysis['action_plan'] = [{'area': area, 'text': 'A proposed action, not completed.',
                                   'kind': 'suggestion', 'evidence': [eid]}
                                  for area in ('学习', '恢复', '饮食', '时间安排')]
        with self.assertRaises(ValueError): daily.validate_analysis(self.context(), analysis)
        result = daily.report(self.root, self.context(), analysis, 'model', True, 'detailed')
        self.assertEqual(result['report']['layout'], 'detailed')
        self.assertIn('尚未执行', result['markdown'])
        self.assertIn('恢复', result['markdown'])
        self.assertFalse(daily.report(self.root, self.context(), analysis, 'model', True, 'detailed')['changed'])

    def test_detailed_report_keeps_evidence_category_checks(self):
        eid = self.add(); analysis = self.analysis(eid)
        analysis['progress'] = [{'text': 'Claimed independently verified.', 'kind': 'fact', 'evidence': [eid]}]
        with self.assertRaises(ValueError): daily.validate_analysis(self.context(), analysis, 'detailed')

    def test_stale_context_cannot_overwrite_report(self):
        eid = self.add(); context = self.context(); analysis = self.analysis(eid)
        daily.report(self.root, context, analysis, 'model', True)
        path = self.root/'reports/2030-04-03.md'; before = path.read_bytes()
        self.add(key='n-late', text='Late supplement')
        with self.assertRaises(ValueError): daily.report(self.root, context, analysis, 'model', True)
        self.assertEqual(path.read_bytes(), before)

    def test_record_writer_lock_is_never_removed_by_report(self):
        eid = self.add(); lock = self.root/'.life-store.lock'; lock.write_text('other writer')
        with self.assertRaises(ValueError): daily.report(self.root, self.context(), self.analysis(eid), 'model', True)
        self.assertEqual(lock.read_text(), 'other writer')

    def test_cli_scoped_read_retains_global_revision_and_validity(self):
        self.add(); self.add(key='n-other', text='Unrelated synthetic record')
        process = subprocess.run([sys.executable, '-B', str(ROOT/'ai-life-management/scripts/life_store.py'),
                                  '--root', str(self.root), 'show', '--record-id', 'n-source', '--with-validity'],
                                 capture_output=True, text=True, encoding='utf-8')
        self.assertEqual(process.returncode, 0, process.stderr)
        result = json.loads(process.stdout)
        self.assertEqual(result['state']['revision'], 2)
        self.assertEqual(set(result['state']['notes']), {'n-source'})
        self.assertEqual(set(result['current_sources']), {'note:n-source'})

    def test_legacy_to_correction_to_report_end_to_end(self):
        self.seed_legacy({'as_of': '2030-04-03 Asia/Shanghai'})
        old_log = (self.root/'history.jsonl').read_bytes()
        correction = self.add(text='User corrected the reported amount.')
        estimate = self.add(key='n-total', category='estimate', depends_on=[correction])
        analysis = self.analysis(estimate)
        first = daily.report(self.root, self.context(), analysis, 'model', True)
        self.assertTrue(first['saved'])
        self.assertFalse(daily.report(self.root, self.context(), analysis, 'model', True)['changed'])
        newer = self.add(text='Another correction')
        self.assertIn('note:n-total', self.context()['invalidated'])
        with self.assertRaises(ValueError): daily.validate_analysis(self.context(), analysis)
        final = self.add(key='n-total', category='estimate', depends_on=[newer])
        daily.report(self.root, self.context(), self.analysis(final), 'model', True)
        self.assertEqual(len(list((self.root/'reports/history').glob('*.md'))), 1)
        self.assertTrue((self.root/'history.jsonl').read_bytes().startswith(old_log))


if __name__ == '__main__': unittest.main()
