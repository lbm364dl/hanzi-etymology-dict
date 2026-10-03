"""Publish evidence-backed findings to GitHub with stable deduplication markers."""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
import subprocess

from pipeline import editorial

FINDING_SCHEMA = {'type': 'object', 'additionalProperties': False, 'required': ['findings'],
    'properties': {'findings': {'type': 'array', 'items': {
        'type': 'object', 'additionalProperties': False,
        'required': ['topic', 'existing_key', 'kind', 'title', 'details', 'verification', 'evidence'],
        'properties': {'topic': {'type': 'string', 'pattern': '^[a-z0-9][a-z0-9-]*$'}, 'existing_key': {'type': ['string', 'null']},
            'kind': {'enum': ['ocr', 'factual', 'readability', 'pipeline', 'clarification']},
            **{k: {'type': 'string', 'minLength': 1} for k in ('title', 'details', 'verification')},
            'evidence': {'type': 'array', 'items': {'type': 'string'}}}}}}}


def triage_job(job, source, runner):
    """Use a separate Luna low agent to turn actual findings into issue records."""
    import re
    job = Path(job)
    if runner.model != 'gpt-6-luna' or runner.reasoning != 'low':
        raise ValueError('Finding triage requires gpt-6-luna low')
    state = editorial.read(job / 'status.json')
    records = []
    for path in sorted(job.rglob('*.json')):
        relative = path.relative_to(job)
        if any(part in ('attempts', 'finding-triage', 'issue-bodies') or part.startswith('finding-triage-repair-') for part in relative.parts):
            continue
        if path.name in ('verified-review.json', 'validation.json', 'source-enrichment-failure.json'):
            records.append({'artifact': str(relative), 'content': editorial.read(path)})
        elif path.name == 'result.json' and ('research' in path.parent.name):
            product = editorial.read(path)
            if isinstance(product, dict) and 'search_audit' in product:
                records.append({'artifact': str(relative), 'content': {
                    'search_audit': product.get('search_audit', []), 'gaps': product.get('gaps', [])}})
    reviews_path = job / 'reviews.json'
    if reviews_path.is_file():
        records.append({'artifact': 'reviews.json', 'content': editorial.read(reviews_path)})
    known_path = editorial.ROOT / 'research/source-enrichment-findings.json'
    known = editorial.read(known_path)['findings'] if known_path.is_file() else []
    character = state.get('character') or editorial.read(job / 'source.json')['character']
    # Character findings cannot be reused merely because another entry has the
    # same failure class. Keep genuinely shared pipeline/source findings available.
    def in_scope(finding):
        if finding.get('kind') == 'work':
            return False  # Umbrella work items are parents, never reusable findings.
        pieces = finding['key'].split(':', 2)
        if len(pieces) < 3:
            return True
        host = pieces[1]
        if re.fullmatch(r'[0-9A-Fa-f]{4,6}', host):
            codepoint = int(host, 16)
            host = chr(codepoint) if codepoint <= 0x10ffff else host
        if len(host) == 1 and ord(host) > 127:
            return pieces[0] == source['id'] and host == character
        return True
    known = [finding for finding in known if in_scope(finding)]
    current_article = editorial.read(job / 'article.json') if (job / 'article.json').is_file() else None
    dossier_path = job / 'dossier.json'
    current_dossier = editorial.read(dossier_path) if dossier_path.is_file() else None
    # A review mentions evidence IDs, not their source contents. Triage must see
    # the actual support before calling a repaired claim an unresolved gap.
    packet_text = json.dumps([current_article, records], ensure_ascii=False)
    evidence_packet = None if current_dossier is None else {
        'character': current_dossier.get('character'),
        'dossier_hash': editorial.digest(current_dossier),
        'evidence': [e for e in current_dossier.get('evidence', [])
                     if re.search(r'(?<![\w-])' + re.escape(e['id']) + r'(?![\w-])', packet_text)]}
    inputs = {'character': character, 'source': source, 'job_state': state,
              'actual_findings': records, 'existing_findings': known,
              'current_article': current_article, 'current_dossier_evidence': evidence_packet,
              'task': 'Track material findings with evidence. Rejected proposals are not factual errors. '
                      'An OCR suspicion needs source verification; never guess a replacement. '
                      'Return no finding for correctly supported current prose, a resolved '
                      'review disagreement, or advice to preserve a correct treatment in '
                      'future edits. Identify a concrete current defect or unapplied repair. '
                      'Umbrella work issues are tracking parents, not finding identities. '
                      'Keep public issue text concise and paraphrase books instead of quoting passages.'}
    known_by_key = {f["key"]: f for f in known}
    schema = copy.deepcopy(FINDING_SCHEMA)
    schema["properties"]["findings"]["items"]["properties"]["existing_key"]["enum"] = [None, *known_by_key]
    for attempt in range(3):
        stage = job / ('finding-triage' if attempt == 0 else f'finding-triage-repair-{attempt}')
        try:
            result = runner.run('finding_triage', inputs, schema, stage)
            if any(item.get('existing_key') is not None and item['existing_key'] not in known_by_key
                   for item in result['findings']):
                raise ValueError('Triage selected an unknown existing finding key; choose a supplied key or null for a new finding')
            break
        except (ValueError, editorial.ValidationError) as exc:
            if attempt == 2:
                raise
            inputs = {**inputs, 'validation_error': str(exc),
                      'repair_task': 'Repair only the invalid issue-record contract. Topic must be a lowercase English slug without source prefixes, colons or Han characters. Keep the actual evidence and scope.'}
    findings = []
    known_by_key = {f['key']: f for f in known}
    for item in result['findings']:
        existing_key = item.get('existing_key')
        if existing_key:
            if existing_key not in known_by_key:
                raise ValueError('Triage selected an unknown existing finding key')
            key = existing_key
        else:
            if not re.fullmatch(r'[a-z0-9][a-z0-9-]*', item['topic']):
                raise ValueError('Finding topic must be a stable lowercase identifier')
            key = f"{source['id']}:{character}:{item['topic']}"
        finding = {k: item[k] for k in ('kind', 'title', 'details', 'verification', 'evidence')}
        finding['key'] = key
        if source.get('tracking_issue_url'):
            finding['evidence'].append('Parent work: ' + source['tracking_issue_url'])
        validate_finding(finding)
        if not any(f['key'] == key for f in findings):
            findings.append(finding)
    editorial.write(job / 'issue_findings.json', {'findings': findings})
    return findings


