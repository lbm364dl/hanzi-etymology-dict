"""Safe fresh continuation for failed source-enrichment editorial stages.

This helper reuses an exact retained research dossier while creating a new job,
new authorship and new independent reviews. It never publishes or syncs issues.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import copy
import fcntl
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from pipeline import editorial, source_enrichment
from pipeline.agent_slots import AgentSlots


def _lock(lockfile):
    lockfile.parent.mkdir(parents=True, exist_ok=True)
    handle = lockfile.open('a')
    try:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError as exc:
        handle.close()
        raise ValueError(f'Attention repair resource is already locked: {lockfile}') from exc
    return handle


def _terminal_error(prior_job):
    status = editorial.read(prior_job / 'status.json')
    if status.get('status') not in {'failed', 'needs_revision', 'needs_source_evidence',
                                   'needs_source_verification'}:
        raise ValueError(f"Prior job is not an attention state: {status.get('status')}")
    failure = editorial.read(prior_job / 'source-enrichment-failure.json') if \
        (prior_job / 'source-enrichment-failure.json').is_file() else {}
    return status, status.get('error') or failure.get('error') or ''


def _check_prior(prior_job, source, root):
    prior_job = Path(prior_job)
    state, error = _terminal_error(prior_job)
    saved = editorial.read(prior_job / 'source.json')
    if saved.get('source_id') != source.get('id'):
        raise ValueError('Prior job belongs to another registered source')
    if not source_enrichment._recorded_source_hash_matches(
            saved.get('registry_source_hash'), saved.get('registry_source'), source):
        raise ValueError('Prior source identity differs from the current registry')
    if editorial.digest(editorial.read(prior_job / 'source_article.json')) != saved.get('article_hash'):
        raise ValueError('Prior frozen article snapshot is altered')
    if editorial.digest(editorial.read(prior_job / 'source_dossier.json')) != saved.get('dossier_hash'):
        raise ValueError('Prior frozen dossier snapshot is altered')
    canonical_article, canonical_dossier = source_enrichment._canonical(root, saved['character'])
    if (editorial.digest(canonical_article) != saved.get('article_hash')
            or editorial.digest(canonical_dossier) != saved.get('dossier_hash')):
        raise ValueError('Canonical baseline changed since the failed source job')
    findings = editorial.read(prior_job / 'source_findings.json') if \
        (prior_job / 'source_findings.json').is_file() else {'findings': []}
    return saved, state, error, findings


def _check_locator(prior_job, character, source, dossier):
    """Reuse scan research only when the source leads still resolve identically."""
    locator = source_enrichment._load_source_tools().locate_sources(
        {'schema_version': 1, 'sources': [source]}, character, dossier)
    locator_hash = source_enrichment._locator_hash(locator)
    checkpoint_path = Path(prior_job) / 'source_checkpoint.json'
    if checkpoint_path.is_file():
        prior_locator = editorial.read(checkpoint_path).get('locator_hash')
        if prior_locator and prior_locator != locator_hash:
            raise ValueError('Current source locator differs from failed job; source refresh is required')
    return locator, locator_hash


def _validated_draft(prior_job, dossier):
    """Use the latest mechanically valid candidate; otherwise start from frozen baseline."""
    candidates = [prior_job / 'article.json', prior_job / 'source_article.json']
    for candidate_path in candidates:
        if not candidate_path.is_file():
            continue
        candidate = editorial.read(candidate_path)
        try:
            editorial.validate_article(candidate, dossier)
        except (ValueError, editorial.ValidationError):
            continue
        return candidate, candidate_path
    raise ValueError('Neither latest candidate nor frozen baseline validates against retained dossier')


def _review_context(prior_job, error, findings):
    prior_reviews = []
    review_path = prior_job / 'reviews.json'
    if review_path.is_file():
        for review in editorial.read(review_path):
            prior_reviews.append({'receipt': 'reviews.json', 'review': review})
    # Preserve each actual review result and its path; these are repair context,
    # never approvals for the new article/dossier pair.
    for path in sorted(prior_job.glob('round-*/factual/result.json')) + \
                 sorted(prior_job.glob('round-*/readability/result.json')) + \
                 sorted(prior_job.glob('round-*/factual-verification/result.json')) + \
                 sorted(prior_job.glob('round-*/readability-verification/result.json')):
        record = editorial.read(path)
        if record.get('findings'):
            prior_reviews.append({'receipt': str(path.relative_to(prior_job)), 'review': record,
                                  'result_hash': editorial.digest(record)})
    prior_author = []
    for path in sorted(prior_job.glob('round-*/editor/result.json')) + \
                 sorted(prior_job.glob('round-*/editor/patch-repair-*/result.json')) + \
                 sorted(prior_job.glob('round-*/revision/result.json')) + \
                 sorted(prior_job.glob('round-*/revision/patch-repair-*/result.json')):
        record = editorial.read(path)
        if record.get('edits'):
            prior_author.append({'receipt': str(path.relative_to(prior_job)),
                                 'result_hash': editorial.digest(record), 'result': record})
    return {
        'terminal_validation_error': error,
        'previous_review_receipts': prior_reviews,
        'previous_failed_author_receipts': prior_author,
        'source_findings': findings.get('findings', []),
        'repair_instructions': (
            'Treat retained reviews and failed author outputs as diagnostic evidence only. '
            'Resolve the concrete validation/review findings with the smallest evidence-supported '
            'changes. Preserve supported claims, IDs and unrelated records. Do not treat this '
            'context as an approval. Any source finding remains unresolved until the normal '
            'source-resolution gate handles it; do not claim an OCR correction from prose.'),
    }


def _retain_research(prior_job, new_job):
    """Copy exact completed Luna-low research result/receipt bytes for later source audit."""
    copied = []
    paths = sorted(prior_job.glob('**/research/result.json')) + \
        sorted(prior_job.glob('**/research-repair-*/result.json'))
    for result_path in dict.fromkeys(paths):
        meta_path = result_path.parent / 'meta.json'
        if not meta_path.is_file():
            continue
        relative = result_path.relative_to(prior_job)
        target = new_job / 'retained-research' / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(result_path, target)
        target_meta = target.parent / 'meta.json'
        shutil.copy2(meta_path, target_meta)
        if target.read_bytes() != result_path.read_bytes() or target_meta.read_bytes() != meta_path.read_bytes():
            raise ValueError('Retained research copy did not preserve source bytes')
        copied.append({'original_result': str(result_path), 'retained_result': str(target),
                       'result_hash': editorial.digest(editorial.read(target)),
                       'meta_hash': editorial.digest(editorial.read(target_meta))})
    return copied


def run_one(prior_job, output_job, source, runner, root=source_enrichment.ROOT,
            max_revisions=3, allowed_edit_paths=None):
    prior_job, output_job = Path(prior_job), Path(output_job)
    source_hash = source_enrichment._research_source_hash(source)
    character = editorial.read(prior_job / 'source.json')['character']
    claim_path = Path(root) / 'runs/.locks' / f'source-{source_hash[:16]}-{ord(character):04X}.lock'
    output_job.mkdir(parents=True, exist_ok=True)
    claim = _lock(claim_path)
    old_lock = new_lock = None
    try:
        old_lock = _lock(prior_job / 'coordinator.lock')
        new_lock = _lock(output_job / 'coordinator.lock')
        saved, prior_state, error, findings = _check_prior(prior_job, source, root)
        if output_job.joinpath('attention_repair.json').exists():
            raise ValueError('Output already contains an attention-repair attempt; use a new directory')
        prior_dossier = editorial.read(prior_job / 'dossier.json') if \
            (prior_job / 'dossier.json').is_file() else editorial.read(prior_job / 'source_dossier.json')
        if findings.get('findings') and any(item.get('kind') == 'ocr' for item in findings['findings']):
            raise ValueError('Known OCR/source-literal findings must be verified before editorial continuation')
        latest = prior_job / 'article.json'
        dossier = prior_dossier
        article, used_article_path = _validated_draft(prior_job, dossier)
        locator, locator_hash = _check_locator(prior_job, character, source, dossier)

        snapshot = source_enrichment.prepare_job(character, output_job, source, root)
        if snapshot.get('article_hash') != saved.get('article_hash') or snapshot.get('dossier_hash') != saved.get('dossier_hash'):
            raise ValueError('Fresh job canonical baseline differs from the failed job baseline')
        feedback = _review_context(prior_job, error, findings)
        feedback.update({
            'attention_repair': True,
            'prior_job': str(prior_job),
            'prior_status': prior_state,
            'prior_article_path': str(used_article_path),
            'prior_article_hash': editorial.digest(article),
            'retained_dossier_hash': editorial.digest(dossier),
            'registered_source': source,
            'source_scan_images': locator.get('source_scan_images', []),
            'target_language': article.get('language') or dossier.get('context', {}).get('target_language', 'zh'),
            'verified_uncited_book_records': editorial.read(prior_job / 'source_audit.json').get('consulted_citations', [])
                if (prior_job / 'source_audit.json').is_file() else [],
            'previous_source_audit_failed': (
                'Retained source audit and exact consulted page records are included. Recheck which '
                'current claims those records support, cite only supported claims through evidence_ids, '
                'and keep source-workflow information out of reader prose.'),
        })
        if allowed_edit_paths is not None:
            if (not isinstance(allowed_edit_paths, list) or not allowed_edit_paths
                    or len(set(allowed_edit_paths)) != len(allowed_edit_paths)):
                raise ValueError('Repair path scope must be a nonempty array of unique article paths')
            feedback['allowed_edit_paths'] = allowed_edit_paths
        editorial.write(output_job / 'attention_repair.json', {
            'created_at': datetime.now(timezone.utc).isoformat(),
            'prior_job': str(prior_job), 'prior_status_hash': editorial.digest(prior_state),
            'prior_source_snapshot_hash': editorial.digest(saved),
            'canonical_article_hash': snapshot['article_hash'], 'canonical_dossier_hash': snapshot['dossier_hash'],
            'source_hash': source_hash, 'locator_hash': locator_hash,
            'article_input_hash': editorial.digest(article), 'dossier_input_hash': editorial.digest(dossier),
            'source_findings_hash': editorial.digest(findings),
            'retained_research': _retain_research(prior_job, output_job),
        })
        runner.profile_policy = source_enrichment.SOURCE_POLICY
        runner.inherited_lock_fds = tuple(handle.fileno() for handle in (claim, old_lock, new_lock))
        if getattr(runner, 'model', None) != 'gpt-6-luna' or getattr(runner, 'reasoning', None) != 'low':
            raise ValueError('Attention repair requires gpt-6-luna with low reasoning')
        state = editorial.refine(article, dossier, output_job, runner, max_revisions,
                                 feedback=feedback, research_first=False, edit_first=True)
        candidate = editorial.read(output_job / 'article.json') if (output_job / 'article.json').is_file() else article
        final_dossier = editorial.read(output_job / 'dossier.json')
        audit = source_enrichment._capture_source_audit(output_job, source, final_dossier)
        scan_findings = source_enrichment._capture_scan_findings(output_job, source)
        # The scan collector only knows how to regenerate OCR findings. Carry
        # every earlier coordinator finding forward instead of silently dropping
        # source-claim, metadata or identity findings during a fresh continuation.
        combined = {item['key']: item for item in findings.get('findings', [])}
        combined.update({item['key']: item for item in scan_findings.get('findings', [])})
        scan_findings['findings'] = list(combined.values())
        scan_findings['requires_coordinator_verification'] = bool(combined)
        editorial.write(output_job / 'source_findings.json', scan_findings)
        state.update(source_id=source['id'], registry_source_hash=source_hash,
                     locator_hash=locator_hash, source_snapshot_hash=editorial.digest(snapshot),
                     source_audit_hash=editorial.digest(audit), source_verification_pending=scan_findings['requires_coordinator_verification'])
        if state.get('status') == 'approved' and not audit.get('verified'):
            state['review_status'] = 'approved'
            state['status'] = 'needs_source_evidence'
        elif state.get('status') == 'approved' and scan_findings['requires_coordinator_verification']:
            state['review_status'] = 'approved'
            state['status'] = 'needs_source_verification'
        editorial.write(output_job / 'status.json', state)
        editorial.write(output_job / 'attention_repair_result.json', {
            'status': state.get('status'), 'character': character,
            'article_hash': editorial.digest(candidate), 'dossier_hash': editorial.digest(final_dossier),
            'reviews': editorial.read(output_job / 'reviews.json') if (output_job / 'reviews.json').is_file() else [],
            'source_audit_hash': editorial.digest(audit), 'source_audit_verified': audit.get('verified'),
            'source_findings_pending': scan_findings['requires_coordinator_verification'],
            'publication_performed': False, 'issue_sync_performed': False,
        })
        return state
    except BaseException as exc:
        editorial.write(output_job / 'attention_repair_failure.json', {
            'status': 'failed', 'prior_job': str(prior_job), 'error': str(exc)})
        raise
    finally:
        for handle in (new_lock, old_lock, claim):
            if handle is not None:
                fcntl.flock(handle, fcntl.LOCK_UN)
                handle.close()


def run_many(jobs, output_root, registry_path, root=source_enrichment.ROOT,
             workers=3, agents=24, timeout=1200, max_revisions=3, edit_scopes=None,
             source_id=None):
    registry = source_enrichment._source_registry(Path(registry_path))
    if not source_id:
        sources = registry.get('sources', [])
        if len(sources) != 1:
            raise ValueError('Specify --source when the registry contains multiple books')
        source_id = sources[0].get('id')
    source = source_enrichment._source(registry, source_id)
    slots = AgentSlots(Path(root) / 'runs/.locks/agent-slots', agents)
    def submit(prior):
        prior = Path(prior)
        character = editorial.read(prior / 'source.json')['character']
        output = Path(output_root) / source['id'] / f'{ord(character):04X}'
        runner = editorial.Runner(copy.deepcopy(editorial.DEFAULT_COMMAND), 'gpt-6-luna', timeout, 'low')
        runner.agent_slots = slots
        scopes = edit_scopes or {}
        return run_one(prior, output, source, runner, root=root, max_revisions=max_revisions,
                       allowed_edit_paths=scopes.get(character))
    results = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(submit, job) for job in jobs]
        for future in as_completed(futures):
            try:
                results.append(future.result())
            except Exception as exc:
                results.append({'status': 'failed', 'error': str(exc)})
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--registry', type=Path, default=source_enrichment.ROOT / 'research/digitised-sources.json')
    parser.add_argument('--source', help='Registered source ID; required for multi-source registries')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--root', type=Path, default=source_enrichment.ROOT)
    parser.add_argument('--workers', type=int, default=3)
    parser.add_argument('--agents', type=int, default=24)
    parser.add_argument('--timeout', type=int, default=1200)
    parser.add_argument('--max-revisions', type=int, default=3)
    parser.add_argument('--edit-scopes', type=Path,
                        help='Optional JSON object mapping characters to precise allowed article paths')
    parser.add_argument('jobs', nargs='+', type=Path)
    args = parser.parse_args()
    scopes = editorial.read(args.edit_scopes) if args.edit_scopes else None
    result = run_many(args.jobs, args.output, args.registry, args.root,
                      args.workers, args.agents, args.timeout, args.max_revisions, scopes, args.source)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
