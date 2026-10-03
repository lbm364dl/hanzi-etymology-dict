"""Export reviewed editorial relationships, without inferring edges from shapes."""
from __future__ import annotations

import argparse
from pathlib import Path
from pipeline.editorial import ROOT, read, write, validate_published


def export_graph(directory=ROOT / 'content/entries', characters=None):
    nodes, edges, included, legacy = {}, [], [], []
    for path in sorted(Path(directory).glob('*.json')):
        entry = read(path)
        if characters is not None and entry.get('character') not in characters:
            continue
        dossier_path = path.parent.parent / 'dossiers' / path.name
        article = validate_published(entry, read(dossier_path) if dossier_path.exists() else None)
        char = article['character']
        if article.get('schema_version') != 2:
            legacy.append(char)
            continue
        included.append(char)
        evidence = {item['id']: item for item in entry['evidence']}
        senses = {item['id']: item for item in article['meaning_history']['senses']}
        marks = {item['element_id']: item for item in article['components']
                 if item.get('element_kind') == 'noncharacter_mark'}
        for relationship in article['relationships']:
            endpoints = {}
            for side in ('subject', 'object'):
                node = relationship[side]
                key = node['kind'] + ':' + node['id']
                endpoints[side] = key
                if key not in nodes:
                    nodes[key] = {'id': key, 'kind': node['kind'], 'form': node['id']}
                    if node['kind'] == 'component' and node['id'] in marks:
                        mark = marks[node['id']]
                        nodes[key].pop('form')
                        nodes[key].update(element_kind='noncharacter_mark',
                                          display_label=mark['element_label'],
                                          context_character=mark.get('scope_character', char),
                                          character_entry=None)
                    elif node['kind'] == 'sense':
                        nodes[key]['sense'] = senses[node['id']]
                    else:
                        nodes[key]['character_entry'] = node['id'] if len(node['id']) == 1 else None
                if node['kind'] == 'character' and node['id'] == char:
                    nodes[key]['formation'] = article['formation']
                    nodes[key]['components'] = article['components']
                    claims = [article['formation'], *article['components'],
                              *[sound for component in article['components'] for sound in component.get('sound', [])],
                              *[c['sound_limitation'] for c in article['components'] if c.get('sound_limitation')]]
                    used = {id for claim in claims for id in claim['evidence_ids']}
                    nodes[key]['evidence'] = [item for id, item in evidence.items() if id in used]
                    nodes[key]['article_hash'] = entry['review']['article_hash']
                    nodes[key]['dossier_hash'] = entry['review']['dossier_hash']
            sound = []
            sound_limitations = []
            if relationship['predicate'] == 'phonetic_component_of':
                for component in article['components']:
                    if (relationship['subject']['id'] in (component.get('form'), component.get('origin_form'), component.get('element_id'))
                            and relationship['object']['id'] == component.get('scope_character', char)):
                        sound.extend({**comparison, 'evidence': [evidence[id] for id in comparison['evidence_ids']]}
                                     for comparison in component.get('sound', []))
                        if component.get('sound_limitation'):
                            limitation = component['sound_limitation']
                            sound_limitations.append({**limitation, 'evidence': [evidence[id] for id in limitation['evidence_ids']]})
            edges.append({**relationship, 'id': char + ':' + relationship['id'],
                          **endpoints, 'entry_character': char,
                          'sound_comparisons': sound, 'sound_limitations': sound_limitations,
                          'article_hash': entry['review']['article_hash'],
                          'dossier_hash': entry['review']['dossier_hash'],
                          'evidence': [evidence[id] for id in relationship['evidence_ids']]})
    return {'schema_version': 1, 'entries': included, 'legacy_entries_without_graph': legacy,
            'nodes': sorted(nodes.values(), key=lambda n: n['id']),
            'edges': edges}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--entries', type=Path, default=ROOT / 'content/entries')
    parser.add_argument('--characters', help='Optional literal character subset')
    parser.add_argument('--output', type=Path, default=ROOT / 'output/editorial-graph.json')
    args = parser.parse_args()
    graph = export_graph(args.entries, args.characters)
    write(args.output, graph)
    print(f"{len(graph['entries'])} entries, {len(graph['nodes'])} nodes, {len(graph['edges'])} cited relationships: {args.output}")


if __name__ == '__main__':
    main()
