"""Japanese editorial adaptation with audited Chinese evidence reuse and separate publication."""
from __future__ import annotations
import argparse
import copy
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from pathlib import Path
import shutil
from pipeline import editorial

ROOT = editorial.ROOT
JAPANESE_POLICY = '''Write an English-language etymology entry for a JAPANESE learner, about the
Japanese graph named in this dossier. The historical graph may originate in China, but current
Japanese readings and senses are separate research questions. The source_reuse packet is a
reviewed prior Chinese research starting point, not an approved Japanese article. Consult local
sources AND external Japanese dictionary references; verify citations before transferring claims.
Use authoritative Japanese dictionaries (Kanjipedia, KANJIDIC2/JMdict, scholarly sources) for
Japanese readings and senses, and Cultural Affairs form tables for documented form conventions.
Write independently. Reuse supported historical facts, source records and exact-graph glyphs;
In initial Japanese research, use at most 6 distinct search queries and 12 page opens. If a
named essential question remains, use at most 3 additional queries and 6 opens. Do not browse
every compound linked from a character page: verify character-level readings, meanings and required historical claims.
do not transfer modern Chinese usage, meaning history, Mandarin learner sound comparisons or
components from a different graph. Inspect prior_analysis as a lead and correct it where needed.
For shinjitai, distinguish the Japanese current form, kyujitai, and simplified Chinese; similarity
alone is not proof of shared reform history. A counterpart's images remain explicitly scoped to
that counterpart. Do not infer a Japanese-created character merely from its absence in Chinese.
Read Japanese dictionary form labels precisely: 本字 refers to an original/full graph, 旧字
to an older Japanese form, and 教育用漢字 to the educational current form. An analysis under
the current headword may explicitly describe 本字 instead. Do not assign its absent elements
to the current graph or to a different abbreviated form. Track the subject of each sentence,
including pronouns and omitted subjects. Scope component roles and sound comparisons to the
actual graph analyzed. A current component breakdown needs visible current components, not
an inventory from a historical predecessor. Keep old analyses in expert discussion.
Learner overview starts with useful Japanese meaning and a sourced logical current component
split. Learner cards must cover each component marked current_form_component=true exactly once.
Mark expert-only historical analyses false even when scope_character equals the Japanese entry;
absent or null retains the legacy scope-based rule. Historical-only component cards are optional
and usually belong in the expert explanation; do not expand the quick learner split merely to
cover every detailed historical component. This flag does not change evidence, roles, scopes or edges.
Keep ancient Chinese sound roles separate from Japanese on/kun readings. A Chinese
phonetic role need not predict a kun reading. If comparing Japanese on readings, provide supported
component and host readings; matching current readings alone do not prove historical phonetic
formation. Mandarin comparisons belong only in clearly labeled expert historical context when
actually useful, never as the Japanese learner default.
Include language="ja" and japanese_usage: a cited character-level summary and selected
reading notes using reading, type (on/kun/special), text and evidence_ids. Select only readings
that help explain this character; do not require every reading or both on and kun.
Do not produce vocabulary cards, word examples, compound glosses or a lesson for each reading.
Put useful Japanese meaning context in learner overview and meaning_history, and relevant
sound comparisons in component sound records. On readings reflect Chinese borrowing; inherited
Chinese phonetic components concern historical Chinese sounds, not native Japanese kun words.
Use supported Japanese on comparisons when helpful; modern matching readings alone do not
prove ancient formation. Kun readings normally associate Japanese words with the graph by
meaning. Cite reading and meaning claims and only supported transmission details.
Meaning_history distinguishes early graph/Chinese word history from established Japanese uses;
do not invent a continuous semantic path between them. Inspect Japanese attestations where
available and record gaps. Write neutral reader prose; bibliography specifics stay in citations.
Reviewers must evaluate the Japanese adaptation, character meanings and sounds, form scopes, reuse provenance
and all ordinary factual/readability gates independently. An approved Chinese entry is not a
Japanese approval.'''

JAPANESE_POLICY += "\nHiragana and katakana spellings of the same reading are equivalent. " \
    "Historical scoped components may explain a specific change or sound role; " \
    "do not demand exhaustive decomposition of ancillary historical graphs.\n"

