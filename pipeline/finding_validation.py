"""Independently validate current factual/readability issue proposals."""
from __future__ import annotations

from pathlib import Path

from jsonschema import Draft202012Validator, ValidationError

from pipeline import editorial


def _decision_schema(article, dossier, topics):
    return {
        'type': 'object', 'additionalProperties': False,
        'required': ['article_hash', 'dossier_hash', 'findings'],
        'properties': {
            'article_hash': {'type': 'string', 'enum': [editorial.digest(article)]},
            'dossier_hash': {'type': 'string', 'enum': [editorial.digest(dossier)]},
            'findings': {'type': 'array', 'minItems': len(topics), 'maxItems': len(topics),
                'items': {'type': 'object', 'additionalProperties': False,
                    'required': ['topic', 'confirmed', 'reason'],
                    'properties': {
                        'topic': {'type': 'string', 'enum': topics},
                        'confirmed': {'type': 'boolean'},
                        'reason': {'type': 'string', 'minLength': 1},
                    }}},
        },
    }


def validate_proposals(job, proposals, article, dossier, runner):
    """Keep only issue proposals independently confirmed on an exact approved pair.

    This creates a hash-bound decision receipt, never factual/readability review
    receipts or article authorship. Any incomplete, duplicated or unbound agent
    output fails closed so an issue cannot disappear through malformed triage.
    """
    job = Path(job)
    if getattr(runner, 'model', None) != 'gpt-6-luna' or getattr(runner, 'reasoning', None) != 'low':
        raise ValueError('Finding validation requires gpt-6-luna with low reasoning')
    if not isinstance(proposals, list):
        raise ValueError('Issue proposals must be an array')
    if not proposals:
        return []
    topics = []
    for index, proposal in enumerate(proposals):
        if not isinstance(proposal, dict) or not isinstance(proposal.get('topic'), str) or not proposal['topic']:
            raise ValueError(f'Issue proposal {index} requires a nonempty topic')
        topics.append(proposal['topic'])
    if len(topics) != len(set(topics)):
        raise ValueError('Issue proposals contain duplicate topics')

    article_path, dossier_path, reviews_path = (job / 'article.json', job / 'dossier.json', job / 'reviews.json')
    if not all(path.is_file() for path in (article_path, dossier_path, reviews_path)):
        raise ValueError('Finding validation requires the exact approved article, dossier and reviews')
    saved_article, saved_dossier, reviews = [editorial.read(path) for path in
                                             (article_path, dossier_path, reviews_path)]
    if (editorial.digest(saved_article) != editorial.digest(article)
            or editorial.digest(saved_dossier) != editorial.digest(dossier)):
        raise ValueError('Finding validation inputs differ from the job’s current article or dossier')
    editorial.validate_reviews(article, dossier, reviews)

    article_hash, dossier_hash = editorial.digest(article), editorial.digest(dossier)
    schema = _decision_schema(article, dossier, topics)
    inputs = {
        'article': article,
        'dossier': dossier,
        'exact_reviews': reviews,
        'article_hash': article_hash,
        'dossier_hash': dossier_hash,
        'proposals': proposals,
        'validation_policy': (
            'Independently check each proposal against the exact current article, dossier evidence, '
            'and the supplied exact-pair approvals. Confirm only a concrete current factual defect '
            'or readability problem that materially obstructs understanding. Reject resolved, '
            'unsupported, duplicate, superseded, or stylistic-preference requests. Do not invent '
            'new topics or rewrite the entry. This decision does not alter authorship or grant '
            'review approval.'),
    }
    stage = job / 'finding-validation'
    result = runner.run('finding_validation', inputs, schema, stage)
    try:
        Draft202012Validator(schema).validate(result)
    except ValidationError as exc:
        raise ValueError(f'Finding-validation result violates its exact-pair schema: {exc.message}') from exc
    if not isinstance(result, dict) or result.get('article_hash') != article_hash or result.get('dossier_hash') != dossier_hash:
        raise ValueError('Finding-validation result is not bound to the exact article/dossier pair')
    returned = result.get('findings')
    if not isinstance(returned, list) or len(returned) != len(proposals):
        raise ValueError('Finding validation must decide every proposal exactly once')
    returned_topics = [item.get('topic') for item in returned if isinstance(item, dict)]
    if len(returned_topics) != len(returned) or len(set(returned_topics)) != len(returned_topics):
        raise ValueError('Finding validation duplicated or malformed a proposal topic')
    if set(returned_topics) != set(topics):
        raise ValueError('Finding validation omitted or added proposal topics')
    if any(not item['reason'].strip() for item in returned):
        raise ValueError('Finding validation returned an empty explanation')

    meta_path, result_path = stage / 'meta.json', stage / 'result.json'
    if not meta_path.is_file() or not result_path.is_file():
        raise ValueError('Finding-validation runner did not retain its genuine result and metadata')
    meta, saved_result = editorial.read(meta_path), editorial.read(result_path)
    if (saved_result != result or meta.get('status') != 'complete'
            or meta.get('role') != 'finding_validation'
            or meta.get('model') != 'gpt-6-luna' or meta.get('reasoning') != 'low'
            or meta.get('result_hash') != editorial.digest(saved_result)
            or not isinstance(meta.get('fingerprint'), str) or not meta['fingerprint']
            or not isinstance(meta.get('agent_thread_ids'), list) or not meta['agent_thread_ids']):
        raise ValueError('Finding-validation metadata is not a genuine completed Luna-low receipt')

    current_pair_paths = (job / 'article.json', job / 'dossier.json', job / 'reviews.json')
    if not all(path.is_file() for path in current_pair_paths):
        raise ValueError('Exact approved pair disappeared during finding validation')
    current_article, current_dossier, current_reviews = [editorial.read(path) for path in current_pair_paths]
    if (editorial.digest(current_article) != article_hash
            or editorial.digest(current_dossier) != dossier_hash
            or editorial.digest(current_reviews) != editorial.digest(reviews)):
        raise ValueError('Article, dossier or exact reviews changed during finding validation')

    decisions = {item['topic']: item for item in returned}
    confirmed = [proposal for proposal in proposals if decisions[proposal['topic']]['confirmed']]
    editorial.write(stage / 'decision.json', {
        'status': 'complete', 'article_hash': article_hash, 'dossier_hash': dossier_hash,
        'reviews_hash': editorial.digest(reviews), 'proposals_hash': editorial.digest(proposals),
        'result_hash': editorial.digest(saved_result), 'meta_hash': editorial.digest(meta),
        'confirmed_topics': [item['topic'] for item in returned if item['confirmed']],
        'rejected_topics': [item['topic'] for item in returned if not item['confirmed']],
        'confirmed_proposals': confirmed,
        'authorship_changed': False, 'review_approval_created': False,
    })
    return confirmed
