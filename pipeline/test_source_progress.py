from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from pipeline import editorial, source_progress


class SourceProgressTests(unittest.TestCase):
    def test_full_scope_uses_current_gates_and_deduplicates_outputs(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            first, second = root / 'batch-one', root / 'batch-two'
            for location, character, source_id in (
                    (first, '木', 'book'), (second, '木', 'book'),
                    (first, '水', 'book'), (second, '火', 'other-book')):
                job = location / f'{ord(character):04X}'
                editorial.write(job / 'source.json', {'character': character, 'source_id': source_id})
                editorial.write(job / 'status.json', {'status': 'published'})
            archive = first / 'archive'
            editorial.write(archive / 'source.json', {'character': '火', 'source_id': 'book'})
            calls = []
            def verify(job, source, canonical_root):
                calls.append(job)
                self.assertEqual(canonical_root, root)
                return job == (second / '6728').resolve()
            with patch.object(source_progress.se, '_published_matches', side_effect=verify):
                result = source_progress.report({'characters': ['木', '水', '火']},
                    {'id': 'book'}, [first, second, first], root)
            self.assertEqual(result['characters_total'], 3)
            self.assertEqual(result['verified_source_complete'], 1)
            self.assertEqual([r['verified_source_completion'] for r in result['characters']],
                             [True, False, False])
            self.assertEqual(len(calls), 3)
            self.assertEqual(len(result['characters'][0]['jobs']), 2)
            self.assertFalse(result['characters'][2]['jobs'])

    def test_verification_failure_is_visible_and_never_counts(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            editorial.write(root / '6728/source.json', {'character': '木', 'source_id': 'book'})
            editorial.write(root / '6728/status.json', {'status': 'published'})
            with patch.object(source_progress.se, '_published_matches', side_effect=ValueError('stale receipts')):
                result = source_progress.report({'characters': ['木']}, {'id': 'book'}, [root])
            self.assertEqual(result['verified_source_complete'], 0)
            self.assertEqual(result['characters'][0]['jobs'][0]['verification_error'], 'stale receipts')


if __name__ == '__main__':
    unittest.main()
