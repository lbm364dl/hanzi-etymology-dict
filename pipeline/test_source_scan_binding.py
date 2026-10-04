import json
from pathlib import Path
import tempfile
import unittest

from pipeline import editorial, source_adoption, source_enrichment, source_scan_binding


class SourceScanBindingTests(unittest.TestCase):
    def test_cached_coverage_pass_cannot_override_wrong_page_hash(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            corpus = root / 'pages.jsonl'
            corpus.write_text(json.dumps({'book_id': 'book', 'pdf_page_1based': 1050,
                                         'source_sha256': 'b' * 64}))
            source = {'book_id': 'book', 'title': 'Book', 'corpus_path': str(corpus)}
            article = {'summary': {'evidence_ids': ['E1']}}
            dossier = {'evidence': [{'id': 'E1', 'source': 'Book',
                'field': 'PDF p. 1050; source scan SHA-256 ' + 'a' * 64}]}
            result = {'verdict': 'pass', 'findings': [], 'evidence_ids': ['E1']}
            editorial.write(root / 'source.json', {'registry_source': source})
            editorial.write(root / 'source-coverage/result.json', result)
            editorial.write(root / 'source-coverage/meta.json', {
                'result_hash': editorial.digest(result), 'status': 'complete',
                'role': 'source_coverage', 'model': 'gpt-6-luna', 'reasoning': 'low'})
            audit = {'article_hash': editorial.digest(article),
                     'dossier_hash': editorial.digest(dossier),
                     'coverage_result_hash': editorial.digest(result)}
            self.assertFalse(source_adoption.valid_audit(root, audit, article, dossier))
            dossier['evidence'][0]['field'] = 'PDF p. 1050; source scan SHA-256 ' + 'b' * 64
            audit['dossier_hash'] = editorial.digest(dossier)
            self.assertTrue(source_adoption.valid_audit(root, audit, article, dossier))

    def test_hash_from_another_page_cannot_certify_the_cited_page(self):
        with tempfile.TemporaryDirectory() as temporary:
            corpus = Path(temporary) / 'pages.jsonl'
            corpus.write_text('\n'.join(json.dumps(page) for page in [
                {'book_id': 'book', 'pdf_page_1based': 961, 'source_sha256': 'a' * 64},
                {'book_id': 'book', 'pdf_page_1based': 1050, 'source_sha256': 'b' * 64},
            ]))
            source = {'book_id': 'book', 'title': 'Book', 'corpus_path': str(corpus)}
            record = {'id': 'E1', 'source': 'Book',
                      'field': 'Entry; PDF p. 1050; source scan SHA-256 ' + 'a' * 64}
            errors = source_scan_binding.mismatches(source, [record])
            self.assertEqual(errors, [{'evidence_id': 'E1', 'pdf_page': 1050,
                'claimed_scan_sha256': 'a' * 64, 'current_scan_sha256': 'b' * 64}])
            record['field'] = 'Entry; PDF p. 1050; source scan SHA-256 ' + 'b' * 64
            self.assertEqual(source_scan_binding.mismatches(source, [record]), [])

    def test_only_used_registered_book_records_are_checked(self):
        source = {'book_id': 'book', 'title': 'Book', 'corpus_path': '/not/read/unused'}
        dossier = {'evidence': [{'id': 'E1', 'source': 'Book',
            'field': 'PDF p. 1050; scan SHA-256 ' + 'a' * 64},
            {'id': 'E2', 'source': 'Another source',
             'field': 'PDF p. 1050; scan SHA-256 ' + 'a' * 64}]}
        article = {'summary': {'evidence_ids': ['E2']}}
        self.assertEqual(source_enrichment._source_scan_binding_errors(source, article, dossier), [])

    def test_missing_explicit_hash_is_not_a_fabricated_mismatch(self):
        self.assertEqual(source_scan_binding.mismatches(
            {'corpus_path': '/not/read'}, [{'id': 'E1', 'field': 'PDF p. 1050'}]), [])
