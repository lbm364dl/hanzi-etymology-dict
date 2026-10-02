"""Contract fixtures; actual producer validation is exercised separately on book pages."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from pipeline import editorial, source_repairs, source_enrichment


class AppliedRepairTests(unittest.TestCase):
    def test_exact_overlay_and_consumer_are_required_and_offset_tracks_prior_patches(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            overlay = {'patches': [
                {'start': 0, 'end': 3, 'before': 'abc', 'after': 'x', 'source_checked': True},
                {'start': 3, 'end': 4, 'before': '兒', 'after': '皃', 'source_checked': True}]}
            editorial.write(root / 'ocr.json', {'evidence_sha256': 'raw-fixture'})
            editorial.write(root / 'ocr-corrections.json', overlay)
            effective = {'pdf_page_1based': 1, 'source_sha256': 'pixels-fixture',
                         'evidence_sha256': 'effective-fixture', 'ocr': {'text': 'x皃'}}
            page = {**effective, 'book_id': 'book-fixture', 'text': 'x皃'}
            corpus = root / 'corpus.jsonl'
            corpus.write_text(__import__('json').dumps(page))
            source = {'book_id': 'book-fixture', 'corpus_path': str(corpus)}
            check = {'key': 'fixture', 'pdf_page': 1, 'producer_page_dir': str(root),
                     'raw_start': 3, 'raw_end': 4, 'before': '兒', 'after': '皃'}
            with patch.object(source_repairs, 'producer_effective', return_value=effective):
                receipt = source_repairs.verify(source, check)
                self.assertEqual(receipt['current_offset'], 1)
                with self.assertRaisesRegex(ValueError, 'exact validated'):
                    source_repairs.verify(source, {**check, 'before': 'wrong'})
                corpus.write_text(__import__('json').dumps({**page, 'text': 'x兒'}))
                with self.assertRaisesRegex(ValueError, 'evidence differ'):
                    source_repairs.verify(source, check)

    def test_resolution_requires_live_repair_receipt_and_matching_scan_observation(self):
        with tempfile.TemporaryDirectory() as temp:
            job = Path(temp)
            article, dossier = {'fixture': 'article'}, {'fixture': 'dossier'}
            findings = {'requires_coordinator_verification': True, 'findings': [{'key': 'repair'}]}
            repair = {'key': 'repair', 'after': '皃', 'overlay_hash': 'fixture'}
            result = {'findings': [{'key': 'repair', 'disposition': 'applied_repair_scan_matches_corpus'}],
                      'repair_observations': [{'key': 'repair', 'observed_literal': '皃', 'pixel_reason': 'Fixture'}]}
            for name, value in [('article.json', article), ('dossier.json', dossier),
                                ('source_findings.json', findings), ('source.json', {'registry_source': {}}),
                                ('source-resolution/result.json', result)]:
                editorial.write(job / name, value)
            editorial.write(job / 'source-resolution/meta.json', {
                'role': 'source_resolution', 'status': 'complete', 'model': 'gpt-6-luna',
                'reasoning': 'low', 'result_hash': editorial.digest(result)})
            record = {'findings_hash': editorial.digest(findings), 'article_hash': editorial.digest(article),
                      'dossier_hash': editorial.digest(dossier), 'result_hash': editorial.digest(result),
                      'model': 'gpt-6-luna', 'reasoning': 'low', 'review_path': 'source-resolution/result.json'}
            editorial.write(job / 'source_resolution.json', record)
            self.assertTrue(source_enrichment._source_findings_pending(job))
            editorial.write(job / 'source_resolution.json', {**record, 'applied_repairs': [repair]})
            with patch.object(source_repairs, 'verify', return_value=repair):
                self.assertFalse(source_enrichment._source_findings_pending(job))
            with patch.object(source_repairs, 'verify', return_value={**repair, 'overlay_hash': 'changed'}):
                self.assertTrue(source_enrichment._source_findings_pending(job))