def gh(*args):
    result = subprocess.run(['gh', *args], check=True, text=True, capture_output=True)
    return result.stdout.strip()


def validate_finding(finding):
    for key in ('key', 'kind', 'title', 'details', 'verification'):
        if not isinstance(finding.get(key), str) or not finding[key].strip():
            raise ValueError(f'Finding requires {key}')
    if '\n' in finding['key'] or '-->' in finding['key']:
        raise ValueError('Invalid finding identity')
    if finding['kind'] not in ('work', 'ocr', 'factual', 'readability', 'pipeline', 'clarification'):
        raise ValueError('Unknown finding kind')


def marker(finding):
    return '<!-- hanzi-finding:' + finding['key'] + ' -->'


def body(finding):
    validate_finding(finding)
    evidence = finding.get('evidence', [])
    text = f"{marker(finding)}\n\n{finding['details']}\n\n"
    if evidence:
        text += 'Evidence and affected artifacts:\n\n' + '\n'.join('- ' + item for item in evidence) + '\n\n'
    text += 'Verification required:\n\n' + finding['verification'] + '\n'
    return text


def _paginated_items(raw):
    """gh api --paginate emits consecutive JSON arrays on older CLI versions."""
    items = []
    decoder = json.JSONDecoder()
    while raw.strip():
        raw = raw.lstrip()
        page, end = decoder.raw_decode(raw)
        if not isinstance(page, list):
            raise ValueError('Expected a GitHub list response')
        items.extend(page)
        raw = raw[end:]
    return items


