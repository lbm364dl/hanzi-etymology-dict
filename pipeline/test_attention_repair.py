import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from pipeline import attention_repair, editorial


class AttentionRepairTests(unittest.TestCase):
    def test_patch_contract_names_the_exact_overlapping_paths(self):
        paths = {
            'components': ('components',),
            'components/0/text': ('components', 0, 'text'),
            'learner/components': ('learner', 'components'),
        }
        edits = [{'path': path} for path in paths]
        self.assertEqual(editorial.overlapping_article_patch_paths(edits, paths),
                         [('components', 'components/0/text')])

    def test_only_terminal_attention_jobs_can_be_reused(self):
        with tempfile.TemporaryDirectory() as temporary:
            job = Path(temporary)
            editorial.write(job / 'status.json', {'status': 'running'})
            with self.assertRaisesRegex(ValueError, 'not an attention state'):
                attention_repair._terminal_error(job)
            editorial.write(job / 'status.json', {'status': 'failed', 'error': 'specific validator error'})
            state, error = attention_repair._terminal_error(job)
            self.assertEqual(state['status'], 'failed')
            self.assertEqual(error, 'specific validator error')

    def test_invalid_latest_candidate_falls_back_to_frozen_baseline(self):
        with tempfile.TemporaryDirectory() as temporary:
            job = Path(temporary)
            latest = {'character': '唱', 'invalid': True}
            frozen = {'character': '唱', 'valid': True}
            editorial.write(job / 'article.json', latest)
            editorial.write(job / 'source_article.json', frozen)

            def validate(article, dossier):
                if article.get('invalid'):
                    raise ValueError('mechanically invalid retained draft')
                return article

            with patch.object(editorial, 'validate_article', side_effect=validate):
                chosen, path = attention_repair._validated_draft(job, {'evidence': []})
            self.assertEqual(chosen, frozen)
            self.assertEqual(path, job / 'source_article.json')

    def test_repair_context_carries_findings_and_does_not_call_them_approval(self):
        with tempfile.TemporaryDirectory() as temporary:
            job = Path(temporary)
            stage = job / 'round-2' / 'readability'
            stage.mkdir(parents=True)
            editorial.write(stage / 'result.json', {'verdict': 'revise', 'findings': ['A specific retained concern.']})
            editorial.write(job / 'round-0' / 'editor' / 'result.json', {'edits': [
                {'path': 'formation/text', 'value_json': '"old patch"'}]})
            context = attention_repair._review_context(
                job, 'schema path error', {'findings': [{'key': 's:1', 'kind': 'source_gap'}]})
            self.assertEqual(context['terminal_validation_error'], 'schema path error')
            self.assertEqual(context['source_findings'][0]['key'], 's:1')
            self.assertTrue(any(item['review'].get('findings') == ['A specific retained concern.']
                                for item in context['previous_review_receipts']))
            self.assertTrue(any(item['result'].get('edits') for item in context['previous_failed_author_receipts']))
            self.assertIn('as an approval', context['repair_instructions'])

    def test_canonical_baseline_change_blocks_attention_reuse(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            job = root / 'old-job'; job.mkdir()
            source = {'id': 'test-source'}
            original_article = {'character': '木', 'baseline': 1}
            original_dossier = {'character': '木', 'evidence': []}
            saved = {'source_id': 'test-source', 'character': '木',
                     'registry_source': source, 'registry_source_hash': 'source-hash',
                     'article_hash': editorial.digest(original_article),
                     'dossier_hash': editorial.digest(original_dossier)}
            editorial.write(job / 'source.json', saved)
            editorial.write(job / 'source_article.json', original_article)
            editorial.write(job / 'source_dossier.json', original_dossier)
            editorial.write(job / 'status.json', {'status': 'failed', 'error': 'old failure'})
            editorial.write(job / 'source_findings.json', {'findings': []})
            with patch.object(attention_repair.source_enrichment, '_recorded_source_hash_matches', return_value=True), \
                 patch.object(attention_repair.source_enrichment, '_canonical',
                              return_value=({'character': '木', 'baseline': 2}, original_dossier)):
                with self.assertRaisesRegex(ValueError, 'Canonical baseline changed'):
                    attention_repair._check_prior(job, source, root)

    def test_changed_current_locator_requires_source_refresh(self):
        with tempfile.TemporaryDirectory() as temporary:
            job = Path(temporary)
            editorial.write(job / 'source_checkpoint.json', {'locator_hash': 'old-locator'})
            class LocatorTools:
                @staticmethod
                def locate_sources(*args): return {'source_leads': []}
            with patch.object(attention_repair.source_enrichment, '_load_source_tools',
                              return_value=LocatorTools), \
                 patch.object(attention_repair.source_enrichment, '_locator_hash', return_value='new-locator'):
                with self.assertRaisesRegex(ValueError, 'source refresh is required'):
                    attention_repair._check_locator(job, '木', {'id': 'book'}, {'character': '木'})

    def test_runner_child_inherits_live_job_resource_lock(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            lock_path = root / 'job.lock'
            script = root / 'check_lock.py'
            script.write_text(
                'import fcntl,json,os,sys\n'
                'fd=int(sys.argv[2]); path=sys.argv[3]\n'
                'inherited=os.fstat(fd).st_ino > 0\n'
                'h=open(path,"a")\n'
                'try:\n fcntl.flock(h,fcntl.LOCK_EX|fcntl.LOCK_NB); blocked=False\n'
                'except BlockingIOError: blocked=True\n'
                'json.dump({"inherited":inherited,"blocked":blocked},open(sys.argv[1],"w"))\n')
            held = attention_repair._lock(lock_path)
            try:
                runner = editorial.Runner([sys.executable, str(script), '{output}',
                                           str(held.fileno()), str(lock_path)], 'fixture', 30, 'low')
                runner.inherited_lock_fds = (held.fileno(),)
                result = runner.run('analysis', {}, {'type': 'object', 'properties': {
                    'inherited': {'type': 'boolean'}, 'blocked': {'type': 'boolean'}},
                    'required': ['inherited', 'blocked'], 'additionalProperties': False}, root / 'agent')
                self.assertEqual(result, {'inherited': True, 'blocked': True})
            finally:
                import fcntl
                fcntl.flock(held, fcntl.LOCK_UN)
                held.close()


if __name__ == '__main__':
    unittest.main()
