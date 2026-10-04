"""Conservative routing of explicit contradictory review instructions.

This detects routing signals, never decides whether a claim is true or approves it.
Unstructured prose that cannot be parsed still goes to the planning agent with history.
"""
import re

SENSE_STATUS_POLICY = """COMMON SENSE-STATUS CONTRACT:
current requires evidence of present use in the target language; historical describes a
supported earlier use and does not mean obsolete. earliest_attested describes a supported
use in the earliest documented corpus/period, or explicitly identified as earliest attested.
It does not claim that this sense preceded every other sense, was the original meaning, or
that the spoken word originated then. An old example alone does not establish earliest status;
evidence must connect the use to that earliest corpus/period. Several senses may be coattested.
Uncertain original-meaning proposals and unknown precise inscription dates do not negate a
supported early attestation. Keep original-priority and sense-occurrence claims separate.
Apply this same definition to writing, review, adjudication and revision planning.
"""


def requested_statuses(findings):
    requests = {}
    statuses = r"earliest_attested|historical|current"
    for finding in findings:
        paths = re.findall(r"meaning_history[./]senses(?:\[\d+\]|/\d+|\.\d+)(?:[./]status)?", finding)
        target = re.search(r"\b(?:to|as)\s*[`\"']?(" + statuses + r")\b", finding, re.I)
        if not target or not paths:
            continue
        for path in paths:
            path = re.sub(r"\[(\d+)\]", r"/\1", path).replace('.', '/')
            path = path.removesuffix('/status') + '/status'
            requests.setdefault(path, set()).add(target.group(1).lower())
    return requests


def status_conflicts(review, previous_reviews):
    """Return exact field targets requested differently in earlier genuine reviews."""
    current = requested_statuses(review.get('findings', []))
    previous = {}
    for record in previous_reviews:
        record = record.get('review', record)
        for path, targets in requested_statuses(record.get('findings', [])).items():
            previous.setdefault(path, set()).update(targets)
    return sorted(path for path, targets in current.items()
                  if path in previous and previous[path] - targets)


def consolidated_findings(reviews):
    """Deduplicate exact correction text without erasing either review receipt."""
    result = []
    for review in reviews:
        if review['verdict'] != 'revise':
            continue
        for finding in review['findings']:
            if finding not in result:
                result.append(finding)
    return result


def repeated_fields(review, previous_reviews):
    """Flag explicit paths repeatedly rejected; a signal for a final adjudication."""
    def paths(record):
        return set(re.findall(r"(?:learner|summary|formation|meaning_history|components|relationships)"
                              r"(?:\[\d+\]|[./][A-Za-z_]+|/\d+)+",
                              ' '.join(record.get('findings', []))))
    counts = {}
    for record in previous_reviews:
        for path in paths(record.get('review', record)):
            counts[path] = counts.get(path, 0) + 1
    return sorted(path for path in paths(review) if counts.get(path, 0) >= 2)
