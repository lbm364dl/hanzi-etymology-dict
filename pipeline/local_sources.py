"""Bounded scan-backed locator leads for registered digitised sources.

Recognition of a headword-like OCR line is a locator, never a source verification.
"""
from __future__ import annotations

from functools import lru_cache
import json
from pathlib import Path
import re

from pipeline import editorial


def load_registry(path):
    registry = editorial.read(path)
    if registry.get('schema_version') != 1 or not isinstance(registry.get('sources'), list):
        raise ValueError('Source registry requires schema_version 1 and a sources array')
    ids = set()
    for source in registry['sources']:
        for key in ('id', 'title', 'bibliography', 'corpus_path', 'book_id'):
            if not isinstance(source.get(key), str) or not source[key].strip():
                raise ValueError(f'Source requires {key}')
        if source['id'] in ids or not re.fullmatch(r'[a-z0-9][a-z0-9-]*', source['id']):
            raise ValueError('Source IDs must be unique lowercase identifiers')
        ids.add(source['id'])
    if not ids:
        raise ValueError('Source registry is empty')
    return registry


@lru_cache(maxsize=8)
def _pages(path, mtime_ns, size):
    # The stat arguments invalidate the in-process cache after consumer OCR repairs.
    with Path(path).open() as stream:
        return tuple(json.loads(line) for line in stream if line.strip())


def search_forms(character, dossier):
    forms = [character]
    variants = dossier.get('context', {}).get('unverified_pipeline_metadata', {}).get('variants') or {}
    for key in ('traditional', 'simplified'):
        value = variants.get(key, '')
        for match in re.findall(r'U\+([0-9A-Fa-f]{4,6})', str(value)):
            counterpart = chr(int(match, 16))
            if counterpart not in forms:
                forms.append(counterpart)
    return forms


def _headword_line(line, forms):
    # Typical dictionary lines include a literal headword, pinyin and phonology.
    # Index pointers, quotations and '楷书' specimen captions are not such lines.
    pattern = r'^\s*([^\W\d_a-zA-Z])(?:[（(]([^）)]+)[）)])?\s+([a-zA-ZüÜāáǎàēéěèīíǐìōóǒòūúǔùǖǘǚǜ]+)\b'
    match = re.search(pattern, line)
    return bool(match and (match.group(1) in forms or any(
        form in (match.group(2) or '') for form in forms)) and re.search(r'[纽紐韵韻切部组組]', line))


def locate_sources(registry, character, dossier):
    """Return compact, explicitly unverified leads and bounded source attachments."""
    forms = search_forms(character, dossier)
    leads = []
    images = []
    for source in registry['sources']:
        path = Path(source['corpus_path']).expanduser()
        packet = {'source_id': source['id'], 'title': source['title'],
                  'bibliography': source['bibliography'], 'book_id': source['book_id'],
                  'search_forms': forms, 'corpus_path': str(path), 'candidates': [],
                  'use': 'Locator leads only; inspect scan pixels and exact headword before citing.'}
        if not path.is_file():
            packet['access_gap'] = 'Registered consumer corpus is unavailable'
            leads.append(packet)
            continue
        stat = path.stat()
        pages = _pages(str(path), stat.st_mtime_ns, stat.st_size)
        if any(p.get('book_id') != source['book_id'] for p in pages):
            raise ValueError('Corpus book identity differs from registered source')
        ranked = []
        for index, page in enumerate(pages):
            text = page.get('text', '')
            lines = [line for line in text.splitlines() if _headword_line(line, forms)]
            count = sum(text.count(form) for form in forms)
            if lines or count:
                ranked.append((bool(lines), count, index, lines))
        ranked.sort(key=lambda item: (-item[0], -item[1], item[2]))
        # Prefer exact header-shaped candidates. Mentions are only fallback leads.
        selected = ranked[:2] if ranked and ranked[0][0] else ranked[:3]
        selected_indices = {item[2] for item in selected}
        if selected and selected[0][0]:
            following = selected[0][2] + 1
            if following < len(pages) and following not in selected_indices:
                selected.append((False, 0, following, []))
        for is_header, count, index, lines in selected[:3]:
            page = pages[index]
            text = page.get('text', '')
            anchor = text.find(lines[0]) if lines else min(
                (text.find(form) for form in forms if form in text), default=0)
            candidate = {key: page.get(key) for key in
                         ('page_id', 'pdf_page_1based', 'printed_page', 'source_scan',
                          'source_sha256', 'evidence_sha256', 'ocr_review_status')}
            corrections = page.get('correction_provenance')
            if corrections:
                candidate['applied_ocr_corrections'] = {
                    'original_evidence_sha256': page.get('original_evidence_sha256'),
                    'corrections_sha256': corrections.get('corrections_sha256'),
                    'text_patches': [{k: patch[k] for k in ('start', 'end', 'before', 'after')}
                                     for patch in corrections.get('patches', [])],
                    'scope': 'Applied producer overlay, not whole-page approval. Compare current corrected '
                             'corpus text with original pixels before proposing another correction.'}
            candidate.update(match_type=('unverified_headword_line' if is_header else
                'possible_continuation' if count == 0 else 'text_mention'),
                headword_lines=lines, excerpt=text[max(0, anchor - 150):anchor + 1800])
            packet['candidates'].append(candidate)
            if is_header or count == 0:
                scan = Path(page.get('source_scan', ''))
                if scan.is_file() and len(images) < 3:
                    images.append({'path': str(scan.resolve()), 'pdf_page': page['pdf_page_1based'],
                                   'source_pixel_sha256': page.get('source_sha256'),
                                   **({'printed_page': page['printed_page']}
                                      if type(page.get('printed_page')) is int else {})})
        if not selected or not selected[0][0]:
            packet['locator_gap'] = 'No headword-shaped OCR line found; mentions are not verified entries'
        leads.append(packet)
    return {'source_leads': leads, 'source_scan_images': images}
