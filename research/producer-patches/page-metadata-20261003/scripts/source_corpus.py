"""Build/query a provisional page-text corpus independently of clean PDF rendering.

Records refer to original page scans and glyph crops. OCR search hits are leads,
not scholarly approval or a substitute for inspecting the cited source page.
"""
import argparse
import hashlib
import json
import re
import tempfile
import fitz
from book_catalog import catalog_entry
from pathlib import Path


def record(root,book):
    root=Path(root).resolve();m=json.loads((root/'manifest.json').read_text());reading=json.loads((root/'reading.json').read_text())
    provenance=reading.get('source_provenance',{})
    if provenance.get('evidence_sha256')!=m['evidence_sha256'] or provenance.get('source_sha256')!=m['source_sha256']:raise ValueError('Stale reading export: '+str(root))
    images={x['id']:x for x in reading['image_occurrences']}
    chunks=[]
    for span in reading['ordered_spans']:
        if span['kind']=='text':chunks.append(span['text'])
        else:
            image=images[span['id']]
            marker='image' if image['kind'] in ('illustration','decorative_mark') else 'glyph'
            chunks.append('['+marker+':'+span['id']+']')
    book_id=book['book_id']
    selection=json.loads((root/'selection.json').read_text()) if (root/'selection.json').exists() else {}
    return {'schema_version':2,'page_id':book_id+f':{m["pdf_page"]:06}','book_id':book_id,
        'source_file':m['source_file'],'source_pdf':selection.get('pdf_path'),
        'pdf_page_1based':m['pdf_page'],'printed_page':m.get('printed_page'),
        'source_sha256':m['source_sha256'],'evidence_sha256':m['evidence_sha256'],
        'ocr_review_status':m['status'],'review_dimensions':{'transcription':m['status'],'layout':json.loads((root/'spatial.json').read_text()).get('status','needs_spatial_review') if (root/'spatial.json').exists() else 'not_requested','glyph_identification':'separate_source_crop_evidence'},'book':book,'entry_metadata':'not_extracted','use':'provisional_research_lead_inspect_original_page',
        'text':''.join(chunks),'source_scan':str(root/'source.png'),
        'reading_json':str(root/'reading.json'),'manifest':str(root/'manifest.json'),'block_anchors':[{'block_id':b['id'],'source_bbox_xyxy':b['source_bbox_xyxy'],'text':''.join(s.get('text','') for p in b['paragraphs'] for s in p['spans'] if s['kind']=='text')} for b in m['blocks']],
        'glyph_assets':[{'id':a['id'],'path':str(root/a['asset']),'sha256':a.get('asset_sha256'),'source_bbox_xyxy':a['source_bbox_xyxy']} for a in m['assets']],
        'uncertainties':reading.get('recognition_uncertainties',[]),'review_queue':m.get('review_queue',[]),
        'spatial_repair_warnings':json.loads((root/'spatial-repair.json').read_text()).get('skipped_repairs',[]) if (root/'spatial-repair.json').exists() else [],
        'review':reading.get('review')}


