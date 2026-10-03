"""Source-bound page labels are separate from raw OCR and text evidence."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from PIL import Image
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from research_corrections import load_page_metadata


class PageMetadataTests(unittest.TestCase):
    def fixture(self, root):
        image = Image.new('RGB', (5, 5), 'white'); image.save(root / 'source.png')
        pixels = hashlib.sha256(image.tobytes()).hexdigest()
        raw = {'source_sha256': pixels, 'evidence_sha256': 'raw-evidence',
               'pdf_page_1based': 10, 'ocr': {'text': 'unchanged'}}
        result = {'findings': [{'key': 'label', 'disposition': 'verified_metadata_not_extracted'}],
                  'metadata_observations': [{'key': 'label', 'observed_value': 'viii'}]}
        digest = hashlib.sha256(json.dumps(result, ensure_ascii=False, sort_keys=True,
                                         separators=(',', ':')).encode()).hexdigest()
        meta = {'status': 'complete', 'role': 'source_resolution', 'model': 'gpt-6-luna',
                'reasoning': 'low', 'result_hash': digest}
        binding = {'result_hash': digest, 'metadata_checks': [{'key': 'label',
            'field': 'printed_page', 'pdf_page': 10, 'current_value': None,
            'expected_value': 'viii', 'source_pixel_sha256': pixels}]}
        for name, data in [('result.json', result), ('meta.json', meta), ('binding.json', binding)]:
            (root / name).write_text(json.dumps(data))
        overlay = {'schema_version': 1, 'source_sha256': pixels,
                   'parent_evidence_sha256': 'raw-evidence', 'pdf_page_1based': 10,
                   'printed_page': 'viii', 'review': {'finding_key': 'label', 'result_hash': digest,
                       'result_path': str(root / 'result.json'), 'meta_path': str(root / 'meta.json'),
                       'binding_path': str(root / 'binding.json')}}
        (root / 'page-metadata.json').write_text(json.dumps(overlay))
        return raw, overlay, meta, binding, result

    def test_verified_label_preserves_ocr_and_raw_evidence(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); raw, *_ = self.fixture(root); original = copy.deepcopy(raw)
            effective = load_page_metadata(root, raw)
            self.assertEqual(effective['printed_page'], 'viii')
            self.assertEqual(effective['evidence_sha256'], original['evidence_sha256'])
            self.assertEqual(effective['ocr'], original['ocr'])
            self.assertEqual(raw, original)
            self.assertIn('metadata_sha256', effective['metadata_provenance'])

    def test_rejects_stale_source_wrong_label_and_unverified_receipt(self):
        for change in ('raw', 'page', 'label', 'boolean', 'model', 'hash', 'observation', 'pixels'):
            with self.subTest(change=change), tempfile.TemporaryDirectory() as temp:
                root = Path(temp); raw, overlay, meta, binding, result = self.fixture(root)
                if change == 'raw': raw['evidence_sha256'] = 'changed'
                elif change == 'page': overlay['pdf_page_1based'] = 11
                elif change == 'label': overlay['printed_page'] = 'ix'
                elif change == 'boolean': overlay['printed_page'] = True
                elif change == 'model': meta['model'] = 'another-model'
                elif change == 'hash': overlay['review']['result_hash'] = 'wrong'
                elif change == 'observation': result['metadata_observations'] = []
                elif change == 'pixels': Image.new('RGB', (5, 5), 'black').save(root / 'source.png')
                for name, data in [('page-metadata.json', overlay), ('meta.json', meta), ('result.json', result)]:
                    (root / name).write_text(json.dumps(data))
                with self.assertRaises(ValueError): load_page_metadata(root, raw)
