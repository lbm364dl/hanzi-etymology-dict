"""Apply source-verified, evidence-bound OCR corrections without changing raw responses."""
import copy
import hashlib
import json
from pathlib import Path
from PIL import Image
from research_ocr import validate, normalize_prefixed_glyph_ids


def digest(value):
    return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True).encode()).hexdigest()


def load_page_metadata(root, raw):
    """Apply independently observed page metadata without changing OCR evidence."""
    root = Path(root)
    path = root / 'page-metadata.json'
    if not path.exists():
        return raw
    record = json.loads(path.read_text())
    value = record.get('printed_page')
    if (record.get('schema_version') != 1
            or raw.get('printed_page') is not None
            or record.get('source_sha256') != raw['source_sha256']
            or record.get('parent_evidence_sha256') != raw['evidence_sha256']
            or record.get('pdf_page_1based') != raw['pdf_page_1based']
            or not ((type(value) is int and value >= 0)
                    or (isinstance(value, str) and value.strip()))):
        raise ValueError('Page metadata requires exact source, raw evidence and page identity')
    with Image.open(root / 'source.png') as image:
        if hashlib.sha256(image.convert('RGB').tobytes()).hexdigest() != raw['source_sha256']:
            raise ValueError('Page metadata source pixels changed')
    review = record['review']
    result = json.loads(Path(review['result_path']).read_text())
    meta = json.loads(Path(review['meta_path']).read_text())
    canonical = hashlib.sha256(json.dumps(result, ensure_ascii=False, sort_keys=True,
                                         separators=(',', ':')).encode()).hexdigest()
    binding = json.loads(Path(review['binding_path']).read_text())
    key = review['finding_key']
    observations = [o for o in result.get('metadata_observations', []) if o['key'] == key]
    checks = [c for c in binding.get('metadata_checks', []) if c['key'] == key]
    dispositions = [f for f in result.get('findings', []) if f['key'] == key]
    if (canonical != review['result_hash'] or meta.get('result_hash') != canonical
            or binding.get('result_hash') != canonical
            or meta.get('status') != 'complete' or meta.get('role') != 'source_resolution'
            or meta.get('model') != 'gpt-6-luna' or meta.get('reasoning') != 'low'
            or len(observations) != 1 or len(checks) != 1 or len(dispositions) != 1
            or observations[0].get('observed_value') != str(value)
            or checks[0].get('expected_value') != str(value)
            or checks[0].get('current_value') is not None
            or checks[0].get('field') != 'printed_page'
            or checks[0].get('pdf_page') != raw['pdf_page_1based']
            or checks[0].get('source_pixel_sha256') != raw['source_sha256']
            or dispositions[0].get('disposition') != 'verified_metadata_not_extracted'):
        raise ValueError('Page metadata requires a matching completed independent scan observation')
    result = copy.deepcopy(raw)
    result['printed_page'] = value
    result['metadata_provenance'] = {**record, 'metadata_sha256': digest(record)}
    return result


