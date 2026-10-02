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
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
import shutil
from pathlib import Path
import re

from pipeline import batch, editorial

ROOT = editorial.ROOT
MAX_SELECTION = 10
MAX_WORKERS = 3
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

SOURCE_POLICY = """
SOURCE-SPECIFIC CHINESE ENRICHMENT:
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
        value["source_scan_images"] = merged[:3]
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
        editorial.validate_reviews(article, dossier, reviews)
        canonical_article, canonical_dossier = _canonical(root, article["character"])
        located = _load_source_tools().locate_sources({"schema_version": 1, "sources": [source]},
            article["character"], editorial.read(job / "source_dossier.json"))
    except (ValueError, KeyError, OSError, editorial.ValidationError):
        return False
    audit_path = job / "source_audit.json"
    if audit_path.is_file() and editorial.read(audit_path).get('mode') == 'existing_approved_research':
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
                                context, research_first=False, edit_first=False)
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
                    "rejected_proposal_scan_matches_corpus", "applied_repair_scan_matches_corpus") for item in result["findings"]))


def resolve_source_findings(job, runner, source_context=None, literal_checks=None, repair_checks=None):
    """Check whether retained uncertainty is immaterial; actual OCR errors stay blocked."""
    job = Path(job)
    if runner.model != "gpt-6-luna" or runner.reasoning != "low":
        raise ValueError("Source resolution requires gpt-6-luna low")
    findings = editorial.read(job / "source_findings.json")
    article, dossier = editorial.read(job / "article.json"), editorial.read(job / "dossier.json")
    editorial.validate_reviews(article, dossier, editorial.read(job / "reviews.json"))
    checkpoint = editorial.read(job / "source_checkpoint.json")
    schema = {"type": "object", "additionalProperties": False, "required": ["findings"],
        "properties": {"findings": {"type": "array", "items": {
            "type": "object", "additionalProperties": False,
            "required": ["key", "disposition", "reason", "affected_paths"],
            "properties": {"key": {"type": "string"},
                "disposition": {"enum": ["pending", "unresolved_identity_not_used",
                                          "rejected_proposal_scan_matches_corpus", "applied_repair_scan_matches_corpus"]},
                "reason": {"type": "string", "minLength": 1},
                "affected_paths": {"type": "array", "items": {"type": "string"}}}}}}}
    inputs = {"article": article, "dossier": dossier, "findings": findings,
              "feedback": {"source_scan_images": (
                  list(checkpoint["locator"].get("source_scan_images", [])) + list(source_context or []))[:3]}}
    checks = list(literal_checks or [])
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
            'Your pixel_reason must agree with those fields; a contradictory rationale is not approval.')
        schema['required'].append('literal_observations')
        schema['properties']['literal_observations'] = {'type': 'array', 'items': {
            'type': 'object', 'additionalProperties': False,
            'required': ['key', 'current_corpus_literal', 'proposed_literal', 'observed_literal', 'pixel_reason'],
            'properties': {field: {'type': 'string', 'minLength': 1} for field in
                           ['key', 'current_corpus_literal', 'proposed_literal', 'observed_literal', 'pixel_reason']}}}
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
            'Use applied_repair_scan_matches_corpus only if observed_literal equals after. '
            'Preserve original findings and report pending for unclear pixels or unsupported claims.')
        schema['required'].append('repair_observations')
        schema['properties']['repair_observations'] = {'type': 'array', 'items': {
            'type': 'object', 'additionalProperties': False,
            'required': ['key', 'observed_literal', 'pixel_reason'],
            'properties': {f: {'type': 'string', 'minLength': 1}
                           for f in ('key', 'observed_literal', 'pixel_reason')}}}
    allowed_dispositions = ['pending', 'unresolved_identity_not_used']
    if checks:
        allowed_dispositions.append('rejected_proposal_scan_matches_corpus')
    if repairs:
        allowed_dispositions.append('applied_repair_scan_matches_corpus')
    schema['properties']['findings']['items']['properties']['disposition']['enum'] = allowed_dispositions
    inputs['disposition_policy'] = (
        'A rejected replacement requires a supplied exact literal_checks occurrence and proposal. '
        'An identity gap without such a proposal is not a rejected OCR replacement: '
        'use unresolved_identity_not_used only after independently verifying no article claim '
        'depends on that identity; otherwise pending. Applied repairs require supplied validated '
        'producer/consumer checks. Retain every original finding.')
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
    record = {"findings_hash": editorial.digest(findings), "article_hash": editorial.digest(article),
              "dossier_hash": editorial.digest(dossier), "result_hash": editorial.digest(result),
              "review_path": str((directory / 'result.json').relative_to(job)), "model": runner.model,
              "reasoning": runner.reasoning, "literal_checks": checks, "applied_repairs": repairs}
    editorial.write(job / "source_resolution.json", record)
    if not _source_findings_pending(job):
        state = editorial.read(job / "status.json")
        if state.get("status") == "needs_source_verification":
            state.update(status="approved", source_verification_pending=False,
                         article_hash=editorial.digest(article), dossier_hash=editorial.digest(dossier))
            editorial.write(job / "status.json", state)
    return record


def _book_identity_matches(label, source):
    title, book_id = source.get('title', ''), source.get('book_id', '')
    return bool((title and re.search(r"(?<!\w)" + re.escape(title) + r"(?!\w)", label))
                or (book_id and book_id in label))


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


def status(cohort, source, output, root=ROOT):
    rows = []
    for char in cohort["characters"]:
        job = job_path(output, source["id"], char)
        if _published_matches(job, source, root):
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
    if limit < 1 or limit > MAX_SELECTION:
        raise ValueError(f"Selection limit must be between 1 and {MAX_SELECTION}")
    rows, selected = [], 0
    for char in cohort["characters"]:
        job = job_path(output, source["id"], char)
        if _published_matches(job, source, root):
            rows.append({"character": char, "status": "published", "job": str(job)})
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
        publish_now=False, source_context=None, continuation=None, research_context=None):
    if not 1 <= workers <= MAX_WORKERS:
        raise ValueError(f"Workers must be between 1 and {MAX_WORKERS}")
    if not 1 <= limit <= MAX_SELECTION:
        raise ValueError(f"Selection limit must be between 1 and {MAX_SELECTION}")
    rows = {}
    selected = []
    for char in cohort["characters"]:
        job = job_path(output, source["id"], char)
        if _published_matches(job, source, root):
            rows[char] = {"character": char, "status": "published", "job": str(job)}
        elif len(selected) < limit:
            selected.append(char)
        else:
            rows[char] = {"character": char, "status": "deferred", "job": str(job)}

    def process_unlocked(char, runner):
        job = job_path(output, source["id"], char)

        def sync_findings(state):
            try:
                issue_sync = _triage_and_sync_issues(job, source, runner)
            except Exception as exc:
                issue_sync = {"status": "pending", "repository": source.get("github_repo"),
                              "error": str(exc)}
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
                return publish_job(job, source, root)
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
        # An OS lock releases on coordinator exit and prevents two harnesses from
        # writing the same stage outputs. A status file is never proof of liveness.
        with (job / "coordinator.lock").open("a") as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                return {"character": char, "status": "already_running", "job": str(job)}
            try:
                local_runner = copy.copy(runner)
                local_runner.inherited_lock_fds = (lock.fileno(),)
                return process_unlocked(char, local_runner)
            finally:
                fcntl.flock(lock, fcntl.LOCK_UN)

    if selected:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {char: pool.submit(process, char) for char in selected}
            for char in selected:
                rows[char] = futures[char].result()
    return [rows[char] for char in cohort["characters"]]


def publish_job(job, source, root=ROOT):
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
    if source.get("github_repo") and state.get("issue_sync_status") != "synced":
        raise ValueError("Issue tracking must sync successfully before publication")
    article, dossier = editorial.read(job / "article.json"), editorial.read(job / "dossier.json")
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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "run", "publish", "status"))
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--source", required=True)
    parser.add_argument("--cohort", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=ROOT / "runs/source-enrichment")
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--limit", type=int, default=3)
    parser.add_argument("--workers", type=int, default=1, help="Parallel character jobs, capped at 3")
    parser.add_argument("--max-revisions", type=int, default=3)
    parser.add_argument("--timeout", type=int, default=600)
    parser.add_argument("--command", default=json.dumps(editorial.DEFAULT_COMMAND), help="Custom command; stages remain gpt-6-luna/low")
    parser.add_argument("--publish-now", action="store_true")
    parser.add_argument("--scan-context", type=Path, help="JSON records with absolute path, pdf_page, optional printed_page")
    parser.add_argument("--continue-from", type=Path, help="Unfinished terminal source job; fresh research and reviews required")
    parser.add_argument("--research-context", type=Path, help="JSON object of additional source leads and findings to research directly")
    parser.add_argument("--tracking-issue-url", help="Existing GitHub issue for this enrichment or source finding")
    args = parser.parse_args()
    if not 1 <= args.limit <= MAX_SELECTION:
        parser.error(f"--limit must be between 1 and {MAX_SELECTION}")
    registry = _source_registry(args.registry)
    source = _source(registry, args.source)
    tracking_issue = args.tracking_issue_url or source.get("tracking_issue_url") or registry.get("tracking_issue_url")
    if tracking_issue:
        source = {**source, "tracking_issue_url": tracking_issue}
    cohort = load_cohort(args.cohort)
    context = editorial.read(args.scan_context) if args.scan_context else None
    runner = editorial.Runner(json.loads(args.command), "gpt-6-luna", args.timeout, "low")
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
                    state = editorial.read(job / "status.json")
                    try:
                        issue_sync = _triage_and_sync_issues(job, source, runner)
                    except Exception as exc:
                        issue_sync = {"status": "pending", "repository": source.get("github_repo"),
                                      "error": str(exc)}
                        editorial.write(job / "issue_sync.json", issue_sync)
                    if issue_sync["status"] == "pending":
                        state["issue_sync_status"] = "pending"
                        editorial.write(job / "status.json", state)
                        result.append({"character": row, "status": "pending_issue_sync", "job": str(job),
                                       "error": issue_sync.get("error")})
                        continue
                    state["issue_sync_status"] = issue_sync["status"]
                    state["issue_receipts_hash"] = editorial.digest(issue_sync.get("issues", []))
                    editorial.write(job / "status.json", state)
                    result.append(publish_job(job, source, args.root))
                    published += 1
                except Exception as exc:
                    result.append({"character": row, "status": "failed", "job": str(job), "error": str(exc)})
    else:
        result = run(cohort, source, args.output, runner, args.limit, args.workers, args.root,
                     args.max_revisions, args.publish_now, context, args.continue_from,
                     editorial.read(args.research_context) if args.research_context else None)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if any(row.get("status") in ("failed", "needs_revision") for row in result):
        raise SystemExit(2)


if __name__ == "__main__":
    main()