JAPANESE_POLICY += "\nFor a sourced standardized abbreviation, use derived for the current " \
    "formation when that describes its relationship to the older whole graph. Describe the " \
    "older graph's formation separately. For a visibly preserved component, historical role " \
    "plus sourced whole-form standardization can support a qualified inference of continuity " \
    "(probable graph certainty); it need not be declared completely unknowable. Distinguish " \
    "preserved components from replaced strokes: do not carry an old role into a replacement " \
    "without supporting evidence. Judge role, text, scope and certainty together.\n"


JAPANESE_POLICY += "\nSynthesize a coherent sourced explanation rather than enumerating every " \
    "source assertion. Include materially competing analyses where omitting them would " \
    "overstate certainty, but do not require every dossier claim in the article or every " \
    "alternative theory in each glyph caption or learner paragraph. An expert account can " \
    "carry those alternatives while a concise caption identifies the relevant visible form.\n"


JAPANESE_POLICY += "\nAn edge whose predicate ends in _component_of must target the host " \
    "that actually contains that component, matching its scope_character. A replacement " \
    "component belongs to the new host containing the replacement, not to the older host " \
    "containing the replaced form. Keep the replaced form in origin metadata or a separate " \
    "supported form relationship. Do not demand a graph edge that violates this contract.\n"


JAPANESE_POLICY += "\nAn unresolved historical pathway does not make visible current " \
    "component identity unknowable: current IDS supports graphic identity, not ancient function. " \
    "Archived word examples are legacy data, not requirements for new writing.\n"

JAPANESE_POLICY += "\nFor a separate historical variant, briefly explain its relation in " \
    "history and retain the cited variant_of character relationship for crosslinking. " \
    "Put that variant's own component breakdown and sound comparisons in its separate " \
    "entry. Keep components of the current graph and essential ancestral-form changes " \
    "in the current entry; do not expand it into a full account of a sibling variant.\n"


class JapaneseRunner(editorial.Runner):
    profile_policy = JAPANESE_POLICY
    def run(self, role, inputs, schema, directory):
        inputs = {**inputs, 'japanese_editorial_instructions': JAPANESE_POLICY}
        if 'article' in inputs and inputs.get('dossier', {}).get('source_reuse'):
            # The Chinese draft is useful at creation, but a second complete article
            # in later review packets can be mistaken for the current Japanese draft.
            inputs = copy.deepcopy(inputs)
            inputs['dossier']['source_reuse'].pop('prior_analysis', None)
        if role in ('factual', 'readability') and 'article' in inputs:
            inputs['current_article_index'] = {
                'language': inputs['article'].get('language'),
                'has_japanese_usage': bool(inputs['article'].get('japanese_usage')),
                'selected_reading_count': len(inputs['article'].get('japanese_usage', {}).get('readings', [])),
                'learner_component_indices': [c['component_index'] for c in inputs['article'].get('learner', {}).get('components', [])],
                'components': [{'component_index': i, 'form': c['form'],
                    'scope_character': c.get('scope_character', inputs['article']['character']),
                    'current_form_component': c.get('current_form_component'),
                    'roles': c['roles']}
                    for i, c in enumerate(inputs['article']['components'])],
                'instruction': 'Review inputs.article only. Use current_form_component when '
                    'present; false marks expert-only history even at the entry scope and absent/null '
                    'retains the old scope rule. Learner cards cover current members. Parent Chinese prose '
                    'is not the current draft.'}
        if role in ('writer', 'editor', 'revision'):
            schema = copy.deepcopy(schema)
            schema['properties'].update(language={'type':'string','const':'ja'},
                                        japanese_usage=editorial.CHARACTER_JAPANESE_USAGE)
            schema['required'] += ['language', 'japanese_usage']
        if role in ('editor', 'revision') and 'article' in inputs:
            return editorial.apply_article_patch(role, inputs, schema, directory, super().run)
        return super().run(role, inputs, schema, directory)


