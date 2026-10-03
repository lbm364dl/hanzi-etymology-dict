"""Check explicit scan hashes against the cited page of a registered corpus."""
import re
from pathlib import Path

from pipeline import local_sources


def used_mismatches(source, article, dossier):
    used = set()
    def visit(value):
        if isinstance(value, dict):
            used.update(value.get('evidence_ids', []))
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)
    visit(article)
    title, book_id = source.get('title', ''), source.get('book_id', '')
    citations = []
    for item in dossier['evidence']:
        label = item.get('source', '')
        matches = ((title and re.search(r'(?<!\w)' + re.escape(title) + r'(?!\w)', label))
                   or (book_id and book_id in label))
        if item['id'] in used and matches:
            citations.append(item)
    return mismatches(source, citations)


def mismatches(source, citations):
    declared = []
    for evidence in citations:
        text = ' '.join(str(evidence.get(key, '')) for key in ('source', 'field'))
        pages = set(int(value) for value in re.findall(
            r'\bPDF\s+(?:pages?|p\.)\s*(\d+)', text, re.I))
        hashes = set(value.lower() for value in re.findall(
            r'(?:source\s+)?scan\s+(?:pixel\s+)?SHA[- ]?256\s*[:=]?\s*([0-9a-f]{64})',
            text, re.I))
        # This checks unambiguous explicit bindings, not missing citation details
        # or a multi-page account that needs independent source coverage review.
        if len(pages) == 1 and len(hashes) == 1:
            declared.append((evidence.get('id'), next(iter(pages)), next(iter(hashes))))
    if not declared:
        return []
    corpus = Path(source['corpus_path']).expanduser()
    pages = {page.get('pdf_page_1based'): page for page in local_sources._pages(str(corpus))
             if page.get('book_id') == source['book_id']}
    errors = []
    for evidence_id, page_number, claimed_hash in declared:
        actual = pages.get(page_number, {}).get('source_sha256')
        if actual != claimed_hash:
            errors.append({'evidence_id': evidence_id, 'pdf_page': page_number,
                           'claimed_scan_sha256': claimed_hash, 'current_scan_sha256': actual})
    return errors
