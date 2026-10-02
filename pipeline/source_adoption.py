"""Register existing approved book research after an independent source check."""
from pathlib import Path
import copy
import fcntl
import re
import shutil

from pipeline import editorial, source_enrichment as se


def _used_ids(value):
    result = set()
    if isinstance(value, dict):
        result.update(value.get('evidence_ids', []))
        for child in value.values():
            result.update(_used_ids(child))
    elif isinstance(value, list):
        for child in value:
            result.update(_used_ids(child))
    return result


def valid_audit(job, audit, article, dossier):
    job = Path(job)
    try:
        result = editorial.read(job / 'source-coverage/result.json')
        meta = editorial.read(job / 'source-coverage/meta.json')
    except (OSError, ValueError):
        return False
    return (audit.get('article_hash') == editorial.digest(article)
            and audit.get('dossier_hash') == editorial.digest(dossier)
            and audit.get('coverage_result_hash') == editorial.digest(result)
            and meta.get('result_hash') == editorial.digest(result)
            and meta.get('status') == 'complete' and meta.get('role') == 'source_coverage'
            and meta.get('model') == 'gpt-6-luna' and meta.get('reasoning') == 'low'
            and result.get('verdict') == 'pass' and not result.get('findings')
            and bool(result.get('evidence_ids')))


def adopt(character, source, output, runner, root=se.ROOT):
    job = se.job_path(output, source['id'], character)
    job.mkdir(parents=True, exist_ok=True)
    with (job / 'coordinator.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return {'character': character, 'status': 'already_running', 'job': str(job)}
        local_runner = copy.copy(runner)
        local_runner.inherited_lock_fds = (lock.fileno(),)
        return _adopt(character, source, output, local_runner, root)


def _adopt(character, source, output, runner, root):
    """No authorship or publication: preserve the exact already-reviewed content."""
    if runner.model != 'gpt-6-luna' or runner.reasoning != 'low':
        raise ValueError('Source adoption requires gpt-6-luna low')
    root, job = Path(root), se.job_path(output, source['id'], character)
    if se._published_matches(job, source, root):
        return {'character': character, 'status': 'published', 'job': str(job)}
    article, dossier = se._canonical(root, character)
    entry = editorial.read(root / 'content/entries' / f'{ord(character):04X}.json')
    reviews = entry['review']['reviews']
    editorial.validate_reviews(article, dossier, reviews)
    used = _used_ids(article)
    citations = [item for item in dossier['evidence'] if item['id'] in used
                 and source['title'] in item.get('source', '')
                 and re.search(r'(?:PDF|printed).*?\bp\.?\s*\d+|頁\s*\d+|页\s*\d+', item.get('field', ''), re.I)]
    if not citations:
        raise ValueError('No used page-specific evidence from this registered book; research is required')
    if (job / 'status.json').exists() and editorial.read(job / 'status.json')['status'] not in ('prepared', 'needs_source_verification'):
        raise ValueError('Preserve existing source work; adopt into a fresh source job')
    snapshot = se.prepare_job(character, job, source, root)
    if snapshot['article_hash'] != editorial.digest(article) or snapshot['dossier_hash'] != editorial.digest(dossier):
        raise ValueError('Prepared source snapshot does not match current approved content')
    located = se._load_source_tools().locate_sources({'schema_version': 1, 'sources': [source]}, character, dossier)
    if not located.get('source_scan_images'):
        raise ValueError('Independent adoption requires original source scan attachments')
    editorial.write(job / 'article.json', article)
    editorial.write(job / 'dossier.json', dossier)
    editorial.write(job / 'reviews.json', reviews)
    schema = {'type': 'object', 'additionalProperties': False,
              'required': ['verdict', 'evidence_ids', 'findings'], 'properties': {
                  'verdict': {'enum': ['pass', 'revise']},
                  'evidence_ids': {'type': 'array', 'items': {'type': 'string', 'enum': [e['id'] for e in citations]}},
                  'findings': {'type': 'array', 'items': {'type': 'string'}}}}
    result = runner.run('source_coverage', {'character': character, 'source': se._research_source(source),
        'article': article, 'dossier': dossier, 'book_evidence': citations,
        'feedback': {**located, 'source_scan_images': located['source_scan_images']}}, schema, job / 'source-coverage')
    if editorial.read(job / 'source-coverage/result.json') != result:
        raise ValueError('Source check differs from saved actual agent output')
    verified = result['verdict'] == 'pass' and not result['findings'] and bool(result['evidence_ids'])
    audit = {'source_id': source['id'], 'source_hash': se._research_source_hash(source),
             'mode': 'existing_approved_research', 'verified': verified,
             'coverage_result_hash': editorial.digest(result),
             'article_hash': editorial.digest(article), 'dossier_hash': editorial.digest(dossier),
             'citations': [item for item in citations if item['id'] in result['evidence_ids']]}
    editorial.write(job / 'source_audit.json', audit)
    editorial.write(job / 'source-coverage/verified-review.json', result)
    editorial.write(job / 'source_checkpoint.json', {'character': character, 'source_id': source['id'],
        'registry_source_hash': se._research_source_hash(source), 'locator': located,
        'locator_hash': se._locator_hash(located), 'status': 'source_checked'})
    state = {**snapshot, 'article_hash': editorial.digest(article), 'dossier_hash': editorial.digest(dossier),
             'source_audit_hash': editorial.digest(audit), 'locator_hash': se._locator_hash(located),
             'status': 'approved' if verified else 'needs_source_research'}
    editorial.write(job / 'status.json', state)
    if not verified:
        return {'character': character, 'status': state['status'], 'job': str(job), 'findings': result['findings']}
    if not valid_audit(job, audit, article, dossier):
        raise ValueError('Source coverage receipt does not bind the actual completed Luna low check')
    sync = se._triage_and_sync_issues(job, source, runner)
    if sync['status'] not in ('synced', 'not_configured'):
        raise ValueError('Source adoption findings must sync before registration')
    # Do not replace canonical authorship provenance with a bookkeeping check.
    target = root / 'content/source_coverage' / source['id'] / f'{ord(character):04X}'
    for path in job.rglob('*'):
        if path.is_file() and path.suffix in ('.json', '.txt') and 'attempts' not in path.relative_to(job).parts:
            destination = target / path.relative_to(job)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, destination)
    state.update(status='published', issue_sync_status=sync['status'],
                 adoption_artifacts=str(target.relative_to(root)))
    editorial.write(job / 'status.json', state)
    editorial.write(target / 'status.json', state)
    return {'character': character, 'status': 'published', 'job': str(job), 'adoption_artifacts': str(target)}