def sync(findings, repository, receipt_path, invoke=gh, parent_issue=None, milestone=None, labels=(), parent_by_kind=None,
         active_findings=False):
    """Create missing issues; preserve human discussion and never close by inference."""
    if not repository or len(repository.split('/')) != 2:
        raise ValueError('Repository must be owner/name')
    findings = list(findings)
    for finding in findings:
        validate_finding(finding)
    if len({finding['key'] for finding in findings}) != len(findings):
        raise ValueError('Duplicate finding keys')
    existing = json.loads(invoke('issue', 'list', '--repo', repository, '--state', 'all',
                                 '--limit', '1000', '--json', 'number,url,body,state,labels,milestone'))
    parents = set((parent_by_kind or {}).values()) | ({parent_issue} if parent_issue is not None else set())
    child_numbers = {parent: {item['number'] for item in _paginated_items(
        invoke('api', '--paginate', f'repos/{repository}/issues/{parent}/sub_issues'))} for parent in parents}
    if labels or parent_issue is not None:
        expected = set(labels) | {'kind:' + finding['kind'] for finding in findings}
        present = {item['name'] for item in json.loads(invoke('label', 'list', '--repo', repository,
                                                             '--limit', '1000', '--json', 'name'))}
        for label in sorted(expected - present):
            invoke('label', 'create', label, '--repo', repository, '--color', 'bfd4f2',
                   '--description', 'Source enrichment finding classification')
    receipts = []
    for finding in findings:
        target_parent = (parent_by_kind or {}).get(finding['kind'], parent_issue)
        created = False
        matches = [item for item in existing if marker(finding) in item.get('body', '')]
        if len(matches) > 1:
            raise ValueError('Duplicate GitHub issue markers require reconciliation')
        if matches:
            issue = matches[0]
            if active_findings and issue['state'].upper() == 'CLOSED':
                invoke('issue', 'reopen', str(issue['number']), '--repo', repository)
                issue['state'] = 'OPEN'
            # Preserve the original issue and discussion; append new evidence once.
            if issue.get('body', '').strip() != body(finding).strip():
                update_marker = '<!-- hanzi-finding-update:' + editorial.digest(finding) + ' -->'
                discussion = json.loads(invoke('issue', 'view', str(issue['number']), '--repo',
                                               repository, '--json', 'comments'))
                if not any(update_marker in c.get('body', '') for c in discussion.get('comments', [])):
                    target = Path(receipt_path).parent / 'issue-bodies' / (editorial.digest(finding) + '.md')
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_text(update_marker + '\n\nFinding update:\n\n' + body(finding))
                    invoke('issue', 'comment', str(issue['number']), '--repo', repository,
                           '--body-file', str(target))
        else:
            target = Path(receipt_path).parent / 'issue-bodies' / (editorial.digest(finding['key']) + '.md')
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(body(finding))
            url = invoke('issue', 'create', '--repo', repository, '--title', finding['title'],
                         '--body-file', str(target))
            issue = {'url': url, 'number': int(url.rstrip('/').split('/')[-1]), 'state': 'OPEN',
                     'body': body(finding)}
            existing.append(issue)
            created = True
        if labels or parent_issue is not None or milestone:
            args = ['issue', 'edit', str(issue['number']), '--repo', repository]
            present_labels = {item['name'] for item in issue.get('labels', [])}
            for label in sorted(set([*labels, 'kind:' + finding['kind']]) - present_labels):
                args.extend(['--add-label', label])
            current_milestone = issue.get('milestone') or {}
            same_milestone = str(milestone) in {
                str(current_milestone.get('title')), str(current_milestone.get('number'))}
            if milestone and issue['number'] != parent_issue and not same_milestone:
                args.extend(['--milestone', str(milestone)])
            if len(args) > 5:
                invoke(*args)
        attach = target_parent is not None and issue['number'] != target_parent and issue['number'] not in child_numbers[target_parent]
        if attach and not created:
            try:
                existing_parent = json.loads(invoke('api', f"repos/{repository}/issues/{issue['number']}/parent"))
            except subprocess.CalledProcessError as exc:
                if '404' not in (exc.stderr or ''):
                    raise
                existing_parent = None
            # Preserve a hierarchy curated by the user; new issues get configured parents.
            if existing_parent:
                attach = False
        if attach:
            if len(child_numbers[target_parent]) >= 100:
                raise ValueError(f'GitHub parent #{target_parent} has 100 direct subissues; '
                                 'configure a nested findings parent and retry the existing '
                                 'issue marker without duplicating the finding')
            remote = json.loads(invoke('api', f"repos/{repository}/issues/{issue['number']}"))
            invoke('api', '--method', 'POST', f'repos/{repository}/issues/{target_parent}/sub_issues',
                   '-F', f"sub_issue_id={remote['id']}")
            child_numbers[target_parent].add(issue['number'])
        receipts.append({'key': finding['key'], 'kind': finding['kind'], 'url': issue['url'],
                         'number': issue['number'], 'state': issue['state'],
                         'finding_hash': editorial.digest(finding)})
        # Checkpoint immediately so interrupted syncs can be recovered by marker lookup.
        editorial.write(receipt_path, {'repository': repository, 'issues': receipts})
    return receipts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('findings', type=Path, help='JSON document containing a findings array')
    parser.add_argument('--repo', required=True)
    parser.add_argument('--receipts', type=Path, required=True)
    parser.add_argument('--parent', type=int, help='GitHub parent issue number')
    parser.add_argument('--milestone', help='GitHub milestone title or number')
    parser.add_argument('--label', action='append', default=[])
    args = parser.parse_args()
    records = editorial.read(args.findings)['findings']
    print(json.dumps(sync(records, args.repo, args.receipts, parent_issue=args.parent,
                          milestone=args.milestone, labels=args.label), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
