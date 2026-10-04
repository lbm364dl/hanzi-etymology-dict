import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from pipeline import dictionary_recovery as recovery, editorial, source_enrichment


def _write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False), encoding='utf-8')


def _fixture(root):
    parent, output = root / 'runs/source-job', root / 'runs/dictionary-job'
    article, dossier = {'character': '字'}, {'character': '字'}
    source_article = {'character': '字', 'canonical': 'baseline'}
    source_dossier = {'character': '字', 'canonical': 'baseline'}
    _write(parent / 'source_article.json', source_article)
    _write(parent / 'source_dossier.json', source_dossier)
    _write(parent / 'article.json', article)
    _write(parent / 'dossier.json', dossier)
    _write(parent / 'reviews.json', [{'role': 'factual', 'verdict': 'pass'}])
    source = {'character': '字', 'registry_source': {'id': 'book-test'},
              'article_hash': editorial.digest(source_article),
              'dossier_hash': editorial.digest(source_dossier)}
    _write(parent / 'source.json', source)
    audit = {'verified': False, 'consulted_citations': [{'evidence_ids': ['BOOK1']}]}
    _write(parent / 'source_audit.json', audit)
    _write(parent / 'status.json', {'status': 'needs_source_evidence', 'review_status': 'approved',
                                     'source_audit_hash': editorial.digest(audit)})
    result = {'unsupported_records': [{'evidence_id': 'BOOK1', 'reason': 'irrelevant'}]}
    stage = parent / 'citation-integration/citation-author'
    _write(stage / 'result.json', result)
    _write(stage / 'meta.json', {'status': 'complete', 'role': 'book_citation',
                                  'model': 'gpt-6-luna', 'reasoning': 'low',
                                  'fingerprint': 'fingerprint-test',
                                  'agent_thread_ids': ['thread-test'],
                                  'result_hash': editorial.digest(result)})
    audit_record = audit['consulted_citations']
    inputs = {'candidate_claims': {}, 'current_book_records': audit_record,
              'superseded_book_evidence_ids': [], 'correction_instructions': '',
              'citation_findings': [], 'retained_evidence': None}
    (stage / 'prompt.txt').write_text('INPUTS:\n' + json.dumps(inputs) +
        '\nCOMMON SENSE-STATUS CONTRACT:\ncontract', encoding='utf-8')
    _write(parent / 'citation-integration/completion.json', {
        'status': 'unchanged', 'article_hash': editorial.digest(article),
        'dossier_hash': editorial.digest(dossier), 'reviews_reused': True,
        'source_adoption_verified': False})
    return parent, output, source, source_article, source_dossier


class DictionaryRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.parent, self.output, self.source, self.source_article, self.source_dossier = _fixture(self.root)
        self.stack = patch.multiple(editorial, validate_article=lambda *args: None,
                                    validate_reviews=lambda *args: None)
        self.stack.start()
        self.addCleanup(self.stack.stop)

    def patch_gates(self, *, pending=False, canonical=None):
        p1 = patch.object(source_enrichment, '_canonical', lambda root, character: canonical or
                          (self.source_article, self.source_dossier))
        p2 = patch.object(source_enrichment, '_source_findings_pending', lambda parent: pending)
        p1.start(); p2.start()
        self.addCleanup(p1.stop); self.addCleanup(p2.stop)

    def test_rejects_false_unsupported_book_proof(self):
        self.patch_gates()
        result_path = self.parent / 'citation-integration/citation-author/result.json'
        _write(result_path, {'unsupported_records': []})
        meta_path = result_path.parent / 'meta.json'
        meta = editorial.read(meta_path)
        meta['result_hash'] = editorial.digest(editorial.read(result_path))
        _write(meta_path, meta)
        with self.assertRaisesRegex(ValueError, 'every consulted'):
            recovery.recover(self.parent, self.output, root=self.root, runner=object())
        self.assertFalse((self.output / 'publication_scope.json').exists())
        self.assertEqual(editorial.read(self.parent / 'status.json')['status'], 'needs_source_evidence')

    def test_baseline_drift_fails_before_model_work(self):
        self.patch_gates(canonical=({'character': '字', 'drift': True}, self.source_dossier))
        with self.assertRaisesRegex(ValueError, 'Canonical baseline drifted'):
            recovery.recover(self.parent, self.output, root=self.root, runner=object())
        self.assertFalse((self.output / 'publication_scope.json').exists())

    def test_pending_source_findings_do_not_mutate_parent(self):
        self.patch_gates(pending=True)
        before = (self.parent / 'status.json').read_bytes()
        with self.assertRaisesRegex(ValueError, 'Unresolved source findings'):
            recovery.recover(self.parent, self.output, root=self.root, runner=object())
        self.assertEqual((self.parent / 'status.json').read_bytes(), before)

    def test_fresh_reviews_publish_dictionary_scope_without_parent_mutation(self):
        self.patch_gates()
        calls = {}

        class Runner:
            model = 'gpt-6-luna'
            reasoning = 'low'

        def refine(article, dossier, directory, runner, max_revisions, **kwargs):
            calls['refine'] = (article, dossier, kwargs)
            _write(directory / 'article.json', article)
            _write(directory / 'dossier.json', dossier)
            _write(directory / 'reviews.json', [{'role': 'factual', 'verdict': 'pass'}])
            _write(directory / 'status.json', {'status': 'approved'})
            return {'status': 'approved'}

        def publish(job, publish_root):
            calls['publish'] = (job, publish_root)
            return Path(publish_root) / 'content/entries/5B57.json'

        before = (self.parent / 'status.json').read_bytes()
        with patch.object(editorial, 'refine', refine), patch.object(recovery.batch, 'publish_job', publish):
            result = recovery.recover(self.parent, self.output, root=self.root, runner=Runner())
        marker = editorial.read(self.output / 'publication_scope.json')
        self.assertEqual(result['status'], 'published')
        json.dumps(result)
        completion = editorial.read(self.output / 'recovery_completion.json')
        self.assertEqual(completion['publication_receipt'], {
            'canonical_entry': str(self.root / 'content/entries/5B57.json')})
        self.assertEqual(result['publication'], completion['publication_receipt'])
        self.assertEqual(marker['scope'], 'dictionary_improvement_only')
        self.assertIs(marker['source_adoption'], False)
        self.assertEqual(editorial.read(self.output / 'source.json'), self.source)
        self.assertEqual((self.output / 'source_article.json').read_bytes(),
                         (self.parent / 'source_article.json').read_bytes())
        self.assertIs(calls['refine'][2]['edit_first'], False)
        self.assertEqual(calls['publish'], (self.output, self.root))
        self.assertEqual((self.parent / 'status.json').read_bytes(), before)
        published_article = editorial.read(self.output / 'article.json')
        published_dossier = editorial.read(self.output / 'dossier.json')
        with patch.object(source_enrichment, '_canonical', lambda root, character:
                          (published_article, published_dossier)), \
             patch.object(editorial, 'refine', side_effect=AssertionError('must not rerun reviews')):
            retry = recovery.recover(self.parent, self.output, root=self.root, runner=Runner())
        self.assertTrue(retry['idempotent'])
        self.assertTrue(retry['published'])

    def test_rejected_reviews_never_publish(self):
        self.patch_gates()

        class Runner:
            model = 'gpt-6-luna'
            reasoning = 'low'

        with patch.object(editorial, 'refine', lambda *args, **kwargs: {'status': 'needs_revision'}), \
             patch.object(recovery.batch, 'publish_job', side_effect=AssertionError('unexpected publication')):
            result = recovery.recover(self.parent, self.output, root=self.root, runner=Runner())
        self.assertEqual(result['status'], 'needs_revision')

    def _published_parent(self):
        parent = self.root / 'runs/published-parent'
        article = {'character': '字', 'summary': {'text': 'current', 'evidence_ids': ['E1']}}
        dossier = {'character': '字', 'evidence': [{'id': 'E1', 'text': 'supported'}]}
        old_article, old_dossier = {'character': '字', 'old': True}, {'character': '字', 'old': True}
        source = {'character': '字', 'source_id': 'book-test', 'registry_source': {'id': 'book-test'},
                  'article_hash': editorial.digest(old_article), 'dossier_hash': editorial.digest(old_dossier)}
        _write(parent / 'source.json', source)
        _write(parent / 'source_article.json', old_article)
        _write(parent / 'source_dossier.json', old_dossier)
        _write(parent / 'article.json', article)
        _write(parent / 'dossier.json', dossier)
        _write(parent / 'reviews.json', [{'role': 'factual', 'verdict': 'pass'}])
        _write(parent / 'publication_scope.json', {
            'scope': 'dictionary_improvement_only', 'source_adoption': False})
        _write(parent / 'status.json', {'status': 'published',
            'article_hash': editorial.digest(article), 'dossier_hash': editorial.digest(dossier)})
        return parent, article, dossier, source

    def test_published_repair_rejects_canonical_mismatch(self):
        parent, article, dossier, _ = self._published_parent()
        output = self.root / 'runs/repair-mismatch'
        with patch.object(source_enrichment, '_source_findings_pending', return_value=False), \
             patch.object(source_enrichment, '_canonical', return_value=({'character': '字'}, dossier)), \
             patch.object(source_enrichment, 'prepare_job', side_effect=AssertionError('must reject before freezing')):
            with self.assertRaisesRegex(ValueError, 'does not match the current canonical'):
                recovery.repair_published(parent, output, {'issue': 'recheck claim'}, root=self.root,
                                          runner=object())
        self.assertFalse((output / 'publication_scope.json').exists())

    def test_published_repair_requires_explicit_nonempty_context(self):
        parent, _, _, _ = self._published_parent()
        with self.assertRaisesRegex(ValueError, 'nonempty review context'):
            recovery.repair_published(parent, self.root / 'runs/repair-empty', {}, root=self.root)

    def test_published_repair_freezes_current_baseline_and_keeps_book_hold(self):
        parent, article, dossier, source = self._published_parent()
        output = self.root / 'runs/repair-published'
        context = {'issue': 'Verify the wording against the cited evidence.'}
        captured = {}

        class Runner:
            model = 'gpt-6-luna'
            reasoning = 'low'

        def refine(candidate, packet, job, runner, max_revisions, **kwargs):
            captured['inputs'] = (candidate, packet, kwargs)
            _write(job / 'article.json', candidate)
            _write(job / 'dossier.json', packet)
            _write(job / 'reviews.json', [{'role': 'factual', 'verdict': 'pass'}])
            _write(job / 'status.json', {'status': 'approved'})
            return {'status': 'approved'}

        def publish(job, root):
            return root / 'content/entries/5B57.json'

        with patch.object(source_enrichment, '_source_findings_pending', return_value=False), \
             patch.object(source_enrichment, '_canonical', return_value=(article, dossier)), \
             patch.object(editorial, 'refine', refine), \
             patch.object(recovery.batch, 'publish_job', publish):
            result = recovery.repair_published(parent, output, context, root=self.root, runner=Runner())
        scope = editorial.read(output / 'publication_scope.json')
        self.assertIs(scope['source_adoption'], False)
        self.assertEqual(scope['review_context'], context)
        self.assertEqual(scope['source_parent_status'], 'published')
        self.assertEqual(editorial.read(output / 'source.json')['article_hash'], editorial.digest(article))
        self.assertEqual(editorial.read(output / 'source.json')['dossier_hash'], editorial.digest(dossier))
        self.assertEqual(captured['inputs'][0], article)
        self.assertIs(captured['inputs'][2]['edit_first'], True)
        self.assertEqual(captured['inputs'][2]['feedback']['additional_research_context'], context)
        self.assertNotIn('source_adoption', captured['inputs'][2]['feedback'])
        self.assertEqual(editorial.read(output / 'source.json')['registry_source'], source['registry_source'])
        self.assertEqual(result['publication']['canonical_entry'], str(self.root / 'content/entries/5B57.json'))
        self.assertEqual(editorial.read(parent / 'source.json'), source)


if __name__ == '__main__':
    unittest.main()