def prepare(character, root=ROOT):
    root = Path(root)
    local = None
    with (root/'output/kanji_etymology.jsonl').open(encoding='utf-8') as stream:
        for line in stream:
            record=json.loads(line)
            if record['character']==character:
                local=record; break
    if local is None:
        raise ValueError(f'No Japanese local record for {character}')
    # Exact graph only. Related graph mappings remain source leads, never silent equivalence.
    source=root/'content/entries'/f'{ord(character):04X}.json'
    if source.exists():
        entry=editorial.read(source)
        current=editorial.read(root/'content/dossiers'/source.name)
        prior=editorial.validate_published(entry, current)
        packet=copy.deepcopy(entry['dossier'])
        packet['source_reuse']={'same_graph':True, 'language':'zh',
            'entry_path':str(source.relative_to(root)),
            'article_hash':editorial.digest(prior), 'dossier_hash':editorial.digest(current),
            'prior_analysis':prior,
            'reuse_scope':'Cited historical research and reviewed exact-graph glyph candidates only; Japanese adaptation requires fresh research and independent review.'}
    else:
        # Pull imported excerpts without mutating the Chinese dossiers directory.
        packet={'character':character,'evidence':[], 'context':{}}
        chinese=root/'content/dossiers'/f'{ord(character):04X}.json'
        if chinese.exists():
            packet=copy.deepcopy(editorial.read(chinese))
        packet['source_reuse']={'same_graph':False,
            'reuse_scope':'Imported/source dossier leads only; no approved exact-graph Chinese entry.'}
    context=packet.setdefault('context',{})
    context['target_language']='ja'
    context['japanese_local_record']=local
    context['japanese_editorial_instructions']=JAPANESE_POLICY
    context['provenance']=context.get('provenance','Local source leads, not independently verified facts.')+' Japanese adaptation retains Chinese source record identities; Japanese metadata requires lexical verification.'
    # Imported Japanese metadata is explicitly not an external-source research receipt.
    packet['evidence'].append({'id':'JA-local-'+f'{ord(character):04X}',
        'source':'KANJIDIC2 and kanji-data via build_kanji', 'field':'Japanese local readings and definition',
        'text':json.dumps({'readings':local.get('readings'), 'definition':local.get('definition')},ensure_ascii=False),
        'record_character':character, 'kind':'imported_metadata'})
    editorial.validate_dossier(packet)
    return packet


def publish_job(job, root=ROOT):
    job,root=Path(job),Path(root)
    state=editorial.read(job/'status.json')
    if state['status']!='approved':
        raise ValueError('Only independently approved Japanese jobs may be published')
    article,dossier,reviews=[editorial.read(job/n) for n in ('article.json','dossier.json','reviews.json')]
    if article.get('language')!='ja':
        raise ValueError('Refusing non-Japanese entry in Japanese publication')
    editorial.validate_reviews(article,dossier,reviews)
    content=root/'content/ja'
    retained=content/'editorial_runs'/f'{ord(article["character"]):04X}'/editorial.digest(article)
    for path in job.rglob('*'):
        if path.is_file() and path.suffix in ('.json','.txt') and 'attempts' not in path.relative_to(job).parts:
            target=retained/path.relative_to(job); target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(path,target)
    result=editorial.publish(article,dossier,reviews,content/'entries')
    editorial.write(content/'provenance'/result.name,{'job':str(job.resolve()),
        'source_reuse':{k:v for k,v in dossier.get('source_reuse',{}).items() if k!='prior_analysis'},
        'article_hash':editorial.digest(article),'dossier_hash':editorial.digest(dossier)})
    return result


def ready(character, root=ROOT):
    root=Path(root)
    name=f'{ord(character):04X}.json'
    entry_path=root/'content/ja/entries'/name
    dossier_path=root/'content/ja/dossiers'/name
    if not entry_path.exists() or not dossier_path.exists(): return False
    try:
        entry,dossier=editorial.read(entry_path),editorial.read(dossier_path)
        article=editorial.validate_published(entry,dossier)
        if article.get('language')!='ja': return False
        reuse=dossier.get('source_reuse',{})
        if reuse.get('same_graph'):
            source=root/reuse['entry_path']
            source_dossier=editorial.read(root/'content/dossiers'/source.name)
            original=editorial.validate_published(editorial.read(source),source_dossier)
            if (editorial.digest(original)!=reuse['article_hash']
                    or editorial.digest(source_dossier)!=reuse['dossier_hash']): return False
        return True
    except (OSError,ValueError,KeyError,editorial.ValidationError):
        return False


