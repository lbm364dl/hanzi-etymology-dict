import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from pipeline import editorial, source_adoption, source_enrichment as se
from pipeline.test_editorial import ARTICLE_V2, DOSSIER, GLYPHS
from pipeline.test_source_enrichment import SOURCE, LocalSources


class SourceAdoptionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        dossier = copy.deepcopy(DOSSIER)
        dossier['evidence'][0].update(source='李學勤主編《字源》', field='木; PDF p.123, printed p.110')
        dossier.update(glyph_research={'historical_glyphs': copy.deepcopy(GLYPHS)}, glyph_assets=[])
        article = copy.deepcopy(ARTICLE_V2)
        reviews = [editorial.make_review(role, 'pass', [], article, dossier, f'fixture-{role}')
                   for role in ('factual', 'readability')]
        editorial.publish(article, dossier, reviews, self.root / 'content/entries')
        self.entry = self.root / 'content/entries/6728.json'

    def test_registers_actual_source_check_without_rewriting_published_content(self):
        class Locator(LocalSources):
            def locate_sources(self, source, character, dossier):
                return {**super().locate_sources(source, character, dossier),
                        'source_scan_images': [{'path': '/original.png', 'pdf_page': 123}]}
        class Runner:
            model = 'gpt-6-luna'
            reasoning = 'low'
            def run(self, role, inputs, schema, directory):
                self_case.assertEqual(role, 'source_coverage')
                self_case.assertIn('source_scan_images', inputs['feedback'])
                result = {'verdict': 'pass', 'evidence_ids': ['source:1'], 'findings': []}
                editorial.write(Path(directory) / 'result.json', result)
                editorial.write(Path(directory) / 'meta.json', {
                    'role': role, 'status': 'complete', 'model': self.model,
                    'reasoning': self.reasoning, 'result_hash': editorial.digest(result)})
                return result
        self_case = self
        before = self.entry.read_bytes()
        with patch.object(se, '_load_source_tools', return_value=Locator()):
            result = source_adoption.adopt('木', SOURCE, self.root / 'runs', Runner(), self.root)
            self.assertEqual(result['status'], 'published')
            self.assertEqual(self.entry.read_bytes(), before)
            job = se.job_path(self.root / 'runs', SOURCE['id'], '木')
            self.assertTrue(se._published_matches(job, SOURCE, self.root))
            self.assertTrue((self.root / 'content/source_coverage/ziyuan-2012/6728/source-coverage/result.json').is_file())
            editorial.write(job / 'source-coverage/result.json', {'verdict': 'revise', 'evidence_ids': [],
                                                                'findings': ['Scan disagrees.']})
            self.assertFalse(se._published_matches(job, SOURCE, self.root))

    def test_failed_source_check_tracks_findings_without_publishing(self):
        class Locator(LocalSources):
            def locate_sources(self, source, character, dossier):
                return {'source_scan_images': [{'path': '/original.png', 'pdf_page': 123}]}
        class Runner:
            model = 'gpt-6-luna'
            reasoning = 'low'
            def run(self, role, inputs, schema, directory):
                result = {'verdict': 'revise', 'evidence_ids': ['source:1'],
                          'findings': ['A material claim needs more research.']}
                editorial.write(Path(directory) / 'result.json', result)
                editorial.write(Path(directory) / 'meta.json', {
                    'role': role, 'status': 'complete', 'model': self.model,
                    'reasoning': self.reasoning, 'result_hash': editorial.digest(result)})
                return result
        before = self.entry.read_bytes()
        with patch.object(se, '_load_source_tools', return_value=Locator()), \
                patch.object(se, '_triage_and_sync_issues', return_value={'status': 'synced'}) as sync:
            result = source_adoption.adopt('木', SOURCE, self.root / 'runs', Runner(), self.root)
        self.assertEqual(result['status'], 'needs_source_research')
        self.assertEqual(result['issue_sync_status'], 'synced')
        sync.assert_called_once()
        self.assertEqual(self.entry.read_bytes(), before)
        self.assertFalse((self.root / 'content/source_coverage').exists())

    def test_book_title_without_used_page_evidence_cannot_be_adopted(self):
        source = {**SOURCE, 'title': 'Another book'}
        class Runner:
            model = 'gpt-6-luna'
            reasoning = 'low'
        with self.assertRaisesRegex(ValueError, 'No used page-specific evidence'):
            source_adoption.adopt('木', source, self.root / 'runs', Runner(), self.root)

    def test_independent_adjudication_preserves_failed_check_and_binds_exact_pair(self):
        class Locator(LocalSources):
            def locate_sources(self, source, character, dossier):
                return {**super().locate_sources(source, character, dossier),
                        'source_scan_images': [{'path': '/original.png', 'pdf_page': 123}]}
        class FixtureRunner:
            model = 'gpt-6-luna'
            reasoning = 'low'
            def run(self, role, inputs, schema, directory):
                second = Path(directory).name == 'source-coverage-adjudication'
                if second:
                    self_case.assertEqual(inputs['prior_review']['verdict'], 'revise')
                    self_case.assertIn('source_scan_images', inputs['feedback'])
                result = {'verdict': 'pass' if second else 'revise',
                          'evidence_ids': ['source:1'],
                          'findings': [] if second else ['Fixture omission allegation.']}
                editorial.write(Path(directory) / 'result.json', result)
                editorial.write(Path(directory) / 'meta.json', {
                    'role': role, 'status': 'complete', 'model': self.model,
                    'reasoning': self.reasoning, 'result_hash': editorial.digest(result)})
                return result
        self_case = self
        before = self.entry.read_bytes()
        with patch.object(se, '_load_source_tools', return_value=Locator()):
            result = source_adoption.adopt('木', SOURCE, self.root / 'runs', FixtureRunner(), self.root)
            self.assertEqual(result['status'], 'published')
            self.assertEqual(self.entry.read_bytes(), before)
            job = se.job_path(self.root / 'runs', SOURCE['id'], '木')
            self.assertEqual(editorial.read(job / 'source-coverage/result.json')['verdict'], 'revise')
            self.assertTrue(se._published_matches(job, SOURCE, self.root))
            binding = editorial.read(job / 'source-coverage-adjudication/binding.json')
            binding['article_hash'] = 'changed-pair'
            editorial.write(job / 'source-coverage-adjudication/binding.json', binding)
            self.assertFalse(se._published_matches(job, SOURCE, self.root))


if __name__ == '__main__':
    unittest.main()
