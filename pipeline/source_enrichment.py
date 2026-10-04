"""Resumable, source-specific enrichment of already published editorial cohorts.

Registry example::

    {"schema_version": 1, "sources": [{"id": "ziyuan-2012",
      "title": "字源", "bibliography": "李學勤主編《字源》, 2012.",
      "book_id": "ziyuan-2012", "corpus_path": "/path/to/ziyuan-pages.jsonl"}]}

Run from the repository root with ``python3 -m pipeline.source_enrichment prepare
--registry sources.json --source ziyuan-2012 --cohort content/cohorts/hsk1.json``.
The separate ``run``, ``publish``, and ``status`` actions resume that exact source job.
"""
from __future__ import annotations

import argparse
import copy
import fcntl
from datetime import datetime, timezone
import hashlib
import json
import shutil
from pathlib import Path
import re

from pipeline import batch, editorial, work_queue

ROOT = editorial.ROOT
ISSUE_METADATA = {"github_repo", "tracking_issue_url", "issue_parent_number",
                  "issue_milestone", "issue_labels", "issue_parent_by_kind"}


def _locator_hash(located):
    """Pixel hash labels repeat page identity already bound in candidate provenance."""
    value = copy.deepcopy(located)
    for scan in value.get("source_scan_images", []):
        pixel_hash = scan.get("source_pixel_sha256")
        candidates = [candidate for lead in value.get("source_leads", [])
                      for candidate in lead.get("candidates", [])]
        # Ignore only redundant metadata, never a new or conflicting source identity.
        if pixel_hash and any(candidate.get("source_sha256") == pixel_hash
                              and candidate.get("pdf_page_1based") == scan.get("pdf_page")
                              for candidate in candidates):
            scan.pop("source_pixel_sha256")
    for lead in value.get('source_leads', []):
        for candidate in lead.get('candidates', []):
            if candidate.get('evidence_sha256'):
                # The exact effective evidence remains bound; this is a derived status reminder.
                candidate.pop('applied_ocr_corrections', None)
    return editorial.digest(value)


def validate_correct_raw_occurrence_receipt(job, finding_key, receipt_path, occurrence_ids):
    """Validate a completed Luna scan receipt for exact existing raw occurrences.

    This proof can release only an already-disproved replacement hypothesis from
    the editorial-continuation preflight. It does not mutate OCR, remove the
    retained source finding, or satisfy the final exact-pair source-resolution
    gate. The normal source resolver must still assess every retained finding.
    """
    from pipeline import ocr_verification

    job = Path(job)
    receipt_path = Path(receipt_path)
    receipt = editorial.read(receipt_path)
    occurrence_packet_path = receipt_path.parent / 'occurrences.json'
    packet_record = editorial.read(occurrence_packet_path)
    source_snapshot = editorial.read(job / 'source.json')
    source = source_snapshot.get('registry_source', {})
    findings = editorial.read(job / 'source_findings.json').get('findings', [])
    finding = next((item for item in findings if item.get('key') == finding_key), None)
    if not finding or _source_finding_class(finding) != 'transcription_correction':
        raise ValueError('Raw-occurrence proof must bind a retained transcription finding')
    if not isinstance(occurrence_ids, list) or not occurrence_ids or len(occurrence_ids) != len(set(occurrence_ids)):
        raise ValueError('Raw-occurrence proof requires unique exact occurrence IDs')
    if (receipt.get('model') != 'gpt-6-luna' or receipt.get('reasoning') != 'low'
            or receipt.get('result_hash') != editorial.digest(receipt.get('result'))):
        raise ValueError('Raw-occurrence receipt is not bound to a Luna-low result')
    review_dir = Path(receipt.get('review_directory', ''))
    meta_path = review_dir / 'meta.json'
    if not meta_path.is_file():
        raise ValueError('Raw-occurrence receipt has no completed review metadata')
    meta = editorial.read(meta_path)
    if (meta.get('role') != 'ocr_verification' or meta.get('status') != 'complete'
            or meta.get('model') != 'gpt-6-luna' or meta.get('reasoning') != 'low'
            or meta.get('result_hash') != receipt.get('result_hash')):
        raise ValueError('Raw-occurrence receipt metadata is not a completed Luna-low scan review')
    provenance = packet_record.get('provenance', {})
    if (receipt.get('provenance') != provenance
            or receipt.get('occurrences_hash') != editorial.digest(packet_record.get('occurrences', []))
            or provenance.get('source_id') != source_snapshot.get('source_id')
            or provenance.get('book_id') != source.get('book_id')):
        raise ValueError('Raw-occurrence receipt does not match the frozen registered source identity')
    if (editorial.digest(editorial.read(job / 'source_article.json')) != source_snapshot.get('article_hash')
            or editorial.digest(editorial.read(job / 'source_dossier.json')) != source_snapshot.get('dossier_hash')):
        raise ValueError('Raw-occurrence proof job has altered frozen article or dossier inputs')
    page_number = provenance.get('pdf_page')
    matched_pages = []
    with Path(source.get('corpus_path', '')).open(encoding='utf-8') as corpus:
        for line in corpus:
            page = json.loads(line)
            if (page.get('pdf_page_1based') == page_number
                    and page.get('book_id') == source.get('book_id')):
                matched_pages.append(page)
    if len(matched_pages) != 1:
        raise ValueError('Raw-occurrence receipt source page is absent or ambiguous in the registered corpus')
    page = matched_pages[0]
    raw_text = page.get('text', '')
    if (page.get('source_scan') != provenance.get('source_scan_path')
            or (provenance.get('source_sha256') is not None
                and page.get('source_sha256') != provenance.get('source_sha256'))
            or hashlib.sha256(raw_text.encode('utf-8')).hexdigest() != provenance.get('raw_text_sha256')):
        raise ValueError('Raw-occurrence receipt does not bind the current registered page text and scan')
    scan_manifest = {str(Path(item.get('path', '')).resolve()): item
                     for item in meta.get('image_argument_manifest', [])}
    scan_path = Path(page['source_scan']).resolve()
    scan_manifest_entry = scan_manifest.get(str(scan_path))
    scan_file_hash = hashlib.sha256(scan_path.read_bytes()).hexdigest()
    if (not scan_manifest_entry or scan_manifest_entry.get('sha256') != scan_file_hash
            or provenance.get('source_pixel_sha256') != scan_file_hash):
        raise ValueError('Luna review metadata does not bind the registered original page scan')
    # The legacy OCR verifier receipt field named source_pixel_sha256 contains
    # encoded-file SHA-256 (as recorded in its run metadata), not decoded RGB
    # bytes. Independently validate the actual decoded pixels against the
    # consumer corpus's source hash before using the receipt.
    from PIL import Image
    with Image.open(scan_path) as image:
        actual_pixel_hash = hashlib.sha256(image.convert('RGB').tobytes()).hexdigest()
    if page.get('source_sha256') != actual_pixel_hash:
        raise ValueError('Original scan pixels differ from the registered consumer corpus source hash')
    occurrences = packet_record.get('occurrences', [])
    if {item.get('id') for item in occurrences} != set(occurrence_ids):
        raise ValueError('Raw-occurrence proof must name every and only packet occurrence')
    for item in occurrences:
        start, end = item.get('start'), item.get('end')
        if (type(start) is not int or type(end) is not int or not 0 <= start < end <= len(raw_text)
                or raw_text[start:end] != item.get('before')):
            raise ValueError('Raw-occurrence packet span differs from the registered current corpus')
    ocr_verification.validate_result(receipt.get('result', {}), occurrences)
    result_by_id = {item['id']: item for item in receipt['result']['occurrences']}
    if any(result_by_id[identity].get('verdict') != 'correct_raw' for identity in occurrence_ids):
        raise ValueError('Only unanimous correct_raw occurrence receipts release this editorial preflight')
    finding_text = ' '.join(str(finding.get(field, '')) for field in ('title', 'details', 'verification'))
    if any(item['before'] not in finding_text for item in occurrences):
        raise ValueError('Proof occurrences are not textually bound to the retained finding')
    transcription_check = {
        'key': finding_key,
        'pdf_page': page_number,
        'source_pixel_sha256': actual_pixel_hash,
        'occurrences': [{'id': item['id'], 'text_offset': item['start'],
                         'current': item['before']} for item in occurrences],
    }
    return {
        'finding_key': finding_key,
        'receipt_path': str(receipt_path.resolve()),
        'receipt_hash': editorial.digest(receipt),
        'result_hash': receipt['result_hash'],
        'occurrence_ids': list(occurrence_ids),
        'pdf_page': page_number,
        'source_sha256': page['source_sha256'],
        'source_scan_file_sha256': scan_file_hash,
        'source_pixel_sha256': actual_pixel_hash,
        'raw_text_sha256': provenance['raw_text_sha256'],
        'article_hash': source_snapshot['article_hash'],
        'dossier_hash': source_snapshot['dossier_hash'],
        'transcription_check': transcription_check,
        'disposition': 'correct_raw_preflight_only',
        'final_source_resolution_still_required': True,
    }

SOURCE_POLICY = """
SOURCE-SPECIFIC CHINESE ENRICHMENT:
An account that reports borrowing does not by itself identify the earlier word's
name, reading or exact sound match. Cite those specific lexical/phonological claims
separately when supported; otherwise retain the borrowing account with its precise
qualification and omit the unsupported mechanism from learner prose.
Keep chronology and attestation tied to the actual evidence. A received dictionary
or Shuowen gloss is an attested lexicographic interpretation; it does not by itself
date a historical lexical use or establish the original sense. When dating is
unresolved, do not call that use early without separate period evidence. A source
saying that another spelling later came to be used does not demonstrate that one
written graph changed into the other. Distinguish alternative graphs, later sense
assignment and an evidenced graphic change in both learner wording and metadata.
Do not add a whole-graph borrowing limitation when no supported borrowing account
is at issue. State the specific evidential gap instead. Non-display of historical
forms in consulted records establishes only what those records show, not their
absence from an entire period or corpus.
Modern visible assembly and ancient derivation require separate evidence. A source
rejecting derivation from a look-alike graph does not itself negate a supported
current decomposition. Verify the grouped modern unit or positional variant through
current-form sources; do not promote mere resemblance to a standalone component
identity or replace a supported current account with an ancient research gap.
In expert phonetic comparisons, qualify approximate matches with the actual relevant
sound contrast and identify the reconstruction/reading system; avoid an unexplained
statement that sounds simply differ. Keep specialist contrasts after the learner
account and do not invent a word pronunciation to justify proposed borrowing.
The supplied source bibliography and corpus are research leads for this character, not
pre-verified evidence. Search the supplied corpus and inspect all relevant records. Confirm
the actual headword, passage, page continuation, component identity and any cited rare glyph
against the source scan where available. Distinguish provisional OCR from verified transcription.
Before citing a crop as verification, confirm that the suspect printed occurrence and
its adjacent anchor are actually inside the crop. A correct pixel hash verifies the
image bytes, not coverage of the occurrence. A missing or clipped target remains unresolved
until the original source bounds are corrected. Derive Unicode scalar labels from the
literal string with codepoint tooling rather than recalling hexadecimal values.
Do not repair or normalize questionable OCR by inference. For each unresolved scan or OCR issue,
    add a research gap beginning exactly `[SCAN VERIFICATION REQUIRED]` or
`[OCR CORRECTION REQUIRED]`, followed by the exact
suspect page/span and why it needs scan verification.
Use those markers for checks that actually remain unresolved. A printed page number
you directly read from the scan is verified citation provenance even when the corpus
has not extracted it; report that metadata omission separately without describing the
number as scan-unverified. Choosing not to replace existing article glyphs with the
book's specimens is not itself an unresolved scan check. Identify a specific unread
or disputed feature if a specimen really requires verification, and state whether an
article claim depends on it. Preserve genuine identity, transcription and scope gaps.
If an earlier attempt could not identify a printed component, a later assertion that it was
inspected does not by itself resolve the gap. Inspect a targeted original-resolution crop,
record the distinguishing visible strokes and exact raw occurrence, and preserve competing
identifications for an independent check. Keep proposed literal replacements tagged as
`[OCR CORRECTION REQUIRED]` until a source-bound producer correction is actually verified;
research must not claim that a corpus repair has occurred from its own proposed reading.
Use other authoritative references to test the book's claims and preserve disagreements and precise
uncertainty. Add only source-backed findings with page-specific provenance; retain all existing
evidence unless a reviewed correction is necessary. Do not infer missing evidence from the
existing article. Preserve the current historical glyph selection for this text-focused task.
For a source's report that a graph has not been found, preserve its combined period,
corpus and author scope. Do not turn reported non-attestation into proven absence from
all writing in each named period. Keep an inferred date from a transmitted text distinct
from a verified dated artifact, even when both appear in the same paragraph.
""".strip()


def _load_source_tools():
    # Kept lazy so CLI help and unit tests can import the module while the registry
    # producer is being developed alongside this consumer.
    from pipeline import local_sources
    return local_sources


def _source_registry(path):
    return _load_source_tools().load_registry(path)


def _source(registry, source_id):
    sources = registry.get("sources", [])
    for item in sources if isinstance(sources, list) else []:
        if item.get("id") == source_id:
            return item
    raise ValueError(f"Unknown source: {source_id}")


def _research_source(source):
    """Identity of the researched book/corpus, excluding issue workflow settings."""
    return {key: value for key, value in source.items() if key not in ISSUE_METADATA}


def _research_source_hash(source):
    return editorial.digest(_research_source(source))


def _same_research_source(left, right):
    return _research_source_hash(left) == _research_source_hash(right)


def _recorded_source_hash_matches(recorded_hash, saved_source, current_source):
    """Accept current identity hashes and legacy full hashes from the immutable snapshot."""
    if not isinstance(saved_source, dict) or not _same_research_source(saved_source, current_source):
        return False
    compatible = {_research_source_hash(saved_source), _research_source_hash(current_source),
                  editorial.digest(saved_source)}
    return recorded_hash in compatible


def load_cohort(path):
    cohort = editorial.read(path)
    chars = cohort.get("characters")
    if not isinstance(chars, list) or not chars or any(not isinstance(c, str) or len(c) != 1 for c in chars):
        raise ValueError("Cohort requires an explicit nonempty array of single characters")
    if len(set(chars)) != len(chars):
        raise ValueError("Cohort contains duplicate characters")
    return cohort


def job_path(output, source_id, character):
    safe_id = "".join(c if c.isalnum() or c in "-_" else "_" for c in source_id)
    return Path(output) / safe_id / f"{ord(character):04X}"


def _canonical(root, character):
    name = f"{ord(character):04X}.json"
    ep = Path(root) / "content/entries" / name
    dp = Path(root) / "content/dossiers" / name
    if not ep.is_file() or not dp.is_file():
        raise ValueError(f"No published article and dossier for {character}")
    dossier = editorial.read(dp)
    article = editorial.validate_published(editorial.read(ep), dossier)
    return article, dossier


def prepare_job(character, job, source, root=ROOT):
    """Freeze exact published inputs and source identity for a resumable job."""
    job = Path(job)
    source_path, article_path, dossier_path = (job / "source.json", job / "source_article.json", job / "source_dossier.json")
    if source_path.exists():
        saved = editorial.read(source_path)
        if (saved.get("source_id") != source["id"] or saved.get("character") != character
                or not _recorded_source_hash_matches(saved.get("registry_source_hash"),
                    saved.get("registry_source"), source)):
            raise ValueError("Existing job is bound to another source or character")
        if not article_path.exists() or not dossier_path.exists():
            raise ValueError("Existing source job is missing its provenance snapshot")
        if editorial.digest(editorial.read(article_path)) != saved.get("article_hash") or editorial.digest(editorial.read(dossier_path)) != saved.get("dossier_hash"):
            raise ValueError("Source job snapshot hash mismatch")
        return saved
    article, dossier = _canonical(root, character)
    job.mkdir(parents=True, exist_ok=True)
    editorial.write(article_path, article)
    editorial.write(dossier_path, dossier)
    saved = {"character": character, "source_id": source["id"],
             "registry_source": source,
             "registry_source_hash": _research_source_hash(source),
             "article_hash": editorial.digest(article), "dossier_hash": editorial.digest(dossier),
             "prepared_at": datetime.now(timezone.utc).isoformat()}
    editorial.write(source_path, saved)
    editorial.write(job / "status.json", {**saved, "status": "prepared"})
    return saved


