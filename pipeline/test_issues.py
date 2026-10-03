import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import subprocess
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from pipeline.issues import GH_TIMEOUT_SECONDS, sync, body, triage_job, gh
from pipeline import editorial


class IssueTests(unittest.TestCase):
    def test_remote_sync_retry_preserves_finding_packet_but_new_review_changes_it(self):
        with tempfile.TemporaryDirectory() as temp:
            job = Path(temp)
            state = {'character': '八', 'status': 'approved', 'article_hash': 'original'}
            editorial.write(job / 'status.json', state)
            packets = []
            class Runner:
                model, reasoning = 'gpt-6-luna', 'low'
                def run(self, role, inputs, schema, directory):
                    packets.append(inputs)
                    return {'findings': []}
            runner = Runner()
            triage_job(job, {'id': 'fixture'}, runner)
            editorial.write(job / 'status.json', {**state, 'issue_sync_status': 'pending',
                                                   'issue_receipts_hash': 'remote-retry'})
            triage_job(job, {'id': 'fixture'}, runner)
            self.assertEqual(packets[0], packets[1])
            editorial.write(job / 'status.json', {**state, 'article_hash': 'new-candidate'})
            triage_job(job, {'id': 'fixture'}, runner)
            self.assertNotEqual(packets[1], packets[2])

    def test_triage_sees_current_page_label_instead_of_stale_locator_null(self):
        with tempfile.TemporaryDirectory() as temp:
            job = Path(temp)
            corpus = job / 'corpus.jsonl'
            corpus.write_text('\n'.join(json.dumps(row) for row in [
                {'book_id': 'edition', 'pdf_page_1based': 76, 'printed_page': 64,
                 'source_sha256': 'pixels', 'text': 'Do not send full page text',
                 'metadata_provenance': {'metadata_sha256': 'verified-overlay'}},
                {'book_id': 'other-edition', 'pdf_page_1based': 76, 'printed_page': 99},
                {'book_id': 'edition', 'pdf_page_1based': 77, 'printed_page': None}]) + '\n')
            editorial.write(job / 'status.json', {'character': '八'})
            editorial.write(job / 'source_checkpoint.json', {'locator': {'source_leads': [
                {'candidates': [{'pdf_page_1based': 76, 'printed_page': None}]}]}})
            class Runner:
                model, reasoning = 'gpt-6-luna', 'low'
                def run(self, role, inputs, schema, directory):
                    observed = inputs['current_source_page_metadata']
                    assert len(observed) == 1 and observed[0]['printed_page'] == 64
                    assert observed[0]['metadata_provenance']['metadata_sha256'] == 'verified-overlay'
                    assert 'text' not in observed[0]
                    return {'findings': []}
            triage_job(job, {'id': 'book', 'book_id': 'edition', 'corpus_path': str(corpus)}, Runner())

    def test_full_parent_reports_actionable_capacity_without_duplicate_or_post(self):
        finding = dict(key='book:claim', kind='factual', title='Claim',
                       details='A supported finding.', verification='Fresh review.')
        calls = []
        def invoke(*args):
            calls.append(args)
            if args[:2] == ('issue', 'list'):
                return json.dumps([dict(number=500, url='https://github.com/owner/repo/issues/500',
                                       body=body(finding), state='OPEN', labels=[{'name':'kind:factual'}])])
            if args[:2] == ('label', 'list'):
                return '[{"name":"kind:factual"}]'
            if args[-1].endswith('/sub_issues'):
                return json.dumps([{'number': n} for n in range(2, 102)])
            if args[-1].endswith('/parent'):
                return '{}'
            self.fail('Unexpected mutation: ' + repr(args))
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(ValueError, 'configure a nested findings parent'):
                sync([finding], 'owner/repo', Path(temp)/'receipt.json', invoke, parent_issue=1)
        self.assertFalse(any(c[:2] == ('issue', 'create') or '--method' in c for c in calls))

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

    def test_concurrent_same_key_syncs_serialize_lookup_and_create(self):
        finding = dict(key='source:木:claim', kind='factual', title='Verify claim',
                       details='A cited claim needs checking.', verification='Fresh factual review.')
        remote, calls = [], []
        lock = threading.Lock()
        def invoke(*args):
            with lock:
                calls.append(args)
                if args[:2] == ('issue', 'list'):
                    return json.dumps(list(remote))
                if args[:2] == ('issue', 'create'):
                    content = Path(args[args.index('--body-file') + 1]).read_text()
                    # Widen the race window: without the repo lock both workers
                    # observe an empty list before either issue is visible.
                    time.sleep(0.05)
                    issue = {'number': len(remote) + 1,
                             'url': f'https://github.com/owner/repo/issues/{len(remote) + 1}',
                             'body': content, 'state': 'OPEN'}
                    remote.append(issue)
                    return issue['url']
                self.fail('Unexpected GitHub operation: ' + repr(args))
        with tempfile.TemporaryDirectory() as temp:
            receipts = [Path(temp) / 'first.json', Path(temp) / 'second.json']
            barrier = threading.Barrier(2)
            def run(receipt):
                barrier.wait()
                return sync([finding], 'owner/repo', receipt, invoke)
            with ThreadPoolExecutor(max_workers=2) as pool:
                first, second = [future.result() for future in
                                 [pool.submit(run, receipt) for receipt in receipts]]
        self.assertEqual(first[0]['number'], second[0]['number'])
        self.assertEqual(len(remote), 1)
        self.assertEqual(sum(call[:2] == ('issue', 'create') for call in calls), 1)

    def test_gh_subprocess_timeout_is_bounded_and_propagates_for_retry(self):
        timeout = subprocess.TimeoutExpired(['gh', 'issue', 'list'], 1)
        with patch('pipeline.issues.subprocess.run', side_effect=timeout) as run:
            with self.assertRaises(subprocess.TimeoutExpired):
                gh('issue', 'list')
        self.assertEqual(run.call_args.kwargs['timeout'], GH_TIMEOUT_SECONDS)

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

    def test_triage_receives_validated_resolution_without_claiming_corpus_repair(self):
        from unittest.mock import patch
        class Runner:
            model = 'gpt-6-luna'
            reasoning = 'low'
            def run(self, role, inputs, schema, directory):
                self.inputs = inputs
                return {'findings': []}
        with tempfile.TemporaryDirectory() as temp:
            job = Path(temp)
            editorial.write(job / 'status.json', {'character': '八', 'status': 'approved'})
            result = {'findings': [{'key': 'label', 'disposition': 'verified_metadata_not_extracted'}],
                      'metadata_observations': [{'key': 'label', 'observed_value': '64'}]}
            binding = {'review_path': 'source-resolution/result.json',
                       'result_hash': editorial.digest(result)}
            editorial.write(job / 'source_resolution.json', binding)
            editorial.write(job / binding['review_path'], result)
            runner = Runner()
            with patch('pipeline.source_enrichment._source_findings_pending', return_value=False):
                triage_job(job, {'id': 'book'}, runner)
            packet = next(r['content'] for r in runner.inputs['actual_findings']
                          if r['artifact'] == 'source_resolution.json')
            self.assertFalse(packet['pending'])
            self.assertEqual(packet['actual_result'], result)
            self.assertEqual(packet['binding'], binding)
            self.assertIn('corpus metadata repair may remain unapplied', runner.inputs['task'])

    def test_triage_reuses_only_hash_bound_previous_syncs_for_the_same_repository(self):
        from unittest.mock import patch
        class Runner:
            model = 'gpt-6-luna'
            reasoning = 'low'
            def run(self, role, inputs, schema, directory):
                self.inputs = inputs
                return {'findings': []}
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            job = root / 'new'
            editorial.write(job / 'status.json', {'character': '八'})
            for name, repository, valid in [('synced', 'owner/repo', True),
                                             ('other-repo', 'other/repo', True),
                                             ('changed-proposal', 'owner/repo', False)]:
                finding = {'key': f'book:八:{name}', 'kind': 'factual', 'title': name,
                           'details': 'Fixture finding.', 'verification': 'Fixture check.', 'evidence': []}
                previous = root / 'runs' / name
                editorial.write(previous / 'issue_findings.json', {'findings': [finding]})
                editorial.write(previous / 'issue_receipts.json', {'repository': repository, 'issues': [{
                    'key': finding['key'], 'number': 42,
                    'finding_hash': editorial.digest(finding) if valid else 'stale'}]})
            runner = Runner()
            with patch.object(editorial, 'ROOT', root):
                triage_job(job, {'id': 'book', 'github_repo': 'owner/repo'}, runner)
            self.assertEqual([f['key'] for f in runner.inputs['existing_findings']], ['book:八:synced'])

    def test_triage_does_not_reuse_another_character_or_source_finding(self):
        from unittest.mock import patch
        from pipeline import editorial
        class Runner:
            model = 'gpt-6-luna'
            reasoning = 'low'
            def run(self, role, inputs, schema, directory):
                self.inputs, self.schema = inputs, schema
                return {'findings': []}
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            job = root/'job'
            editorial.write(job/'status.json', {'character':'月', 'status':'approved'})
            keys = ['book:爱:meaning-status', 'book:6708:meaning-status',
                    'book:月:dating', 'other-book:月:dating', 'pipeline:review:certainty']
            editorial.write(root/'research/source-enrichment-findings.json',
                            {'findings': [{'key': key} for key in keys] +
                             [{'key':'hsk1:source-enrichment:book', 'kind':'work'}]})
            runner = Runner()
            with patch.object(editorial, 'ROOT', root):
                triage_job(job, {'id':'book'}, runner)
            expected = ['book:6708:meaning-status', 'book:月:dating', 'pipeline:review:certainty']
            self.assertEqual([f['key'] for f in runner.inputs['existing_findings']], expected)
            self.assertEqual(runner.schema['properties']['findings']['items']['properties']
                             ['existing_key']['enum'], [None, *expected])

    def test_triage_receives_exact_current_cited_and_review_referenced_evidence(self):
        class Runner:
            model = 'gpt-6-luna'
            reasoning = 'low'
            def run(self, role, inputs, schema, directory):
                self.inputs = inputs
                return {'findings': []}
        with tempfile.TemporaryDirectory() as temp:
            job = Path(temp)
            editorial.write(job/'status.json', {'character':'火', 'status':'approved'})
            editorial.write(job/'article.json', {'summary':{'text':'Fire.', 'evidence_ids':['E1']}})
            dossier = {'character':'火', 'evidence':[
                {'id':'E1', 'text':'Current meaning from inspected dictionary.'},
                {'id':'X-abc123', 'text':'Support mentioned by the retained review.'},
                {'id':'E11', 'text':'Unrelated imported definition.'}]}
            editorial.write(job/'dossier.json', dossier)
            editorial.write(job/'round-0/factual-verification/verified-review.json',
                            {'verdict':'revise', 'findings':['Inspect X-abc123 for this claim.']})
            runner = Runner()
            triage_job(job, {'id':'book'}, runner)
            packet = runner.inputs['current_dossier_evidence']
            self.assertEqual(packet['dossier_hash'], editorial.digest(dossier))
            self.assertEqual([e['id'] for e in packet['evidence']], ['E1','X-abc123'])
            self.assertEqual(packet['evidence'][0]['text'], dossier['evidence'][0]['text'])
            runner.reasoning = 'high'
            with self.assertRaises(ValueError):
                triage_job(job, {'id': 'book'}, runner)


if __name__ == '__main__':
    unittest.main()
