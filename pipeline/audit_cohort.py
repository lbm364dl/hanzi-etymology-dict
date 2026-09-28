"""Snapshot cohort publication, production receipts, assets and rendered data coverage.

This is an integrity audit, not a substitute for the independent content reviews.
Run again after the final publication and site build; a live run is only a checkpoint.
"""
import argparse
from datetime import datetime, timezone
import gzip
import hashlib
import json
from pathlib import Path

from pipeline import editorial


def audit(cohort, site_path, root=editorial.ROOT, graph_path=None):
    root = Path(root)
    site = {row['c']: row.get('article') for row in
            json.loads(gzip.decompress(Path(site_path).read_bytes()))}
    graph = editorial.read(graph_path or root / 'output/editorial-graph.json')
    nodes = {node['id'] for node in graph['nodes']}
    edges = {}
    for edge in graph['edges']:
        edges.setdefault(edge['entry_character'], []).append(edge)
    rows = []
    for character in cohort['characters']:
        row = {'character': character, 'errors': []}
        name = f'{ord(character):04X}.json'
        try:
            entry = editorial.read(root / 'content/entries' / name)
            dossier = editorial.read(root / 'content/dossiers' / name)
            article = editorial.validate_published(entry, dossier)
            if article.get('schema_version') != 2 or not article.get('learner'):
                raise ValueError('Missing structured learner entry')
            reviewers = [r['reviewer'] for r in entry['review']['reviews']]
            if not all(r.startswith('gpt-6-luna:low:') for r in reviewers):
                row['errors'].append('Production reviewer model differs from Luna low')
            if not dossier.get('external_research', {}).get('search_audit'):
                row['errors'].append('Missing external research audit')
            if not article['meaning_history']['senses']:
                row['errors'].append('Missing meaning history senses')
            for asset in dossier.get('glyph_assets', []):
                path = Path(asset['path'])
                if not path.is_absolute():
                    path = root / path
                if not path.exists() or hashlib.sha256(path.read_bytes()).hexdigest() != asset['sha256']:
                    row['errors'].append(f"Missing or changed glyph asset: {asset['glyph_id']}")
            rendered = site.get(character)
            if not rendered:
                row['errors'].append('Missing site article')
            elif editorial.digest(editorial.extract_article(rendered)) != editorial.digest(article):
                row['errors'].append('Stale site article')
            if rendered:
                displayed = rendered.get('display_glyphs', {})
                for asset in dossier.get('glyph_assets', []):
                    relative = displayed.get(asset['glyph_id'])
                    path = Path(site_path).parent / relative if relative else None
                    if (path is None or not path.exists() or
                            hashlib.sha256(path.read_bytes()).hexdigest() != asset['sha256']):
                        row['errors'].append(f"Missing or changed site glyph: {asset['glyph_id']}")
            exported = edges.get(character, [])
            expected_ids = {character + ':' + relation['id'] for relation in article['relationships']}
            if (character not in graph['entries'] or len(exported) != len(expected_ids) or
                    {edge['id'] for edge in exported} != expected_ids):
                row['errors'].append('Missing or stale graph relationships')
            evidence = {item['id']: item for item in dossier['evidence']}
            for edge in exported:
                if (edge['article_hash'] != entry['review']['article_hash'] or
                        edge['dossier_hash'] != entry['review']['dossier_hash']):
                    row['errors'].append('Stale graph review hashes')
                    break
                if edge['subject'] not in nodes or edge['object'] not in nodes:
                    row['errors'].append('Missing graph endpoint')
                if not edge['evidence_ids'] or any(
                        evidence.get(item['id']) != item for item in edge['evidence']):
                    row['errors'].append('Missing or mismatched exported graph evidence')
                if {item['id'] for item in edge['evidence']} != set(edge['evidence_ids']):
                    row['errors'].append('Incomplete exported graph citations')
            row.update(article_hash=entry['review']['article_hash'],
                       dossier_hash=entry['review']['dossier_hash'], reviewers=reviewers,
                       glyph_count=len(article['historical_glyphs']['items']),
                       sense_count=len(article['meaning_history']['senses']),
                       relationship_count=len(article['relationships']))
        except (OSError, ValueError, KeyError, editorial.ValidationError) as exc:
            row['errors'].append(str(exc))
        rows.append(row)
    return {'checked_at': datetime.now(timezone.utc).isoformat(),
            'cohort': cohort['id'], 'count': len(rows),
            'integrity_pass': all(not row['errors'] for row in rows),
            'limitation': 'Integrity and coverage only; independent content and visual reviews remain required.',
            'rows': rows}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cohort', type=Path, default=editorial.ROOT / 'content/cohorts/hsk3-2021-level-1.json')
    parser.add_argument('--site', type=Path, default=editorial.ROOT / 'docs/data.json.gz')
    parser.add_argument('--graph', type=Path, default=editorial.ROOT / 'output/editorial-graph.json')
    parser.add_argument('--output', type=Path, default=editorial.ROOT / 'output/hsk1-integrity-audit.json')
    args = parser.parse_args()
    result = audit(editorial.read(args.cohort), args.site, graph_path=args.graph)
    editorial.write(args.output, result)
    failures = [row for row in result['rows'] if row['errors']]
    print(f"{result['count'] - len(failures)}/{result['count']} entries pass snapshot integrity")
    for row in failures:
        print(row['character'], '; '.join(row['errors']))
    return int(bool(failures))


if __name__ == '__main__':
    raise SystemExit(main())