def recover_frozen_inputs(job, root=ROOT):
    """Restore collided job inputs only from the exact unchanged canonical baseline."""
    job = Path(job)
    with (job / 'coordinator.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError('Cannot recover frozen inputs while a coordinator or agent is live')
        saved = editorial.read(job / 'source.json')
        article, dossier = _canonical(root, saved['character'])
        if (editorial.digest(article) != saved['article_hash']
                or editorial.digest(dossier) != saved['dossier_hash']):
            raise ValueError('Canonical baseline changed; frozen inputs cannot be recovered')
        previous = {name: editorial.read(job / name) for name in
                    ('source_article.json', 'source_dossier.json')}
        if (editorial.digest(previous['source_article.json']) == saved['article_hash']
                and editorial.digest(previous['source_dossier.json']) == saved['dossier_hash']):
            return {'status': 'unchanged'}
        archive = job / 'frozen-input-recovery' / editorial.digest(previous)
        archive.mkdir(parents=True, exist_ok=True)
        for name in previous:
            if not (archive / name).exists():
                shutil.copy2(job / name, archive / name)
        receipt = {'status': 'restored_exact_baseline', 'source_snapshot_hash': editorial.digest(saved),
                   'article_hash': saved['article_hash'], 'dossier_hash': saved['dossier_hash'],
                   'previous_inputs_hash': editorial.digest(previous),
                   'archive': str(archive), 'creates_authorship_or_approval': False}
        editorial.write(archive / 'recovery.json', receipt)
        editorial.write(job / 'source_article.json', article)
        editorial.write(job / 'source_dossier.json', dossier)
        return receipt


def feedback(source, located=None, source_context=None):
    value = {"reuse_existing_glyph_candidates": True,
        "source_enrichment": {"source": _research_source(source),
            "corpus_instructions": "Search this supplied corpus directly; verify candidate passages against source scans where possible.",
            "preserve_existing_evidence": True,
        "record_ocr_uncertainty": "Do not guess OCR corrections. Report the exact suspect page/span and why it needs scan verification in the research gaps; do not silently normalize it."},
        "task": ("Research this already published character with the supplied local scholarly source. "
                 "Search and inspect the supplied corpus, verify the actual headword and relevant passage "
                 "against scan images when available, and compare the book with other authoritative "
                 "references. Preserve existing supported evidence and article content unless a precise "
                 "source-backed improvement is warranted. Keep uncertainty scoped and glyph assets intact. "
                 "Cite at least one relevant finding from the named book with its exact page; "
                 "In the authored article, cite the retained book evidence ID on the specific supported "
                 "claim; placing a new book record only in the dossier is not article enrichment. "
                 "Use evidence_ids arrays, never inline labels. If the book corroborates existing "
                 "prose, preserve that prose and add only the supported citation before fresh reviews. "
                 "if no relevant claim can be established, record a source-specific access or "
                 "relevance gap. For each unresolved OCR or scan identity issue, add a gap beginning "
                 "exactly [SCAN VERIFICATION REQUIRED] or [OCR CORRECTION REQUIRED] and state page, "
                 "span, and reason.")}
    if located:
        value.update(located)
    if source_context:
        merged = list(value.get("source_scan_images", [])) + list(source_context)
        value["source_scan_images"] = merged
    return value


def _published_matches(job, source, root):
    job = Path(job)
    status_path = job / "status.json"
    if not status_path.exists():
        return False
    state = editorial.read(status_path)
    required = ("article.json", "dossier.json", "reviews.json")
    if state.get("status") != "published" or not all((job / n).is_file() for n in required):
        return False
    article, dossier, reviews = [editorial.read(job / n) for n in required]
    try:
        if _source_scan_binding_errors(source, article, dossier):
            return False
        editorial.validate_reviews(article, dossier, reviews)
        canonical_article, canonical_dossier = _canonical(root, article["character"])
        located = _load_source_tools().locate_sources({"schema_version": 1, "sources": [source]},
            article["character"], editorial.read(job / "source_dossier.json"))
    except (ValueError, KeyError, OSError, editorial.ValidationError):
        return False
    audit_path = job / "source_audit.json"
    if audit_path.is_file() and editorial.read(audit_path).get('mode') in (
            'existing_approved_research', 'source_coverage_candidate'):
        from pipeline.source_adoption import valid_audit
        if not valid_audit(job, editorial.read(audit_path), article, dossier):
            return False
    return (not _source_findings_pending(job)
            and audit_path.is_file()
            and editorial.read(audit_path).get("verified") is True
            and _article_used_book_evidence(editorial.read(audit_path), article, dossier)
            and state.get("source_id") == source["id"]
            and _recorded_source_hash_matches(state.get("registry_source_hash"),
                editorial.read(job / "source.json").get("registry_source"), source)
            and state.get("locator_hash") == _locator_hash(located)
            and state.get("source_audit_hash") == editorial.digest(editorial.read(audit_path))
            and _recorded_source_hash_matches(editorial.read(audit_path).get("source_hash"),
                editorial.read(job / "source.json").get("registry_source"), source)
            and state.get("article_hash") == editorial.digest(article)
            and state.get("dossier_hash") == editorial.digest(dossier)
            and editorial.digest(canonical_article) == editorial.digest(article)
            and editorial.digest(canonical_dossier) == editorial.digest(dossier))


def _integrate_uncited_book_records(job, source, runner, state, audit, feedback, max_revisions):
    """One genuine editing/review pass over current research, without minting more IDs."""
    job = Path(job)
    if state.get('status') not in ('approved', 'needs_source_evidence', 'needs_source_verification') or audit.get('verified') or not audit.get('consulted_citations'):
        return state, audit
    article, dossier = editorial.read(job / 'article.json'), editorial.read(job / 'dossier.json')
    editorial.validate_reviews(article, dossier, editorial.read(job / 'reviews.json'))
    approved_base = {'article': copy.deepcopy(article), 'dossier': copy.deepcopy(dossier),
                     'reviews': editorial.read(job / 'reviews.json')}
    archive = job / 'before-citation-integration' / editorial.digest(article)
    for name in ('article.json', 'dossier.json', 'reviews.json', 'status.json'):
        if (job / name).exists():
            archive.mkdir(parents=True, exist_ok=True)
            shutil.copy2(job / name, archive / name)
    context = {**feedback, 'current_uncited_book_records': audit['consulted_citations'],
        'citation_integration_policy': (
            'Research has already returned the supplied exact page-specific book records. '
            'Use the current retained evidence IDs on article claims that these records support. '
            'Unchanged supported prose plus a citation is sufficient. Do not invent support, '
            'put IDs in prose, or cite unrelated claims. If no record supports an article claim, '
            'retain a precise research gap. Obtain fresh independent factual and readability reviews.')}
    stage = job / 'citation-integration'
    article = editorial.author_book_citations(article, dossier, audit['consulted_citations'],
                                             stage / 'citation-author', runner, context)
    repaired = editorial.refine(article, dossier, stage, runner, max_revisions,
                                context, research_first=False, edit_first=False,
                                approved_base=approved_base)
    for name in ('article.json', 'dossier.json', 'reviews.json'):
        if (stage / name).exists():
            shutil.copy2(stage / name, job / name)
    repaired_audit = _capture_source_audit(job, source, editorial.read(job / 'dossier.json'))
    return repaired, repaired_audit


def _capture_scan_findings(job, source):
    """Promote explicitly tagged unresolved OCR gaps from every research attempt."""
    root = Path(job)
    paths = sorted(root.glob("**/research/result.json")) + sorted(root.glob("**/research-repair-*/result.json"))
    gaps = []
    markers = ("[SCAN VERIFICATION REQUIRED]", "[OCR CORRECTION REQUIRED]")
    for path in dict.fromkeys(paths):
        try:
            result = editorial.read(path)
        except (OSError, ValueError):
            continue
        for gap in result.get("gaps", []):
            if isinstance(gap, str) and gap.startswith(markers):
                gaps.append({"key": f"{source['id']}:{root.name}:{editorial.digest(gap)[:12]}",
                    "kind": "ocr", "title": f"Verify {source.get('title', source['id'])} scan finding for {root.name}",
                    "details": gap, "verification": "Check the identified printed page and exact scan span; correct source-bound OCR or record an unresolved glyph identity.",
                    "evidence": [f"Source job: {root}", f"Research output: {path.relative_to(root)}"]})
    # Stable de-duplication covers repeated gaps across research repair attempts.
    unique = {item["key"]: item for item in gaps}
    gaps = list(unique.values())
    record = {"source_id": source["id"], "tracking_issue_url": source.get("tracking_issue_url"),
              "requires_coordinator_verification": bool(gaps), "findings": gaps}
    editorial.write(Path(job) / "source_findings.json", record)
    return record


def _verify_missing_page_metadata(job, checks):
    """Bind citation-label observations to an absent field and original page pixels."""
    job = Path(job)
    registered = editorial.read(job / 'source.json')['registry_source']
    findings = {f['key'] for f in editorial.read(job / 'source_findings.json')['findings']}
    if len({c['key'] for c in checks}) != len(checks):
        raise ValueError('Metadata checks must identify unique findings')
    needed = {c['pdf_page'] for c in checks}
    pages = {}
    with Path(registered['corpus_path']).open() as corpus:
        for line in corpus:
            page = json.loads(line)
            if page.get('pdf_page_1based') in needed:
                if page['pdf_page_1based'] in pages:
                    raise ValueError('Metadata page identity is ambiguous')
                pages[page['pdf_page_1based']] = page
    for check in checks:
        page = pages.get(check['pdf_page'], {})
        if (check['key'] not in findings or check.get('field') != 'printed_page'
                or check.get('current_value') is not None
                or page.get('printed_page') is not None
                or not isinstance(check.get('expected_value'), str)
                or not check['expected_value'].strip()
                or ('source_scan' in check and check['source_scan'] != page.get('source_scan'))
                or page.get('source_sha256') != check.get('source_pixel_sha256')):
            raise ValueError('Metadata check requires an absent printed-page field and exact source identity')
        editorial.source_scan_attachments([{'path': page['source_scan'],
            'pdf_page': check['pdf_page'], 'source_pixel_sha256': check['source_pixel_sha256']}])
    return [{**check, 'source_scan': pages[check['pdf_page']]['source_scan']} for check in checks]


def _verify_transcription_checks(job, checks):
    """Bind an observation of existing text, without inventing a replacement proposal."""
    job = Path(job)
    source = editorial.read(job / 'source.json')['registry_source']
    keys = {f['key'] for f in editorial.read(job / 'source_findings.json')['findings']}
    if len({c['key'] for c in checks}) != len(checks):
        raise ValueError('Transcription checks require unique retained findings')
    pages = {}
    needed = {c['pdf_page'] for c in checks}
    with Path(source['corpus_path']).open() as corpus:
        for line in corpus:
            page = json.loads(line)
            number = page.get('pdf_page_1based')
            if number in needed:
                if number in pages:
                    raise ValueError('Transcription page identity is ambiguous')
                pages[number] = page
    normalized = []
    for check in checks:
        page = pages.get(check['pdf_page'], {})
        source_occurrences = check.get('occurrences')
        if source_occurrences is None:
            source_occurrences = [{'id': 'single', 'text_offset': check.get('text_offset'),
                                   'current': check.get('current')}]
        ids = [item.get('id') for item in source_occurrences if isinstance(item, dict)]
        if (check['key'] not in keys or not source_occurrences
                or len(ids) != len(source_occurrences) or len(ids) != len(set(ids))
                or page.get('source_sha256') != check.get('source_pixel_sha256')
                or ('source_scan' in check and check['source_scan'] != page.get('source_scan'))):
            raise ValueError('Transcription check requires exact current text and source pixels')
        spans = []
        for occurrence in source_occurrences:
            start, current = occurrence.get('text_offset'), occurrence.get('current')
            end = start + len(current) if type(start) is int and isinstance(current, str) else -1
            if (type(start) is not int or start < 0 or not isinstance(current, str) or not current
                    or page.get('text', '')[start:end] != current
                    or any(start < previous_end and previous_start < end for previous_start, previous_end in spans)):
                raise ValueError('Transcription check requires exact nonoverlapping current text spans')
            spans.append((start, end))
        editorial.source_scan_attachments([{'path': page['source_scan'],
            'pdf_page': check['pdf_page'], 'source_pixel_sha256': check['source_pixel_sha256']}])
        normalized.append({**check, 'occurrences': source_occurrences,
                           'source_scan': page['source_scan']})
    return normalized


def _verify_source_claim_checks(job, checks, scans):
    """Bind a research-gap disposition to an actual Luna research result and its scans."""
    job = Path(job)
    findings = {f['key']: f for f in editorial.read(job / 'source_findings.json')['findings']}
    if len({c.get('key') for c in checks}) != len(checks):
        raise ValueError('Source claim checks require unique retained findings')
    attached = {s.get('source_pixel_sha256'): s for s in scans
                if isinstance(s, dict) and s.get('source_pixel_sha256')}
    normalized = []
    for check in checks:
        key = check.get('key')
        finding = findings.get(key)
        result_path = Path(check.get('research_result_path', ''))
        meta_path = Path(check.get('research_meta_path', ''))
        gap_text = ' '.join(str(finding.get(k, '')) for k in ('title', 'details', 'verification')) if finding else ''
        if (not finding or not result_path.is_file() or not meta_path.is_file()
                or finding.get('kind') != 'ocr'
                or not re.search(r'failed to open|not (?:directly )?inspected|was not inspected|not supplied|was not supplied',
                                 gap_text, re.I)):
            raise ValueError('Source claim check requires a retained primary-source access gap and research artifacts')
        result, meta = editorial.read(result_path), editorial.read(meta_path)
        if (meta.get('role') != 'research' or meta.get('status') != 'complete'
                or meta.get('model') != 'gpt-6-luna' or meta.get('reasoning') != 'low'
                or meta.get('result_hash') != editorial.digest(result)):
            raise ValueError('Source claim check requires completed Luna-low research bound to its result')
        indices, pixels = check.get('evidence_indices'), check.get('source_pixel_sha256s')
        evidence, manifest = result.get('evidence', []), meta.get('image_argument_manifest', [])
        manifest_by_path = {str(Path(item.get('path', '')).resolve()): item for item in manifest}
        if (not isinstance(indices, list) or not indices or len(indices) != len(set(indices))
                or not isinstance(pixels, list) or len(pixels) != len(indices)
                or any(type(i) is not int or i < 0 or i >= len(evidence) for i in indices)):
            raise ValueError('Source claim check must name exact research evidence records')
        bindings = []
        for index, pixel in zip(indices, pixels):
            record = evidence[index]
            if record.get('kind') != 'primary_source_scan_inspection' or not isinstance(pixel, str):
                raise ValueError('Source claim evidence must be a primary scan inspection')
            scan = attached.get(pixel)
            if not scan:
                raise ValueError('Source claim evidence requires its exact attached source scan')
            editorial.source_scan_attachments([scan])
            scan_path = Path(scan['path']).resolve()
            manifest_entry = manifest_by_path.get(str(scan_path))
            file_hash = hashlib.sha256(scan_path.read_bytes()).hexdigest()
            if (not manifest_entry or manifest_entry.get('sha256') != file_hash
                    or pixel not in json.dumps(record, ensure_ascii=False)):
                raise ValueError('Research evidence is not bound to the attached pixels')
            bindings.append({'evidence_index': index, 'source_pixel_sha256': pixel,
                             'scan_path': str(scan_path), 'scan_file_sha256': file_hash,
                             'pdf_page': scan.get('pdf_page')})
        normalized.append({'key': key, 'research_result_path': str(result_path.resolve()),
            'research_meta_path': str(meta_path.resolve()), 'research_result_hash': editorial.digest(result),
            'research_meta_file_sha256': hashlib.sha256(meta_path.read_bytes()).hexdigest(),
            'evidence_indices': indices, 'source_pixel_sha256s': pixels, 'scan_bindings': bindings,
            'research_evidence': [evidence[i] for i in indices]})
    return normalized


def _source_finding_class(finding):
    """Classify only explicit retained finding language; never infer OCR disposition from plausibility."""
    text = ' '.join(str(finding.get(k, '')) for k in ('title', 'details', 'verification'))
    # Findings are sometimes tagged with an OCR action marker even when their
    # body explicitly says that no literal replacement is proposed and that
    # the issue is a page/entry boundary (for example, a running header above
    # a different headword).  Treat those as source-access/scope gaps so the
    # normal exact-pair source resolver can determine whether the candidate
    # depends on the missing entry.  The original finding remains in the
    # inventory; a real before→after proposal still takes the transcription
    # lane below.
    explicit_literal_proposal = (
        finding.get('proposed_literal') is not None
        or finding.get('proposed') is not None
        or re.search(r'\b(?:propos(?:e|es|ed|al))\b.{0,120}'
                     r'(?:rather than|instead of|replace|correction|current(?:ly)? reads)', text, re.I)
    )
    no_literal_proposal = re.search(
        r'\bno\s+(?:replacement\s+)?(?:unicode\s+)?(?:transcription|ocr|literal|character)'
        r'(?:\s+(?:span|text|value))?\s+(?:is\s+)?(?:proposed|requested|identified|specified)',
        text, re.I)
    entry_boundary_issue = re.search(
        r'entry[- ]boundary|running[- ]header|header.{0,80}(?:not|rather than).{0,80}headword|'
        r'not a substantive entry|body.{0,80}belongs to|entry text belongs to', text, re.I)
    if no_literal_proposal and entry_boundary_issue and not explicit_literal_proposal:
        return 'primary_access_gap'
    if (explicit_literal_proposal or '[OCR CORRECTION REQUIRED]' in text or 'raw provisional OCR span' in text
            or 'proposed source-bound OCR correction' in text
            or ('raw OCR' in text and re.search(r'not use .{0,80}confirmed source text', text, re.I))):
        return 'transcription_correction'
    if re.search(r'failed to open|not (?:directly )?inspected|(?:was|were|did) not '
                  r'(?:directly )?inspect(?:ed|ing)?|not supplied|was not supplied|'
                  r'this invocation (?:did not|has not) inspect|'
                  r'this invocation.{0,80}directly inspected only', text, re.I):
        return 'primary_access_gap'
    absent_source = re.search(
        r'\b(?:source|dataset|database|official page|reading(?:s)? source)\b.{0,180}'
        r'(?:absent|unavailable|not available|not accessible|not supplied|not obtained)', text, re.I)
    absent_source = absent_source or re.search(
        r'\b(?:absent|unavailable|not available|not accessible|not supplied|not obtained)\b.{0,180}'
        r'\b(?:source|dataset|database|official page|reading(?:s)? source)\b', text, re.I)
    if absent_source:
        return 'primary_access_gap'
    identity_term = r'(?:\bidentit(?:y|ies)\b|\bidentification(?:s)?\b|\bUnicode scalar(?:s)?\b)'
    identity_gap = re.search(identity_term + r'.{0,120}(?:unresolved|unclear|not established|'
                              r'not (?:separately |individually |independently )?(?:checked|verified|identified)|'
                              r'did not (?:separately |individually |independently )?(?:check|verify|identify)|'
                              r'should be verified|not distinct enough|remain(?:s|ed)? uncertain)', text, re.I)
    identity_gap = identity_gap or re.search(
        r'did not (?:separately |individually |independently )?(?:check|verify|identify).{0,100}'
        + identity_term, text, re.I)
    # Research findings often phrase a gap in the inverse order: the reviewer
    # "did not establish the Unicode identity" rather than "the identity was
    # not established." Keep those occurrence-bound identity gaps in the
    # identity lane so resolution requires an exact claim inventory.
    identity_gap = identity_gap or re.search(
        r'did not (?:separately |individually |independently )?(?:establish|determine|ascertain)'
        r'.{0,140}' + identity_term, text, re.I)
    specimen_gap = re.search(r'\b(?:glyph|specimen|graph|form)s?\b.{0,120}'
                             r'(?:not (?:separately |individually |independently )?(?:identified|interpreted|checked|verified)|'
                             r'did not (?:separately |individually |independently )?(?:identify|interpret|check|verify)|'
                             r'not (?:all )?distinct enough to assign)', text, re.I)
    specimen_gap = specimen_gap or re.search(
        r'no claim (?:is|was) made.{0,220}\b(?:glyph|specimen|graph|form)s?\b.{0,140}'
        r'(?:identified|interpreted|checked|verified)', text, re.I)
    if identity_gap or specimen_gap:
        return 'identity_gap'
    return 'other'


def _historical_checked_keys(job):
    """Find prior check classes only from exact, completed, re-verifiable receipts."""
    job = Path(job)
    required = {'rejected_proposal_scan_matches_corpus': set(),
                'applied_repair_scan_matches_corpus': set(),
                'verified_metadata_not_extracted': set(),
                'verified_transcription_matches_corpus': set()}
    for path in job.rglob('source_resolution.json'):
        try:
            receipt = editorial.read(path)
            result_path = (job / receipt['review_path']).resolve()
            if not result_path.is_relative_to(job.resolve()):
                continue
            result = editorial.read(result_path)
            meta = editorial.read(result_path.parent / 'meta.json')
            findings = editorial.read(job / 'source_findings.json')
            article = editorial.read(job / 'article.json')
            dossier = editorial.read(job / 'dossier.json')
            if (receipt.get('findings_hash') != editorial.digest(findings)
                    or receipt.get('article_hash') != editorial.digest(article)
                    or receipt.get('dossier_hash') != editorial.digest(dossier)
                    or receipt.get('result_hash') != editorial.digest(result)
                    or meta.get('role') != 'source_resolution' or meta.get('status') != 'complete'
                    or meta.get('model') != 'gpt-6-luna' or meta.get('reasoning') != 'low'
                    or meta.get('result_hash') != editorial.digest(result)):
                continue
        except (OSError, ValueError, KeyError, TypeError):
            continue
        result_items = {item.get('key'): item for item in result.get('findings', [])
                        if isinstance(item, dict)}
        if len(result_items) != len(result.get('findings', [])):
            continue
        checks_by_field = [
            ('literal_checks', 'literal_observations', 'rejected_proposal_scan_matches_corpus'),
            ('applied_repairs', 'repair_observations', 'applied_repair_scan_matches_corpus'),
            ('metadata_checks', 'metadata_observations', 'verified_metadata_not_extracted'),
            ('transcription_checks', 'transcription_observations', 'verified_transcription_matches_corpus')]
        for check_field, observation_field, disposition in checks_by_field:
            checks = receipt.get(check_field, [])
            if not checks:
                continue
            keys = {check.get('key') for check in checks if isinstance(check, dict)}
            observations = result.get(observation_field, [])
            observed = {item.get('key'): item for item in observations if isinstance(item, dict)}
            if (len(keys) != len(checks) or len(observed) != len(observations)
                    or keys != set(observed)
                    or any(result_items.get(key, {}).get('disposition') != disposition for key in keys)):
                continue
            try:
                if check_field == 'literal_checks':
                    _verify_literal_checks(job, checks)
                    for check in checks:
                        item = observed[check['key']]
                        if (item.get('current_corpus_literal') != check.get('current')
                                or item.get('proposed_literal') != check.get('proposed')
                                or item.get('observed_literal') != check.get('current')):
                            raise ValueError('Prior literal observation does not match its exact check')
                elif check_field == 'applied_repairs':
                    from pipeline import source_repairs
                    registered = editorial.read(job / 'source.json')['registry_source']
                    for check in checks:
                        if (source_repairs.verify(registered, check) != check
                                or observed[check['key']].get('observed_literal') != check.get('after')):
                            raise ValueError('Prior repair proof no longer matches the source')
                elif check_field == 'metadata_checks':
                    _verify_missing_page_metadata(job, checks)
                    for check in checks:
                        if observed[check['key']].get('observed_value') != check.get('expected_value'):
                            raise ValueError('Prior metadata observation differs from its check')
                else:
                    _verify_transcription_checks(job, checks)
                    for check in checks:
                        if observed[check['key']].get('observed_literal') != check.get('current'):
                            raise ValueError('Prior transcription observation differs from its check')
            except (OSError, ValueError, KeyError, ImportError, TypeError):
                continue
            required[disposition].update(keys)
    return required


def _verify_literal_checks(job, checks):
    """Validate exact current corpus spans and original source pixels for literal checks."""
    job = Path(job)
    source = editorial.read(job / 'source.json')['registry_source']
    keys = {f['key'] for f in editorial.read(job / 'source_findings.json')['findings']}
    needed = {item.get('pdf_page') for item in checks}
    pages = {}
    with Path(source['corpus_path']).open() as corpus:
        for line in corpus:
            page = json.loads(line)
            number = page.get('pdf_page_1based')
            if number in needed:
                if number in pages:
                    raise ValueError('Literal source page identity is ambiguous')
                pages[number] = page
    scans = []
    for check in checks:
        page = pages.get(check.get('pdf_page'), {})
        offset, current, proposed = (check.get('text_offset'), check.get('current'),
                                    check.get('proposed'))
        if (check.get('key') not in keys or type(offset) is not int or offset < 0
                or not isinstance(current, str) or not current
                or not isinstance(proposed, str) or not proposed or proposed == current
                or page.get('text', '')[offset:offset + len(current)] != current
                or page.get('source_sha256') != check.get('source_pixel_sha256')
                or not page.get('source_scan')):
            raise ValueError('Literal check is not bound to its current corpus occurrence')
        scans.append({'path': page['source_scan'], 'pdf_page': check['pdf_page'],
                      'source_pixel_sha256': check['source_pixel_sha256']})
    editorial.source_scan_attachments(scans)
    return checks


def _article_path_node(article, path):
    if (not isinstance(path, str)
            or not re.fullmatch(r'article(?:\.[A-Za-z_][A-Za-z0-9_]*|\[\d+\])+', path)):
        raise ValueError('Independent support must name an exact article path')
    tokens = re.findall(r'[^.\[\]]+|\[\d+\]', path[len('article.'):])
    node = article
    for token in tokens:
        if token.startswith('['):
            node = node[int(token[1:-1])]
        else:
            node = node[token]
    return node


def _identity_support_valid(article, dossier, finding_result, observation):
    paths = observation.get('claim_paths', [])
    by_path = {item.get('article_path'): item for item in paths}
    if len(by_path) != len(paths):
        return False
    if set(finding_result.get('affected_paths', [])) != set(by_path):
        return False
    if not paths:
        # An empty affected-claim inventory is a substantive independent judgment,
        # not a shortcut. Bind it to the exact complete candidate pair and require
        # the reviewer to attest that both article and dossier were checked.
        return bool(
            observation.get('independent_support') is True
            and observation.get('whole_candidate_reviewed') is True
            and observation.get('reviewed_article_hash') == editorial.digest(article)
            and observation.get('reviewed_dossier_hash') == editorial.digest(dossier)
            and re.search(r'no (?:(?:article or dossier)|(?:article and dossier)|candidate) claim.{0,120}(?:depend|rely|use)',
                          str(observation.get('support_reason', '')), re.I)
            and re.search(r'(?:article (?:and|or) dossier|both (?:the )?article and dossier|entire candidate)',
                          str(observation.get('support_reason', '')), re.I)
        )
    dossier_ids = {e.get('id') for e in dossier.get('evidence', [])}
    for path, item in by_path.items():
        try:
            node = _article_path_node(article, path)
        except (KeyError, IndexError, TypeError, ValueError):
            return False
        cited = set()
        text_parts = []
        def collect(value):
            if isinstance(value, dict):
                cited.update(value.get('evidence_ids', []))
                if isinstance(value.get('text'), str):
                    text_parts.append(value['text'])
                for child in value.values():
                    if isinstance(child, (dict, list)):
                        collect(child)
            elif isinstance(value, list):
                for child in value:
                    collect(child)
        collect(node)
        ids = item.get('independent_evidence_ids', [])
        if (not item.get('claim_text') or not any(item['claim_text'] in text for text in text_parts)
                or not ids or len(ids) != len(set(ids))
                or not set(ids) <= cited or not set(ids) <= dossier_ids):
            return False
    return bool(observation.get('independent_support') is True
                and observation.get('support_reason'))


def _source_gap_support_valid(article, dossier, finding_result, observation):
    """A no-claim source-gap disposition must attest and bind the whole exact pair."""
    return (observation.get('whole_candidate_reviewed') is True
            and observation.get('reviewed_article_hash') == editorial.digest(article)
            and observation.get('reviewed_dossier_hash') == editorial.digest(dossier)
            and _identity_support_valid(article, dossier, finding_result, observation))


def _validate_codex_object_schema(schema, path='$'):
    """Fail locally when strict Codex structured output would reject an object schema."""
    if isinstance(schema, dict):
        if schema.get('type') == 'object' and isinstance(schema.get('properties'), dict):
            required = schema.get('required')
            if not isinstance(required, list) or not set(schema['properties']) <= set(required):
                missing = sorted(set(schema['properties']) - set(required or []))
                raise ValueError(f'Codex strict schema requires every object property at {path}: {missing}')
        for key, value in schema.items():
            _validate_codex_object_schema(value, f'{path}.{key}')
    elif isinstance(schema, list):
        for index, value in enumerate(schema):
            _validate_codex_object_schema(value, f'{path}[{index}]')


def _source_findings_pending(job):
    """Retain findings; only an exact independent resolution can release their gate."""
    job = Path(job)
    findings_path = job / "source_findings.json"
    if not findings_path.exists():
        return False
    findings = editorial.read(findings_path)
    if not findings.get("requires_coordinator_verification"):
        return False
    resolution_path = job / "source_resolution.json"
    if not resolution_path.exists():
        return True
    resolution = editorial.read(resolution_path)
    if (resolution.get("findings_hash") != editorial.digest(findings)
            or resolution.get("article_hash") != editorial.digest(editorial.read(job / "article.json"))
            or resolution.get("dossier_hash") != editorial.digest(editorial.read(job / "dossier.json"))
            or resolution.get("model") != "gpt-6-luna" or resolution.get("reasoning") != "low"):
        return True
    review_path = job / resolution["review_path"]
    if not review_path.is_file() or editorial.digest(editorial.read(review_path)) != resolution.get("result_hash"):
        return True
    result = editorial.read(review_path)
    transcription_keys = {f['key'] for f in result['findings']
                          if f['disposition'] == 'verified_transcription_matches_corpus'}
    transcriptions = resolution.get('transcription_checks', [])
    if transcription_keys or transcriptions:
        try:
            _verify_transcription_checks(job, transcriptions)
            observations = result.get('transcription_observations', [])
            observed = {o['key']: o for o in observations}
            if (transcription_keys != {c['key'] for c in transcriptions}
                    or set(observed) != transcription_keys or len(observed) != len(observations)):
                return True
            for check in transcriptions:
                item = observed[check['key']]
                if check.get('occurrences'):
                    occurrence_checks = check['occurrences']
                    occurrence_observations = item.get('occurrence_observations', [])
                    by_id = {observation.get('id'): observation for observation in occurrence_observations}
                    if (len(by_id) != len(occurrence_observations)
                            or set(by_id) != {occurrence.get('id') for occurrence in occurrence_checks}
                            or any(by_id[occurrence['id']].get('observed_literal') != occurrence['current']
                                   for occurrence in occurrence_checks)):
                        return True
                elif item.get('observed_literal') != check.get('current'):
                    return True
        except (OSError, ValueError, KeyError, ImportError):
            return True
    source_claim_keys = {f['key'] for f in result['findings']
                         if f['disposition'] == 'verified_source_claim'}
    source_claims = resolution.get('source_claim_checks', [])
    if source_claim_keys or source_claims:
        try:
            verified = _verify_source_claim_checks(job, source_claims,
                                                   resolution.get('source_scan_images', []))
            observations = result.get('source_claim_observations', [])
            observed = {o['key']: o for o in observations}
            if (verified != source_claims
                    or source_claim_keys != {c['key'] for c in verified}
                    or set(observed) != source_claim_keys or len(observed) != len(observations)):
                return True
            for check in verified:
                item = observed[check['key']]
                if item.get('supported') is not True:
                    return True
        except (OSError, ValueError, KeyError, TypeError):
            return True
    identity_keys = {f['key'] for f in result['findings']
                     if f['disposition'] == 'unresolved_identity_not_used'}
    if identity_keys:
        expected_identity_keys = {f['key'] for f in findings['findings']
                                  if _source_finding_class(f) == 'identity_gap'}
        observations = result.get('identity_observations', [])
        observed = {o['key']: o for o in observations}
        by_key = {f['key']: f for f in result['findings']}
        dossier = editorial.read(job / 'dossier.json')
        article = editorial.read(job / 'article.json')
        if (not identity_keys <= expected_identity_keys
                or set(observed) != expected_identity_keys or len(observed) != len(observations)
                or any(not _identity_support_valid(article, dossier, by_key[key], observed[key])
                       for key in identity_keys)):
            return True
    historical = _historical_checked_keys(job)
    historical_keys = set().union(*historical.values()) if historical else set()
    source_gap_keys = {f['key'] for f in result['findings']
                       if f['disposition'] == 'source_gap_not_used'}
    if source_gap_keys:
        expected_source_gap_keys = {f['key'] for f in findings['findings']
                                    if _source_finding_class(f) == 'primary_access_gap'}
        observations = result.get('source_gap_observations', [])
        observed = {o['key']: o for o in observations}
        by_key = {f['key']: f for f in result['findings']}
        dossier = editorial.read(job / 'dossier.json')
        article = editorial.read(job / 'article.json')
        if (not source_gap_keys <= expected_source_gap_keys
                or bool(source_gap_keys & historical_keys)
                or set(observed) != expected_source_gap_keys or len(observed) != len(observations)
                or any(not _source_gap_support_valid(article, dossier, by_key[key], observed[key])
                       for key in source_gap_keys)):
            return True
    dispositions = {f['key']: f['disposition'] for f in result['findings']}
    for disposition, keys in historical.items():
        if any(dispositions.get(key) != disposition for key in keys):
            return True
    if any(item['disposition'] == 'verified_source_claim'
           and _source_finding_class(next((f for f in findings['findings']
                                           if f['key'] == item['key']), {})) != 'primary_access_gap'
           for item in result['findings']):
        return True
    metadata_keys = {f['key'] for f in result['findings']
                     if f['disposition'] == 'verified_metadata_not_extracted'}
    metadata_checks = resolution.get('metadata_checks', [])
    if metadata_keys or metadata_checks:
        try:
            _verify_missing_page_metadata(job, metadata_checks)
            observations = result.get('metadata_observations', [])
            observed = {o['key']: o for o in observations}
            if (metadata_keys != {c['key'] for c in metadata_checks}
                    or set(observed) != metadata_keys or len(observed) != len(observations)
                    or any(observed[c['key']].get('observed_value') != c['expected_value']
                           for c in metadata_checks)):
                return True
        except (OSError, ValueError, KeyError, ImportError):
            return True
    checks = resolution.get('literal_checks', [])
    rejected_keys = {f['key'] for f in result['findings']
                     if f['disposition'] == 'rejected_proposal_scan_matches_corpus'}
    if not rejected_keys <= {check['key'] for check in checks}:
        return True
    if checks:
        observations = result.get('literal_observations', [])
        if len(observations) != len(checks) or len({o['key'] for o in observations}) != len(checks):
            return True
        observed = {o['key']: o for o in observations}
        dispositions = {f['key']: f['disposition'] for f in result['findings']}
        for check in checks:
            item = observed.get(check['key'], {})
            if (item.get('current_corpus_literal') != check['current']
                    or item.get('proposed_literal') != check['proposed']
                    or dispositions.get(check['key']) != 'rejected_proposal_scan_matches_corpus'
                    or item.get('observed_literal') != check['current']):
                return True
    repairs = resolution.get('applied_repairs', [])
    repaired_keys = {f['key'] for f in result['findings']
                     if f['disposition'] == 'applied_repair_scan_matches_corpus'}
    if repaired_keys:
        from pipeline import source_repairs
        try:
            registered = editorial.read(job / 'source.json')['registry_source']
            observations = result.get('repair_observations', [])
            observed = {o['key']: o for o in observations}
            if len(observed) != len(observations) or set(observed) != repaired_keys or repaired_keys != {r['key'] for r in repairs}:
                return True
            for repair in repairs:
                if (source_repairs.verify(registered, repair) != repair
                        or observed.get(repair['key'], {}).get('observed_literal') != repair['after']):
                    return True
        except (OSError, ValueError, KeyError, ImportError):
            return True
    validation_path = job / 'source_resolution_validation.json'
    if validation_path.is_file():
        validation = editorial.read(validation_path)
        if (validation.get('result_hash') == editorial.digest(result)
                and validation.get('status') == 'rejected'):
            return True
    meta_path = review_path.parent / 'meta.json'
    if not meta_path.is_file():
        return True
    meta = editorial.read(meta_path)
    if (meta.get('role') != 'source_resolution' or meta.get('status') != 'complete'
            or meta.get('model') != 'gpt-6-luna' or meta.get('reasoning') != 'low'
            or meta.get('result_hash') != editorial.digest(result)):
        return True
    keys = [item["key"] for item in result["findings"]]
    return (len(keys) != len(set(keys)) or set(keys) != {item["key"] for item in findings["findings"]}
            or any(item["disposition"] not in ("unresolved_identity_not_used",
                    "source_gap_not_used",
                    "rejected_proposal_scan_matches_corpus", "applied_repair_scan_matches_corpus",
                    "verified_metadata_not_extracted", "verified_transcription_matches_corpus",
                    "verified_source_claim")
                   for item in result["findings"]))


def refresh_source_resolution_status(job):
    """Keep the saved status aligned with the current exact source-resolution gate."""
    job = Path(job)
    pending = _source_findings_pending(job)
    state_path = job / 'status.json'
    if state_path.is_file():
        state = editorial.read(state_path)
        if state.get('status') in ('approved', 'needs_source_verification'):
            desired = 'needs_source_verification' if pending else 'approved'
            if state.get('status') != desired or state.get('source_verification_pending') != pending:
                state.update(status=desired, source_verification_pending=pending)
                editorial.write(state_path, state)
    return pending


def auto_resolve_source_findings(job, runner, source_context=None, transcription_checks=None):
    """Run one separate source-resolution stage for a newly reviewed exact pair."""
    job = Path(job)
    article, dossier = editorial.read(job / 'article.json'), editorial.read(job / 'dossier.json')
    reviews = editorial.read(job / 'reviews.json')
    editorial.validate_reviews(article, dossier, reviews)
    findings_path = job / 'source_findings.json'
    if not findings_path.is_file():
        return {'status': 'not_required'}
    findings = editorial.read(findings_path)
    if not findings.get('requires_coordinator_verification'):
        return {'status': 'not_required', 'findings_hash': editorial.digest(findings)}
    state_path = job / 'status.json'
    state = editorial.read(state_path)
    original_status = state.get('status')
    if original_status not in ('approved', 'needs_source_verification', 'published'):
        return {'status': 'held', 'reason': 'candidate reviews or source evidence are not approved'}
    if original_status == 'published':
        audit_path = job / 'source_audit.json'
        if not audit_path.is_file():
            return {'status': 'held', 'reason': 'published candidate has no current source audit'}
        audit = editorial.read(audit_path)
        saved_source = editorial.read(job / 'source.json')
        if (audit.get('verified') is not True
                or audit.get('article_hash') != editorial.digest(article)
                or audit.get('dossier_hash') != editorial.digest(dossier)
                or state.get('source_id') != saved_source.get('source_id')
                or state.get('source_audit_hash') != editorial.digest(audit)):
            return {'status': 'held', 'reason': 'published candidate source audit is not bound to the reviewed pair'}
    before = {'article_hash': editorial.digest(article), 'dossier_hash': editorial.digest(dossier),
              'reviews_hash': editorial.digest(reviews), 'findings_hash': editorial.digest(findings)}
    attempt_path = (job / 'source-resolution-auto'
                    / f"{before['article_hash'][:12]}-{before['dossier_hash'][:12]}-{before['findings_hash'][:12]}.json")
    if attempt_path.is_file():
        return {**editorial.read(attempt_path), 'status': 'already_attempted'}
    try:
        if transcription_checks is None:
            proof_path = job / 'verified_raw_occurrence_proofs.json'
            transcription_checks = []
            if proof_path.is_file():
                for proof in editorial.read(proof_path).get('proofs', []):
                    verified = validate_correct_raw_occurrence_receipt(
                        job, proof['finding_key'], proof['receipt_path'], proof['occurrence_ids'])
                    transcription_checks.append(verified['transcription_check'])
        if transcription_checks:
            receipt = resolve_source_findings(job, runner, source_context=source_context,
                                              transcription_checks=transcription_checks)
        else:
            receipt = resolve_source_findings(job, runner, source_context=source_context)
        state = editorial.read(state_path)
        final_article, final_dossier = editorial.read(job / 'article.json'), editorial.read(job / 'dossier.json')
        final_reviews = editorial.read(job / 'reviews.json')
        if (editorial.digest(final_article) != before['article_hash']
                or editorial.digest(final_dossier) != before['dossier_hash']
                or editorial.digest(final_reviews) != before['reviews_hash']):
            raise ValueError('Source resolution changed the reviewed article, dossier or approvals')
        pending = _source_findings_pending(job)
        if pending:
            state.update(status='needs_source_verification', source_verification_pending=True)
            editorial.write(state_path, state)
        result_status = ('needs_source_verification' if pending else
                         ('published' if original_status == 'published' else 'approved'))
        record = {**before, 'source_resolution_hash': editorial.digest(receipt),
                  'source_resolution_result_hash': receipt['result_hash'],
                  'status': result_status,
                  'resolved_at': datetime.now(timezone.utc).isoformat(),
                  'creates_or_changes_authorship_or_review': False}
    except Exception as exc:
        state = editorial.read(state_path)
        state.update(status='needs_source_verification', source_verification_pending=True)
        editorial.write(state_path, state)
        record = {**before, 'status': 'needs_source_verification', 'error': str(exc),
                  'attempted_at': datetime.now(timezone.utc).isoformat(),
                  'creates_or_changes_authorship_or_review': False}
    editorial.write(attempt_path, record)
    state = editorial.read(state_path)
    state['source_resolution_auto_path'] = str(attempt_path.relative_to(job))
    state['source_resolution_auto_hash'] = editorial.digest(record)
    editorial.write(state_path, state)
    return record


def _retained_source_checks(job):
    """Reuse only exact prior observation payloads whose source checks still verify."""
    job = Path(job)
    receipt_path = job / 'source_resolution.json'
    if not receipt_path.is_file():
        return {}
    receipt = editorial.read(receipt_path)
    checked = _historical_checked_keys(job)
    fields = {
        'literal_checks': ('literal_checks', 'rejected_proposal_scan_matches_corpus'),
        # The saved receipt names producer results, while the resolver API accepts
        # the same checks under repair_checks. Do not splat the receipt key into
        # resolve_source_findings (which would fail before its model stage).
        'applied_repairs': ('repair_checks', 'applied_repair_scan_matches_corpus'),
        'metadata_checks': ('metadata_checks', 'verified_metadata_not_extracted'),
        'transcription_checks': ('transcription_checks', 'verified_transcription_matches_corpus'),
    }
    reusable = {}
    for receipt_field, (argument_name, disposition) in fields.items():
        checks = receipt.get(receipt_field, [])
        if checks and {item.get('key') for item in checks} <= checked[disposition]:
            reusable[argument_name] = copy.deepcopy(checks)
    return reusable


def _retained_finding_scans(job, source):
    """Resolve marked PDF pages to exact current corpus scans for bounded review."""
    job = Path(job)
    checkpoint_path = job / 'source_checkpoint.json'
    scans = []
    if checkpoint_path.is_file():
        scans.extend(copy.deepcopy(editorial.read(checkpoint_path).get('locator', {}).get('source_scan_images', [])))
    findings_path = job / 'source_findings.json'
    if not findings_path.is_file():
        return scans
    pages_needed = set()
    for finding in editorial.read(findings_path).get('findings', []):
        text = ' '.join(str(finding.get(field, '')) for field in ('title', 'details', 'verification'))
        pages_needed.update(int(value) for value in re.findall(
            r'\bPDF(?:\s+page)?\s*(?:p\.?\s*)?(\d+)\b', text, re.I))
    if pages_needed:
        with Path(source['corpus_path']).open() as corpus:
            for line in corpus:
                page = json.loads(line)
                if (page.get('pdf_page_1based') in pages_needed and page.get('source_scan')
                        and page.get('source_sha256')):
                    scans.append({'path': page['source_scan'], 'pdf_page': page['pdf_page_1based'],
                                  'source_pixel_sha256': page['source_sha256'],
                                  'printed_page': page.get('printed_page')})
    unique = {}
    for scan in scans:
        key = (str(Path(scan['path']).resolve()), scan.get('pdf_page'), scan.get('source_pixel_sha256'))
        unique[key] = scan
    return list(unique.values())


def revalidate_published_source_jobs(jobs, runner, root=ROOT, workers=1, republish=True, plan_only=False):
    """Freshly resolve retained source findings for unchanged, exactly published pairs.

    Jobs are deduplicated by character and exact article/dossier hashes. Each candidate
    must still equal the canonical pair and retain its exact reviews and verified source
    audit. Prior literal/repair/metadata/transcription checks are replayed only when the
    current source-bound receipt validates them. Successful formerly-published jobs are
    returned through the ordinary publication gate; this function never edits authored
    article, dossier or review data.
    """
    if runner.model != 'gpt-6-luna' or runner.reasoning != 'low':
        raise ValueError('Source-only revalidation requires gpt-6-luna low')
    if workers < 1:
        raise ValueError('workers must be positive')
    candidates, seen = [], set()
    for raw_job in jobs:
        job = Path(raw_job)
        try:
            article, dossier = editorial.read(job / 'article.json'), editorial.read(job / 'dossier.json')
            character = article['character']
            pair = (character, editorial.digest(article), editorial.digest(dossier))
            canonical, canonical_dossier = _canonical(root, character)
            if (pair[1] != editorial.digest(canonical)
                    or pair[2] != editorial.digest(canonical_dossier)):
                candidates.append((job, None, {'status': 'skipped', 'reason': 'canonical_pair_mismatch'}))
                continue
            if pair in seen:
                candidates.append((job, None, {'status': 'skipped', 'reason': 'duplicate_exact_pair'}))
                continue
            seen.add(pair)
            state = editorial.read(job / 'status.json')
            if state.get('status') not in ('published', 'approved', 'needs_source_verification'):
                candidates.append((job, None, {'status': 'skipped', 'reason': 'not_a_published_pair'}))
                continue
            reviews = editorial.read(job / 'reviews.json')
            editorial.validate_reviews(article, dossier, reviews)
            audit_path = job / 'source_audit.json'
            audit = editorial.read(audit_path)
            saved = editorial.read(job / 'source.json')
            source = saved['registry_source']
            if (audit.get('verified') is not True
                    or state.get('source_audit_hash') != editorial.digest(audit)
                    or not _recorded_source_hash_matches(audit.get('source_hash'),
                        saved.get('registry_source'), source)
                    or not _article_used_book_evidence(audit, article, dossier)):
                candidates.append((job, None, {'status': 'skipped', 'reason': 'source_audit_not_current'}))
                continue
            findings = job / 'source_findings.json'
            if not findings.is_file() or not editorial.read(findings).get('requires_coordinator_verification'):
                candidates.append((job, None, {'status': 'skipped', 'reason': 'no_source_findings'}))
                continue
            pending = _source_findings_pending(job)
            if not pending:
                if (state.get('status') in ('approved', 'published') and state.get('published_at')
                        and state.get('canonical_entry')):
                    candidates.append((job, source, {'status': 'ready', 'action': 'publish_only',
                        'pair': pair, 'original_status': 'published', 'checks': {},
                        'article_hash': pair[1], 'dossier_hash': pair[2],
                        'reviews_hash': editorial.digest(reviews)}))
                else:
                    candidates.append((job, None, {'status': 'skipped', 'reason': 'source_gate_already_current'}))
                continue
            candidates.append((job, source, {'status': 'ready', 'pair': pair,
                'original_status': state.get('status'), 'checks': _retained_source_checks(job),
                'article_hash': pair[1], 'dossier_hash': pair[2],
                'reviews_hash': editorial.digest(reviews)}))
        except (OSError, ValueError, KeyError, TypeError, editorial.ValidationError) as exc:
            candidates.append((job, None, {'status': 'skipped', 'reason': 'invalid_candidate', 'error': str(exc)}))

    if plan_only:
        return [{'job': str(job), **{k: v for k, v in info.items() if k not in ('pair', 'checks')},
                 'replayed_check_counts': {key: len(value) for key, value in info.get('checks', {}).items()}}
                for job, _, info in candidates]

    def process(candidate):
        job, source, info = candidate
        if info['status'] != 'ready':
            return {'job': str(job), **{k: v for k, v in info.items() if k != 'checks'}}
        pair = info['pair']
        attempt_root = job / 'source-only-revalidation' / f'{pair[1][:12]}-{pair[2][:12]}'
        attempt_dir = attempt_root
        summary_path = attempt_dir / 'summary.json'
        lock_dir = Path(root) / 'runs' / '.locks'
        lock_dir.mkdir(parents=True, exist_ok=True)
        claim_path = lock_dir / f"source-{_research_source_hash(source)[:16]}-{ord(pair[0]):04X}.lock"
        try:
            with claim_path.open('a') as claim:
                try:
                    fcntl.flock(claim, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    return {'job': str(job), 'status': 'already_running', 'lock': str(claim_path)}
                with (job / 'coordinator.lock').open('a') as lock:
                    try:
                        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    except BlockingIOError:
                        return {'job': str(job), 'status': 'already_running',
                                'lock': str(job / 'coordinator.lock')}
                    try:
                        if attempt_root.exists():
                            prior_summaries = [attempt_root / 'summary.json',
                                               *sorted(attempt_root.glob('attempt-*/summary.json'))]
                            prior_summaries = [path for path in prior_summaries if path.is_file()]
                            latest = editorial.read(prior_summaries[-1]) if prior_summaries else {}
                            terminal_success = latest.get('status') == 'published'
                            terminal_nonpending = (not latest.get('pending')
                                and latest.get('status') != 'failed'
                                and info.get('action') != 'publish_only')
                            if prior_summaries and (terminal_success or terminal_nonpending):
                                return {'job': str(job), **latest, 'status': 'already_attempted'}
                            attempt_number = 2
                            while (attempt_root / f'attempt-{attempt_number:02d}').exists():
                                attempt_number += 1
                            attempt_dir = attempt_root / f'attempt-{attempt_number:02d}'
                            summary_path = attempt_dir / 'summary.json'
                        attempt_dir.mkdir(parents=True, exist_ok=True)
                        current, current_dossier = editorial.read(job / 'article.json'), editorial.read(job / 'dossier.json')
                        reviews = editorial.read(job / 'reviews.json')
                        if (editorial.digest(current) != info['article_hash']
                                or editorial.digest(current_dossier) != info['dossier_hash']
                                or editorial.digest(reviews) != info['reviews_hash']):
                            raise ValueError('Exact approved pair changed before source-only review')
                        canonical, canonical_dossier = _canonical(root, pair[0])
                        if (editorial.digest(canonical) != info['article_hash']
                                or editorial.digest(canonical_dossier) != info['dossier_hash']):
                            raise ValueError('Canonical pair changed before source-only review')
                        prior_receipt = job / 'source_resolution.json'
                        if prior_receipt.is_file():
                            shutil.copy2(prior_receipt, attempt_dir / 'prior-source-resolution.json')
                        prior_status = job / 'status.json'
                        if prior_status.is_file():
                            shutil.copy2(prior_status, attempt_dir / 'prior-status.json')
                        editorial.write(attempt_dir / 'inputs.json', {
                            'article_hash': info['article_hash'], 'dossier_hash': info['dossier_hash'],
                            'reviews_hash': editorial.digest(reviews),
                            'findings_hash': editorial.digest(editorial.read(job / 'source_findings.json')),
                            'replayed_check_counts': {key: len(value) for key, value in info['checks'].items()},
                        })
                        summary = None
                        if info.get('action') == 'publish_only':
                            summary = {'status': 'approved', 'article_hash': info['article_hash'],
                                'dossier_hash': info['dossier_hash'],
                                'source_resolution_hash': editorial.digest(editorial.read(job / 'source_resolution.json')),
                                'pending': False, 'scan_count': 0,
                                'creates_or_changes_authorship_or_review': False}
                        else:
                            local_runner = copy.copy(runner)
                            inherited = tuple(getattr(runner, 'inherited_lock_fds', ()))
                            local_runner.inherited_lock_fds = tuple(dict.fromkeys(
                                (*inherited, claim.fileno(), lock.fileno())))
                            scan_context = _retained_finding_scans(job, source)
                            receipt = resolve_source_findings(job, local_runner, source_context=scan_context,
                                                              **info['checks'])
                            pending = _source_findings_pending(job)
                            summary = {'status': 'needs_source_verification' if pending else 'approved',
                                'article_hash': info['article_hash'], 'dossier_hash': info['dossier_hash'],
                                'result_hash': receipt['result_hash'], 'source_resolution_hash': editorial.digest(receipt),
                                'pending': pending, 'scan_count': len(scan_context),
                                'creates_or_changes_authorship_or_review': False}
                        if (summary.get('status') == 'approved' and info['original_status'] == 'published'
                                and republish):
                            state = editorial.read(job / 'status.json')
                            if state.get('issue_sync_status') == 'synced':
                                if state.get('status') == 'published':
                                    state['status'] = 'approved'
                                    state['source_revalidation_cleared_at'] = datetime.now(timezone.utc).isoformat()
                                    editorial.write(job / 'status.json', state)
                                summary['publication'] = _publish_job_locked(job, source, root)
                                summary['status'] = summary['publication']['status']
                            else:
                                summary['publication'] = {'status': 'pending_issue_sync'}
                        editorial.write(summary_path, summary)
                        return {'job': str(job), **summary}
                    except Exception as exc:
                        summary = {'status': 'failed', 'error': str(exc),
                            'article_hash': info['article_hash'], 'dossier_hash': info['dossier_hash'],
                            'creates_or_changes_authorship_or_review': False}
                        editorial.write(summary_path, summary)
                        return {'job': str(job), **summary}
                    finally:
                        fcntl.flock(lock, fcntl.LOCK_UN)
        except OSError as exc:
            return {'job': str(job), 'status': 'failed', 'error': str(exc)}

    if workers == 1:
        return [process(candidate) for candidate in candidates]
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(process, candidates))


def resolve_source_findings(job, runner, source_context=None, literal_checks=None, repair_checks=None,
                            metadata_checks=None, transcription_checks=None, source_claim_checks=None):
    """Check whether retained uncertainty is immaterial; actual OCR errors stay blocked."""
    job = Path(job)
    if runner.model != "gpt-6-luna" or runner.reasoning != "low":
        raise ValueError("Source resolution requires gpt-6-luna low")
    findings = editorial.read(job / "source_findings.json")
    article, dossier = editorial.read(job / "article.json"), editorial.read(job / "dossier.json")
    editorial.validate_reviews(article, dossier, editorial.read(job / "reviews.json"))
    checkpoint = editorial.read(job / "source_checkpoint.json")
    identity_checks = [f for f in findings['findings'] if _source_finding_class(f) == 'identity_gap']
    source_gap_checks = [f for f in findings['findings']
                         if _source_finding_class(f) == 'primary_access_gap']
    article_path_pattern = r'^article(?:\.[A-Za-z_][A-Za-z0-9_]*|\[\d+\])+$'
    schema = {"type": "object", "additionalProperties": False, "required": ["findings"],
        "properties": {"findings": {"type": "array",
            "minItems": len(findings['findings']), "maxItems": len(findings['findings']), "items": {
            "type": "object", "additionalProperties": False,
            "required": ["key", "disposition", "reason", "affected_paths"],
            "properties": {"key": {"type": "string", "enum": [f['key'] for f in findings['findings']]},
                "disposition": {"enum": ["pending", "unresolved_identity_not_used",
                                          "rejected_proposal_scan_matches_corpus", "applied_repair_scan_matches_corpus"]},
                "reason": {"type": "string", "minLength": 1},
                "affected_paths": {"type": "array", "items": {"type": "string"}}}}}}}
    inputs = {"article": article, "dossier": dossier, "findings": findings,
              "feedback": {"source_scan_images": (
                  list(checkpoint["locator"].get("source_scan_images", [])) + list(source_context or []))}}
    if identity_checks:
        schema['properties']['findings']['items']['properties']['affected_paths']['items'] = {
            'type': 'string', 'pattern': article_path_pattern}
        inputs['identity_gap_checks'] = identity_checks
        schema['required'].append('identity_observations')
        schema['properties']['identity_observations'] = {'type': 'array',
            'minItems': len(identity_checks), 'maxItems': len(identity_checks), 'items': {
            'type': 'object', 'additionalProperties': False,
            'required': ['key', 'independent_support', 'claim_paths', 'support_reason',
                         'whole_candidate_reviewed', 'reviewed_article_hash', 'reviewed_dossier_hash'],
                'properties': {'key': {'type': 'string', 'enum': [f['key'] for f in identity_checks]},
                'independent_support': {'type': 'boolean'},
                'whole_candidate_reviewed': {'type': 'boolean'},
                'reviewed_article_hash': {'type': 'string', 'enum': [editorial.digest(article)]},
                'reviewed_dossier_hash': {'type': 'string', 'enum': [editorial.digest(dossier)]},
                'claim_paths': {'type': 'array', 'uniqueItems': True, 'items': {
                    'type': 'object', 'additionalProperties': False,
                    'required': ['article_path', 'claim_text', 'independent_evidence_ids'],
                    'properties': {'article_path': {'type': 'string',
                            'pattern': article_path_pattern},
                        'claim_text': {'type': 'string', 'minLength': 1},
                        'independent_evidence_ids': {'type': 'array', 'minItems': 1,
                            'uniqueItems': True, 'items': {'type': 'string'}}}}},
                'support_reason': {'type': 'string', 'minLength': 1}}}}
        inputs['identity_gap_instruction'] = (
            'For each printed-identity gap, independently decide whether this exact article makes a claim that '
            'depends on assigning the unresolved occurrence a Unicode identity. `unresolved_identity_not_used` '
            'is allowed only when the identity remains unresolved, no claim depends on that identity, and you '
            'inventory every affected claim path and its existing independent evidence IDs. `affected_paths` must '
            'exactly match the article paths you report. For each path, quote a literal substring from that exact '
            'field and copy only evidence IDs present in that field’s own evidence_ids array; do not borrow an ID from '
            'a neighboring formation/uncertainty/component record. Use a path such as '
            '`article.formation`, `article.components[5]`, or `article.uncertainties[0]` (no quote or text after it); '
            'the IDs must independently support the quoted claim without relying on the unresolved specimen. If you cannot identify such support, leave the '
            'finding pending. If neither the exact article nor dossier makes a claim that depends on this identity, '
            'you may report an empty affected_paths and empty claim_paths inventory only after reviewing the complete '
            'article and dossier. Set whole_candidate_reviewed=true and echo the exact reviewed_article_hash and '
            'reviewed_dossier_hash supplied by the packet. In support_reason explicitly state that no article or dossier '
            'claim depends on or uses the unresolved identity. This empty inventory is bound to this exact pair and is '
            'not permitted for literal, applied-repair, metadata or transcription findings. Do not use this disposition '
            'for source access gaps or retained literal/repair checks.')
    if source_gap_checks:
        inputs['source_gap_checks'] = source_gap_checks
        schema['required'].append('source_gap_observations')
        schema['properties']['source_gap_observations'] = {'type': 'array',
            'minItems': len(source_gap_checks), 'maxItems': len(source_gap_checks), 'items': {
            'type': 'object', 'additionalProperties': False,
            'required': ['key', 'independent_support', 'claim_paths', 'support_reason',
                         'whole_candidate_reviewed', 'reviewed_article_hash', 'reviewed_dossier_hash'],
            'properties': {'key': {'type': 'string', 'enum': [f['key'] for f in source_gap_checks]},
                'independent_support': {'type': 'boolean'},
                'whole_candidate_reviewed': {'type': 'boolean'},
                'reviewed_article_hash': {'type': 'string', 'enum': [editorial.digest(article)]},
                'reviewed_dossier_hash': {'type': 'string', 'enum': [editorial.digest(dossier)]},
                'claim_paths': {'type': 'array', 'uniqueItems': True, 'items': {
                    'type': 'object', 'additionalProperties': False,
                    'required': ['article_path', 'claim_text', 'independent_evidence_ids'],
                    'properties': {'article_path': {'type': 'string', 'pattern': article_path_pattern},
                        'claim_text': {'type': 'string', 'minLength': 1},
                        'independent_evidence_ids': {'type': 'array', 'minItems': 1,
                            'uniqueItems': True, 'items': {'type': 'string'}}}}},
                'support_reason': {'type': 'string', 'minLength': 1}}}}
        inputs['source_gap_instruction'] = (
            'For each primary-source access gap, inspect the attached source scans and the complete exact article and dossier. '
            '`source_gap_not_used` is allowed only if no claim in this exact candidate depends on the missing observation. '
            'If a claim does depend on it, report each exact article path, quote a literal substring from that field, and list '
            'only independently supporting evidence IDs actually cited by that field; otherwise leave pending. For an empty '
            'claim list, attest that the whole article and dossier were reviewed and set independent_support=true for that '
            'independent exact-pair judgment; this does not assert a missing source fact. State explicitly that no article or dossier '
            'claim depends on or uses this missing source observation. Echo the exact article and dossier hashes. Do not use this '
            'disposition for OCR/transcription, printed-identity, literal or applied-repair findings. This does not verify or '
            'reject an unread source; it only records whether this exact candidate depends on it.')
    checks = list(literal_checks or [])
    transcription_grouped = any(isinstance(check, dict) and 'occurrences' in check
                                for check in (transcription_checks or []))
    transcriptions = _verify_transcription_checks(job, list(transcription_checks or [])) if transcription_checks else []
    if transcriptions:
        inputs['transcription_checks'] = transcriptions
        inputs['transcription_check_instruction'] = (
            'These are exact existing corpus occurrences, with no proposed replacement. '
            'Read original pixels independently; current is a locator, not your observation. '
            'Report only the exact span, preserving printed character variants and neighbors. '
            'Use null and pending if unclear. verified_transcription_matches_corpus applies '
            'only when the observed literal equals current and this resolves the retained '
            'transcription check. It does not certify a whole page, missing metadata, an '
            'unseen index hit, or the interpretation of a book passage. No OCR repair is claimed.')
        schema['required'].append('transcription_observations')
        if transcription_grouped:
            occurrence_ids = sorted({occurrence['id'] for check in transcriptions
                                     for occurrence in check['occurrences']})
            schema['properties']['transcription_observations'] = {'type': 'array',
                'minItems': len(transcriptions), 'maxItems': len(transcriptions), 'items': {
                'type': 'object', 'additionalProperties': False,
                'required': ['key', 'occurrence_observations', 'pixel_reason'],
                'properties': {'key': {'type': 'string', 'enum': [c['key'] for c in transcriptions]},
                    'occurrence_observations': {'type': 'array', 'minItems': 1,
                        'maxItems': len(occurrence_ids), 'items': {
                        'type': 'object', 'additionalProperties': False,
                        'required': ['id', 'observed_literal', 'pixel_reason'],
                        'properties': {'id': {'type': 'string', 'enum': occurrence_ids},
                            'observed_literal': {'type': ['string', 'null']},
                            'pixel_reason': {'type': 'string', 'minLength': 1}}}},
                    'pixel_reason': {'type': 'string', 'minLength': 1}}}}
            inputs['transcription_check_instruction'] = (
                'A finding may cover several exact current OCR spans. Inspect every listed occurrence '
                'on the attached original scan and report exactly one occurrence_observation for each '
                'listed id, preserving its exact printed literal. Do not infer that one clear span '
                'settles another. Use null when unreadable. verified_transcription_matches_corpus is '
                'valid only when every observed literal equals its matching current literal; this '
                'does not change OCR or certify interpretations elsewhere on the page.')
        else:
            schema['properties']['transcription_observations'] = {'type': 'array',
                'minItems': len(transcriptions), 'maxItems': len(transcriptions), 'items': {
                'type': 'object', 'additionalProperties': False,
                'required': ['key', 'observed_literal', 'pixel_reason'],
                'properties': {'key': {'type': 'string', 'enum': [c['key'] for c in transcriptions]},
                    'observed_literal': {'type': ['string', 'null']},
                    'pixel_reason': {'type': 'string', 'minLength': 1}}}}
    metadata = _verify_missing_page_metadata(job, list(metadata_checks or [])) if metadata_checks else []
    if metadata or transcriptions:
        observations_to_attach = metadata + transcriptions
        scans = [{'path': c['source_scan'], 'pdf_page': c['pdf_page'],
                  'source_pixel_sha256': c['source_pixel_sha256']} for c in observations_to_attach]
        scans.extend(inputs['feedback']['source_scan_images'])
        unique_scans = {}
        for scan in scans:
            unique_scans.setdefault((scan['path'], scan['pdf_page']), scan)
        if len({(c['source_scan'], c['pdf_page']) for c in observations_to_attach}) > 3:
            raise ValueError('Source observations exceed the source attachment budget')
        inputs['feedback']['source_scan_images'] = list(unique_scans.values())
    if metadata:
        inputs['metadata_checks'] = metadata
        inputs['metadata_check_instruction'] = (
            'These are citation metadata omissions, not proposed OCR text replacements. '
            'Independently read each original scan printed-page label. expected_value is '
            'a hypothesis, not your observation. Report observed_value and the visible '
            'label location; use null and pending if unclear. Use verified_metadata_not_extracted '
            'only if the label matches expected_value, the retained finding concerns this '
            'absent metadata field, and no transcription or identity correction is required '
            'to support the affected article claims. This verifies citation provenance only; '
            'the corpus metadata remains absent and no producer repair is claimed.')
        schema['required'].append('metadata_observations')
        schema['properties']['metadata_observations'] = {'type': 'array',
            'minItems': len(metadata), 'maxItems': len(metadata), 'items': {
            'type': 'object', 'additionalProperties': False,
            'required': ['key', 'observed_value', 'pixel_reason'],
            'properties': {'key': {'type': 'string', 'enum': [c['key'] for c in metadata]},
                'observed_value': {'type': ['string', 'null']},
                'pixel_reason': {'type': 'string', 'minLength': 1}}}}
    if checks:
        registered = editorial.read(job / 'source.json')['registry_source']
        needed = {check['pdf_page'] for check in checks}
        pages = {}
        with Path(registered['corpus_path']).open() as corpus:
            for line in corpus:
                page = json.loads(line)
                if page.get('pdf_page_1based') in needed:
                    pages[page['pdf_page_1based']] = page
        for check in checks:
            page = pages[check['pdf_page']]
            start = check['text_offset']
            if (check['current'] == check['proposed']
                    or page['text'][start:start + len(check['current'])] != check['current']
                    or page['source_sha256'] != check['source_pixel_sha256']
                    or check['key'] not in {f['key'] for f in findings['findings']}):
                raise ValueError('Literal source check must match the actual current corpus occurrence')
        inputs['literal_checks'] = checks
        inputs['literal_check_instruction'] = (
            'The current_corpus_literal is a verified current text occurrence, not your scan reading. '
            'Keep current corpus, proposed replacement and observed printed literal separate. '
            'Read the targeted pixels; use unresolved if unclear. Reject a proposal only when '
            'the observed literal equals the current corpus literal and differs from the proposal. '
            'For every finding with a literal_observation, its reason must state the final observed literal '
            'and agree with current_corpus_literal, proposed_literal and observed_literal. If the pixels reject '
            'the proposal, describe the proposal only as rejected; do not say the scan shows the rejected literal. '
            'If the pixels support the proposal, do not describe the current corpus literal as printed. Label any '
            'earlier mistaken hypothesis as a prior proposal, never as the scan reading. Before returning, cross-check '
            'each finding disposition and reason against its exact observation; if they differ or the pixels do not '
            'establish a literal, use pending. A contradictory rationale is not approval.')
        schema['required'].append('literal_observations')
        schema['properties']['literal_observations'] = {'type': 'array',
            'minItems': len(checks), 'maxItems': len(checks), 'items': {
            'type': 'object', 'additionalProperties': False,
            'required': ['key', 'current_corpus_literal', 'proposed_literal', 'observed_literal', 'pixel_reason'],
            'properties': {**{field: {'type': 'string', 'minLength': 1} for field in
                           ['current_corpus_literal', 'proposed_literal', 'observed_literal', 'pixel_reason']},
                           'key': {'type': 'string', 'enum': [check['key'] for check in checks]}}}}
    repairs = []
    if repair_checks:
        from pipeline import source_repairs
        registered = editorial.read(job / 'source.json')['registry_source']
        repairs = [source_repairs.verify(registered, check) for check in repair_checks]
        if len({r['key'] for r in repairs}) != len(repairs) or not {r['key'] for r in repairs} <= {f['key'] for f in findings['findings']}:
            raise ValueError('Applied repairs must identify unique retained findings')
        inputs['applied_repairs'] = repairs
        inputs['applied_repair_instruction'] = (
            'The original before→after proposal was a genuine error, now repaired. '
            'Producer overlays and current consumer occurrences have been validated. '
            'Independently inspect exact original pixels: report the printed literal, not a guess. '
            'observed_literal covers only the changed raw_start/raw_end span, never '
            'the surrounding phrase or a normalized neighboring character. For a '
            'single-character repair report only that character. If unreadable, '
            'return null and disposition pending rather than guessing. '
            'Use applied_repair_scan_matches_corpus only if observed_literal equals after. '
            'Preserve original findings and report pending for unclear pixels or unsupported claims.')
        schema['required'].append('repair_observations')
        schema['properties']['repair_observations'] = {'type': 'array',
            'minItems': len(repairs), 'maxItems': len(repairs), 'items': {
            'type': 'object', 'additionalProperties': False,
            'required': ['key', 'observed_literal', 'pixel_reason'],
            'properties': {'pixel_reason': {'type': 'string', 'minLength': 1},
                           'observed_literal': {'type': ['string', 'null'], 'minLength': 1,
                               'maxLength': max(max(len(r['before']), len(r['after'])) for r in repairs)},
                           'key': {'type': 'string', 'enum': [repair['key'] for repair in repairs]}}}}
    claim_checks = _verify_source_claim_checks(
        job, list(source_claim_checks or []), inputs['feedback']['source_scan_images']) if source_claim_checks else []
    if claim_checks:
        inputs['source_claim_checks'] = claim_checks
        inputs['source_claim_check_instruction'] = (
            'A source-claim check concerns a retained primary-source ACCESS gap, not an OCR identity or replacement. '
            'The attached research result/meta and source pages are provenance-bound, but their conclusions are not '
            'preapproved. Independently inspect the named original page images and compare the exact source entry '
            'with the finding and candidate claim. Return one observation per check. Use verified_source_claim only '
            'when the primary source directly resolves that access gap and supports the affected claim; use the exact '
            'evidence indices and pixel hashes bound to that finding (the schema fixes those values). Otherwise leave the finding pending. '
            'Never use this disposition for a scan transcription, unresolved printed identity, or inference absent from '
            'the cited page. This does not assert an ancient etymology, change OCR, or resolve unrelated findings.')
        schema['required'].append('source_claim_observations')
        schema['properties']['source_claim_observations'] = {'type': 'array',
            'minItems': len(claim_checks), 'maxItems': len(claim_checks),
            'items': {'type': 'object', 'additionalProperties': False,
                'required': ['key', 'supported', 'support_reason'],
                'properties': {'key': {'type': 'string', 'enum': [c['key'] for c in claim_checks]},
                    'supported': {'type': 'boolean'},
                    'support_reason': {'type': 'string', 'minLength': 1}}}}
    allowed_dispositions = ['pending']
    if identity_checks:
        allowed_dispositions.append('unresolved_identity_not_used')
    if source_gap_checks:
        allowed_dispositions.append('source_gap_not_used')
    if checks:
        allowed_dispositions.append('rejected_proposal_scan_matches_corpus')
    if repairs:
        allowed_dispositions.append('applied_repair_scan_matches_corpus')
    if metadata:
        allowed_dispositions.append('verified_metadata_not_extracted')
    if transcriptions:
        allowed_dispositions.append('verified_transcription_matches_corpus')
    if claim_checks:
        allowed_dispositions.append('verified_source_claim')
    schema['properties']['findings']['items']['properties']['disposition']['enum'] = allowed_dispositions
    inputs['disposition_policy'] = (
        'Assess EVERY retained finding exactly once, including findings with no supplied '
        'literal, repair, metadata or transcription check. Those supplied checks are '
        'additional observation contracts, not a filter on the findings array. '
        'A rejected replacement requires a supplied exact literal_checks occurrence and proposal. '
        'An identity gap without such a proposal is not a rejected OCR replacement: '
        'use unresolved_identity_not_used only after independently verifying no article claim '
        'depends on that identity; otherwise pending. Applied repairs require supplied validated '
        'producer/consumer checks. Retain every original finding. '
        'Trace each allegedly affected claim through its actual cited evidence IDs '
        'and read those records. Mentioning a graph also present in an ambiguous scan '
        'does not prove dependence on that ambiguous occurrence: independently '
        'verified transcriptions may support the same graph identity. Conversely, '
        'a plausible alternative is not independent verification. A book citation '
        'may support a whole-graph claim without supporting every adjacent claim '
        'in the same section. For pending, identify the actual affected article '
        'field and explain which necessary support depends on the unresolved '
        'occurrence; do not substitute a scan-file path for a claim location. '
        'Preserve the printed identity gap even when independent support makes '
        'it immaterial to this exact article. A primary-source access gap may be resolved '
        'as verified_source_claim only under the exact source_claim_checks and scan-observation contract.')
    scans = inputs['feedback']['source_scan_images']
    if not scans:
        raise ValueError('Source resolution requires original source scan attachments')
    _validate_codex_object_schema(editorial.agent_schema(schema))
    # Check availability and supplied pixel bindings before spending a review call.
    editorial.source_scan_attachments(scans)
    directory = job / "source-resolution"
    attempt = 1
    while directory.exists():
        directory = job / f'source-resolution-{attempt}'
        attempt += 1
    result = runner.run("source_resolution", inputs, schema, directory)
    keys = [item["key"] for item in result["findings"]]
    if len(keys) != len(set(keys)) or set(keys) != {item["key"] for item in findings["findings"]}:
        raise ValueError("Source resolution must assess every exact finding once")
    # Runner retains the real output; no coordinator-authored verdict is substituted.
    if editorial.read(directory / "result.json") != result:
        raise ValueError("Source resolution differs from saved agent result")
    if claim_checks:
        observations = result.get('source_claim_observations', [])
        observed = {o['key']: o for o in observations}
        dispositions = {f['key']: f['disposition'] for f in result['findings']}
        if len(observed) != len(observations) or set(observed) != {c['key'] for c in claim_checks}:
            raise ValueError('Source claim checks require one independent observation per finding')
        for check in claim_checks:
            item = observed[check['key']]
            if dispositions[check['key']] == 'verified_source_claim':
                if item.get('supported') is not True:
                    raise ValueError('Verified source claim lacks a matching independent observation')
            elif item.get('supported') is True:
                raise ValueError('A supported source claim must use its verified disposition')
    if identity_checks:
        observations = result.get('identity_observations', [])
        observed = {o['key']: o for o in observations}
        dispositions = {f['key']: f['disposition'] for f in result['findings']}
        if len(observed) != len(observations) or set(observed) != {f['key'] for f in identity_checks}:
            raise ValueError('Identity findings require independent claim-support observations')
        for identity_finding in identity_checks:
            key = identity_finding['key']
            if dispositions[key] == 'unresolved_identity_not_used' and not _identity_support_valid(
                    article, dossier, next(f for f in result['findings'] if f['key'] == key), observed[key]):
                raise ValueError('Identity disposition lacks exact independent article-claim support')
    if source_gap_checks:
        observations = result.get('source_gap_observations', [])
        observed = {o['key']: o for o in observations}
        dispositions = {f['key']: f['disposition'] for f in result['findings']}
        if len(observed) != len(observations) or set(observed) != {f['key'] for f in source_gap_checks}:
            raise ValueError('Source access gaps require independent claim-support observations')
        source_gap_dispositions = {f['key'] for f in result['findings']
                                   if f['disposition'] == 'source_gap_not_used'}
        if not source_gap_dispositions <= {f['key'] for f in source_gap_checks}:
            raise ValueError('Only an explicit primary-source access gap may use source_gap_not_used')
        for source_gap in source_gap_checks:
            key = source_gap['key']
            if dispositions[key] == 'source_gap_not_used' and not _source_gap_support_valid(
                    article, dossier, next(f for f in result['findings'] if f['key'] == key), observed[key]):
                raise ValueError('Source-gap disposition lacks exact independent article-claim support')
    record = {"findings_hash": editorial.digest(findings), "article_hash": editorial.digest(article),
              "dossier_hash": editorial.digest(dossier), "result_hash": editorial.digest(result),
              "review_path": str((directory / 'result.json').relative_to(job)), "model": runner.model,
              "reasoning": runner.reasoning, "literal_checks": checks, "applied_repairs": repairs,
              "metadata_checks": metadata, "transcription_checks": transcriptions,
              "source_claim_checks": claim_checks,
              "source_scan_images": inputs['feedback']['source_scan_images'] if claim_checks else []}
    editorial.write(job / "source_resolution.json", record)
    pending = refresh_source_resolution_status(job)
    state = editorial.read(job / 'status.json')
    if not pending and state.get('status') == 'approved':
        state.update(article_hash=editorial.digest(article), dossier_hash=editorial.digest(dossier))
        editorial.write(job / 'status.json', state)
    return record


def _book_identity_matches(label, source):
    title, book_id = source.get('title', ''), source.get('book_id', '')
    return bool((title and re.search(r"(?<!\w)" + re.escape(title) + r"(?!\w)", label))
                or (book_id and book_id in label))


def _source_scan_binding_errors(source, article, dossier):
    from pipeline.source_scan_binding import used_mismatches
    return used_mismatches(source, article, dossier)


def _has_page_provenance(evidence):
    pattern = re.compile(r"(?:\bPDF\s+page\b|\bprinted\s+page\b|\bpages?\b|\bpp?\.?\s*|頁|页)\s*\d+", re.I)
    return any(pattern.search(str(evidence.get(field, '')))
               for field in ('source', 'field', 'text', 'title'))


def _article_used_book_evidence(audit, article, dossier):
    from pipeline.source_adoption import _used_ids
    used = _used_ids(article)
    return any(e.get('id') in used and all(e.get(k) == citation.get(k)
               for k in ('source', 'field', 'text'))
               for citation in audit.get('citations', []) for e in dossier.get('evidence', []))


def _capture_source_audit(job, source, dossier):
    """Require research output to cite the configured book with page provenance."""
    root = Path(job)
    result_paths = sorted(root.glob("**/research/result.json")) + sorted(root.glob("**/research-repair-*/result.json"))
    title = source.get("title", "")
    book_id = source.get("book_id", "")
    pattern = re.compile(r"(?:\bPDF\s+page\b|\bprinted\s+page\b|\bpages?\b|\bpp?\.?\s*|頁|页)\s*\d+", re.I)
    citations = []
    consulted = []
    from pipeline.source_adoption import _used_ids
    article_path = root / "article.json"
    used = _used_ids(editorial.read(article_path)) if article_path.is_file() else set()
    for path in dict.fromkeys(result_paths):
        try:
            raw = editorial.read(path)
            receipt = editorial.read(path.parent / "meta.json")
        except (OSError, ValueError):
            continue
        if not (receipt.get("status") == "complete"
                and receipt.get("role") == "research"
                and receipt.get("model") == "gpt-6-luna"
                and receipt.get("reasoning") == "low"
                and receipt.get("result_hash") == editorial.digest(raw)
                and any(receipt.get("web_action_counts", {}).get(action, 0)
                        for action in ("search", "open_page", "open"))):
            continue
        for item in raw.get("evidence", []):
            source_label = str(item.get("source", ""))
            field = str(item.get("field", ""))
            text = str(item.get("text", ""))
            identity_match = _book_identity_matches(source_label, source)
            page_match = _has_page_provenance(item)
            matching = [e for e in dossier.get("evidence", [])
                        if all(e.get(k) == item.get(k) for k in ("source", "field", "text"))]
            if identity_match and page_match and matching:
                record = {"research_output": str(path.relative_to(root)),
                          "research_receipt_hash": editorial.digest(receipt),
                          "research_result_hash": editorial.digest(raw), "source": source_label,
                          "field": field, "text": text,
                          "evidence_ids": [e['id'] for e in matching]}
                consulted.append(record)
                if any(e['id'] in used for e in matching):
                    citations.append(record)
    audit = {"source_id": source["id"], "source_hash": _research_source_hash(source),
             "verified": bool(citations), "citations": citations, "consulted_citations": consulted}
    editorial.write(root / "source_audit.json", audit)
    return audit


def _triage_and_sync_issues(job, source, runner):
    """Track material job findings when the registered source names a GitHub repository."""
    repository = source.get("github_repo")
    if not repository:
        return {"status": "not_configured", "issues": []}
    from pipeline import issues
    findings = issues.triage_job(job, source, runner)
    receipts = issues.sync(findings, repository, Path(job) / "issue_receipts.json",
                          parent_issue=source.get("issue_parent_number"),
                          milestone=source.get("issue_milestone"),
                          labels=source.get("issue_labels", []),
                          parent_by_kind=source.get("issue_parent_by_kind", {}), active_findings=True)
    record = {"status": "synced", "repository": repository, "issues": receipts,
              "findings_hash": editorial.digest(findings)}
    editorial.write(Path(job) / "issue_sync.json", record)
    return record


def _verified_cohort_jobs(cohort, source, output, root):
    """Reuse only current exact completions, including earlier batch locations."""
    from pipeline.source_progress import report
    audit = report(cohort, source, [Path(root)/'runs', Path(root)/'content/source_coverage',
                                   Path(output)], root)
    verified = {}
    for row in audit['characters']:
        jobs = [Path(item['job']) for item in row['jobs'] if item['verified_source_completion']]
        if jobs:
            requested = job_path(output, source['id'], row['character']).resolve()
            verified[row['character']] = requested if requested in jobs else jobs[0]
    return verified


def status(cohort, source, output, root=ROOT):
    rows = []
    verified = _verified_cohort_jobs(cohort, source, output, root)
    for char in cohort["characters"]:
        job = job_path(output, source["id"], char)
        if char in verified:
            job = verified[char]
            value = "published"
        elif (job / "source.json").is_file() and editorial.read(job / "source.json").get(
                "registry_source_hash") and not _recorded_source_hash_matches(
                    editorial.read(job / "source.json").get("registry_source_hash"),
                    editorial.read(job / "source.json").get("registry_source"), source):
            value = "stale"
        elif (job / "status.json").exists():
            state = editorial.read(job / "status.json")
            value = state.get("status", "unknown")
            if value == "published":
                value = "stale"
            elif value == "approved" and (not (job / "source_audit.json").is_file()
                    or not editorial.read(job / "source_audit.json").get("verified")):
                value = "needs_source_evidence"
        else:
            value = "pending"
        rows.append({"character": char, "source": source["id"], "status": value, "job": str(job)})
    return rows


def prepare(cohort, source, output, limit=3, root=ROOT):
    if limit < 1:
        raise ValueError("Selection limit must be positive")
    rows, selected = [], 0
    verified = _verified_cohort_jobs(cohort, source, output, root)
    for char in cohort["characters"]:
        job = job_path(output, source["id"], char)
        if char in verified:
            rows.append({"character": char, "status": "published", "job": str(verified[char])})
            continue
        if selected >= limit:
            rows.append({"character": char, "status": "deferred", "job": str(job)})
            continue
        try:
            prepare_job(char, job, source, root)
            rows.append({"character": char, "status": "prepared", "job": str(job)})
        except Exception as exc:
            rows.append({"character": char, "status": "failed", "job": str(job), "error": str(exc)})
        selected += 1
    return rows


def _hold_changed_source_inputs(job, state, located):
    current_hash = _locator_hash(located)
    if not state.get('locator_hash') or state['locator_hash'] == current_hash:
        return state
    editorial.write(Path(job) / 'source-refresh-required.json', {
        'previous_state': state, 'current_locator_hash': current_hash,
        'reason': 'Source inputs changed after research; prior exact reviews remain preserved, but fresh source research is required.'})
    held = {**state, 'status': 'needs_source_refresh',
            'source_refresh_required': 'source-refresh-required.json'}
    editorial.write(Path(job) / 'status.json', held)
    return held


def _continuation_inputs(previous, job, character, source, snapshot):
    """Freeze an unfinished draft, preserving canonical anchors and requiring new gates."""
    previous, job = Path(previous).resolve(), Path(job).resolve()
    if previous == job:
        raise ValueError('Continuation requires a fresh source job directory')
    with (previous / 'coordinator.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError('Previous source job still has a live coordinator or agent')
        state = editorial.read(previous / 'status.json')
        provenance = editorial.read(previous / 'source.json')
        if (provenance.get('character') != character or provenance.get('source_id') != source['id']
                or not _same_research_source(provenance['registry_source'], source)
                or provenance.get('article_hash') != snapshot['article_hash']
                or provenance.get('dossier_hash') != snapshot['dossier_hash']):
            raise ValueError('Continuation source or canonical baseline changed')
        if state.get('status') == 'approved':
            located = _load_source_tools().locate_sources(
                {'schema_version': 1, 'sources': [source]}, character,
                editorial.read(previous / 'source_dossier.json'))
            state = _hold_changed_source_inputs(previous, state, located)
        if state.get('status') not in ('failed', 'needs_revision', 'needs_source_refresh',
                                       'needs_source_verification', 'needs_source_evidence',
                                       'needs_source_research'):
            raise ValueError('Continuation requires an unfinished terminal source job')
        article, dossier = editorial.read(previous / 'article.json'), editorial.read(previous / 'dossier.json')
        if article.get('character') != character or dossier.get('character') != character:
            raise ValueError('Continuation character identity differs')
        editorial.validate_article(editorial.assemble_article(article, dossier), dossier)
        receipt = {'previous_job': str(previous), 'article_hash': editorial.digest(article),
                   'dossier_hash': editorial.digest(dossier), 'previous_state_hash': editorial.digest(state),
                   'canonical_article_hash': snapshot['article_hash'],
                   'canonical_dossier_hash': snapshot['dossier_hash'],
                   'requires_fresh_research_and_reviews': True}
        review_path = previous / 'reviews.json'
        proposals = [review for review in editorial.read(review_path)
                     if review.get('article_hash') == receipt['article_hash']
                     and review.get('dossier_hash') == receipt['dossier_hash']
                     and review.get('verdict') == 'revise'] if review_path.exists() else []
        receipt['prior_review_proposals_hash'] = editorial.digest(proposals)
        path = job / 'continuation.json'
        if path.exists() and editorial.read(path) != receipt:
            raise ValueError('Continuation inputs changed; preserve this job and start a fresh one')
        editorial.write(path, receipt)
        editorial.write(job / 'continuation_article.json', article)
        editorial.write(job / 'continuation_dossier.json', dossier)
        editorial.write(job / 'continuation_review_proposals.json', proposals)
        # These are research leads, never reusable source verification or reviews.
        audit_path = previous / 'source_audit.json'
        audit = editorial.read(audit_path) if audit_path.exists() else {}
        retained = {e['id']: e for e in dossier.get('evidence', [])}
        leads = []
        for record in audit.get('consulted_citations', audit.get('citations', [])):
            ids = [eid for eid in record.get('evidence_ids', []) if eid in retained
                   and all(retained[eid].get(k) == record.get(k)
                           for k in ('source', 'field', 'text'))]
            if ids:
                leads.append({**record, 'evidence_ids': ids})
        editorial.write(job / 'continuation_book_leads.json', {
            'previous_job': str(previous), 'previous_audit_hash': editorial.digest(audit),
            'records': leads, 'requires_current_source_research': True})
        return article, dossier


def run(cohort, source, output, runner, limit=3, workers=1, root=ROOT, max_revisions=3,
        publish_now=False, source_context=None, continuation=None, research_context=None,
        retry_attention=False, excluded=()):
    if workers < 1 or limit < 1:
        raise ValueError("Workers and selection limit must be positive")
    queue_dir = Path(output) / source['id']
    with work_queue.supervisor(queue_dir / 'queue.lock'):
        return _run_queue(cohort, source, output, runner, limit, workers, root,
                          max_revisions, publish_now, source_context, continuation,
                          research_context, retry_attention, excluded)


def _run_queue(cohort, source, output, runner, limit, workers, root, max_revisions,
               publish_now, source_context, continuation, research_context, retry_attention, excluded):
    verified = _verified_cohort_jobs(cohort, source, output, root)
    queue_path = Path(output) / source['id'] / 'queue.json'
    previous_identity = editorial.read(queue_path)['identity'] if queue_path.exists() else {}
    # Omitted optional contexts resume their frozen queue values. Explicitly changed
    # contexts require a fresh queue, just as changed per-job research inputs do.
    source_context = source_context if source_context is not None else previous_identity.get('source_context')
    research_context = research_context if research_context is not None else previous_identity.get('research_context')
    continuation = continuation if continuation is not None else previous_identity.get('continuation')
    queue = work_queue.Queue(queue_path, {
        'characters': cohort['characters'], 'source_hash': _research_source_hash(source),
        'root': str(Path(root).resolve()), 'source_context': source_context,
        'continuation': str(continuation) if continuation else None,
        'research_context': research_context})
    queue.state['agent_capacity'] = getattr(getattr(runner, 'agent_slots', None), 'capacity', workers)

    def process_unlocked(char, runner):
        job = job_path(output, source["id"], char)

        def sync_findings(state):
            try:
                issue_sync = _triage_and_sync_issues(job, source, runner)
            except Exception as exc:
                issue_sync = {"status": "pending", "repository": source.get("github_repo"),
                              "error": str(exc)}
                if getattr(exc, 'stderr', None):
                    issue_sync['command_stderr'] = exc.stderr
                editorial.write(job / "issue_sync.json", issue_sync)
            if issue_sync["status"] == "pending":
                state["issue_sync_status"] = "pending"
                editorial.write(job / "status.json", state)
                return issue_sync
            state["issue_sync_status"] = issue_sync["status"]
            state["issue_receipts_hash"] = editorial.digest(issue_sync.get("issues", []))
            editorial.write(job / "status.json", state)
            return issue_sync

        def complete_approval(state):
            issue_sync = sync_findings(state)
            if issue_sync["status"] == "pending":
                return {"character": char, "status": "pending_issue_sync", "job": str(job),
                        "error": issue_sync.get("error")}
            if publish_now:
                return _publish_job_locked(job, source, root)
            return {"character": char, "status": "approved", "job": str(job)}

        try:
            snapshot = prepare_job(char, job, source, root)
            context_path = job / 'research_context.json'
            if research_context is not None:
                if not isinstance(research_context, dict):
                    raise ValueError('Research context must be an object of source leads and findings')
                if context_path.exists() and editorial.read(context_path) != research_context:
                    raise ValueError('Research context changed; use a fresh source job directory')
                if not context_path.exists() and (job / 'source_checkpoint.json').exists():
                    raise ValueError('New research context requires a fresh source job directory')
                editorial.write(context_path, research_context)
            article = editorial.read(job / "source_article.json")
            dossier = editorial.read(job / "source_dossier.json")
            saved_source = snapshot.get("registry_source")
            if not _recorded_source_hash_matches(snapshot.get("registry_source_hash"), saved_source, source):
                raise ValueError("Prepared job registry source changed; use a fresh source job directory")
            located = _load_source_tools().locate_sources({"schema_version": 1, "sources": [source]}, char, dossier)
            locator_hash = _locator_hash(located)
            checkpoint_path = job / "source_checkpoint.json"
            checkpoint = editorial.read(checkpoint_path) if checkpoint_path.exists() else {}
            if checkpoint.get("registry_source_hash") and not _recorded_source_hash_matches(
                    checkpoint.get("registry_source_hash"), saved_source, source):
                raise ValueError("Source checkpoint belongs to another registered book/corpus")
            if checkpoint.get("locator_hash") not in (None, locator_hash):
                raise ValueError("Per-character source leads changed; prepare a fresh source job directory")
            checkpoint = {"character": char, "source_id": source["id"],
                "registry_source_hash": _research_source_hash(source), "snapshot_hash": editorial.digest(snapshot),
                "locator": located, "locator_hash": locator_hash, "status": "research_pending",
                "updated_at": datetime.now(timezone.utc).isoformat()}
            # This durable packet survives editorial.refine replacing status.json at stage start.
            editorial.write(checkpoint_path, checkpoint)
            runner.profile_policy = SOURCE_POLICY
            if getattr(runner, "model", "gpt-6-luna") != "gpt-6-luna" or getattr(runner, "reasoning", "low") != "low":
                raise ValueError("Source enrichment requires gpt-6-luna with low reasoning")
            findings_path = job / "source_findings.json"
            if _source_findings_pending(job):
                raise ValueError("Unresolved source/OCR finding requires coordinator verification before continuing")
            state = editorial.read(job / "status.json")
            audit_path = job / "source_audit.json"
            if state.get("status") == "approved" and audit_path.is_file():
                audit = editorial.read(audit_path)
                candidate = editorial.read(job / "article.json")
                candidate_dossier = editorial.read(job / "dossier.json")
                try:
                    editorial.validate_reviews(candidate, candidate_dossier, editorial.read(job / "reviews.json"))
                    reusable = (audit.get("verified") is True
                        and _recorded_source_hash_matches(audit.get("source_hash"), saved_source, source)
                        and state.get("source_id") == source["id"]
                        and _recorded_source_hash_matches(state.get("registry_source_hash"), saved_source, source)
                        and state.get("locator_hash") == locator_hash
                        and state.get("source_audit_hash") == editorial.digest(audit)
                        and state.get("article_hash") == editorial.digest(candidate)
                        and state.get("dossier_hash") == editorial.digest(candidate_dossier))
                except (ValueError, KeyError, editorial.ValidationError):
                    reusable = False
                if reusable:
                    return complete_approval(state)
            followup = feedback(source, located, source_context)
            followup['target_language'] = (article.get('language')
                or dossier.get('context', {}).get('target_language')
                or cohort.get('language', 'zh'))
            if context_path.exists():
                followup['additional_research_context'] = editorial.read(context_path)
                if followup['additional_research_context'].get('review_existing_glyphs') is True:
                    followup['review_existing_glyphs'] = True
                followup['additional_context_policy'] = (
                    'These source leads and prior findings are research tasks, not preverified dossier evidence. '
                    'Consult the referenced sources directly, check exact graph identity and scope, '
                    'and add cited evidence for useful claims before authorship. Recheck reviewer hypotheses; '
                    'modern structure does not establish historical roles. Record inaccessible sources as gaps.')
            if continuation:
                if len(cohort['characters']) != 1:
                    raise ValueError('A continuation names one exact character job')
                article, dossier = _continuation_inputs(continuation, job, char, source, snapshot)
                followup['unfinished_draft_provenance'] = editorial.read(job / 'continuation.json')
                followup['prior_review_proposals'] = editorial.read(job / 'continuation_review_proposals.json')
                followup['prior_consulted_book_records'] = editorial.read(job / 'continuation_book_leads.json')
                followup['continuation_policy'] = ('This is an unapproved draft, not reusable approval. '
                    'Recheck source-dependent claims against current source scans/corpus. '
                    'Prior revise findings are hypotheses to recheck, including possible source identity errors; '
                    'do not obey them merely because a previous verifier repeated them. '
                    'Prior consulted book records identify exact retained evidence IDs and claims to recheck. '
                    'After current-source verification, cite relevant supported claims through evidence_ids metadata; '
                    'dossier-only records do not count as article source use. '
                    'Preserve prior supported work and obtain fresh factual/readability reviews.')
            followup["require_source_specific_page_evidence"] = True
            if audit_path.exists() and not editorial.read(audit_path).get("verified"):
                previous_audit = editorial.read(audit_path)
                if previous_audit.get('consulted_citations'):
                    followup['verified_uncited_book_records'] = previous_audit['consulted_citations']
                    followup['previous_source_audit_failed'] = (
                        'Prior completed research read these exact book records, but the article did not cite them. '
                        'Verify which current claims they support, then cite those evidence IDs at those claims '
                        'through authorship and fresh reviews. Do not attach arbitrary citations.')
                else:
                    followup["previous_source_audit_failed"] = (
                        "Prior research did not return retained page-specific evidence from this registered source. "
                        "Inspect it and either cite a relevant page or state a specific source access/relevance gap.")
            state = editorial.refine(article, dossier, job, runner, max_revisions,
                                     followup, research_first=True)
            scan_findings = _capture_scan_findings(job, source)
            final_dossier = editorial.read(job / "dossier.json")
            audit = _capture_source_audit(job, source, final_dossier)
            state, audit = _integrate_uncited_book_records(
                job, source, runner, state, audit, followup, max_revisions)
            scan_findings = _capture_scan_findings(job, source)
            state.update(source_id=source["id"], registry_source_hash=_research_source_hash(source),
                         locator_hash=locator_hash, source_snapshot_hash=editorial.digest(snapshot),
                         source_audit_hash=editorial.digest(audit), tracking_issue_url=source.get("tracking_issue_url"))
            checkpoint.update(status="research_complete", source_audit_hash=editorial.digest(audit),
                              updated_at=datetime.now(timezone.utc).isoformat())
            editorial.write(checkpoint_path, checkpoint)
            if state.get("status") == "approved" and not audit["verified"]:
                state["status"] = "needs_source_evidence"
                state["source_audit_error"] = ("Verified book records remain uncited by the article."
                    if audit.get("consulted_citations") else "No retained page-specific book evidence was returned.")
            if scan_findings["requires_coordinator_verification"]:
                state["source_verification_pending"] = True
                if state.get("status") == "approved":
                    state["status"] = "needs_source_verification"
            editorial.write(job / "status.json", state)
            if (scan_findings["requires_coordinator_verification"]
                    and state.get('status') == 'needs_source_verification'
                    and audit.get('verified') is True):
                auto_resolve_source_findings(job, runner, source_context=followup.get('source_scan_images'))
                state = editorial.read(job / 'status.json')
            if state.get("status") == "approved":
                return complete_approval(state)
            issue_sync = sync_findings(state)
            if issue_sync["status"] == "pending":
                return {"character": char, "status": "pending_issue_sync", "underlying_status": state.get("status"),
                        "job": str(job), "error": issue_sync.get("error")}
            return {"character": char, "status": state.get("status", "unknown"), "job": str(job)}
        except Exception as exc:
            research_results = list(job.glob("**/research/result.json")) + list(job.glob("**/research-repair-*/result.json"))
            if research_results:
                _capture_scan_findings(job, source)
                _capture_source_audit(job, source, editorial.read(job / "dossier.json")
                    if (job / "dossier.json").exists() else editorial.read(job / "source_dossier.json"))
            failure = {"character": char, "status": "failed", "job": str(job), "error": str(exc)}
            editorial.write(job / "source-enrichment-failure.json", failure)
            if source.get("github_repo") and (job / "status.json").is_file():
                try:
                    _triage_and_sync_issues(job, source, runner)
                except Exception as issue_exc:
                    editorial.write(job / "issue_sync.json", {"status": "pending",
                        "repository": source["github_repo"], "error": str(issue_exc)})
            return failure

    def process(char):
        job = job_path(output, source["id"], char)
        job.mkdir(parents=True, exist_ok=True)
        # Share a claim across output folders, then protect the actual job files.
        # Both locks survive an orphaned live model subprocess.
        lock_dir = Path(root) / 'runs' / '.locks'
        lock_dir.mkdir(parents=True, exist_ok=True)
        claim_path = lock_dir / f"source-{_research_source_hash(source)[:16]}-{ord(char):04X}.lock"
        with claim_path.open('a') as claim, (job / 'coordinator.lock').open('a') as lock:
            try:
                fcntl.flock(claim, fcntl.LOCK_EX | fcntl.LOCK_NB)
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                return {"character": char, "status": "already_running", "job": str(job)}
            try:
                local_runner = copy.copy(runner)
                local_runner.inherited_lock_fds = (claim.fileno(), lock.fileno())
                return process_unlocked(char, local_runner)
            finally:
                fcntl.flock(lock, fcntl.LOCK_UN)
                fcntl.flock(claim, fcntl.LOCK_UN)

    return queue.execute(cohort['characters'], process,
                         lambda char: job_path(output, source['id'], char), verified,
                         workers, limit, retry_attention, publish_now, excluded)


def publish_job(job, source, root=ROOT):
    """Lock the exact job before its source gates and canonical publication lock."""
    job = Path(job)
    with (job / 'coordinator.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ValueError('Source job coordinator or agent is live') from exc
        try:
            return _publish_job_locked(job, source, root)
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def _publish_job_locked(job, source, root=ROOT):
    job = Path(job)
    state = editorial.read(job / "status.json")
    if state.get("status") != "approved":
        raise ValueError("Only an approved source-enrichment job can be published")
    saved = editorial.read(job / "source.json")
    prepare_job(saved['character'], job, source, root)
    if not _same_research_source(saved.get("registry_source", {}), source):
        raise ValueError("Job source provenance differs from requested source")
    if not _recorded_source_hash_matches(saved.get("registry_source_hash"), saved.get("registry_source"), source):
        raise ValueError("Job source registry hash is stale")
    findings_path = job / "source_findings.json"
    if _source_findings_pending(job):
        raise ValueError("Source findings require coordinator verification")
    located = _load_source_tools().locate_sources({"schema_version": 1, "sources": [source]},
        saved["character"], editorial.read(job / "source_dossier.json"))
    if state.get("locator_hash") != _locator_hash(located):
        _hold_changed_source_inputs(job, state, located)
        raise ValueError("Source inputs changed after research; new source research is required")
    audit_path = job / "source_audit.json"
    if not audit_path.is_file():
        raise ValueError("No source-specific audit was recorded")
    audit = editorial.read(audit_path)
    if (audit.get("verified") is not True
            or not _recorded_source_hash_matches(audit.get("source_hash"), saved.get("registry_source"), source)
            or state.get("source_audit_hash") != editorial.digest(audit)):
        raise ValueError("Source-specific page evidence is missing or stale")
    if audit.get('mode') in ('existing_approved_research', 'source_coverage_candidate'):
        from pipeline.source_adoption import valid_audit
        candidate, dossier = editorial.read(job / 'article.json'), editorial.read(job / 'dossier.json')
        if not valid_audit(job, audit, candidate, dossier):
            raise ValueError('Source coverage receipt does not bind the exact completed Luna-low candidate review')
    if source.get("github_repo") and state.get("issue_sync_status") != "synced":
        raise ValueError("Issue tracking must sync successfully before publication")
    article, dossier = editorial.read(job / "article.json"), editorial.read(job / "dossier.json")
    binding_errors = _source_scan_binding_errors(source, article, dossier)
    if binding_errors:
        raise ValueError('Cited scan provenance differs from its registered PDF page: ' + str(binding_errors))
    if not _article_used_book_evidence(audit, article, dossier):
        raise ValueError("Registered book evidence is not cited by the article")
    reviews = editorial.read(job / "reviews.json")
    hashes = {"article_hash": editorial.digest(article), "dossier_hash": editorial.digest(dossier)}
    if state.get("article_hash") not in (None, hashes["article_hash"]) or state.get("dossier_hash") not in (None, hashes["dossier_hash"]):
        raise ValueError("Approved status hashes do not match reviewed job artifacts")
    result = batch.publish_job(job, root)
    state = {**state, "status": "published", **hashes, "source_id": source["id"],
             "registry_source_hash": _research_source_hash(source),
             "locator_hash": state.get("locator_hash"), "published_at": datetime.now(timezone.utc).isoformat(),
             "canonical_entry": str(Path(root) / "content/entries" / f"{ord(article['character']):04X}.json")}
    editorial.write(job / "status.json", state)
    return {"character": article["character"], "status": "published", "job": str(job), **hashes,
            "batch_publication": str(result)}



def sync_and_publish_job(job, source, runner, root=ROOT):
    """Keep remote triage, saved status and publication under the same job lock."""
    job = Path(job)
    with (job / 'coordinator.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return {'character': editorial.read(job / 'source.json')['character'],
                    'status': 'already_running', 'job': str(job)}
        try:
            state = editorial.read(job / 'status.json')
            if state.get('status') != 'approved':
                raise ValueError('Only an approved source job can be published')
            local_runner = copy.copy(runner)
            local_runner.inherited_lock_fds = (lock.fileno(),)
            try:
                issue_sync = _triage_and_sync_issues(job, source, local_runner)
            except Exception as exc:
                issue_sync = {'status': 'pending', 'repository': source.get('github_repo'),
                              'error': str(exc)}
                editorial.write(job / 'issue_sync.json', issue_sync)
            state['issue_sync_status'] = issue_sync['status']
            state['issue_receipts_hash'] = editorial.digest(issue_sync.get('issues', []))
            editorial.write(job / 'status.json', state)
            if issue_sync['status'] == 'pending':
                return {'character': state['character'], 'status': 'pending_issue_sync',
                        'job': str(job), 'error': issue_sync.get('error')}
            return _publish_job_locked(job, source, root)
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "run", "publish", "status"))
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--source", required=True)
    parser.add_argument("--cohort", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=ROOT / "runs/source-enrichment")
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--limit", type=int, default=3)
    parser.add_argument("--workers", type=int, default=1, help="Maximum concurrent character jobs (start small, then raise after a smoke run)")
    parser.add_argument("--agents", type=int, default=2, help="Maximum active model processes, shared across character workers")
    parser.add_argument("--max-revisions", type=int, default=2)
    parser.add_argument("--timeout", type=int, default=600)
    parser.add_argument("--command", default=json.dumps(editorial.DEFAULT_COMMAND), help="Custom command; stages remain gpt-6-luna/low")
    parser.add_argument("--publish-now", action="store_true")
    parser.add_argument("--exclude", default="", help="Characters currently owned by separate work; leave them queued")
    parser.add_argument("--retry-attention", action="store_true",
                        help="Explicitly retry held failures/review/source blockers after fixing their cause")
    parser.add_argument("--scan-context", type=Path, help="JSON records with absolute path, pdf_page, optional printed_page")
    parser.add_argument("--continue-from", type=Path, help="Unfinished terminal source job; fresh research and reviews required")
    parser.add_argument("--research-context", type=Path, help="JSON object of additional source leads and findings to research directly")
    parser.add_argument("--tracking-issue-url", help="Existing GitHub issue for this enrichment or source finding")
    args = parser.parse_args()
    if args.limit < 1 or args.workers < 1 or (args.agents is not None and args.agents < 1):
        parser.error("--limit, --workers and --agents must be positive")
    registry = _source_registry(args.registry)
    source = _source(registry, args.source)
    tracking_issue = args.tracking_issue_url or source.get("tracking_issue_url") or registry.get("tracking_issue_url")
    if tracking_issue:
        source = {**source, "tracking_issue_url": tracking_issue}
    cohort = load_cohort(args.cohort)
    context = editorial.read(args.scan_context) if args.scan_context else None
    runner = editorial.Runner(json.loads(args.command), "gpt-6-luna", args.timeout, "low")
    from pipeline.agent_slots import AgentSlots
    runner.agent_slots = AgentSlots(args.root / 'runs/.locks/agent-slots', args.agents or args.workers)
    if args.action == "prepare":
        result = prepare(cohort, source, args.output, args.limit, args.root)
    elif args.action == "status":
        result = status(cohort, source, args.output, args.root)
    elif args.action == "publish":
        result, published = [], 0
        for row in cohort["characters"]:
            job = job_path(args.output, source["id"], row)
            approved = ((job / "status.json").exists()
                        and editorial.read(job / "status.json").get("status") == "approved")
            if approved and published >= args.limit:
                result.append({"character": row, "status": "deferred", "job": str(job)})
                continue
            if approved:
                try:
                    publication = sync_and_publish_job(job, source, runner, args.root)
                    result.append(publication)
                    if publication['status'] == 'published':
                        published += 1
                except Exception as exc:
                    result.append({"character": row, "status": "failed", "job": str(job), "error": str(exc)})
    else:
        result = run(cohort, source, args.output, runner, args.limit, args.workers, args.root,
                     args.max_revisions, args.publish_now, context, args.continue_from,
                     editorial.read(args.research_context) if args.research_context else None,
                     args.retry_attention, set(args.exclude))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if any(row.get("status") in ("failed", "needs_revision") for row in result):
        raise SystemExit(2)


if __name__ == "__main__":
    main()