def fast_record(root,book):
    root=Path(root).resolve()
    from research_corrections import load_effective
    r=load_effective(root)
    from research_ocr import validate
    validate(r['ocr'], allow_blank=bool(r.get('page_classification')))
    evidence={k:r[k] for k in ('source_sha256','request_cache_key','ocr')}
    if hashlib.sha256(json.dumps(evidence,ensure_ascii=False,sort_keys=True).encode()).hexdigest()!=r['evidence_sha256']:raise ValueError('Changed OCR evidence: '+str(root))
    review_path=root/'research-review.json'
    review=json.loads(review_path.read_text()) if review_path.exists() else None
    if review and (review.get('evidence_sha256')!=r.get('original_evidence_sha256',r['evidence_sha256']) or review.get('source_sha256')!=r['source_sha256']):
        raise ValueError('Stale research review: '+str(root))
    findings=review.get('findings',[]) if review else []
    resolved=set(r.get('correction_provenance',{}).get('resolved_finding_indices',[]))
    findings=[{**f,**({'resolution':'source_verified_correction_applied'} if i in resolved else {})} for i,f in enumerate(findings)]
    status='needs_correction' if any(f.get('severity') in ('minor','moderate','major','critical','error') for f in findings if f.get('resolution')!='source_verified_correction_applied') else r['transcription_status']
    return {'schema_version':2,'page_id':book['book_id']+f':{r["pdf_page_1based"]:06}','book_id':book['book_id'],'book':book,
        'source_file':r['source_file'],'source_pdf':r['source_pdf'],'pdf_page_1based':r['pdf_page_1based'],'printed_page':r.get('printed_page'),
        'metadata_provenance':r.get('metadata_provenance'),
        'source_sha256':r['source_sha256'],'evidence_sha256':r['evidence_sha256'],'ocr_review_status':status,
        'review_dimensions':{'transcription':status,'layout':r['layout_status'],'glyph_identification':'page_references_with_unidentified_printed_characters' if any(g.get('kind')=='unidentified_printed_character' for g in r['ocr']['glyphs']) else r['glyph_status']},
        'text':r['ocr']['text'],'source_scan':str(root/'source.png'),'reading_json':str(root/('ocr-corrected.json' if r.get('correction_provenance') or r.get('metadata_provenance') else 'ocr.json')),'manifest':str(root/'ocr.json'),'original_evidence_sha256':r.get('original_evidence_sha256'),'correction_provenance':r.get('correction_provenance'),
        'glyph_assets':[{'id':g['id'],'description':g['description'],'kind':g.get('kind','historical_form'),'path':None,'source_scan':str(root/'source.png'),'source_bbox_xyxy':None} for g in r['ocr']['glyphs']],
        'block_anchors':[],'entry_metadata':'not_extracted','uncertainties':r['ocr']['uncertainties'],'review_queue':findings,'review':review,
        'spatial_repair_warnings':[],'use':'provisional_research_lead_inspect_original_page'}


def build(pages_root,output):
    output=Path(output);output.parent.mkdir(parents=True,exist_ok=True)
    catalog=output.parent/'books.json';book_cache={};rows=[]
    paths=list(Path(pages_root).rglob('manifest.json'))+list(Path(pages_root).rglob('ocr.json'))
    for path in sorted(paths):
        if any(part in ('history','cache') for part in path.relative_to(pages_root).parts):continue
        fast=path.name=='ocr.json'
        if not fast and not (path.parent/'reading.json').exists():continue
        data=json.loads(path.read_text())
        selection=json.loads((path.parent/'selection.json').read_text()) if (path.parent/'selection.json').exists() else {}
        candidates=[data.get('source_pdf'),selection.get('pdf_path'),str(Path(__file__).resolve().parents[1]/data['source_file'])]
        pdf_path=next((str(Path(p).resolve()) for p in candidates if p and Path(p).is_file()),None)
        if not pdf_path:raise ValueError('Original PDF required for stable book identity: '+str(path))
        if pdf_path not in book_cache:
            book=catalog_entry(pdf_path,catalog)
            with fitz.open(pdf_path) as pdf:book['total_pdf_pages']=len(pdf)
            book_cache[pdf_path]=book
        book=book_cache[pdf_path]
        row=fast_record(path.parent,book) if fast else record(path.parent,book)
        row['source_pdf']=pdf_path;rows.append(row)
    if len({r['page_id'] for r in rows})!=len(rows):raise ValueError('Duplicate editions of the same page; choose one page corpus root')
    catalog_data=json.loads(catalog.read_text()) if catalog.exists() else {'schema_version':1,'books':[]}
    for item in catalog_data['books']:
        for book in book_cache.values():
            if book['book_id']==item['book_id']:item['total_pdf_pages']=book['total_pdf_pages']
    catalog.write_text(json.dumps(catalog_data,ensure_ascii=False,indent=2))
    # Readers see the previous complete edition until the rebuild is complete.
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=output.parent,
                                     prefix=output.name + '.', delete=False) as stream:
        pending = Path(stream.name)
        try:
            for row in rows:
                stream.write(json.dumps(row, ensure_ascii=False) + '\n')
            stream.flush()
        except BaseException:
            pending.unlink(missing_ok=True)
            raise
    pending.replace(output)
    return len(rows)


