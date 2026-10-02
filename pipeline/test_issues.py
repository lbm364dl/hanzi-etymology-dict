import json
from pathlib import Path
import tempfile
import unittest

from pipeline.issues import sync, body, triage_job
from pipeline import editorial


class IssueTests(unittest.TestCase):
    def test_paginated_hierarchy_and_unchanged_metadata_need_no_mutation(self):
        finding = dict(key='book:ocr', kind='ocr', title='OCR', details='Exact occurrence.', verification='Scan check.')
        calls = []
        def invoke(*args):
            calls.append(args)
            if args[:2] == ('issue', 'list'):
                return json.dumps([dict(number=42, url='https://github.com/owner/repo/issues/42',
                    body=body(finding), state='OPEN', labels=[{'name':'scope:hsk1'}, {'name':'kind:ocr'}],
                    milestone={'title':'Smoke', 'number':1})])
            if args[:2] == ('label', 'list'):
                return '[{"name":"scope:hsk1"},{"name":"kind:ocr"}]'
            if args[-1].endswith('/sub_issues'):
                self.assertIn('--paginate', args)
                return '[{"number":2}]\n[{"number":42}]'
            self.fail('Unexpected mutation or parent lookup: ' + repr(args))
        with tempfile.TemporaryDirectory() as temp:
            receipts = sync([finding], 'owner/repo', Path(temp)/'receipts.json', invoke,
                            parent_issue=1, milestone='Smoke', labels=['scope:hsk1'])
        self.assertEqual(receipts[0]['number'], 42)

    def test_active_finding_reopens_closed_issue_but_archive_sync_does_not(self):
        finding = dict(key='book:claim', kind='factual', title='Claim',
                       details='New verification failed.', verification='Fresh reviews.')
        calls = []
        def invoke(*args):
            calls.append(args)
            if args[:2] == ('issue', 'list'):
                return json.dumps([dict(number=3, url='https://github.com/owner/repo/issues/3',
                                        body=body(finding), state='CLOSED')])
            return ''
        with tempfile.TemporaryDirectory() as temp:
            receipt = Path(temp) / 'receipt.json'
            archived = sync([finding], 'owner/repo', receipt, invoke)
            self.assertEqual(archived[0]['state'], 'CLOSED')
            self.assertFalse(any(c[:2] == ('issue', 'reopen') for c in calls))
            active = sync([finding], 'owner/repo', receipt, invoke, active_findings=True)
            self.assertEqual(active[0]['state'], 'OPEN')
            self.assertEqual(sum(c[:2] == ('issue', 'reopen') for c in calls), 1)

    def test_existing_curated_parent_is_preserved(self):
        finding = dict(key='book:ocr', kind='ocr', title='OCR error', details='Scan issue.', verification='Check pixels.')
        calls = []
        def invoke(*args):
            calls.append(args)
            if args[:2] == ('issue', 'list'):
                return json.dumps([dict(number=6, url='https://github.com/owner/repo/issues/6', body=body(finding), state='OPEN')])
            if args[:2] == ('label', 'list') or args[-1].endswith('/sub_issues'):
                return '[]'
            if args[-1].endswith('/parent'):
                return '{"number":5}'
            return ''
        with tempfile.TemporaryDirectory() as temp:
            sync([finding], 'owner/repo', Path(temp) / 'receipt.json', invoke,
                 parent_issue=1, parent_by_kind={'ocr': 5})
        self.assertTrue(any(call[-1].endswith('/issues/5/sub_issues') for call in calls))
        self.assertFalse(any('--method' in call for call in calls))

    def test_hierarchy_uses_database_id_and_preserves_labels_and_milestone(self):
        finding = dict(key='book:木:error', kind='ocr', title='OCR error', details='Observed scan issue.', verification='Verify pixels.')
        calls = []
        def invoke(*args):
            calls.append(args)
            if args[:2] == ('issue', 'list') or args[:2] == ('label', 'list'):
                return '[]'
            if args[:2] == ('issue', 'create'):
                return 'https://github.com/owner/repo/issues/5'
            if args == ('api', 'repos/owner/repo/issues/5'):
                return '{"id":10001,"number":5}'
            if args[:1] == ('api',) and args[-1].endswith('/sub_issues'):
                return '[]'
            return ''
        with tempfile.TemporaryDirectory() as temp:
            sync([finding], 'owner/repo', Path(temp) / 'receipt.json', invoke,
                 parent_issue=1, milestone='Smoke', labels=['scope:hsk1'])
        self.assertTrue(any('sub_issue_id=10001' in call for call in calls))
        self.assertTrue(any('--milestone' in call and 'Smoke' in call and 'kind:ocr' in call for call in calls))

    def test_retry_after_creation_deduplicates_remote_issue(self):
        finding = dict(key='source:木:claim', kind='factual', title='Verify claim',
                       details='A cited claim needs checking.', verification='Fresh factual review.')
        remote = []
        calls = []
        def invoke(*args):
            calls.append(args)
            if args[:2] == ('issue', 'list'):
                return json.dumps(remote)
            self.assertEqual(args[:2], ('issue', 'create'))
            text = Path(args[args.index('--body-file') + 1]).read_text()
            remote.append(dict(number=1, url='https://github.com/owner/repo/issues/1', body=text, state='OPEN'))
            return remote[-1]['url']
        with tempfile.TemporaryDirectory() as temp:
            receipt = Path(temp) / 'receipts.json'
            first = sync([finding], 'owner/repo', receipt, invoke)
            receipt.unlink()  # Remote identity survives loss of a local checkpoint.
            second = sync([finding], 'owner/repo', receipt, invoke)
            self.assertEqual(first, second)
            self.assertEqual(sum(c[:2] == ('issue', 'create') for c in calls), 1)
            self.assertFalse(any('close' in c for c in calls))

    def test_empty_verification_is_rejected(self):
        with self.assertRaises(ValueError):
            body(dict(key='x', kind='ocr', title='Error', details='Text', verification=''))

    def test_unknown_existing_key_is_repaired_before_sync(self):
        class Runner:
            model = 'gpt-6-luna'
            reasoning = 'low'
            calls = 0
            def run(self, role, inputs, schema, directory):
                self.calls += 1
                allowed = schema['properties']['findings']['items']['properties']['existing_key']['enum']
                assert None in allowed and 'invented:key' not in allowed
                if self.calls == 1:
                    return {'findings': [{'existing_key': 'invented:key'}]}
                assert 'unknown existing' in inputs['validation_error']
                return {'findings': []}
        with tempfile.TemporaryDirectory() as temp:
            job = Path(temp)
            editorial.write(job / 'status.json', {'character': '木'})
            runner = Runner()
            self.assertEqual(triage_job(job, {'id': 'book'}, runner), [])
            self.assertEqual(runner.calls, 2)

    def test_triage_uses_verified_artifacts_and_exact_agent_settings(self):
        class Runner:
            model = 'gpt-6-luna'
            reasoning = 'low'
            def run(self, role, inputs, schema, directory):
                self.role, self.inputs = role, inputs
                return {'findings': []}
        with tempfile.TemporaryDirectory() as temp:
            job = Path(temp)
            editorial.write(job / 'status.json', {'character': '木', 'status': 'approved'})
            editorial.write(job / 'round-0/factual/proposed-review.json', {'verdict': 'revise', 'findings': ['Rejected claim']})
            editorial.write(job / 'round-0/factual-verification/verified-review.json', {'verdict': 'pass', 'findings': []})
            runner = Runner()
            self.assertEqual(triage_job(job, {'id': 'book'}, runner), [])
            self.assertEqual(runner.role, 'finding_triage')
            self.assertEqual(len(runner.inputs['actual_findings']), 1)
            self.assertNotIn('Rejected claim', str(runner.inputs['actual_findings']))
            runner.reasoning = 'high'
            with self.assertRaises(ValueError):
                triage_job(job, {'id': 'book'}, runner)


if __name__ == '__main__':
    unittest.main()
