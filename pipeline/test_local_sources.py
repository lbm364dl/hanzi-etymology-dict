import json
from pathlib import Path
import tempfile
import unittest

from pipeline.local_sources import locate_sources, search_forms, load_registry, _headword_line


class LocalSourceTests(unittest.TestCase):
    def test_absent_counterpart_metadata(self):
        self.assertEqual(search_forms('木', {'context': {'unverified_pipeline_metadata': {'variants': None}}}), ['木'])

    def test_parenthetic_counterpart_is_a_lead_not_a_proven_identity(self):
        self.assertTrue(_headword_line('昀(的) dī 端组、药部;', ['的']))
        self.assertFalse(_headword_line('的 600', ['的']))
        self.assertFalse(_headword_line('昀(的) 楷书', ['的']))

    def test_traditional_headword_beats_mentions_and_preserves_unknown_pagination(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            scan = root / 'source.png'
            scan.write_bytes(b'fixture')
            pages = [dict(book_id='book', page_id=str(i), pdf_page_1based=i,
                          printed_page=None, source_scan=str(scan), source_sha256='source',
                          evidence_sha256=str(i), text=text)
                     for i, text in enumerate(['學' * 100, '學(学) xué 匣纽、觉部。\nAccount',
                                              'Continued account'], 1)]
            corpus = root / 'pages.jsonl'
            corpus.write_text('\n'.join(json.dumps(p, ensure_ascii=False) for p in pages))
            registry = {'sources': [{'id': 'book', 'title': 'Book', 'bibliography': 'Edition',
                                      'book_id': 'book', 'corpus_path': str(corpus)}]}
            dossier = {'context': {'unverified_pipeline_metadata': {'variants': {'traditional': 'U+5B78'}}}}
            result = locate_sources(registry, '学', dossier)
            candidates = result['source_leads'][0]['candidates']
            self.assertEqual(candidates[0]['pdf_page_1based'], 2)
            self.assertEqual(candidates[0]['match_type'], 'unverified_headword_line')
            self.assertTrue(any(c['match_type'] == 'possible_continuation' for c in candidates))
            self.assertTrue(all('printed_page' not in i for i in result['source_scan_images']))
            self.assertLessEqual(len(result['source_scan_images']), 3)

    def test_mentions_remain_a_gap_and_changed_corpus_is_read_again(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'corpus'
            source = {'id': 'book', 'title': 'Book', 'bibliography': 'Edition',
                      'book_id': 'book', 'corpus_path': str(path)}
            path.write_text(json.dumps({'book_id': 'book', 'text': 'A quotation about 木', 'pdf_page_1based': 1}))
            first = locate_sources({'sources': [source]}, '木', {})
            self.assertIn('locator_gap', first['source_leads'][0])
            self.assertEqual(first['source_scan_images'], [])
            path.write_text(json.dumps({'book_id': 'different', 'text': '木'}))
            with self.assertRaises(ValueError):
                locate_sources({'sources': [source]}, '木', {})

    def test_registry_rejects_duplicate_identity(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'registry.json'
            source = dict(id='book', title='Book', bibliography='Edition', corpus_path='path', book_id='book')
            path.write_text(json.dumps({'schema_version': 1, 'sources': [source, source]}))
            with self.assertRaises(ValueError):
                load_registry(path)


if __name__ == '__main__':
    unittest.main()