def load_effective(root):
    root=Path(root)
    raw=json.loads((root/'ocr.json').read_text())
    evidence={k:raw[k] for k in ('source_sha256','request_cache_key','ocr')}
    if digest(evidence)!=raw['evidence_sha256']:
        raise ValueError('Changed OCR evidence hash')
    normalization=raw.get('response_normalization')
    if normalization:
        if normalization.get('kind')!='strip_glyph_prefix_from_ids' or normalization.get('source_sha256')!=raw['source_sha256']:
            raise ValueError('Invalid response normalization')
        cache=root/'cache'/(raw['request_cache_key']+'.invalid')
        cache_bytes=cache.read_bytes()
        if hashlib.sha256(cache_bytes).hexdigest()!=normalization.get('raw_response_sha256'):
            raise ValueError('Changed normalized model response')
        saved=json.loads(cache_bytes)
        candidate=saved['candidates'][0]
        if candidate.get('finishReason')!='STOP':
            raise ValueError('Incomplete normalized model response')
        original=json.loads(''.join(p.get('text','') for p in candidate['content']['parts'] if not p.get('thought')))
        if normalize_prefixed_glyph_ids(original)!=raw['ocr']:
            raise ValueError('Normalized OCR differs from saved model response')
        with Image.open(root/'source.png') as image:
            if hashlib.sha256(image.convert('RGB').tobytes()).hexdigest()!=raw['source_sha256']:
                raise ValueError('Normalized OCR source pixels changed')
    classification=raw.get('page_classification')
    if classification:
        if classification.get('kind')!='blank_scan' or classification.get('source_sha256')!=raw['source_sha256']:
            raise ValueError('Invalid blank-page classification')
        if raw['ocr']['text'].strip() or raw['ocr']['glyphs']:
            raise ValueError('Blank-page classification contains content')
        cache=root/'cache'/(raw['request_cache_key']+'.invalid')
        if not cache.is_file() or hashlib.sha256(cache.read_bytes()).hexdigest()!=classification.get('raw_response_sha256'):
            raise ValueError('Changed blank-page model response')
        with Image.open(root/'source.png') as image:
            if hashlib.sha256(image.convert('RGB').tobytes()).hexdigest()!=raw['source_sha256']:
                raise ValueError('Blank-page source pixels changed')
    path=root/'ocr-corrections.json'
    if not path.exists():
        validate(raw['ocr'], allow_blank=bool(classification))
        return load_page_metadata(root, raw)
    changes=json.loads(path.read_text())
    if changes.get('parent_evidence_sha256')!=raw['evidence_sha256'] or changes.get('source_sha256')!=raw['source_sha256']:
        raise ValueError('Stale OCR corrections')
    with Image.open(root/'source.png') as image:
        if hashlib.sha256(image.convert('RGB').tobytes()).hexdigest()!=raw['source_sha256']:
            raise ValueError('Correction source pixels changed')
    patches=changes['patches'];text=raw['ocr']['text'];end=0
    for patch in sorted(patches,key=lambda p:p['start']):
        start,stop=patch['start'],patch['end']
        if type(start) is not int or type(stop) is not int or not end<=start<stop<=len(text):
            raise ValueError('Overlapping or invalid correction range')
        if text[start:stop]!=patch['before'] or not patch.get('source_checked') or not patch.get('reason'):
            raise ValueError('Correction anchor/source verification missing')
        if not isinstance(patch['after'],str):
            raise ValueError('Invalid correction replacement')
        end=stop
    for patch in sorted(patches,key=lambda p:p['start'],reverse=True):
        text=text[:patch['start']]+patch['after']+text[patch['end']:]
    result=copy.deepcopy(raw);result['ocr']['text']=text
    removed=set(changes.get('remove_glyph_ids',[]))
    if not removed.issubset({g['id'] for g in raw['ocr']['glyphs']}):
        raise ValueError('Unknown removed glyph ID')
    result['ocr']['glyphs']=[g for g in raw['ocr']['glyphs'] if g['id'] not in removed]
    for edit in changes.get('glyph_description_patches',[]):
        glyph=next((g for g in result['ocr']['glyphs'] if g['id']==edit['id']),None)
        if not glyph or glyph['description']!=edit['before'] or not edit.get('source_checked') or not edit.get('reason'):
            raise ValueError('Glyph description correction anchor/source verification missing')
        glyph['description']=edit['after']
    result['ocr']['glyphs'].extend(copy.deepcopy(changes.get('add_glyphs',[])))
    result['ocr']['uncertainties'].extend(changes.get('added_uncertainties',[]))
    validate(result['ocr'], allow_blank=bool(classification))
    result['original_evidence_sha256']=raw['evidence_sha256']
    result['correction_provenance']={**changes,'corrections_sha256':digest(changes)}
    result['evidence_sha256']=digest({k:result[k] for k in ('source_sha256','request_cache_key','ocr')})
    # Bind metadata to original OCR; text correction evidence remains separate.
    metadata = load_page_metadata(root, raw)
    if 'metadata_provenance' in metadata:
        result['printed_page'] = metadata['printed_page']
        result['metadata_provenance'] = metadata['metadata_provenance']
    return result


def export_corrected(root):
    root=Path(root);result=load_effective(root)
    (root/'reading-corrected.md').write_text(result['ocr']['text']+'\n')
    (root/'ocr-corrected.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
    return result
