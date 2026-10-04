import json
import importlib
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from pipeline import attention_repair, editorial


class AttentionRepairTests(unittest.TestCase):
    def test_renderer_dependencies_are_checked_before_any_job_or_model_work(self):
        with patch.object(attention_repair, '_renderer_runtime',
                          side_effect=RuntimeError('Missing CairoSVG in this interpreter')), \
             patch.object(attention_repair.source_enrichment, '_source_registry') as registry, \
             patch.object(editorial, 'Runner') as runner:
            with self.assertRaisesRegex(RuntimeError, 'Missing CairoSVG'):
                attention_repair.run_many([], Path('out'), Path('registry.json'))
        registry.assert_not_called()
        runner.assert_not_called()

    def test_renderer_preflight_names_same_interpreter_install(self):
        real_import = importlib.import_module
        def imports(name):
            if name == 'cairosvg':
                raise ImportError('missing CairoSVG', name='cairosvg')
            return real_import(name)
        with patch.object(attention_repair.importlib, 'import_module', side_effect=imports):
            with self.assertRaisesRegex(RuntimeError, 'pipeline/requirements.txt') as caught:
                attention_repair._renderer_runtime()
        self.assertIn(sys.executable, str(caught.exception))

    def test_patch_contract_names_the_exact_overlapping_paths(self):
        paths = {
            'components': ('components',),
            'components/0/text': ('components', 0, 'text'),
            'learner/components': ('learner', 'components'),
        }
        edits = [{'path': path} for path in paths]
        self.assertEqual(editorial.overlapping_article_patch_paths(edits, paths),
                         [('components', 'components/0/text')])

    def test_apply_article_patch_repairs_overlap_without_module_helper(self):
        from pipeline.test_editorial import ARTICLE_V2, DOSSIER
        from pipeline.editorial import WRITER_SCHEMA
        import copy
        with tempfile.TemporaryDirectory() as temporary:
            article = copy.deepcopy(ARTICLE_V2)
            dossier = {**DOSSIER, 'glyph_research': {
                'historical_glyphs': article['historical_glyphs']}}
            calls = []
            def invoke(role, inputs, schema, directory):
                calls.append(inputs)
                if len(calls) == 1:
                    return {'edits': [
                        {'path': 'components/0', 'value_json': json.dumps(article['components'][0])},
                        {'path': 'components/0/form', 'value_json': '木'},
                    ]}
                self.assertIn("'components/0' conflicts with 'components/0/form'",
                              inputs['validation_findings'][0])
                return {'edits': [{'path': 'summary/text', 'value_json': 'A tree.'}]}
            with patch.object(editorial, 'overlapping_article_patch_paths', None, create=True):
                result = editorial.apply_article_patch('revision', {'article': article, 'dossier': dossier},
                                                       WRITER_SCHEMA, Path(temporary), invoke)
            self.assertEqual(len(calls), 2)
            self.assertEqual(result['summary']['text'], 'A tree.')
            self.assertEqual(article['summary']['text'], ARTICLE_V2['summary']['text'])

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

    def test_failed_descendant_falls_back_to_exact_parent_findings(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            parent, child = root / 'parent', root / 'child'
            parent.mkdir(); child.mkdir()
            retained = {'requires_coordinator_verification': True,
                        'findings': [{'key': 'book:ocr:one', 'kind': 'ocr', 'details': 'pending'}]}
            editorial.write(parent / 'source_findings.json', retained)
            editorial.write(child / 'attention_repair.json', {'prior_job': str(parent)})
            self.assertEqual(attention_repair._load_source_findings(child), retained)

    def test_verified_raw_proof_references_survive_failed_descendant(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            parent, child = root / 'parent', root / 'child'
            parent.mkdir(); child.mkdir()
            proof = {'finding_key':'source:literal', 'receipt_path':'runs/ocr/verified-occurrences.json',
                     'occurrence_ids':['hit-1']}
            editorial.write(parent / 'verified_raw_occurrence_proofs.json', {'proofs':[proof]})
            editorial.write(child / 'attention_repair.json', {'prior_job':str(parent)})
            self.assertEqual(attention_repair._load_verified_proof_inputs(child), [proof])

    def test_locator_checkpoint_keeps_scan_context_for_later_source_resolution(self):
        from pipeline import source_enrichment
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            job = root / 'job'; job.mkdir()
            corpus = root / 'pages.jsonl'; corpus.write_text('')
            scan = {'path':str(root / 'page.png'), 'pdf_page':17}
            editorial.write(job / 'source_checkpoint.json', {
                'locator':{'source_scan_images':[scan]}, 'locator_hash':'loc-hash'})
            editorial.write(job / 'source_findings.json', {'findings':[]})
            retained = source_enrichment._retained_finding_scans(
                job, {'id':'book', 'corpus_path':str(corpus)})
            self.assertEqual(retained, [scan])

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

    def test_only_literal_replacement_findings_block_continuation(self):
        findings = {'findings': [
            {'key': 'literal', 'kind': 'ocr', 'details':
             '[OCR CORRECTION REQUIRED] Exact raw OCR span proposes replacing a character.'},
            {'key': 'identity', 'kind': 'ocr', 'details':
             '[SCAN VERIFICATION REQUIRED] Rare specimen identity remains unresolved; no article claim depends on it.'},
        ]}
        blockers = attention_repair._transcription_correction_findings(findings)
        self.assertEqual([item['key'] for item in blockers], ['literal'])

    def test_exact_validated_correct_raw_receipt_releases_only_its_transcription_finding(self):
        findings = {'findings': [
            {'key': 'literal', 'kind': 'ocr', 'details': '[OCR CORRECTION REQUIRED] raw proposes a different printed literal'},
            {'key': 'other-literal', 'kind': 'ocr', 'details': '[OCR CORRECTION REQUIRED] a second replacement is proposed'},
        ]}
        proof_input = [{'finding_key': 'literal', 'receipt_path': 'receipt.json',
                        'occurrence_ids': ['p1-hit1']}]
        checked = {'finding_key': 'literal', 'disposition': 'correct_raw_preflight_only',
                   'final_source_resolution_still_required': True}
        with patch.object(attention_repair.source_enrichment,
                          'validate_correct_raw_occurrence_receipt', return_value=checked) as validator:
            proofs = attention_repair._validated_raw_occurrence_proofs(
                Path('/prior'), findings, proof_input)
        validator.assert_called_once_with(Path('/prior'), 'literal',
                                          Path('/home/catalin/hanzi-etymology-dict/receipt.json'),
                                          ['p1-hit1'])
        allowed = {item['finding_key'] for item in proofs}
        blockers = [item['key'] for item in attention_repair._transcription_correction_findings(findings)
                    if item['key'] not in allowed]
        self.assertEqual(blockers, ['other-literal'])
        self.assertTrue(proofs[0]['validation']['final_source_resolution_still_required'])

    def test_run_many_rejects_unmatched_occurrence_proof_before_scheduling(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            job = root / 'prior'
            job.mkdir()
            editorial.write(job / 'source_findings.json', {'findings': [{'key': 'known'}]})
            proof = [{'finding_key': 'unknown', 'receipt_path': 'receipt.json', 'occurrence_ids': ['x']}]
            source = {'id': 'fixture'}
            with patch.object(attention_repair, '_renderer_runtime', return_value={'executable':'python'}), \
                 patch.object(attention_repair.source_enrichment, '_source_registry', return_value={'sources':[source]}), \
                 patch.object(attention_repair.source_enrichment, '_source', return_value=source), \
                 patch.object(attention_repair, 'run_one') as run_one:
                with self.assertRaisesRegex(ValueError, 'absent or ambiguous'):
                    attention_repair.run_many([job], root/'out', root/'registry.json',
                                              verified_raw_occurrence_proofs=proof)
            run_one.assert_not_called()

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