def coverage(corpus):
    groups={}
    with Path(corpus).open() as stream:
        for line in stream:
            r=json.loads(line);b=r.get('book') or {};group=groups.setdefault(r['book_id'],{'book_id':r['book_id'],'processed_pages':set(),'total_pdf_pages':b.get('total_pdf_pages')})
            group['processed_pages'].add(r['pdf_page_1based'])
    result=[]
    for group in groups.values():
        pages=sorted(group.pop('processed_pages'));ranges=[]
        for page in pages:
            if ranges and page==ranges[-1][1]+1:ranges[-1][1]=page
            else:ranges.append([page,page])
        total=group['total_pdf_pages'];complete=total is not None and pages==list(range(1,total+1))
        result.append({**group,'processed_page_count':len(pages),'processed_page_ranges':ranges,'complete':complete})
    return {'books':result,'no_hit_meaning':'No match in processed OCR pages; not evidence that an unprocessed page/book lacks an account.'}


def compact(r,query,position,context):
    excerpt=r['text'][max(0,position-context):position+len(query)+context]
    refs={match[1] for match in re.findall(r'\[(glyph|image):([^\]]+)\]',excerpt)}
    anchors=[a for a in r.get('block_anchors',[]) if query in a['text']]
    dimensions=r.get('review_dimensions',{'transcription':r['ocr_review_status'],'layout':'unknown','glyph_identification':'unknown'})
    return {'page_id':r['page_id'],'book_id':r['book_id'],'book_label':(r.get('book') or {}).get('title') or r.get('source_file',r['book_id']),'pdf_page_1based':r['pdf_page_1based'],'printed_page':r['printed_page'],
        'match_type':'text_mention','entry_metadata':r.get('entry_metadata','not_extracted'),'excerpt':excerpt,
        'anchors':[{'block_id':a['block_id'],'source_bbox_xyxy':a['source_bbox_xyxy'],'precision':'block'} for a in anchors[:3]],
        'source_scan':r['source_scan'],'source_sha256':r['source_sha256'],'evidence_sha256':r['evidence_sha256'],
        'review_dimensions':dimensions,'uncertainty_count':len(r.get('uncertainties',[])),
        'uncertainty_preview':r.get('uncertainties',[])[:2],'glyph_assets':[a for a in r['glyph_assets'] if a['id'] in refs],
        'inspect_page_id':r['page_id'],'use':r['use']}


def search(corpus,query,context=100,limit=10,details=False):
    if not query or limit<1:raise ValueError('Nonempty query and positive limit required')
    count=0
    with Path(corpus).open() as stream:
        for line in stream:
            r=json.loads(line);position=r['text'].find(query)
            if position>=0:
                yield r if details else compact(r,query,position,context)
                count+=1
                if count>=limit:return


def inspect(corpus,page_id):
    with Path(corpus).open() as stream:
        for line in stream:
            record=json.loads(line)
            if record['page_id']==page_id:return record
    raise ValueError('Page ID not present in corpus')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='command',required=True)
    b=sub.add_parser('build');b.add_argument('--pages-root',required=True);b.add_argument('--output',required=True)
    q=sub.add_parser('search');q.add_argument('--corpus',required=True);q.add_argument('--query',required=True);q.add_argument('--limit',type=int,default=10);q.add_argument('--details',action='store_true')
    i=sub.add_parser('inspect');i.add_argument('--corpus',required=True);i.add_argument('--page-id',required=True)
    args=parser.parse_args()
    if args.command=='build':print(json.dumps({'pages':build(args.pages_root,args.output),'output':args.output}))
    elif args.command=='inspect':print(json.dumps(inspect(args.corpus,args.page_id),ensure_ascii=False))
    else:print(json.dumps({'schema_version':2,'query':args.query,'coverage':coverage(args.corpus),'results':list(search(args.corpus,args.query,limit=args.limit,details=args.details))},ensure_ascii=False))
