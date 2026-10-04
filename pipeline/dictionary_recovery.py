"""Publish a reviewed dictionary improvement while retaining a failed book hold.

This is a deliberately narrow continuation path: it requires a current exact
approved pair, a completed book citation author who found every consulted book
record unsupported, and no pending source findings. The book job stays held.
"""
from __future__ import annotations

import argparse
import fcntl
import json
import shutil
from pathlib import Path

from pipeline import attention_repair, batch, editorial, source_enrichment
from pipeline.agent_slots import AgentSlots


def _exclusive_lock(path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = path.open('a')
    try:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError as exc:
        handle.close()
        raise ValueError(f'Dictionary recovery resource is already locked: {path}') from exc
    return handle


def _candidate_claims(article):
    claims = {}
    def visit(value, parts=()):
        if isinstance(value, dict):
            if 'evidence_ids' in value:
                claims['/'.join(map(str, (*parts, 'evidence_ids')))] = {
                    'claim': {key: item for key, item in value.items() if key != 'evidence_ids'},
                    'evidence_ids': value['evidence_ids']}
            for key, item in value.items():
                if key != 'historical_glyphs':
                    visit(item, (*parts, key))
        elif isinstance(value, list):
            for index, item in enumerate(value):
                visit(item, (*parts, index))
    visit(article)
    return claims


def _json_publication_receipt(value):
    if isinstance(value, Path):
        return {'canonical_entry': str(value)}
    if isinstance(value, dict):
        # Validate nested values before persisting a receipt that the CLI returns.
        json.dumps(value)
        return value
    return {'result': str(value)}


def _unsupported_book_result(parent: Path) -> dict:
    audit = editorial.read(parent / 'source_audit.json')
    consulted = audit.get('consulted_citations')
    if audit.get('verified') is not False or not isinstance(consulted, list) or not consulted:
        raise ValueError('Dictionary-only recovery requires a failed audit with consulted book records')
    stage = parent / 'citation-integration' / 'citation-author'
    meta_path, result_path = stage / 'meta.json', stage / 'result.json'
    if not meta_path.is_file() or not result_path.is_file():
        raise ValueError('Completed citation-author result is required')
    meta, result = editorial.read(meta_path), editorial.read(result_path)
    if (meta.get('status') != 'complete' or meta.get('role') != 'book_citation'
            or meta.get('model') != 'gpt-6-luna' or meta.get('reasoning') != 'low'
            or meta.get('result_hash') != editorial.digest(result)
            or not isinstance(meta.get('fingerprint'), str) or not meta['fingerprint']
            or not isinstance(meta.get('agent_thread_ids'), list) or not meta['agent_thread_ids']):
        raise ValueError('Citation-author receipt is not a genuine completed Luna-low result')
    prompt_path = stage / 'prompt.txt'
    completion_path = parent / 'citation-integration' / 'completion.json'
    if not prompt_path.is_file() or not completion_path.is_file():
        raise ValueError('Citation-author prompt and no-op completion receipt are required')
    prompt = prompt_path.read_text(encoding='utf-8')
    try:
        inputs_text = prompt.split('INPUTS:\n', 1)[1].split('\nCOMMON SENSE-STATUS CONTRACT:', 1)[0]
        inputs = json.loads(inputs_text)
    except (IndexError, json.JSONDecodeError) as exc:
        raise ValueError('Citation-author prompt does not contain parseable frozen JSON inputs') from exc
    article, dossier = editorial.read(parent / 'article.json'), editorial.read(parent / 'dossier.json')
    audit_records = audit['consulted_citations']
    if (inputs.get('candidate_claims') != _candidate_claims(article)
            or inputs.get('current_book_records') != audit_records
            or inputs.get('retained_evidence') != dossier.get('evidence')):
        raise ValueError('Citation-author inputs do not bind the current exact article, dossier and book audit')
    completion = editorial.read(completion_path)
    if (completion.get('status') != 'unchanged'
            or completion.get('article_hash') != editorial.digest(article)
            or completion.get('dossier_hash') != editorial.digest(dossier)
            or completion.get('reviews_reused') is not True
            or completion.get('source_adoption_verified') is not False):
        raise ValueError('Citation integration did not record an exact unchanged-pair source hold')
    evidence_ids = {eid for record in consulted for eid in record.get('evidence_ids', [])}
    unsupported = {item.get('evidence_id') for item in result.get('unsupported_records', [])}
    if not evidence_ids or not evidence_ids <= unsupported:
        raise ValueError('Citation author did not establish that every consulted book record is unsupported')
    return {'audit_hash': editorial.digest(audit), 'consulted_evidence_ids': sorted(evidence_ids),
            'author_result_hash': editorial.digest(result), 'author_meta_hash': editorial.digest(meta)}


def _check_parent(parent: Path, root: Path, allowed_published_pair=None) -> tuple[dict, dict, dict, dict, list, dict]:
    state = editorial.read(parent / 'status.json')
    if state.get('status') != 'needs_source_evidence':
        raise ValueError('Parent must remain needs_source_evidence')
    if source_enrichment._source_findings_pending(parent):
        raise ValueError('Unresolved source findings block dictionary-only publication')
    source = editorial.read(parent / 'source.json')
    source_article = editorial.read(parent / 'source_article.json')
    source_dossier = editorial.read(parent / 'source_dossier.json')
    if (editorial.digest(source_article) != source.get('article_hash')
            or editorial.digest(source_dossier) != source.get('dossier_hash')):
        raise ValueError('Parent frozen canonical snapshots are altered')
    canonical_article, canonical_dossier = source_enrichment._canonical(root, source['character'])
    baseline_matches = (editorial.digest(canonical_article) == source.get('article_hash')
                        and editorial.digest(canonical_dossier) == source.get('dossier_hash'))
    published_pair_matches = (allowed_published_pair is not None
        and editorial.digest(canonical_article) == editorial.digest(allowed_published_pair[0])
        and editorial.digest(canonical_dossier) == editorial.digest(allowed_published_pair[1]))
    if not baseline_matches and not published_pair_matches:
        raise ValueError('Canonical baseline drifted since the source job')
    article, dossier = editorial.read(parent / 'article.json'), editorial.read(parent / 'dossier.json')
    reviews = editorial.read(parent / 'reviews.json')
    editorial.validate_article(article, dossier)
    editorial.validate_reviews(article, dossier, reviews)
    if (state.get('review_status') != 'approved'
            or state.get('source_audit_hash') != editorial.digest(editorial.read(parent / 'source_audit.json'))):
        raise ValueError('Parent review or source audit is not current')
    proof = _unsupported_book_result(parent)
    return state, source, article, dossier, reviews, proof


def recover(parent_job, output_job, *, root=editorial.ROOT, agents=3, max_revisions=2,
            runner=None, publish=True):
    """Run fresh dictionary reviews, then publish through the ordinary batch gate."""
    parent, output, root = Path(parent_job).resolve(), Path(output_job).resolve(), Path(root).resolve()
    if agents < 1:
        raise ValueError('Agent capacity must be positive')
    lock_dir = root / 'runs' / '.locks'
    preliminary_source = editorial.read(parent / 'source.json')
    source_claim = lock_dir / f"source-{source_enrichment._research_source_hash(preliminary_source['registry_source'])[:16]}-{ord(preliminary_source['character']):04X}.lock"
    claim_lock = _exclusive_lock(source_claim)
    parent_lock = output_lock = None
    try:
        parent_lock = _exclusive_lock(parent / 'coordinator.lock')
        output_lock = _exclusive_lock(output / 'coordinator.lock')
        had_job_source = (output / 'source.json').is_file()
        allowed_published_pair = None
        scope_path = output / 'publication_scope.json'
        if scope_path.is_file():
            scope = editorial.read(scope_path)
            if (scope.get('scope') != 'dictionary_improvement_only' or scope.get('source_adoption') is not False
                    or scope.get('parent') != str(parent)):
                raise ValueError('Existing recovery scope does not match this parent')
            if all((output / name).is_file() for name in ('article.json', 'dossier.json', 'reviews.json', 'status.json')):
                prior_candidate = editorial.read(output / 'article.json')
                prior_dossier = editorial.read(output / 'dossier.json')
                prior_reviews = editorial.read(output / 'reviews.json')
                prior_status = editorial.read(output / 'status.json')
                current_article, current_dossier = source_enrichment._canonical(root, prior_candidate.get('character'))
                completion_path = output / 'recovery_completion.json'
                completion = editorial.read(completion_path) if completion_path.is_file() else {}
                receipt_matches = (completion.get('status') == 'published'
                    and completion.get('parent') == str(parent)
                    and completion.get('article_hash') == editorial.digest(prior_candidate)
                    and completion.get('dossier_hash') == editorial.digest(prior_dossier)
                    and completion.get('reviews_hash') == editorial.digest(prior_reviews)
                    and isinstance(completion.get('publication_receipt'), dict))
                if (receipt_matches and prior_status.get('status') in {'approved', 'published'}
                        and editorial.digest(current_article) == editorial.digest(prior_candidate)
                        and editorial.digest(current_dossier) == editorial.digest(prior_dossier)):
                    editorial.validate_reviews(prior_candidate, prior_dossier, prior_reviews)
                    allowed_published_pair = (prior_candidate, prior_dossier)
        state, source, article, dossier, reviews, proof = _check_parent(parent, root, allowed_published_pair)
        output.mkdir(parents=True, exist_ok=True)
        marker = output / 'publication_scope.json'
        if marker.exists():
            saved = editorial.read(marker)
            if saved.get('parent') != str(parent) or saved.get('baseline') != source.get('article_hash', '') + ':' + source.get('dossier_hash', ''):
                raise ValueError('Existing recovery output belongs to another baseline')
        elif any(path.name != 'coordinator.lock' for path in output.iterdir()):
            raise ValueError('Output directory is not empty and has no recovery identity')
        job_source = output / 'source.json'
        if not job_source.exists():
            shutil.copy2(parent / 'source.json', job_source)
            shutil.copy2(parent / 'source_article.json', output / 'source_article.json')
            shutil.copy2(parent / 'source_dossier.json', output / 'source_dossier.json')
            retained = attention_repair._retain_research(parent, output)
            editorial.write(marker, {
                'scope': 'dictionary_improvement_only', 'source_adoption': False,
                'parent': str(parent), 'source_parent_job': str(parent),
                'parent_status': state['status'], 'source_parent_status': state['status'],
                'baseline': source['article_hash'] + ':' + source['dossier_hash'],
                'book_evidence_disposition': proof, 'retained_research': retained,
            })
        if marker.exists() and (output / 'article.json').is_file() and (output / 'dossier.json').is_file() \
                and (output / 'reviews.json').is_file() and (output / 'status.json').is_file():
            current_article, current_dossier = source_enrichment._canonical(root, source['character'])
            candidate = editorial.read(output / 'article.json')
            candidate_dossier = editorial.read(output / 'dossier.json')
            candidate_reviews = editorial.read(output / 'reviews.json')
            candidate_state = editorial.read(output / 'status.json')
            if (candidate_state.get('status') in {'approved', 'published'}
                    and editorial.digest(current_article) == editorial.digest(candidate)
                    and editorial.digest(current_dossier) == editorial.digest(candidate_dossier)):
                editorial.validate_reviews(candidate, candidate_dossier, candidate_reviews)
                if allowed_published_pair is not None:
                    return {'status': 'published', 'job': str(output), 'idempotent': True, 'published': True}
        if had_job_source:
            prior_status = editorial.read(output / 'status.json').get('status') if (output / 'status.json').is_file() else None
            if prior_status != 'approved':
                raise ValueError(f'Existing recovery attempt is {prior_status!r}; preserve it and use a fresh output directory')
            candidate = editorial.read(output / 'article.json')
            candidate_dossier = editorial.read(output / 'dossier.json')
            candidate_reviews = editorial.read(output / 'reviews.json')
            editorial.validate_reviews(candidate, candidate_dossier, candidate_reviews)
            if not publish:
                return {'status': 'approved', 'job': str(output), 'published': False, 'resumed': True}
            publication = batch.publish_job(output, root)
            publication_receipt = _json_publication_receipt(publication)
            editorial.write(output / 'recovery_completion.json', {
                'status': 'published', 'parent': str(parent),
                'article_hash': editorial.digest(candidate),
                'dossier_hash': editorial.digest(candidate_dossier),
                'reviews_hash': editorial.digest(candidate_reviews),
                'publication_receipt': publication_receipt,
            })
            return {'status': 'published', 'job': str(output), 'publication': publication_receipt,
                    'resumed': True, 'parent_status_unchanged': editorial.read(parent / 'status.json') == state}
        runner = runner or editorial.Runner(editorial.DEFAULT_COMMAND, 'gpt-6-luna', 600, 'low')
        if getattr(runner, 'model', None) != 'gpt-6-luna' or getattr(runner, 'reasoning', None) != 'low':
            raise ValueError('Dictionary recovery requires gpt-6-luna with low reasoning')
        runner.agent_slots = AgentSlots(root / 'runs' / '.locks' / 'agent-slots', agents)
        runner.profile_policy = source_enrichment.SOURCE_POLICY
        runner.inherited_lock_fds = tuple(dict.fromkeys((*getattr(runner, 'inherited_lock_fds', ()),
                                                         claim_lock.fileno(), parent_lock.fileno(), output_lock.fileno())))
        feedback = {
            'reuse_existing_glyph_candidates': True,
            'task': ('Review this researched dictionary improvement. The parent scholarly-book '
                     'enrichment remains held because the completed citation author found every '
                     'consulted book record unsupported for article claims. Do not force those '
                     'citations or claim source adoption. Check every actual claim against the '
                     'active evidence supplied and make only evidence-supported edits.'),
        }
        final_state = editorial.refine(article, dossier, output, runner, max_revisions,
                                       feedback=feedback, edit_first=False)
        if final_state.get('status') != 'approved':
            return {'status': final_state.get('status'), 'job': str(output), 'published': False}
        if publish:
            publication = batch.publish_job(output, root)
            publication_receipt = _json_publication_receipt(publication)
            editorial.write(output / 'recovery_completion.json', {
                'status': 'published', 'parent': str(parent),
                'article_hash': editorial.digest(editorial.read(output / 'article.json')),
                'dossier_hash': editorial.digest(editorial.read(output / 'dossier.json')),
                'reviews_hash': editorial.digest(editorial.read(output / 'reviews.json')),
                'publication_receipt': publication_receipt,
            })
            return {'status': 'published', 'job': str(output), 'publication': publication_receipt,
                    'parent_status_unchanged': editorial.read(parent / 'status.json') == state}
        return {'status': 'approved', 'job': str(output), 'published': False}
    finally:
        for handle in (output_lock, parent_lock, claim_lock):
            if handle is not None:
                fcntl.flock(handle, fcntl.LOCK_UN)
                handle.close()


def repair_published(parent_job, output_job, review_context, *, root=editorial.ROOT,
                     agents=3, max_revisions=2, runner=None, publish=True):
    """Freshly review a published dictionary-only entry with explicit feedback."""
    parent, output, root = Path(parent_job).resolve(), Path(output_job).resolve(), Path(root).resolve()
    if not isinstance(review_context, dict) or not review_context:
        raise ValueError('Published dictionary repair requires a nonempty review context object')
    if agents < 1:
        raise ValueError('Agent capacity must be positive')
    scope_path = parent / 'publication_scope.json'
    if not scope_path.is_file():
        raise ValueError('Parent is not marked as a dictionary-only publication')
    parent_scope = editorial.read(scope_path)
    if (parent_scope.get('scope') != 'dictionary_improvement_only'
            or parent_scope.get('source_adoption') is not False):
        raise ValueError('Parent publication must preserve the dictionary-only source hold')
    source = editorial.read(parent / 'source.json')
    registered_source = source.get('registry_source')
    if not isinstance(registered_source, dict) or not registered_source.get('id'):
        raise ValueError('Parent source snapshot has no registered source identity')
    source_id = registered_source['id']
    character = source.get('character')
    if not isinstance(character, str) or len(character) != 1:
        raise ValueError('Parent source snapshot has no valid character identity')

    lock_dir = root / 'runs' / '.locks'
    claim_path = lock_dir / f"source-{source_enrichment._research_source_hash(registered_source)[:16]}-{ord(character):04X}.lock"
    claim_lock = _exclusive_lock(claim_path)
    parent_lock = output_lock = None
    try:
        parent_lock = _exclusive_lock(parent / 'coordinator.lock')
        output_lock = _exclusive_lock(output / 'coordinator.lock')
        state = editorial.read(parent / 'status.json')
        if state.get('status') not in {'approved', 'published'}:
            raise ValueError('Parent dictionary entry must be approved or published')
        if source_enrichment._source_findings_pending(parent):
            raise ValueError('Unresolved source findings block published dictionary repair')
        article = editorial.read(parent / 'article.json')
        dossier = editorial.read(parent / 'dossier.json')
        reviews = editorial.read(parent / 'reviews.json')
        editorial.validate_article(article, dossier)
        editorial.validate_reviews(article, dossier, reviews)
        if article.get('character') != character:
            raise ValueError('Parent article character differs from its source snapshot')
        canonical_article, canonical_dossier = source_enrichment._canonical(root, character)
        if (editorial.digest(article) != editorial.digest(canonical_article)
                or editorial.digest(dossier) != editorial.digest(canonical_dossier)):
            raise ValueError('Parent reviewed pair does not match the current canonical dictionary entry')
        if (state.get('article_hash') and state['article_hash'] != editorial.digest(article)
                or state.get('dossier_hash') and state['dossier_hash'] != editorial.digest(dossier)):
            raise ValueError('Parent status hashes do not bind its exact reviewed pair')
        output.mkdir(parents=True, exist_ok=True)
        if any(path.name != 'coordinator.lock' for path in output.iterdir()):
            raise ValueError('Published-entry repair requires a fresh output directory')

        # Freeze the actual current canonical pair. The parent may have been
        # published from an older source snapshot, which must not be relabeled.
        fresh_source = source_enrichment.prepare_job(character, output, registered_source, root)
        if (fresh_source.get('article_hash') != editorial.digest(canonical_article)
                or fresh_source.get('dossier_hash') != editorial.digest(canonical_dossier)):
            raise ValueError('Fresh repair baseline differs from the current canonical pair')
        retained = attention_repair._retain_research(parent, output)
        editorial.write(output / 'publication_scope.json', {
            'scope': 'dictionary_improvement_only', 'source_adoption': False,
            'parent': str(parent), 'source_parent_job': str(parent),
            'source_parent_status': state['status'],
            'baseline': fresh_source['article_hash'] + ':' + fresh_source['dossier_hash'],
            'review_context': review_context, 'review_context_hash': editorial.digest(review_context),
            'reason': 'Fresh reviews of a published dictionary entry; no scholarly-book adoption is claimed.',
            'retained_research': retained,
        })
        runner = runner or editorial.Runner(editorial.DEFAULT_COMMAND, 'gpt-6-luna', 600, 'low')
        if getattr(runner, 'model', None) != 'gpt-6-luna' or getattr(runner, 'reasoning', None) != 'low':
            raise ValueError('Published dictionary repair requires gpt-6-luna with low reasoning')
        runner.agent_slots = AgentSlots(lock_dir / 'agent-slots', agents)
        runner.profile_policy = source_enrichment.SOURCE_POLICY
        runner.inherited_lock_fds = tuple(dict.fromkeys((*getattr(runner, 'inherited_lock_fds', ()),
                                                         claim_lock.fileno(), parent_lock.fileno(), output_lock.fileno())))
        feedback = {
            'reuse_existing_glyph_candidates': True,
            'additional_research_context': review_context,
            'additional_context_policy': (
                'The supplied review context is a finding to check against the exact current article and '
                'dossier, not an approval or a command to accept a claim. Correct only what the cited '
                'evidence supports. The parent scholarly-book enrichment remains held; do not claim or '
                'imply book-source adoption.'),
            'task': ('Review and repair the current published dictionary entry against the explicit '
                     'review context and its active evidence. Keep supported content, evidence IDs, '
                     'scope and uncertainty intact. Do not claim scholarly-book source adoption.'),
        }
        final_state = editorial.refine(article, dossier, output, runner, max_revisions,
                                       feedback=feedback, research_first=False, edit_first=True)
        if final_state.get('status') != 'approved':
            return {'status': final_state.get('status'), 'job': str(output), 'published': False}
        if not publish:
            return {'status': 'approved', 'job': str(output), 'published': False}
        publication = batch.publish_job(output, root)
        receipt = _json_publication_receipt(publication)
        editorial.write(output / 'recovery_completion.json', {
            'status': 'published', 'parent': str(parent),
            'article_hash': editorial.digest(editorial.read(output / 'article.json')),
            'dossier_hash': editorial.digest(editorial.read(output / 'dossier.json')),
            'reviews_hash': editorial.digest(editorial.read(output / 'reviews.json')),
            'publication_receipt': receipt,
        })
        return {'status': 'published', 'job': str(output), 'publication': receipt,
                'parent_status_unchanged': editorial.read(parent / 'status.json') == state}
    finally:
        for handle in (output_lock, parent_lock, claim_lock):
            if handle is not None:
                fcntl.flock(handle, fcntl.LOCK_UN)
                handle.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--parent', type=Path, required=True, help='needs_source_evidence source job')
    parser.add_argument('--output', type=Path, required=True, help='fresh recovery job directory')
    parser.add_argument('--root', type=Path, default=editorial.ROOT)
    parser.add_argument('--agents', type=int, default=3, help='shared agent slot capacity')
    parser.add_argument('--max-revisions', type=int, default=2)
    parser.add_argument('--no-publish', action='store_true')
    parser.add_argument('--repair-published', action='store_true',
                        help='Repair an already published dictionary-only parent')
    parser.add_argument('--review-context', type=Path,
                        help='JSON review findings required with --repair-published')
    args = parser.parse_args(argv)
    if args.repair_published:
        if args.review_context is None:
            parser.error('--repair-published requires --review-context JSON')
        context = editorial.read(args.review_context)
        result = repair_published(args.parent, args.output, context, root=args.root,
                                  agents=args.agents, max_revisions=args.max_revisions,
                                  publish=not args.no_publish)
    else:
        if args.review_context is not None:
            parser.error('--review-context is only used with --repair-published')
        result = recover(args.parent, args.output, root=args.root, agents=args.agents,
                         max_revisions=args.max_revisions, publish=not args.no_publish)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
