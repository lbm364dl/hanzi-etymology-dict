import copy
from pathlib import Path
import tempfile
import unittest

from pipeline.editorial import make_review, publish, read, write
from pipeline.graph import export_graph
from pipeline.test_editorial import ARTICLE, ARTICLE_V2, DOSSIER, GLYPHS


class GraphTests(unittest.TestCase):
    def test_export_preserves_claim_scope_and_rejects_stale_evidence(self):
        article = copy.deepcopy(ARTICLE_V2)
        article['relationships'][1]['certainty'] = 'disputed'
        dossier = {**copy.deepcopy(DOSSIER), 'glyph_research': {'historical_glyphs': GLYPHS}}
        reviews = [make_review(role, 'pass', [], article, dossier, 'test:' + role)
                   for role in ('factual', 'readability')]
        with tempfile.TemporaryDirectory() as temporary:
            entries = Path(temporary) / 'entries'
            path = publish(article, dossier, reviews, entries)
            graph = export_graph(entries)
            self.assertEqual(graph['entries'], ['木'])
            edge = graph['edges'][1]
            self.assertEqual(edge['certainty'], 'disputed')
            self.assertEqual(edge['context_character'], '木')
            self.assertEqual(edge['subject'], 'component:木')
            self.assertEqual(edge['evidence'], dossier['evidence'])
            self.assertEqual(export_graph(entries, '水')['entries'], [])
            saved = read(path)
            saved['relationships'][1]['certainty'] = 'established'
            write(path, saved)
            with self.assertRaises(ValueError):
                export_graph(entries)

    def test_legacy_prose_is_not_inferred_into_edges(self):
        reviews = [make_review(role, 'pass', [], ARTICLE, DOSSIER, 'test:' + role)
                   for role in ('factual', 'readability')]
        with tempfile.TemporaryDirectory() as temporary:
            entries = Path(temporary) / 'entries'
            publish(ARTICLE, DOSSIER, reviews, entries)
            graph = export_graph(entries)
            self.assertEqual(graph['legacy_entries_without_graph'], ['木'])
            self.assertEqual(graph['edges'], [])


if __name__ == '__main__':
    unittest.main()