def process(character, output, max_revisions=3, research_context=None):
    if ready(character):
        return {'character':character,'status':'approved','reused_publication':True}
    job=Path(output)/f'{ord(character):04X}'
    if (job/'status.json').exists():
        state=editorial.read(job/'status.json')
        if state['status']=='approved':
            if (ROOT/'content/ja/entries'/f'{ord(character):04X}.json').exists():
                raise ValueError('Existing Japanese approval needs refresh; use a new run directory to avoid replacing a later revision with an older cached job')
            publish_job(job); return {'character':character,'status':'approved','reused_job':True}
        if state['status']=='running':
            raise ValueError(f'Job appears active: {job}; inspect its process before restarting')
    packet=prepare(character)
    runner=JapaneseRunner(editorial.DEFAULT_COMMAND,'gpt-6-luna',600,'low')
    state=editorial.run(packet,job,runner,max_revisions,research_context={
        'task':'Research and author the Japanese adaptation. Preserve valid historical evidence; investigate Japanese readings, usage, form history and character-level sound relationships.',
        'reuse_existing_glyph_candidates':packet['source_reuse']['same_graph'], **(research_context or {})})
    if state['status']=='approved': publish_job(job)
    return {'character':character,'status':state['status'],'job':str(job)}


def repair(character, output, feedback=None):
    """Resume a terminal unapproved job through the same independent gates."""
    source=Path(output)/f'{ord(character):04X}'
    candidates=[p.parent for p in source.rglob('status.json')
                if (p.parent/'article.json').exists() and (p.parent/'dossier.json').exists()]
    if candidates:
        source=max(candidates,key=lambda p:(p/'status.json').stat().st_mtime_ns)
    state=editorial.read(source/'status.json')
    if state['status']=='running':
        raise ValueError('Inspect the running process before repairing an active job')
    article,dossier=[editorial.read(source/n) for n in ('article.json','dossier.json')]
    if feedback is None:
        reviews=editorial.read(source/'reviews.json')
        findings=[finding for review in reviews for finding in review.get('findings',[])]
        if not findings:
            validations=sorted(source.glob('round-*/validation.json'),key=lambda p:int(p.parent.name.split('-')[-1]))
            if validations: findings=editorial.read(validations[-1]).get('findings',[])
        try: editorial.validate_article(article,dossier)
        except (ValueError,editorial.ValidationError) as exc: findings.append(str(exc))
        if not findings: raise ValueError('No repair findings; supply an explicit feedback file')
        feedback={'findings':findings}
    ordinal=1
    while (source/f'repair-{ordinal}').exists(): ordinal+=1
    job=source/f'repair-{ordinal}'
    runner=JapaneseRunner(editorial.DEFAULT_COMMAND,'gpt-6-luna',600,'low')
    result=editorial.refine(article,dossier,job,runner,3,feedback,research_first=False)
    if result['status']=='approved': publish_job(job)
    return {'character':character,'status':result['status'],'job':str(job)}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['prepare','run','repair'])
    parser.add_argument('--characters',default='日学国気生聞')
    parser.add_argument('--output',type=Path,default=ROOT/'runs/jlpt-n5-smoke')
    parser.add_argument('--concurrency',type=int,default=6)
    parser.add_argument('--feedback',type=Path,help='Optional explicit findings for repair')
    parser.add_argument('--research-context',type=Path,help='Optional focused questions/source leads for initial research')
    args=parser.parse_args()
    characters=list(dict.fromkeys(args.characters))
    if not 1<=args.concurrency<=20: parser.error('Concurrency must be 1..20')
    args.output.mkdir(parents=True,exist_ok=True)
    status_path=args.output/('repair-batch-status.json' if args.action=='repair' else 'batch-status.json')
    if args.action=='prepare':
        for c in characters:
            p=prepare(c); editorial.write(args.output/f'{ord(c):04X}'/'prepared-dossier.json',p)
            print(c,'Chinese research reuse:',p['source_reuse']['same_graph'])
        return
    results=[]
    with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        feedback=editorial.read(args.feedback) if args.feedback else None
        context=editorial.read(args.research_context) if args.research_context else None
        futures={pool.submit(repair,c,args.output,feedback) if args.action=='repair'
                 else pool.submit(process,c,args.output,3,context):c for c in characters}
        editorial.write(status_path,{'status':'running','characters':characters,'results':results})
        for future in as_completed(futures):
            try: result=future.result()
            except Exception as exc: result={'character':futures[future],'status':'failed','error':str(exc)}
            results.append(result); print(json.dumps(result,ensure_ascii=False),flush=True)
            editorial.write(status_path,{'status':'running','characters':characters,'results':results})
    editorial.write(status_path,{'status':'completed','characters':characters,'results':results})

if __name__=='__main__': main()
