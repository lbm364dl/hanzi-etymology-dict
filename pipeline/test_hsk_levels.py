"""Protect the distinction between the HSK version and the level number."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import build_database


class HskLevelTests(unittest.TestCase):
    def test_animcjk_version_prefix_is_not_part_of_level(self):
        records = [
            {'character': '一', 'set': ['hsk31', 'frequent2500']},
            {'character': '二', 'set': ['hsk32']},
            {'character': '九', 'set': ['hsk39']},
            {'character': '零', 'set': ['hsk30', 'hsk399', 'hsk3bad']},
        ]
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'animcjk').mkdir()
            (root / 'animcjk/dictionaryZhHans.txt').write_text('\n'.join(map(json.dumps, records)))
            with patch.object(build_database, 'SOURCES_DIR', root):
                result = build_database.parse_animcjk()
        self.assertEqual([result[c]['hsk3_level'] for c in '一二九'], [1, 2, 9])
        self.assertEqual(result['一']['frequency_tier'], 'top_2500')
        self.assertNotIn('零', result)


if __name__ == '__main__':
    unittest.main()
