"""Audit a whole cohort across source-job locations using current publication gates."""
import argparse
from pathlib import Path

from pipeline import editorial, source_enrichment as se


def report(cohort, source, job_roots, root=se.ROOT):
    selected = set(cohort['characters'])
    candidates = {}
    errors = []
    for location in job_roots:
        for snapshot_path in sorted(Path(location).glob('**/source.json')):
            try:
                snapshot = editorial.read(snapshot_path)
                if not isinstance(snapshot, dict):
                    raise ValueError('Source snapshot must be an object')
                character = snapshot.get('character')
                if (snapshot.get('source_id') != source['id'] or character not in selected
                        or snapshot_path.parent.name != f'{ord(character):04X}'):
                    continue
                candidates.setdefault(character, set()).add(snapshot_path.parent.resolve())
            except (OSError, ValueError, TypeError) as exc:
                errors.append({'snapshot': str(snapshot_path), 'error': str(exc)})
    rows = []
    for character in cohort['characters']:
        observed = []
        for job in sorted(candidates.get(character, set())):
            try:
                state = editorial.read(job / 'status.json')
                row = {'job': str(job), 'recorded_status': state.get('status', 'unknown'),
                       'verified_source_completion': se._published_matches(job, source, root)}
            except (OSError, ValueError, KeyError) as exc:
                row = {'job': str(job), 'recorded_status': 'unverified',
                       'verified_source_completion': False, 'verification_error': str(exc)}
            observed.append(row)
        rows.append({'character': character,
                     'verified_source_completion': any(j['verified_source_completion'] for j in observed),
                     'jobs': observed})
    return {'source_id': source['id'], 'characters_total': len(rows),
            'verified_source_complete': sum(r['verified_source_completion'] for r in rows),
            'scope': 'Entire selected cohort; only current exact source/publication gates count, not legacy approvals.',
            'scan_errors': errors, 'characters': rows}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--registry', type=Path, required=True)
    parser.add_argument('--source', required=True)
    parser.add_argument('--cohort', type=Path, required=True)
    parser.add_argument('--job-root', type=Path, action='append')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    source = next(s for s in editorial.read(args.registry)['sources'] if s['id'] == args.source)
    result = report(se.load_cohort(args.cohort), source,
                    args.job_root or [se.ROOT / 'runs', se.ROOT / 'content/source_coverage'])
    editorial.write(args.output, result)
    print(f"Verified source-complete: {result['verified_source_complete']}/{result['characters_total']}; scan errors: {len(result['scan_errors'])}")


if __name__ == '__main__':
    main()
