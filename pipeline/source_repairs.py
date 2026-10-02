"""Bind applied literal OCR repairs to actual producer overlays and consumer pages."""
import importlib.util
from pathlib import Path
import sys
import json
from pipeline import editorial


def producer_effective(source, directory):
    root = Path(source['producer_root']).resolve()
    directory = Path(directory).resolve()
    directory.relative_to(root)
    script = root / 'scripts/research_corrections.py'
    # Use the actual producer validator, including source pixels and raw anchors.
    spec = importlib.util.spec_from_file_location('_hanzi_source_corrections', script)
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(script.parent))
    try:
        spec.loader.exec_module(module)
        return module.load_effective(directory)
    finally:
        sys.path.pop(0)


def verify(source, check):
    directory = Path(check['producer_page_dir'])
    effective = producer_effective(source, directory)
    raw = editorial.read(directory / 'ocr.json')
    overlay = editorial.read(directory / 'ocr-corrections.json')
    patches = overlay['patches']
    matching = [p for p in patches if p['start'] == check['raw_start']
                and p['end'] == check['raw_end'] and p['before'] == check['before']
                and p['after'] == check['after'] and p.get('source_checked')]
    if len(matching) != 1 or effective['pdf_page_1based'] != check['pdf_page']:
        raise ValueError('Applied repair must identify an exact validated producer patch')
    with Path(source['corpus_path']).open() as stream:
        pages = [json.loads(line) for line in stream if line.strip()]
    pages = [p for p in pages if p['pdf_page_1based'] == check['pdf_page']]
    if len(pages) != 1:
        raise ValueError('Applied repair consumer page missing or duplicated')
    page = pages[0]
    if (page['book_id'] != source['book_id']
            or page['evidence_sha256'] != effective['evidence_sha256']
            or page['source_sha256'] != effective['source_sha256']
            or page['text'] != effective['ocr']['text']):
        raise ValueError('Applied repair producer and consumer evidence differ')
    offset = check['raw_start'] + sum(len(p['after']) - (p['end'] - p['start'])
                                    for p in patches if p['end'] <= check['raw_start'])
    if page['text'][offset:offset + len(check['after'])] != check['after']:
        raise ValueError('Applied repair is absent from the current corpus occurrence')
    return {**check, 'current_offset': offset,
            'source_pixel_sha256': effective['source_sha256'],
            'raw_evidence_sha256': raw['evidence_sha256'],
            'overlay_hash': editorial.digest(overlay),
            'effective_evidence_sha256': effective['evidence_sha256']}
