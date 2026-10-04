import copy
import fcntl
import hashlib
import json
from pathlib import Path
import tempfile
import sys
import unittest
from unittest.mock import patch

from pipeline import editorial, source_enrichment
from pipeline.test_editorial import ARTICLE_V2, DOSSIER, GLYPHS, RESEARCH


SOURCE = {"schema_version": 1, "id": "ziyuan-2012", "title": "字源",
          "bibliography": "李學勤主編《字源》 (2012)", "corpus_path": "/corpus/ziyuan.jsonl",
          "producer_root": "/books", "book_id": "ziyuan-2012",
          "availability": "provisional_ocr"}
LOCATED = {"source_leads": [{"source_id": "ziyuan-2012", "page_id": "ziyuan:123",
                             "match_type": "headword_candidate", "text": "木 ..."}],
           "source_scan_images": []}


class LocalSources:
    def load_registry(self, path):
        return {"schema_version": 1, "sources": [SOURCE]}

    def locate_sources(self, source, character, dossier):
        return {**copy.deepcopy(LOCATED), "character": character}


class SourceEnrichmentTests(unittest.TestCase):
    def test_codex_wire_schema_requires_every_nested_object_property(self):
        schema = {'type': 'object', 'additionalProperties': False, 'required': ['rows'],
                  'properties': {'rows': {'type': 'array', 'items': {
                      'type': 'object', 'additionalProperties': False, 'required': ['key'],
                      'properties': {'key': {'type': 'string'}, 'hash': {'type': 'string'}}}}}}
        with self.assertRaisesRegex(ValueError, 'rows.items.*hash'):
            source_enrichment._validate_codex_object_schema(editorial.agent_schema(schema))
        schema['properties']['rows']['items']['required'].append('hash')
        source_enrichment._validate_codex_object_schema(editorial.agent_schema(schema))

    def test_identity_gap_classifier_handles_identity_qualified_by_other_nouns(self):
        for details in ('the printed special component identity is unresolved',
                        'the printed unit identity remains unclear',
                        'its exact Unicode identity is not established',
                        'their exact Unicode identities are not established',
                        'individual specimen identities were not separately checked against cited works',
                        'individual specimen identities or dates were not verified',
                        'this research did not verify individual specimen identities or dates',
                        'the identity and intended scope should be verified',
                        'I did not establish every uncommon printed graph’s Unicode identity or verify its underlying paleographic source.',
                        'small individual glyph forms were not independently identified',
                        'numbered glyph drawings and their identifications were not individually checked',
                        'glyph specimens were not individually interpreted',
                        'doubled forms are not all distinct enough to assign Unicode identities'):
            self.assertEqual(source_enrichment._source_finding_class({'kind': 'ocr', 'details': details}),
                             'identity_gap')
        self.assertEqual(source_enrichment._source_finding_class({'details':
            'No claim is made here that the rare glyph drawings have been individually identified.'}),
            'identity_gap')

    def test_source_finding_classifier_keeps_unresolved_ocr_literals_out_of_identity_lane(self):
        self.assertEqual(source_enrichment._source_finding_class({'kind': 'ocr',
            'details': '[OCR CORRECTION REQUIRED] raw OCR span has no verified replacement'}),
            'transcription_correction')
        self.assertEqual(source_enrichment._source_finding_class({'kind': 'ocr',
            'details': '[SCAN VERIFICATION REQUIRED] raw OCR reads 升; do not use this scalar as confirmed source text'}),
            'transcription_correction')

    def test_explicit_no_replacement_entry_boundary_is_not_a_literal_proposal(self):
        finding = {'kind': 'ocr', 'title': '[OCR CORRECTION REQUIRED] Verify header use',
            'details': ('PDF p. 1106 running-header occurrence 媽 is accurately printed as a header, '
                        'not a headword; the entry text belongs to 姨. No replacement Unicode '
                        'transcription is proposed; issue is entry-boundary classification.')}
        self.assertEqual(source_enrichment._source_finding_class(finding), 'primary_access_gap')
        # Keep the original finding inventory; classification only picks the
        # proper exact-pair resolver lane and does not discard the action marker.
        self.assertIn('[OCR CORRECTION REQUIRED]', finding['title'])

    def test_actual_literal_proposal_wins_over_no_replacement_scope_wording(self):
        finding = {'kind': 'ocr', 'title': '[OCR CORRECTION REQUIRED] Check headword boundary',
            'details': ('The page has a running header, but the proposed source-bound OCR correction '
                        'replaces current 語 with 話 in the quoted phrase. No replacement is proposed '
                        'for the header occurrence itself.')}
        self.assertEqual(source_enrichment._source_finding_class(finding), 'transcription_correction')
        self.assertEqual(source_enrichment._source_finding_class({
            'kind': 'ocr', 'proposed_literal': '話', 'details': 'No replacement transcription is proposed.'}),
            'transcription_correction')

    def test_correct_raw_receipt_is_exactly_bound_and_only_releases_preflight(self):
        from PIL import Image
        from pipeline import ocr_verification

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            job = root / 'job'
            job.mkdir()
            scan = root / 'page.png'
            Image.new('RGB', (12, 16), 'white').save(scan)
            with Image.open(scan) as image:
                pixel_hash = hashlib.sha256(image.convert('RGB').tobytes()).hexdigest()
            scan_file_hash = hashlib.sha256(scan.read_bytes()).hexdigest()
            text = 'prefix 木 suffix'
            source = {'id': 'test-book', 'book_id': 'sha256:test', 'corpus_path': str(root / 'corpus.jsonl')}
            article = {'character': '木', 'summary': {'text': '木.'}}
            dossier = {'evidence': []}
            editorial.write(job / 'source.json', {'source_id': source['id'], 'registry_source': source,
                'article_hash': editorial.digest(article), 'dossier_hash': editorial.digest(dossier)})
            editorial.write(job / 'source_article.json', article)
            editorial.write(job / 'source_dossier.json', dossier)
            finding = {'key': 'literal', 'kind': 'ocr',
                       'details': '[OCR CORRECTION REQUIRED] raw OCR span 木 may be a different graph.'}
            editorial.write(job / 'source_findings.json', {'findings': [finding]})
            page = {'book_id': source['book_id'], 'pdf_page_1based': 1, 'source_scan': str(scan),
                    'source_sha256': pixel_hash, 'text': text}
            (root / 'corpus.jsonl').write_text(json.dumps(page, ensure_ascii=False) + '\n', encoding='utf-8')

            proposal = {'id': 'occ-1', 'start': text.index('木'), 'end': text.index('木') + 1,
                        'before': '木', 'after': '本'}
            occurrences = ocr_verification.packet(text, [proposal])
            result = {'occurrences': [{'id': 'occ-1', 'raw_text': '木', 'printed_text': '木',
                                       'verdict': 'correct_raw', 'reason': 'Exact glyph in attached page.'}]}
            output = root / 'receipt'
            review = output / 'review'
            review.mkdir(parents=True)
            provenance = {'source_id': source['id'], 'book_id': source['book_id'], 'pdf_page': 1,
                          'source_scan_path': str(scan), 'source_pixel_sha256': scan_file_hash,
                          'raw_text_sha256': hashlib.sha256(text.encode()).hexdigest()}
            editorial.write(output / 'occurrences.json', {'provenance': provenance, 'occurrences': occurrences})
            result_hash = editorial.digest(result)
            editorial.write(review / 'meta.json', {'role': 'ocr_verification', 'status': 'complete',
                'model': 'gpt-6-luna', 'reasoning': 'low', 'result_hash': result_hash,
                'image_argument_manifest': [{'path': str(scan), 'sha256': scan_file_hash}]})
            receipt = {'provenance': provenance, 'occurrences_hash': editorial.digest(occurrences),
                       'result': result, 'result_hash': result_hash, 'review_directory': str(review),
                       'model': 'gpt-6-luna', 'reasoning': 'low'}
            receipt_path = output / 'verified-occurrences.json'
            editorial.write(receipt_path, receipt)
            valid = source_enrichment.validate_correct_raw_occurrence_receipt(
                job, 'literal', receipt_path, ['occ-1'])
            self.assertEqual(valid['disposition'], 'correct_raw_preflight_only')
            self.assertTrue(valid['final_source_resolution_still_required'])
            self.assertEqual(valid['article_hash'], editorial.digest(article))

            changed_result = copy.deepcopy(result)
            changed_result['occurrences'][0]['verdict'] = 'confirmed_correction'
            receipt['result'] = changed_result
            receipt['result_hash'] = editorial.digest(changed_result)
            editorial.write(receipt_path, receipt)
            editorial.write(review / 'meta.json', {**editorial.read(review / 'meta.json'),
                'result_hash': receipt['result_hash']})
            with self.assertRaises(ValueError):
                source_enrichment.validate_correct_raw_occurrence_receipt(
                    job, 'literal', receipt_path, ['occ-1'])

    def test_verified_source_claim_requires_hash_bound_luna_research_and_pixels(self):
        from PIL import Image
        import hashlib
        job = source_enrichment.job_path(self.output, SOURCE['id'], '木')
        page = self.root / 'primary-table.png'
        Image.new('RGB', (8, 8), 'white').save(page)
        with Image.open(page) as im:
            pixel_hash = hashlib.sha256(im.convert('RGB').tobytes()).hexdigest()
        file_hash = hashlib.sha256(page.read_bytes()).hexdigest()
        finding = {'key': 'access-gap', 'kind': 'ocr', 'title': 'Primary table not directly inspected',
                   'details': 'The primary source table was not directly inspected.'}
        editorial.write(job / 'source_findings.json', {'requires_coordinator_verification': True,
                                                        'findings': [finding]})
        result = {'evidence': [{'kind': 'primary_source_scan_inspection',
            'source': f'Official table scan; decoded RGB pixel SHA-256 {pixel_hash}',
            'field': 'table row', 'text': 'The scan lists the claimed counterpart.'}]}
        result_path = self.root / 'research-result.json'
        meta_path = self.root / 'research-meta.json'
        editorial.write(result_path, result)
        meta = {'role': 'research', 'status': 'complete', 'model': 'gpt-6-luna', 'reasoning': 'low',
                'result_hash': editorial.digest(result), 'image_argument_manifest': [
                    {'path': str(page), 'sha256': file_hash}]}
        editorial.write(meta_path, meta)
        check = {'key': 'access-gap', 'research_result_path': str(result_path),
                 'research_meta_path': str(meta_path), 'evidence_indices': [0],
                 'source_pixel_sha256s': [pixel_hash]}
        scans = [{'path': str(page), 'pdf_page': 900, 'source_pixel_sha256': pixel_hash}]
        normalized = source_enrichment._verify_source_claim_checks(job, [check], scans)
        self.assertEqual(normalized[0]['research_result_hash'], editorial.digest(result))
        with self.assertRaisesRegex(ValueError, 'exact attached source scan'):
            source_enrichment._verify_source_claim_checks(job, [
                {**check, 'source_pixel_sha256s': ['0' * 64]}], scans)
        bad_meta = {**meta, 'result_hash': 'f' * 64}
        editorial.write(meta_path, bad_meta)
        with self.assertRaisesRegex(ValueError, 'completed Luna-low research'):
            source_enrichment._verify_source_claim_checks(job, [check], scans)

    def test_verified_source_claim_resolution_gate_rechecks_all_proof(self):
        from PIL import Image
        import hashlib
        with tempfile.TemporaryDirectory() as temp:
            job = Path(temp)
            scan = job / 'official-table.png'
            Image.new('RGB', (6, 6), 'white').save(scan)
            with Image.open(scan) as im:
                pixel_hash = hashlib.sha256(im.convert('RGB').tobytes()).hexdigest()
            scan_hash = hashlib.sha256(scan.read_bytes()).hexdigest()
            result_path, meta_path = job/'research/result.json', job/'research/meta.json'
            research = {'evidence': [{'kind': 'primary_source_scan_inspection',
                'source': f'official table, pixel SHA-256 {pixel_hash}', 'field': 'row', 'text': 'Observed pair.'}]}
            editorial.write(result_path, research)
            editorial.write(meta_path, {'role':'research', 'status':'complete', 'model':'gpt-6-luna',
                'reasoning':'low', 'result_hash':editorial.digest(research), 'image_argument_manifest':[
                    {'path':str(scan), 'sha256':scan_hash}]})
            finding = {'key':'access', 'kind':'ocr', 'title':'Table not directly inspected',
                'details':'Primary source table was not directly inspected.'}
            findings = {'requires_coordinator_verification':True, 'findings':[finding]}
            article, dossier = {'character':'木'}, {'evidence':[]}
            editorial.write(job/'source_findings.json', findings)
            editorial.write(job/'article.json', article)
            editorial.write(job/'dossier.json', dossier)
            scans = [{'path':str(scan), 'pdf_page':900, 'source_pixel_sha256':pixel_hash}]
            check = {'key':'access', 'research_result_path':str(result_path),
                'research_meta_path':str(meta_path), 'evidence_indices':[0],
                'source_pixel_sha256s':[pixel_hash]}
            checks = source_enrichment._verify_source_claim_checks(job, [check], scans)
            resolution_result = {'findings':[{'key':'access', 'disposition':'verified_source_claim',
                'reason':'The actual primary table scan resolves the recorded access gap.', 'affected_paths':['article.summary']}],
                'source_claim_observations':[{'key':'access','supported':True,
                    'support_reason':'The exact entry is visible.'}]}
            editorial.write(job/'source-resolution/result.json', resolution_result)
            editorial.write(job/'source-resolution/meta.json', {'role':'source_resolution','status':'complete',
                'model':'gpt-6-luna','reasoning':'low','result_hash':editorial.digest(resolution_result)})
            editorial.write(job/'source_resolution.json', {'findings_hash':editorial.digest(findings),
                'article_hash':editorial.digest(article), 'dossier_hash':editorial.digest(dossier),
                'result_hash':editorial.digest(resolution_result), 'model':'gpt-6-luna','reasoning':'low',
                'review_path':'source-resolution/result.json','source_claim_checks':checks,
                'source_scan_images':scans})
            self.assertFalse(source_enrichment._source_findings_pending(job))
            editorial.write(meta_path, {'role':'research','status':'complete','model':'gpt-6-luna',
                'reasoning':'low','result_hash':'0'*64,'image_argument_manifest':[{'path':str(scan),'sha256':scan_hash}]})
            self.assertTrue(source_enrichment._source_findings_pending(job))

    def test_source_gap_not_used_requires_exact_pair_and_supported_claim_inventory(self):
        article = {'character': '一', 'summary': {'text': '一 has a supported entry.',
            'evidence_ids': ['E1']}}
        dossier = {'evidence': [{'id': 'E1', 'source': 'Dictionary', 'field': 'entry',
                                 'text': 'Supports the entry.'}]}
        no_claim = {'key': 'access', 'independent_support': True, 'whole_candidate_reviewed': True,
            'reviewed_article_hash': editorial.digest(article), 'reviewed_dossier_hash': editorial.digest(dossier),
            'claim_paths': [], 'support_reason': 'I reviewed the entire article and dossier; no article or dossier claim depends on or uses the missing source observation.'}
        resolution_finding = {'key': 'access', 'affected_paths': []}
        self.assertTrue(source_enrichment._source_gap_support_valid(article, dossier, resolution_finding, no_claim))
        self.assertFalse(source_enrichment._source_gap_support_valid(article, dossier, resolution_finding,
            {**no_claim, 'whole_candidate_reviewed': False}))
        self.assertFalse(source_enrichment._source_gap_support_valid(article, dossier, resolution_finding,
            {**no_claim, 'reviewed_article_hash': '0' * 64}))
        dependent = {**no_claim, 'claim_paths': [{'article_path': 'article.summary',
            'claim_text': '一 has a supported entry.', 'independent_evidence_ids': ['E2']}]}
        self.assertFalse(source_enrichment._source_gap_support_valid(article, dossier,
            {'key': 'access', 'affected_paths': ['article.summary']}, dependent))

    def test_source_gap_not_used_cannot_downgrade_ocr_or_historical_check(self):
        self.assertEqual(source_enrichment._source_finding_class({'key': 'ocr',
            'details': '[OCR CORRECTION REQUIRED] The uninspected raw OCR span is wrong.'}),
            'transcription_correction')
        self.assertEqual(source_enrichment._source_finding_class({'key': 'scan-gap',
            'details': 'This invocation did not inspect the continuation-page pixels.'}),
            'primary_access_gap')
        self.assertEqual(source_enrichment._source_finding_class({'details':
            'The full Unihan readings source is absent in this checkout.'}), 'primary_access_gap')
        self.assertEqual(source_enrichment._source_finding_class({'details':
            'The local-primary Baxter–Sagart dataset is unavailable here.'}), 'primary_access_gap')
        self.assertEqual(source_enrichment._source_finding_class({'details':
            'This invocation directly inspected only PDF page 71, not the earlier page.'}),
            'primary_access_gap')
        with tempfile.TemporaryDirectory() as temp:
            job = Path(temp)
            article = {'character': '一', 'summary': {'text': '一 has a supported entry.',
                'evidence_ids': ['E1']}}
            dossier = {'evidence': [{'id': 'E1', 'source': 'Dictionary', 'field': 'entry',
                                     'text': 'Supports the entry.'}]}
            finding = {'key': 'access', 'kind': 'source',
                'details': 'An external reference page was not directly inspected.'}
            findings = {'requires_coordinator_verification': True, 'findings': [finding]}
            result = {'findings': [{'key': 'access', 'disposition': 'source_gap_not_used',
                    'affected_paths': []}],
                'source_gap_observations': [{'key': 'access', 'independent_support': True,
                    'whole_candidate_reviewed': True, 'reviewed_article_hash': editorial.digest(article),
                    'reviewed_dossier_hash': editorial.digest(dossier), 'claim_paths': [],
                    'support_reason': 'I reviewed the entire article and dossier; no article or dossier claim depends on or uses the missing source observation.'}]}
            for name, value in [('article.json', article), ('dossier.json', dossier),
                                ('source_findings.json', findings)]:
                editorial.write(job / name, value)
            result_path = job / 'source-resolution' / 'result.json'
            editorial.write(result_path, result)
            editorial.write(result_path.parent / 'meta.json', {'role': 'source_resolution',
                'status': 'complete', 'model': 'gpt-6-luna', 'reasoning': 'low',
                'result_hash': editorial.digest(result)})
            editorial.write(job / 'source_resolution.json', {'findings_hash': editorial.digest(findings),
                'article_hash': editorial.digest(article), 'dossier_hash': editorial.digest(dossier),
                'result_hash': editorial.digest(result), 'review_path': 'source-resolution/result.json',
                'model': 'gpt-6-luna', 'reasoning': 'low'})
            self.assertFalse(source_enrichment._source_findings_pending(job))
            # An active claim that is listed as affected but has no exact independently
            # supported claim record must remain held, even though the finding is an
            # access gap rather than an OCR literal.
            dependent_result = copy.deepcopy(result)
            dependent_result['findings'][0]['affected_paths'] = ['article.summary']
            editorial.write(job / 'source-resolution/result.json', dependent_result)
            editorial.write(job / 'source-resolution/meta.json', {'role': 'source_resolution',
                'status': 'complete', 'model': 'gpt-6-luna', 'reasoning': 'low',
                'result_hash': editorial.digest(dependent_result)})
            editorial.write(job / 'source_resolution.json', {'findings_hash': editorial.digest(findings),
                'article_hash': editorial.digest(article), 'dossier_hash': editorial.digest(dossier),
                'result_hash': editorial.digest(dependent_result), 'review_path': 'source-resolution/result.json',
                'model': 'gpt-6-luna', 'reasoning': 'low'})
            self.assertTrue(source_enrichment._source_findings_pending(job))
            with patch.object(source_enrichment, '_historical_checked_keys', return_value={
                    'verified_transcription_matches_corpus': {'access'}}):
                # Restore the otherwise valid no-claim output to isolate the historical
                # receipt barrier from the affected-path check above.
                editorial.write(job / 'source-resolution/result.json', result)
                editorial.write(job / 'source-resolution/meta.json', {'role': 'source_resolution',
                    'status': 'complete', 'model': 'gpt-6-luna', 'reasoning': 'low',
                    'result_hash': editorial.digest(result)})
                editorial.write(job / 'source_resolution.json', {'findings_hash': editorial.digest(findings),
                    'article_hash': editorial.digest(article), 'dossier_hash': editorial.digest(dossier),
                    'result_hash': editorial.digest(result), 'review_path': 'source-resolution/result.json',
                    'model': 'gpt-6-luna', 'reasoning': 'low'})
                self.assertTrue(source_enrichment._source_findings_pending(job))
            ocr_finding = {'key': 'access', 'kind': 'ocr',
                'details': '[OCR CORRECTION REQUIRED] A source-bound literal requires scan verification.'}
            ocr_findings = {'requires_coordinator_verification': True, 'findings': [ocr_finding]}
            ocr_result = {'findings': [{'key': 'access', 'disposition': 'source_gap_not_used',
                    'affected_paths': []}], 'source_gap_observations': [result['source_gap_observations'][0]]}
            editorial.write(job / 'source_findings.json', ocr_findings)
            editorial.write(job / 'source-resolution/result.json', ocr_result)
            editorial.write(job / 'source-resolution/meta.json', {'role': 'source_resolution',
                'status': 'complete', 'model': 'gpt-6-luna', 'reasoning': 'low',
                'result_hash': editorial.digest(ocr_result)})
            editorial.write(job / 'source_resolution.json', {'findings_hash': editorial.digest(ocr_findings),
                'article_hash': editorial.digest(article), 'dossier_hash': editorial.digest(dossier),
                'result_hash': editorial.digest(ocr_result), 'review_path': 'source-resolution/result.json',
                'model': 'gpt-6-luna', 'reasoning': 'low'})
            self.assertTrue(source_enrichment._source_findings_pending(job))

    def test_source_gap_not_used_requires_actual_source_scan_and_keeps_audit_gate(self):
        from PIL import Image
        import hashlib
        job = source_enrichment.job_path(self.output, SOURCE['id'], '木')
        article = editorial.read(job / 'source_article.json')
        dossier = editorial.read(job / 'source_dossier.json')
        reviews = [editorial.make_review(role, 'pass', [], article, dossier, 'source-gap-' + role)
                   for role in ('factual', 'readability')]
        for name, value in [('article.json', article), ('dossier.json', dossier),
                            ('reviews.json', reviews),
                            ('source_findings.json', {'requires_coordinator_verification': True,
                                'findings': [{'key': 'unused-locator', 'kind': 'source',
                                    'details': 'An unrelated locator page was not directly inspected.'}]})]:
            editorial.write(job / name, value)
        editorial.write(job / 'source_checkpoint.json', {'locator': {'source_scan_images': []}})
        scan = self.root / 'unused-locator.png'
        Image.new('RGB', (4, 4), 'white').save(scan)
        with Image.open(scan) as image:
            pixels = hashlib.sha256(image.convert('RGB').tobytes()).hexdigest()
        class Runner:
            model = 'gpt-6-luna'
            reasoning = 'low'
            def run(self, role, inputs, schema, directory):
                self_outer.assertEqual(role, 'source_resolution')
                self_outer.assertIn('source_gap_observations', schema['required'])
                self_outer.assertEqual(inputs['source_gap_checks'][0]['key'], 'unused-locator')
                self_outer.assertTrue(any(item['path'] == str(scan) for item in
                    inputs['feedback']['source_scan_images']))
                result = {'findings': [{'key': 'unused-locator', 'disposition': 'source_gap_not_used',
                    'reason': 'The unrelated locator was not used by the article.', 'affected_paths': []}],
                    'source_gap_observations': [{'key': 'unused-locator', 'independent_support': True,
                        'whole_candidate_reviewed': True,
                        'reviewed_article_hash': editorial.digest(inputs['article']),
                        'reviewed_dossier_hash': editorial.digest(inputs['dossier']), 'claim_paths': [],
                        'support_reason': 'I reviewed the entire article and dossier; no article or dossier claim depends on or uses this missing source observation.'}]}
                directory.mkdir(parents=True, exist_ok=True)
                editorial.write(directory / 'result.json', result)
                editorial.write(directory / 'meta.json', {'role': 'source_resolution',
                    'status': 'complete', 'model': self.model, 'reasoning': self.reasoning,
                    'result_hash': editorial.digest(result)})
                return result
        self_outer = self
        scan_context = [{'path': str(scan), 'pdf_page': 900, 'source_pixel_sha256': pixels}]
        editorial.write(job / 'status.json', {'status': 'approved'})
        result = source_enrichment.resolve_source_findings(job, Runner(), source_context=scan_context)
        self.assertEqual(result['model'], 'gpt-6-luna')
        self.assertFalse(source_enrichment._source_findings_pending(job))
        self.assertFalse((job / 'source_audit.json').exists(),
            'Resolving an unused access gap must not stand in for the mandatory source adoption audit.')

    def test_unbound_historical_result_cannot_create_repair_obligation(self):
        with tempfile.TemporaryDirectory() as temp:
            job = Path(temp)
            key = 'previously-repaired'
            finding = {'key':key,'kind':'ocr','details':'Its Unicode identity remains unresolved.'}
            findings = {'requires_coordinator_verification':True,'findings':[finding]}
            article = {'character':'一','summary':{'text':'一 is a sourced character.','evidence_ids':['E1']}}
            dossier = {'evidence':[{'id':'E1','source':'Dictionary','field':'entry','text':'Supports 一.'}]}
            result = {'findings':[{'key':key,'disposition':'unresolved_identity_not_used',
                'reason':'The old correction is unnecessary.','affected_paths':['article.summary']}],
                'identity_observations':[{'key':key,'independent_support':True,'claim_paths':[
                    {'article_path':'article.summary','claim_text':'一 is a sourced character.',
                     'independent_evidence_ids':['E1']}], 'support_reason':'The independent dictionary supports it.'}]}
            editorial.write(job/'source_findings.json',findings)
            editorial.write(job/'article.json',article)
            editorial.write(job/'dossier.json',dossier)
            old = {'findings':[{'key':key,'disposition':'applied_repair_scan_matches_corpus'}]}
            editorial.write(job/'source-resolution-1/result.json',old)
            editorial.write(job/'source-resolution-1/meta.json',{'role':'source_resolution','status':'complete',
                'model':'gpt-6-luna','reasoning':'low','result_hash':editorial.digest(old)})
            editorial.write(job/'source-resolution-2/result.json',result)
            editorial.write(job/'source-resolution-2/meta.json',{'role':'source_resolution','status':'complete',
                'model':'gpt-6-luna','reasoning':'low','result_hash':editorial.digest(result)})
            editorial.write(job/'source_resolution.json',{'findings_hash':editorial.digest(findings),
                'article_hash':editorial.digest(article),'dossier_hash':editorial.digest(dossier),
                'result_hash':editorial.digest(result),'model':'gpt-6-luna','reasoning':'low',
                'review_path':'source-resolution-2/result.json'})
            self.assertEqual(source_enrichment._historical_checked_keys(job), {
                'rejected_proposal_scan_matches_corpus': set(),
                'applied_repair_scan_matches_corpus': set(),
                'verified_metadata_not_extracted': set(),
                'verified_transcription_matches_corpus': set()})
            self.assertFalse(source_enrichment._source_findings_pending(job))

    def test_research_feedback_preserves_additional_source_pages(self):
        located = {**copy.deepcopy(LOCATED), 'source_scan_images': [
            {'path': '/page-1.png', 'pdf_page': 1}]}
        additional = [{'path': f'/page-{page}.png', 'pdf_page': page}
                      for page in range(2, 6)]
        packet = source_enrichment.feedback(SOURCE, located, additional)
        self.assertEqual(packet['source_scan_images'],
                         located['source_scan_images'] + additional)

    def test_agent_child_inherits_live_source_lock(self):
        job = source_enrichment.job_path(self.output, SOURCE['id'], '木')
        lock_path = job / 'coordinator.lock'
        with lock_path.open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            script = ('import os,fcntl,json,sys; from pathlib import Path; '
                      f'os.fstat({lock.fileno()}); '
                      'candidate=open(sys.argv[1],"a")\n'
                      'try:\n fcntl.flock(candidate,fcntl.LOCK_EX|fcntl.LOCK_NB)\n'
                      'except BlockingIOError:\n pass\n'
                      'else:\n raise AssertionError("Parent source lock was lost")\n'
                      'Path(sys.argv[2]).write_text(json.dumps(dict(inherited=True)))\n')
            runner = editorial.Runner([sys.executable, '-c', script, str(lock_path), '{output}'],
                                      model='fixture')
            runner.inherited_lock_fds = (lock.fileno(),)
            result = runner.run('prose_repair', {}, {'type': 'object'}, job / 'lock-test')
            self.assertEqual(result, {'inherited': True})

    def test_live_coordinator_lock_prevents_duplicate_stage_writes(self):
        job = source_enrichment.job_path(self.output, SOURCE['id'], '木')
        with (job / 'coordinator.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with patch.object(source_enrichment, '_load_source_tools', return_value=LocalSources()):
                rows = source_enrichment.run({'characters': ['木']}, SOURCE, self.output,
                                             object(), root=self.root)
            self.assertEqual(rows[0]['status'], 'already_running')
            self.assertFalse((job / 'source_checkpoint.json').exists())

    def test_cross_output_live_character_claim_prevents_duplicate_research(self):
        lock_dir = self.root / 'runs/.locks'
        lock_dir.mkdir(parents=True, exist_ok=True)
        path = lock_dir / f"source-{source_enrichment._research_source_hash(SOURCE)[:16]}-6728.lock"
        with path.open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with patch.object(source_enrichment, '_load_source_tools', return_value=LocalSources()):
                rows = source_enrichment.run({'characters': ['木']}, SOURCE, self.output,
                                            object(), root=self.root, workers=24)
            self.assertEqual(rows[0]['status'], 'already_running')
            job = source_enrichment.job_path(self.output, SOURCE['id'], '木')
            self.assertFalse((job / 'source_checkpoint.json').exists())

    def test_locator_hash_ignores_only_redundant_pixel_metadata(self):
        located = {'source_scan_images': [{'pdf_page': 13, 'path': '/scan.png'}],
                   'source_leads': [{'candidates': [{'pdf_page_1based': 13, 'source_sha256': 'pixels'}]}]}
        located['source_leads'][0]['candidates'][0]['evidence_sha256'] = 'effective'
        richer = copy.deepcopy(located)
        richer['source_scan_images'][0]['source_pixel_sha256'] = 'pixels'
        self.assertEqual(source_enrichment._locator_hash(located), source_enrichment._locator_hash(richer))
        richer['source_scan_images'][0]['source_pixel_sha256'] = 'changed'
        self.assertNotEqual(source_enrichment._locator_hash(located), source_enrichment._locator_hash(richer))

    def test_source_resolution_is_bound_to_findings_and_exact_article(self):
        with tempfile.TemporaryDirectory() as temp:
            job = Path(temp)
            findings = {'requires_coordinator_verification': True, 'findings': [{
                'key': 'rare-glyph', 'kind': 'ocr', 'details': 'Its Unicode identity remains unresolved.'}]}
            article = {'character': '一', 'summary': {'text':'一 is a sourced character.', 'evidence_ids':['E1']}}
            dossier = {'evidence': [{'id':'E1','source':'Dictionary','field':'entry','text':'Supports 一.'}]}
            editorial.write(job / 'source_findings.json', findings)
            editorial.write(job / 'article.json', article)
            editorial.write(job / 'dossier.json', dossier)
            self.assertTrue(source_enrichment._source_findings_pending(job))

            result = {'findings': [{'key': 'rare-glyph', 'disposition': 'unresolved_identity_not_used',
                    'affected_paths':['article.summary']}],
                'identity_observations':[{'key':'rare-glyph','independent_support':True,
                    'claim_paths':[{'article_path':'article.summary','claim_text':'一 is a sourced character.',
                                    'independent_evidence_ids':['E1']}],
                    'support_reason':'The actual summary cites the dictionary independently of the unidentified specimen.'}]}
            editorial.write(job / 'source-resolution/result.json', result)
            editorial.write(job / 'source-resolution/meta.json', {
                'role': 'source_resolution', 'status': 'complete', 'model': 'gpt-6-luna',
                'reasoning': 'low', 'result_hash': editorial.digest(result)})
            editorial.write(job / 'source_resolution.json', {
                'findings_hash': editorial.digest(findings), 'article_hash': editorial.digest(article),
                'dossier_hash': editorial.digest(dossier), 'result_hash': editorial.digest(result),
                'model': 'gpt-6-luna', 'reasoning': 'low', 'review_path': 'source-resolution/result.json'})
            self.assertFalse(source_enrichment._source_findings_pending(job))
            editorial.write(job / 'source_resolution_validation.json', {
                'status': 'rejected', 'result_hash': editorial.digest(result)})
            self.assertTrue(source_enrichment._source_findings_pending(job))
            (job / 'source_resolution_validation.json').unlink()
            result['findings'][0]['disposition'] = 'rejected_proposal_scan_matches_corpus'
            editorial.write(job / 'source-resolution/result.json', result)
            self.assertTrue(source_enrichment._source_findings_pending(job))
            resolution = editorial.read(job / 'source_resolution.json')
            editorial.write(job / 'source_resolution.json', {**resolution, 'result_hash': editorial.digest(result)})
            editorial.write(job / 'source-resolution/meta.json', {
                'role': 'source_resolution', 'status': 'complete', 'model': 'gpt-6-luna',
                'reasoning': 'low', 'result_hash': editorial.digest(result)})
            self.assertTrue(source_enrichment._source_findings_pending(job))
            resolution = editorial.read(job / 'source_resolution.json')
            resolution['literal_checks'] = [{'key': 'rare-glyph', 'current': '弋', 'proposed': '戈'}]
            editorial.write(job / 'source_resolution.json', resolution)
            self.assertTrue(source_enrichment._source_findings_pending(job))
            result['literal_observations'] = [{'key': 'rare-glyph', 'current_corpus_literal': '弋',
                'proposed_literal': '戈', 'observed_literal': '戈', 'pixel_reason': 'Fixture observation.'}]
            for observed, expected in [('戈', True), ('弋', False)]:
                result['literal_observations'][0]['observed_literal'] = observed
                editorial.write(job / 'source-resolution/result.json', result)
                editorial.write(job / 'source_resolution.json', {**resolution, 'result_hash': editorial.digest(result)})
                editorial.write(job / 'source-resolution/meta.json', {
                    'role': 'source_resolution', 'status': 'complete', 'model': 'gpt-6-luna',
                    'reasoning': 'low', 'result_hash': editorial.digest(result)})
                self.assertEqual(source_enrichment._source_findings_pending(job), expected)
            editorial.write(job / 'article.json', {**article, 'summary': 'Now cites a glyph.'})
            self.assertTrue(source_enrichment._source_findings_pending(job))

    def test_identity_no_claim_inventory_requires_exact_pair_and_explicit_review(self):
        article = {'character': '边', 'formation': {'text': '边 derives from 边.', 'evidence_ids': ['E1']}}
        dossier = {'evidence': [{'id': 'E1', 'source': 'Dictionary', 'field': 'entry',
                                'text': 'Supports the current character.'}]}
        finding = {'key': 'identity', 'affected_paths': []}
        observation = {
            'key': 'identity', 'independent_support': True, 'claim_paths': [],
            'whole_candidate_reviewed': True,
            'reviewed_article_hash': editorial.digest(article),
            'reviewed_dossier_hash': editorial.digest(dossier),
            'support_reason': ('No article or dossier claim depends on or uses this unresolved identity; '
                               'I reviewed the entire candidate.')}
        self.assertTrue(source_enrichment._identity_support_valid(article, dossier, finding, observation))
        for field, value in [
                ('whole_candidate_reviewed', False),
                ('reviewed_article_hash', '0' * 64),
                ('reviewed_dossier_hash', '0' * 64),
                ('support_reason', 'No article claim depends on it.'),
                ('independent_support', False)]:
            bad = {**observation, field: value}
            self.assertFalse(source_enrichment._identity_support_valid(article, dossier, finding, bad), field)
        alternate = {**observation, 'support_reason': (
            'Review of the complete article and dossier found no claim that depends on or uses '
            'that unresolved identity; the separate discussion cites independent evidence.')}
        self.assertTrue(source_enrichment._identity_support_valid(article, dossier, finding, alternate))
        for reason in ('The article and dossier might contain no claim that depends on it.',
                       'Review of the article found no claim that depends on it.'):
            self.assertFalse(source_enrichment._identity_support_valid(
                article, dossier, finding, {**observation, 'support_reason': reason}))
        contradictory = {**finding, 'affected_paths': ['article.formation']}
        self.assertFalse(source_enrichment._identity_support_valid(article, dossier, contradictory, observation))
        for invalid in ('article.summary.trailing!', 'article.summary[bad]', 'article..summary'):
            with self.assertRaises(ValueError):
                source_enrichment._article_path_node(article, invalid)

    def test_verified_missing_page_metadata_requires_exact_observation_and_current_pixels(self):
        import hashlib
        import json
        from PIL import Image
        with tempfile.TemporaryDirectory() as temp:
            job = Path(temp)
            image = Image.new('RGB', (8, 8), 'white')
            scan = job / 'scan.png'
            image.save(scan)
            pixels = hashlib.sha256(image.tobytes()).hexdigest()
            corpus = job / 'corpus.jsonl'
            page = {'pdf_page_1based': 76, 'printed_page': None,
                    'source_sha256': pixels, 'source_scan': str(scan)}
            def save_page():
                corpus.write_text(json.dumps(page) + '\n')
            save_page()
            findings = {'requires_coordinator_verification': True,
                        'findings': [{'key': 'page-label'}]}
            article, dossier = {'character': '八'}, {'evidence': []}
            for name, value in [('source_findings.json', findings), ('article.json', article),
                                ('dossier.json', dossier), ('source.json', {
                                    'registry_source': {'corpus_path': str(corpus)}})]:
                editorial.write(job / name, value)
            check = {'key': 'page-label', 'pdf_page': 76, 'field': 'printed_page',
                     'current_value': None, 'expected_value': '64', 'source_pixel_sha256': pixels}
            result = {'findings': [{'key': 'page-label',
                                   'disposition': 'verified_metadata_not_extracted'}],
                      'metadata_observations': [{'key': 'page-label', 'observed_value': '64',
                                                'pixel_reason': 'Fixture: lower-left label.'}]}
            def save_result(checks):
                editorial.write(job / 'source-resolution/result.json', result)
                editorial.write(job / 'source-resolution/meta.json', {
                    'role': 'source_resolution', 'status': 'complete', 'model': 'gpt-6-luna',
                    'reasoning': 'low', 'result_hash': editorial.digest(result)})
                editorial.write(job / 'source_resolution.json', {
                    'findings_hash': editorial.digest(findings), 'article_hash': editorial.digest(article),
                    'dossier_hash': editorial.digest(dossier), 'result_hash': editorial.digest(result),
                    'model': 'gpt-6-luna', 'reasoning': 'low',
                    'review_path': 'source-resolution/result.json', 'metadata_checks': checks})
            save_result([])
            self.assertTrue(source_enrichment._source_findings_pending(job))
            save_result([check])
            self.assertFalse(source_enrichment._source_findings_pending(job))
            result['metadata_observations'][0]['observed_value'] = '65'
            save_result([check])
            self.assertTrue(source_enrichment._source_findings_pending(job))
            result['metadata_observations'][0]['observed_value'] = '64'
            result['findings'][0]['disposition'] = 'unresolved_identity_not_used'
            save_result([check])
            self.assertTrue(source_enrichment._source_findings_pending(job))
            result['findings'][0]['disposition'] = 'verified_metadata_not_extracted'
            save_result([check])
            page['printed_page'] = '65'
            save_page()
            self.assertTrue(source_enrichment._source_findings_pending(job))
            page['printed_page'] = None
            save_page()
            image.putpixel((0, 0), (0, 0, 0))
            image.save(scan)
            self.assertTrue(source_enrichment._source_findings_pending(job))
            with self.assertRaises(ValueError):
                source_enrichment._verify_missing_page_metadata(job, [{**check, 'field': 'text'}])

    def test_verified_transcription_rechecks_current_corpus_and_exact_observation(self):
        import hashlib
        import json
        from PIL import Image
        with tempfile.TemporaryDirectory() as temp:
            job = Path(temp)
            image = Image.new('RGB', (8, 8), 'white')
            scan = job / 'scan.png'
            image.save(scan)
            pixels = hashlib.sha256(image.tobytes()).hexdigest()
            corpus = job / 'corpus.jsonl'
            page = {'pdf_page_1based': 951, 'source_sha256': pixels,
                    'source_scan': str(scan), 'text': 'prefix爸妈suffix'}
            def save_page():
                corpus.write_text(json.dumps(page) + '\n')
            save_page()
            findings = {'requires_coordinator_verification': True,
                        'findings': [{'key': 'accurate-mention'}]}
            article, dossier = {'character': '爸'}, {'evidence': []}
            for name, value in [('source_findings.json', findings), ('article.json', article),
                                ('dossier.json', dossier), ('source.json', {
                                    'registry_source': {'corpus_path': str(corpus)}})]:
                editorial.write(job / name, value)
            check = {'key': 'accurate-mention', 'pdf_page': 951, 'text_offset': 6,
                     'current': '爸妈', 'source_pixel_sha256': pixels}
            normalized = source_enrichment._verify_transcription_checks(job, [check])[0]
            self.assertNotIn('occurrences', normalized)
            self.assertEqual(normalized['current'], check['current'])
            result = {'findings': [{'key': 'accurate-mention',
                                   'disposition': 'verified_transcription_matches_corpus'}],
                      'transcription_observations': [{'key': 'accurate-mention',
                          'observed_literal': '爸妈', 'pixel_reason': 'Fixture only.'}]}
            def save_result(checks):
                editorial.write(job / 'source-resolution/result.json', result)
                editorial.write(job / 'source-resolution/meta.json', {
                    'role': 'source_resolution', 'status': 'complete', 'model': 'gpt-6-luna',
                    'reasoning': 'low', 'result_hash': editorial.digest(result)})
                editorial.write(job / 'source_resolution.json', {
                    'findings_hash': editorial.digest(findings), 'article_hash': editorial.digest(article),
                    'dossier_hash': editorial.digest(dossier), 'result_hash': editorial.digest(result),
                    'model': 'gpt-6-luna', 'reasoning': 'low',
                    'review_path': 'source-resolution/result.json', 'transcription_checks': checks})
            save_result([])
            self.assertTrue(source_enrichment._source_findings_pending(job))
            save_result([normalized])
            self.assertFalse(source_enrichment._source_findings_pending(job))
            for bad in (None, '父母', '爸媽'):
                result['transcription_observations'][0]['observed_literal'] = bad
                save_result([check])
                self.assertTrue(source_enrichment._source_findings_pending(job))
            result['transcription_observations'][0]['observed_literal'] = '爸妈'
            result['findings'][0]['disposition'] = 'unresolved_identity_not_used'
            save_result([check])
            self.assertTrue(source_enrichment._source_findings_pending(job))
            result['findings'][0]['disposition'] = 'verified_transcription_matches_corpus'
            save_result([check])
            page['text'] = 'prefix爸媽suffix'
            save_page()
            self.assertTrue(source_enrichment._source_findings_pending(job))
            page['text'] = 'prefix爸妈suffix'
            save_page()
            with self.assertRaises(ValueError):
                source_enrichment._verify_transcription_checks(job, [{**check, 'text_offset': -1}])
            with self.assertRaises(ValueError):
                source_enrichment._verify_transcription_checks(job, [check, check])
            image.putpixel((0, 0), (0, 0, 0))
            image.save(scan)
            self.assertTrue(source_enrichment._source_findings_pending(job))

    def test_grouped_verified_transcription_requires_every_occurrence_to_match(self):
        import hashlib
        import json
        from PIL import Image
        with tempfile.TemporaryDirectory() as temp:
            job = Path(temp)
            scan = job / 'scan.png'
            Image.new('RGB', (8, 8), 'white').save(scan)
            with Image.open(scan) as image:
                pixels = hashlib.sha256(image.convert('RGB').tobytes()).hexdigest()
            text = 'prefix爸妈suffix'
            corpus = job / 'corpus.jsonl'
            page = {'book_id': 'book', 'pdf_page_1based': 951, 'source_sha256': pixels,
                    'source_scan': str(scan), 'text': text}
            corpus.write_text(json.dumps(page, ensure_ascii=False) + '\n', encoding='utf-8')
            finding = {'key': 'grouped', 'kind': 'ocr', 'details': '爸妈 exact text.'}
            findings = {'requires_coordinator_verification': True, 'findings': [finding]}
            article, dossier = {'character': '爸'}, {'evidence': []}
            for name, value in [('source_findings.json', findings), ('article.json', article),
                                ('dossier.json', dossier), ('source.json', {
                                    'registry_source': {'corpus_path': str(corpus)}})]:
                editorial.write(job / name, value)
            checks = [{'key': 'grouped', 'pdf_page': 951, 'source_pixel_sha256': pixels,
                       'occurrences': [
                           {'id': 'span-1', 'text_offset': 6, 'current': '爸'},
                           {'id': 'span-2', 'text_offset': 7, 'current': '妈'}]}]
            observations = [{'key': 'grouped', 'pixel_reason': 'Both occurrences checked.',
                'occurrence_observations': [
                    {'id': 'span-1', 'observed_literal': '爸', 'pixel_reason': 'Visible.'},
                    {'id': 'span-2', 'observed_literal': '妈', 'pixel_reason': 'Visible.'}]}]
            result = {'findings': [{'key': 'grouped',
                                    'disposition': 'verified_transcription_matches_corpus'}],
                      'transcription_observations': observations}
            def save_resolution():
                editorial.write(job / 'source-resolution/result.json', result)
                editorial.write(job / 'source-resolution/meta.json', {
                    'role': 'source_resolution', 'status': 'complete', 'model': 'gpt-6-luna',
                    'reasoning': 'low', 'result_hash': editorial.digest(result)})
                editorial.write(job / 'source_resolution.json', {
                    'findings_hash': editorial.digest(findings), 'article_hash': editorial.digest(article),
                    'dossier_hash': editorial.digest(dossier), 'result_hash': editorial.digest(result),
                    'model': 'gpt-6-luna', 'reasoning': 'low', 'review_path': 'source-resolution/result.json',
                    'transcription_checks': checks})
            save_resolution()
            self.assertFalse(source_enrichment._source_findings_pending(job))
            result['transcription_observations'][0]['occurrence_observations'][1]['observed_literal'] = '媽'
            save_resolution()
            self.assertTrue(source_enrichment._source_findings_pending(job))

    def test_source_resolver_requests_each_grouped_raw_occurrence(self):
        import hashlib
        import json
        from PIL import Image
        with tempfile.TemporaryDirectory() as temp:
            job = Path(temp)
            scan = job / 'scan.png'
            Image.new('RGB', (8, 8), 'white').save(scan)
            with Image.open(scan) as image:
                pixels = hashlib.sha256(image.convert('RGB').tobytes()).hexdigest()
            text = 'prefix木本suffix'
            corpus = job / 'corpus.jsonl'
            corpus.write_text(json.dumps({'book_id': 'book', 'pdf_page_1based': 951,
                'source_sha256': pixels, 'source_scan': str(scan), 'text': text}, ensure_ascii=False) + '\n',
                encoding='utf-8')
            finding = {'key': 'grouped', 'kind': 'ocr',
                       'details': '[OCR CORRECTION REQUIRED] Exact raw span 木本 is under visual review.'}
            article, dossier = copy.deepcopy(ARTICLE_V2), copy.deepcopy(DOSSIER)
            dossier['glyph_research'] = {'historical_glyphs': copy.deepcopy(GLYPHS)}
            dossier['glyph_assets'] = []
            editorial.write(job / 'article.json', article)
            editorial.write(job / 'dossier.json', dossier)
            editorial.write(job / 'reviews.json', [editorial.make_review(role, 'pass', [], article, dossier,
                'fixture-' + role) for role in ('factual', 'readability')])
            editorial.write(job / 'source.json', {'registry_source': {'corpus_path': str(corpus)}})
            editorial.write(job / 'source_findings.json', {'findings': [finding]})
            editorial.write(job / 'status.json', {'status': 'needs_source_verification'})
            editorial.write(job / 'source_checkpoint.json', {'locator': {'source_scan_images': [
                {'path': str(scan), 'pdf_page': 951, 'source_pixel_sha256': pixels}]}})
            check = {'key': 'grouped', 'pdf_page': 951, 'source_pixel_sha256': pixels,
                     'occurrences': [{'id': 'span-1', 'text_offset': 6, 'current': '木'},
                                     {'id': 'span-2', 'text_offset': 7, 'current': '本'}]}
            observed = {'findings': [{'key': 'grouped',
                                      'disposition': 'verified_transcription_matches_corpus'}],
                'transcription_observations': [{'key': 'grouped', 'pixel_reason': 'Both exact spans inspected.',
                    'occurrence_observations': [
                        {'id': 'span-1', 'observed_literal': '木', 'pixel_reason': 'Printed form.'},
                        {'id': 'span-2', 'observed_literal': '本', 'pixel_reason': 'Printed form.'}]}]}
            class FakeRunner:
                model = 'gpt-6-luna'
                reasoning = 'low'
                def run(self, role, inputs, schema, directory):
                    self_outer.assertEqual(role, 'source_resolution')
                    self_outer.assertIn('occurrence_observations', str(schema))
                    self_outer.assertEqual(inputs['transcription_checks'][0]['occurrences'], check['occurrences'])
                    editorial.write(Path(directory) / 'result.json', observed)
                    return observed
            self_outer = self
            record = source_enrichment.resolve_source_findings(job, FakeRunner(),
                transcription_checks=[check])
            self.assertEqual(record['transcription_checks'][0]['key'], 'grouped')
            self.assertFalse(source_enrichment._source_findings_pending(job))

    def test_resolution_transport_limits_repair_observations_to_requested_keys(self):
        job = source_enrichment.job_path(self.output, SOURCE['id'], '木')
        article = editorial.read(job/'source_article.json')
        dossier = editorial.read(job/'source_dossier.json')
        editorial.write(job/'article.json', article)
        editorial.write(job/'dossier.json', dossier)
        editorial.write(job/'reviews.json', [editorial.make_review(role, 'pass', [],
            article, dossier, 'fixture-' + role) for role in ('factual', 'readability')])
        editorial.write(job/'source_findings.json', {'findings': [{'key':'repair'}, {'key':'identity'}]})
        editorial.write(job/'source_checkpoint.json', {'locator': {'source_scan_images': []}})
        test = self
        class Runner:
            model = 'gpt-6-luna'
            reasoning = 'low'
            def run(self, role, inputs, schema, directory):
                findings_validator = editorial.Draft202012Validator(schema['properties']['findings'])
                finding = {'key': 'repair', 'disposition': 'pending',
                           'reason': 'Fixture', 'affected_paths': []}
                test.assertTrue(list(findings_validator.iter_errors([finding])))
                findings_validator.validate([finding, {**finding, 'key': 'identity'}])
                test.assertTrue(list(findings_validator.iter_errors([
                    finding, {**finding, 'key': 'unknown'}])))
                transport = schema['properties']['repair_observations']
                validator = editorial.Draft202012Validator(transport)
                valid = {'key':'repair', 'observed_literal':'皃', 'pixel_reason':'Fixture'}
                validator.validate([valid])
                test.assertTrue(list(validator.iter_errors([valid, {**valid, 'key':'identity'}])))
                test.assertTrue(list(validator.iter_errors([{**valid, 'key':'identity'}])))
                test.assertTrue(list(validator.iter_errors([{**valid, 'observed_literal':'皃鐘'}])))
                validator.validate([{**valid, 'observed_literal':None}])
                raise RuntimeError('Transport checked')
        with patch('pipeline.source_repairs.verify', return_value={'key':'repair', 'before':'兒', 'after':'皃'}):
            with self.assertRaisesRegex(ValueError, 'requires original source scan'):
                source_enrichment.resolve_source_findings(job, Runner(), repair_checks=[{'key':'repair'}])
            self.assertFalse((job/'source-resolution').exists())
            scan = self.root/'resolution-scan.png'
            from PIL import Image
            Image.new('RGB', (2, 2), 'white').save(scan)
            source_context = [{'path': str(scan), 'pdf_page': 1}]
            with self.assertRaisesRegex(RuntimeError, 'Transport checked'):
                source_enrichment.resolve_source_findings(job, Runner(), source_context=source_context,
                                                         repair_checks=[{'key':'repair'}])

    def test_auto_source_resolution_is_a_bounded_separate_stage(self):
        job = source_enrichment.job_path(self.output, SOURCE['id'], '木')
        article, dossier = editorial.read(job/'source_article.json'), editorial.read(job/'source_dossier.json')
        reviews = [editorial.make_review(role, 'pass', [], article, dossier, 'auto-' + role)
                   for role in ('factual', 'readability')]
        findings = {'requires_coordinator_verification': True,
                    'findings': [{'key': 'glyph', 'kind': 'ocr', 'details': 'Printed identity unresolved.'}]}
        for name, value in [('article.json', article), ('dossier.json', dossier),
                            ('reviews.json', reviews), ('source_findings.json', findings),
                            ('status.json', {'status': 'approved'})]:
            editorial.write(job/name, value)
        fake_receipt = {'result_hash': 'real-agent-result-fixture'}
        with patch.object(source_enrichment, 'resolve_source_findings', return_value=fake_receipt) as resolve, \
             patch.object(source_enrichment, '_source_findings_pending', return_value=False):
            result = source_enrichment.auto_resolve_source_findings(job, object(), source_context=[])
            self.assertEqual(result['status'], 'approved')
            resolve.assert_called_once_with(job, resolve.call_args.args[1], source_context=[])
            second = source_enrichment.auto_resolve_source_findings(job, object(), source_context=[])
            self.assertEqual(second['status'], 'already_attempted')
            self.assertEqual(resolve.call_count, 1)
        self.assertEqual(editorial.digest(editorial.read(job/'article.json')), editorial.digest(article))
        self.assertEqual(editorial.digest(editorial.read(job/'dossier.json')), editorial.digest(dossier))
        self.assertEqual(editorial.digest(editorial.read(job/'reviews.json')), editorial.digest(reviews))

    def test_auto_source_resolution_failure_keeps_exact_pair_held(self):
        job = source_enrichment.job_path(self.output, SOURCE['id'], '木')
        article, dossier = editorial.read(job/'source_article.json'), editorial.read(job/'source_dossier.json')
        reviews = [editorial.make_review(role, 'pass', [], article, dossier, 'auto-fail-' + role)
                   for role in ('factual', 'readability')]
        findings = {'requires_coordinator_verification': True, 'findings': [{'key':'ocr', 'kind':'ocr'}]}
        for name, value in [('article.json', article), ('dossier.json', dossier),
                            ('reviews.json', reviews), ('source_findings.json', findings),
                            ('status.json', {'status': 'approved'})]:
            editorial.write(job/name, value)
        with patch.object(source_enrichment, 'resolve_source_findings', side_effect=RuntimeError('fixture failure')):
            result = source_enrichment.auto_resolve_source_findings(job, object())
        self.assertEqual(result['status'], 'needs_source_verification')
        self.assertEqual(editorial.read(job/'status.json')['status'], 'needs_source_verification')
        self.assertIn('error', result)

    def test_source_only_revalidation_preserves_exact_pair_and_republishes_through_gate(self):
        job = source_enrichment.job_path(self.output, SOURCE['id'], '木')
        article = editorial.read(job / 'source_article.json')
        dossier = editorial.read(job / 'source_dossier.json')
        reviews = [editorial.make_review(role, 'pass', [], article, dossier, 'revalidate-' + role)
                   for role in ('factual', 'readability')]
        for name, value in [('article.json', article), ('dossier.json', dossier), ('reviews.json', reviews)]:
            editorial.write(job / name, value)
        from pipeline.source_adoption import _used_ids
        used = _used_ids(article)
        citations = [e for e in dossier['evidence'] if e.get('id') in used]
        audit = {'verified': True, 'source_hash': source_enrichment._research_source_hash(SOURCE),
                 'citations': citations}
        editorial.write(job / 'source_audit.json', audit)
        editorial.write(job / 'source_findings.json', {'requires_coordinator_verification': True,
            'findings': [{'key': 'identity', 'kind': 'ocr',
                'details': 'The printed component identity remains unresolved.'}]})
        editorial.write(job / 'status.json', {'status': 'published', 'source_audit_hash': editorial.digest(audit),
            'issue_sync_status': 'synced'})
        repair_check = {'key': 'repair', 'pdf_page': 1, 'raw_start': 3, 'raw_end': 4,
                        'before': '日', 'after': '曰'}
        old_receipt = {'prior': 'preserved', 'applied_repairs': [repair_check]}
        editorial.write(job / 'source_resolution.json', old_receipt)
        pair_dir = job / 'source-only-revalidation' / (
            f"{editorial.digest(article)[:12]}-{editorial.digest(dossier)[:12]}")
        editorial.write(pair_dir / 'summary.json', {'status': 'failed',
            'error': 'Prior attempt failed before a source verdict.'})

        class Runner:
            model = 'gpt-6-luna'
            reasoning = 'low'

        def resolve(candidate, local_runner, source_context=None, **checks):
            self.assertEqual(candidate, job)
            self.assertEqual(source_context, [])
            self.assertEqual(checks, {'repair_checks': [repair_check]})
            editorial.write(job / 'status.json', {'status': 'approved', 'source_audit_hash': editorial.digest(audit),
                'issue_sync_status': 'synced'})
            fresh = {'fresh': True}
            editorial.write(job / 'source_resolution.json', fresh)
            return {'result_hash': 'fresh-result', 'fresh_receipt': fresh}

        with patch.object(source_enrichment, '_historical_checked_keys', return_value={
                'rejected_proposal_scan_matches_corpus': set(),
                'applied_repair_scan_matches_corpus': {'repair'},
                'verified_metadata_not_extracted': set(),
                'verified_transcription_matches_corpus': set()}), \
             patch.object(source_enrichment, '_source_findings_pending', side_effect=[True, False]), \
             patch.object(source_enrichment, 'resolve_source_findings', side_effect=resolve), \
             patch.object(source_enrichment, '_publish_job_locked', return_value={'status': 'published'}) as publish:
            rows = source_enrichment.revalidate_published_source_jobs([job], Runner(), self.root)
        self.assertEqual(rows[0]['status'], 'published', rows[0])
        self.assertTrue(rows[0]['creates_or_changes_authorship_or_review'] is False)
        publish.assert_called_once()
        self.assertEqual(editorial.digest(editorial.read(job / 'article.json')), editorial.digest(article))
        self.assertEqual(editorial.digest(editorial.read(job / 'dossier.json')), editorial.digest(dossier))
        self.assertEqual(editorial.digest(editorial.read(job / 'reviews.json')), editorial.digest(reviews))
        self.assertEqual(editorial.read(pair_dir / 'summary.json')['status'], 'failed')
        self.assertEqual(editorial.read(pair_dir / 'attempt-02' / 'prior-source-resolution.json'), old_receipt)
        self.assertEqual(editorial.read(job / 'source_resolution.json'), {'fresh': True})

    def test_source_only_revalidation_finalizes_helper_downgraded_published_job(self):
        job = source_enrichment.job_path(self.output, SOURCE['id'], '木')
        article = editorial.read(job / 'source_article.json')
        dossier = editorial.read(job / 'source_dossier.json')
        reviews = [editorial.make_review(role, 'pass', [], article, dossier, 'finalize-' + role)
                   for role in ('factual', 'readability')]
        for name, value in [('article.json', article), ('dossier.json', dossier), ('reviews.json', reviews),
                            ('source_findings.json', {'requires_coordinator_verification': True,
                                'findings': [{'key': 'identity', 'details': 'Identity unresolved.'}]}),
                            ('source_resolution.json', {'verified': True})]:
            editorial.write(job / name, value)
        from pipeline.source_adoption import _used_ids
        used = _used_ids(article)
        audit = {'verified': True, 'source_hash': source_enrichment._research_source_hash(SOURCE),
                 'citations': [e for e in dossier['evidence'] if e.get('id') in used]}
        editorial.write(job / 'source_audit.json', audit)
        editorial.write(job / 'status.json', {'status': 'approved', 'source_audit_hash': editorial.digest(audit),
            'issue_sync_status': 'synced', 'published_at': '2026-10-03T00:00:00Z',
            'canonical_entry': str(self.root / 'content/entries/6728.json')})

        class Runner:
            model = 'gpt-6-luna'
            reasoning = 'low'

        with patch.object(source_enrichment, '_source_findings_pending', return_value=False), \
             patch.object(source_enrichment, 'resolve_source_findings') as resolve, \
             patch.object(source_enrichment, '_publish_job_locked', return_value={'status': 'published'}) as publish:
            rows = source_enrichment.revalidate_published_source_jobs([job], Runner(), self.root)
        self.assertEqual(rows[0]['status'], 'published', rows[0])
        resolve.assert_not_called()
        publish.assert_called_once()

    def test_source_only_revalidation_contention_does_not_create_attempt_or_call_agent(self):
        job = source_enrichment.job_path(self.output, SOURCE['id'], '木')
        article = editorial.read(job / 'source_article.json')
        dossier = editorial.read(job / 'source_dossier.json')
        reviews = [editorial.make_review(role, 'pass', [], article, dossier, 'locked-' + role)
                   for role in ('factual', 'readability')]
        for name, value in [('article.json', article), ('dossier.json', dossier),
                            ('reviews.json', reviews),
                            ('source_findings.json', {'requires_coordinator_verification': True,
                                'findings': [{'key': 'identity', 'details': 'Identity unresolved.'}]})]:
            editorial.write(job / name, value)
        from pipeline.source_adoption import _used_ids
        used = _used_ids(article)
        audit = {'verified': True, 'source_hash': source_enrichment._research_source_hash(SOURCE),
                 'citations': [e for e in dossier['evidence'] if e.get('id') in used]}
        editorial.write(job / 'source_audit.json', audit)
        editorial.write(job / 'status.json', {'status': 'published',
            'source_audit_hash': editorial.digest(audit), 'issue_sync_status': 'synced'})
        old_resolution = {'prior': 'unchanged'}
        editorial.write(job / 'source_resolution.json', old_resolution)
        pair_dir = job / 'source-only-revalidation' / (
            f"{editorial.digest(article)[:12]}-{editorial.digest(dossier)[:12]}")
        claim_dir = self.root / 'runs' / '.locks'
        claim_dir.mkdir(parents=True, exist_ok=True)
        claim_path = claim_dir / (
            f"source-{source_enrichment._research_source_hash(SOURCE)[:16]}-{ord('木'):04X}.lock")

        class Runner:
            model = 'gpt-6-luna'
            reasoning = 'low'

        with claim_path.open('a') as claim:
            fcntl.flock(claim, fcntl.LOCK_EX | fcntl.LOCK_NB)
            before = sorted(str(path.relative_to(job)) for path in job.rglob('*'))
            with patch.object(source_enrichment, 'resolve_source_findings') as resolve:
                rows = source_enrichment.revalidate_published_source_jobs([job], Runner(), self.root)
            after = sorted(str(path.relative_to(job)) for path in job.rglob('*'))

        self.assertEqual(rows[0]['status'], 'already_running', rows[0])
        resolve.assert_not_called()
        self.assertEqual(after, before)
        self.assertFalse(pair_dir.exists())
        self.assertEqual(editorial.read(job / 'source_resolution.json'), old_resolution)

    def test_source_only_revalidation_republishes_published_pair_after_gate_clears(self):
        job = source_enrichment.job_path(self.output, SOURCE['id'], '木')
        article = editorial.read(job / 'source_article.json')
        dossier = editorial.read(job / 'source_dossier.json')
        reviews = [editorial.make_review(role, 'pass', [], article, dossier, 'republish-' + role)
                   for role in ('factual', 'readability')]
        for name, value in [('article.json', article), ('dossier.json', dossier),
                            ('reviews.json', reviews),
                            ('source_findings.json', {'requires_coordinator_verification': True,
                                'findings': [{'key': 'identity', 'details': 'Identity unresolved.'}]}),
                            ('source_resolution.json', {'verified': True})]:
            editorial.write(job / name, value)
        from pipeline.source_adoption import _used_ids
        used = _used_ids(article)
        audit = {'verified': True, 'source_hash': source_enrichment._research_source_hash(SOURCE),
                 'citations': [e for e in dossier['evidence'] if e.get('id') in used]}
        editorial.write(job / 'source_audit.json', audit)
        prior_status = {'status': 'published', 'source_audit_hash': editorial.digest(audit),
            'issue_sync_status': 'synced', 'published_at': '2026-10-02T12:00:00Z',
            'canonical_entry': str(self.root / 'content/entries/6728.json')}
        editorial.write(job / 'status.json', prior_status)

        class Runner:
            model = 'gpt-6-luna'
            reasoning = 'low'

        def publish(candidate, source, root):
            self.assertEqual(candidate, job)
            self.assertEqual(editorial.read(job / 'status.json')['status'], 'approved')
            return {'status': 'published', 'character': '木', 'job': str(job)}

        with patch.object(source_enrichment, '_source_findings_pending', return_value=False), \
             patch.object(source_enrichment, 'resolve_source_findings') as resolve, \
             patch.object(source_enrichment, '_publish_job_locked', side_effect=publish):
            rows = source_enrichment.revalidate_published_source_jobs([job], Runner(), self.root)
        self.assertEqual(rows[0]['status'], 'published', rows[0])
        resolve.assert_not_called()
        attempt = job / 'source-only-revalidation' / (
            f"{editorial.digest(article)[:12]}-{editorial.digest(dossier)[:12]}")
        self.assertEqual(editorial.read(attempt / 'prior-status.json'), prior_status)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.output = self.root / "runs"
        dossier = copy.deepcopy(DOSSIER)
        dossier["glyph_research"] = {"historical_glyphs": copy.deepcopy(GLYPHS)}
        dossier["glyph_assets"] = []
        article = copy.deepcopy(ARTICLE_V2)
        # Publish a genuine canonical fixture so preparation exercises the real gate.
        reviews = [editorial.make_review(role, "pass", [], article, dossier, f"fixture-{role}")
                   for role in ("factual", "readability")]
        editorial.publish(article, dossier, reviews, self.root / "content/entries")
        with patch.object(source_enrichment, "_load_source_tools", return_value=LocalSources()):
            self.snapshot = source_enrichment.prepare_job("木", source_enrichment.job_path(
                self.output, SOURCE["id"], "木"), SOURCE, self.root)

    def test_prepare_freezes_exact_published_inputs_and_refuses_rebinding(self):
        job = source_enrichment.job_path(self.output, SOURCE["id"], "木")
        article = editorial.read(job / "source_article.json")
        dossier = editorial.read(job / "source_dossier.json")
        self.assertEqual(editorial.digest(article), self.snapshot["article_hash"])
        self.assertEqual(editorial.digest(dossier), self.snapshot["dossier_hash"])
        self.assertEqual(source_enrichment.prepare_job("木", job, SOURCE, self.root), self.snapshot)
        metadata_update = {**SOURCE, "github_repo": "owner/repo", "issue_parent_number": 1,
                           "issue_milestone": "Source-enrichment smoke", "issue_labels": ["scope:hsk1"]}
        self.assertEqual(source_enrichment.prepare_job("木", job, metadata_update, self.root), self.snapshot)
        with self.assertRaisesRegex(ValueError, "another source"):
            source_enrichment.prepare_job("木", job, {**SOURCE, "id": "other"}, self.root)
        with self.assertRaisesRegex(ValueError, "another source"):
            source_enrichment.prepare_job("木", job, {**SOURCE, "bibliography": "different edition"}, self.root)

    def test_frozen_input_recovery_requires_exact_unchanged_baseline(self):
        job = source_enrichment.job_path(self.output, SOURCE['id'], '木')
        original = editorial.read(job / 'source_article.json')
        collided = {**original, 'summary': {'text': 'A continuation draft', 'evidence_ids': []}}
        editorial.write(job / 'source_article.json', collided)
        snapshot = editorial.read(job / 'source.json')
        with patch.object(source_enrichment, '_canonical', return_value=(collided, DOSSIER)):
            with self.assertRaisesRegex(ValueError, 'baseline changed'):
                source_enrichment.recover_frozen_inputs(job, self.root)
        self.assertEqual(editorial.read(job / 'source_article.json'), collided)
        with (job / 'coordinator.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with self.assertRaisesRegex(ValueError, 'agent is live'):
                source_enrichment.recover_frozen_inputs(job, self.root)
        receipt = source_enrichment.recover_frozen_inputs(job, self.root)
        self.assertEqual(editorial.read(Path(receipt['archive']) / 'source_article.json'), collided)
        self.assertEqual(editorial.read(job / 'source_article.json'), original)
        self.assertEqual(editorial.read(job / 'source.json'), snapshot)
        self.assertFalse(receipt['creates_authorship_or_approval'])
        self.assertEqual(source_enrichment.recover_frozen_inputs(job, self.root), {'status': 'unchanged'})

    def test_cohort_selection_is_bounded_and_workers_must_be_positive(self):
        cohort = {"characters": ["木", "水", "火", "土"]}
        # Only 木 is canonical in the fixture; other entries fail preparation independently.
        result = source_enrichment.prepare(cohort, SOURCE, self.output, limit=2, root=self.root)
        self.assertEqual([row["status"] for row in result], ["prepared", "failed", "deferred", "deferred"])
        with self.assertRaisesRegex(ValueError, "must be positive"):
            source_enrichment.run(cohort, SOURCE, self.output, object(), workers=0, root=self.root)

    def test_unfinished_draft_continuation_keeps_baseline_and_requires_fresh_gates(self):
        previous = source_enrichment.job_path(self.output, SOURCE['id'], '木')
        snapshot = editorial.read(previous / 'source.json')
        article = editorial.read(previous / 'source_article.json')
        dossier = editorial.read(previous / 'source_dossier.json')
        article['summary']['text'] = 'Wood and trees.'
        editorial.write(previous / 'article.json', article)
        editorial.write(previous / 'dossier.json', dossier)
        editorial.write(previous / 'status.json', {'status': 'needs_revision'})
        revision = editorial.make_review('factual', 'revise', ['Verify this exact draft claim.'],
                                         article, dossier, 'fixture-review')
        stale = {**revision, 'article_hash': 'older-draft'}
        approval = editorial.make_review('readability', 'pass', [], article, dossier, 'fixture-pass')
        editorial.write(previous / 'reviews.json', [revision, stale, approval])
        record = dossier['evidence'][0]
        lead = {k: record.get(k) for k in ('source', 'field', 'text')}
        lead['evidence_ids'] = [record['id'], 'not-retained']
        editorial.write(previous / 'source_audit.json', {'verified': False,
            'consulted_citations': [lead, {**lead, 'text': 'Different source claim'}]})
        job = self.root / 'fresh-job'
        job.mkdir()
        result = source_enrichment._continuation_inputs(previous, job, '木', SOURCE, snapshot)
        self.assertEqual(result[0]['summary']['text'], 'Wood and trees.')
        self.assertEqual(editorial.read(previous / 'source_article.json')['summary'],
                         ARTICLE_V2['summary'])
        self.assertTrue(editorial.read(job / 'continuation.json')['requires_fresh_research_and_reviews'])
        self.assertFalse((job / 'reviews.json').exists())
        self.assertEqual(editorial.read(job / 'continuation_review_proposals.json'), [revision])
        leads = editorial.read(job / 'continuation_book_leads.json')
        self.assertTrue(leads['requires_current_source_research'])
        self.assertEqual(leads['records'], [{**lead, 'evidence_ids': [record['id']]}])
        self.assertFalse((job / 'source_audit.json').exists())
        with self.assertRaisesRegex(ValueError, 'baseline changed'):
            source_enrichment._continuation_inputs(previous, self.root / 'other-job', '木', SOURCE,
                                                   {**snapshot, 'article_hash': 'changed'})
        with (previous / 'coordinator.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with self.assertRaisesRegex(ValueError, 'live coordinator'):
                source_enrichment._continuation_inputs(previous, job, '木', SOURCE, snapshot)

    def test_independent_review_receives_source_followup_questions(self):
        job = self.root / 'review-handoff'
        article = copy.deepcopy(ARTICLE_V2)
        dossier = editorial.read(source_enrichment.job_path(self.output, SOURCE['id'], '木') / 'source_dossier.json')
        feedback = {'additional_research_context': {'superseded_record': 'Old page is an unrelated headword'},
                    'superseded_book_evidence_ids': ['old-record']}
        packets = []
        def capture(role, candidate, evidence, directory, runner, context):
            packets.append((role, context))
            return editorial.make_review(role, 'pass', [], candidate, evidence, f'fixture-{role}')
        with patch.object(editorial, 'independent_review', side_effect=capture):
            state = editorial.review_article(article, dossier, job, object(), {}, 0,
                                               feedback, edit_first=False)
        self.assertEqual(state['status'], 'approved')
        self.assertEqual([role for role, _ in packets], ['factual', 'readability'])
        for _, packet in packets:
            self.assertEqual(packet['source_followup_questions'], feedback)
            self.assertIn('not approvals', packet['source_followup_policy'])

    def test_refine_keeps_outer_source_snapshot_immutable(self):
        job = source_enrichment.job_path(self.output, SOURCE['id'], '木')
        article = editorial.read(job / 'source_article.json')
        dossier = editorial.read(job / 'source_dossier.json')
        draft = copy.deepcopy(article)
        draft['summary']['text'] = 'A different continuation draft.'
        with self.assertRaisesRegex(ValueError, 'nonnegative'):
            editorial.refine(draft, dossier, job, object(), max_revisions=-1)
        self.assertEqual(editorial.read(job / 'source_article.json'), article)
        self.assertEqual(editorial.read(job / 'source_dossier.json'), dossier)
        self.assertEqual(editorial.read(job / 'refine_input_article.json'), draft)
        self.assertEqual(source_enrichment.prepare_job('木', job, SOURCE, self.root), self.snapshot)

    def test_approved_continuation_requires_changed_source_inputs(self):
        previous = source_enrichment.job_path(self.output, SOURCE['id'], '木')
        snapshot = editorial.read(previous / 'source.json')
        for name in ('article', 'dossier'):
            editorial.write(previous / f'{name}.json', editorial.read(previous / f'source_{name}.json'))
        current = source_enrichment._locator_hash(LocalSources().locate_sources(None, '木', None))
        job = self.root / 'source-refresh'
        job.mkdir()
        with patch.object(source_enrichment, '_load_source_tools', return_value=LocalSources()):
            for locator_hash in (current, None):
                editorial.write(previous / 'status.json', {'status': 'approved', 'locator_hash': locator_hash})
                with self.assertRaisesRegex(ValueError, 'unfinished terminal'):
                    source_enrichment._continuation_inputs(previous, job, '木', SOURCE, snapshot)
            approved = {'status': 'approved', 'locator_hash': 'prior-source-inputs'}
            editorial.write(previous / 'status.json', approved)
            source_enrichment._continuation_inputs(previous, job, '木', SOURCE, snapshot)
        hold = editorial.read(previous / 'source-refresh-required.json')
        self.assertEqual(hold['previous_state'], approved)
        self.assertEqual(hold['current_locator_hash'], current)
        self.assertEqual(editorial.read(previous / 'status.json')['status'], 'needs_source_refresh')
        self.assertTrue(editorial.read(job / 'continuation.json')['requires_fresh_research_and_reviews'])
        self.assertFalse((job / 'reviews.json').exists())

    def test_run_uses_source_locator_and_research_first_refine(self):
        job = source_enrichment.job_path(self.output, SOURCE["id"], "木")
        captured = {}
        extra_context = {'review_existing_glyphs': True, 'additional_source_leads': [{'url': 'https://example.org/primary-record',
                                                     'scope_character': '木'}]}

        class FakeRunner:
            model = "gpt-6-luna"
            reasoning = "low"

        def fake_refine(article, dossier, directory, runner, max_revisions, feedback, research_first):
            captured.update(article=article, dossier=dossier, directory=Path(directory), runner=runner,
                            feedback=feedback, research_first=research_first)
            # Store the exact reviewed products that the publication helper will later bind.
            article = copy.deepcopy(ARTICLE_V2)
            dossier = copy.deepcopy(DOSSIER)
            dossier["glyph_research"] = {"historical_glyphs": copy.deepcopy(GLYPHS)}
            dossier["glyph_assets"] = []
            source_evidence = {**dossier["evidence"][0], "id": "X-book-page",
                "source": "李學勤主編《字源》 (2012)", "field": "PDF page 123",
                "text": "The book records a page-specific historical account."}
            dossier["evidence"].append(source_evidence)
            article["summary"]["evidence_ids"].append(source_evidence["id"])
            research = copy.deepcopy(RESEARCH)
            research["evidence"] = [{key: value for key, value in source_evidence.items() if key != "id"}]
            editorial.write(Path(directory) / "initial-followup/research/result.json", research)
            editorial.write(Path(directory) / "initial-followup/research/meta.json", {
                "status": "complete", "role": "research", "model": "gpt-6-luna",
                "reasoning": "low", "web_action_counts": {"search": 1},
                "result_hash": editorial.digest(research)})
            reviews = [editorial.make_review(role, "pass", [], article, dossier, f"new-{role}")
                       for role in ("factual", "readability")]
            editorial.write(Path(directory) / "article.json", article)
            editorial.write(Path(directory) / "dossier.json", dossier)
            editorial.write(Path(directory) / "reviews.json", reviews)
            return {"character": "木", "status": "approved", "article_hash": editorial.digest(article),
                    "dossier_hash": editorial.digest(dossier)}

        with patch.object(source_enrichment, "_load_source_tools", return_value=LocalSources()), \
             patch.object(source_enrichment.editorial, "refine", side_effect=fake_refine):
            result = source_enrichment.run({"characters": ["木"]}, SOURCE, self.output,
                                           FakeRunner(), root=self.root, research_context=extra_context)
        self.assertEqual(result[0]["status"], "approved")
        self.assertTrue(captured["research_first"])
        self.assertEqual(captured['feedback']['target_language'], 'zh')
        self.assertEqual(captured['feedback']['additional_research_context'], extra_context)
        self.assertTrue(captured['feedback']['review_existing_glyphs'])
        self.assertEqual(editorial.read(job / 'research_context.json'), extra_context)
        self.assertEqual(len(captured['runner'].inherited_lock_fds), 2)
        self.assertEqual(captured["feedback"]["source_leads"], LOCATED["source_leads"])
        self.assertTrue(captured["feedback"]["reuse_existing_glyph_candidates"])
        self.assertIn("OCR", captured["feedback"]["source_enrichment"]["record_ocr_uncertainty"])
        state = editorial.read(job / "status.json")
        self.assertEqual(state["locator_hash"], editorial.digest({**LOCATED, "character": "木"}))
        self.assertTrue(editorial.read(job / "source_audit.json")["verified"])
        self.assertEqual(editorial.read(job / "source_checkpoint.json")["status"], "research_complete")
        with patch.object(source_enrichment, "_load_source_tools", return_value=LocalSources()), \
             patch.object(source_enrichment.editorial, "refine", side_effect=AssertionError("approved work reran")):
            resumed = source_enrichment.run({"characters": ["木"]}, SOURCE, self.output,
                                            FakeRunner(), root=self.root)
            self.assertEqual(resumed[0]["status"], "approved")
        frozen = editorial.read(job / 'source_article.json')
        editorial.write(job / 'source_article.json', {**frozen, 'summary': {'text': 'Overwritten draft'}})
        with patch.object(source_enrichment, '_load_source_tools', return_value=LocalSources()):
            with self.assertRaisesRegex(ValueError, 'snapshot hash mismatch'):
                source_enrichment.publish_job(job, SOURCE, self.root)
        self.assertEqual(source_enrichment._canonical(self.root, '木')[0], frozen)

    def test_published_completion_requires_source_job_hashes_and_canonical_match(self):
        job = source_enrichment.job_path(self.output, SOURCE["id"], "木")
        article, dossier = editorial.read(job / "source_article.json"), editorial.read(job / "source_dossier.json")
        reviews = [editorial.make_review(role, "pass", [], article, dossier, f"published-{role}")
                   for role in ("factual", "readability")]
        editorial.write(job / "article.json", article)
        editorial.write(job / "dossier.json", dossier)
        editorial.write(job / "reviews.json", reviews)
        with patch.object(source_enrichment, "_load_source_tools", return_value=LocalSources()):
            loc = LocalSources().locate_sources(SOURCE, "木", dossier)
            audit = {"verified": True, "source_hash": editorial.digest(SOURCE),
                     "citations": [{k: dossier["evidence"][0][k] for k in ("source", "field", "text")}]}
            editorial.write(job / "source_audit.json", audit)
            editorial.write(job / "status.json", {"status": "published", "source_id": SOURCE["id"],
                "registry_source_hash": editorial.digest(SOURCE), "locator_hash": editorial.digest(loc),
                "source_audit_hash": editorial.digest(audit),
                "article_hash": editorial.digest(article), "dossier_hash": editorial.digest(dossier)})
            self.assertTrue(source_enrichment._published_matches(job, SOURCE, self.root))
            fresh_output = self.root/'new-batch'
            cohort = {'characters': ['木']}
            for row in (source_enrichment.status(cohort, SOURCE, fresh_output, self.root)[0],
                        source_enrichment.prepare(cohort, SOURCE, fresh_output, root=self.root)[0],
                        source_enrichment.run(cohort, SOURCE, fresh_output, object(), root=self.root)[0]):
                self.assertEqual(row['status'], 'published')
                self.assertEqual(Path(row['job']), job.resolve())
            self.assertFalse((source_enrichment.job_path(fresh_output, SOURCE['id'], '木')/'source.json').exists())
            next_rows = source_enrichment.prepare({'characters':['木', '水']}, SOURCE,
                                                  fresh_output, limit=1, root=self.root)
            self.assertEqual([r['status'] for r in next_rows], ['published', 'failed'])
            self.assertEqual(source_enrichment.status(cohort, {**SOURCE, 'id':'another-book'},
                                                      fresh_output, self.root)[0]['status'], 'pending')
            editorial.write(job / "source_findings.json", {'requires_coordinator_verification': True,
                                                            'findings': [{'key': 'new-source-error'}]})
            self.assertFalse(source_enrichment._published_matches(job, SOURCE, self.root))
            self.assertEqual(source_enrichment.status(cohort, SOURCE, fresh_output,
                                                      self.root)[0]['status'], 'pending')
            (job / "source_findings.json").unlink()
            editorial.write(job / "status.json", {**editorial.read(job / "status.json"), "status": "approved"})
            with patch.object(LocalSources, 'locate_sources', return_value={'changed': 'page evidence'}):
                with self.assertRaisesRegex(ValueError, 'Source inputs changed'):
                    source_enrichment.publish_job(job, SOURCE, self.root)
            editorial.write(job / "status.json", {**editorial.read(job / "status.json"), "status": "published"})
            editorial.write(job / "status.json", {**editorial.read(job / "status.json"), "article_hash": "stale"})
            self.assertFalse(source_enrichment._published_matches(job, SOURCE, self.root))
            self.assertEqual(source_enrichment.status(cohort, SOURCE, fresh_output,
                                                      self.root)[0]['status'], 'pending')
            self.assertEqual(source_enrichment.status({"characters": ["木"]}, SOURCE, self.output,
                                                       self.root)[0]["status"], "stale")

    def _write_candidate_coverage_audit(self, job, article, dossier):
        result = {'verdict': 'pass', 'evidence_ids': ['source:1'], 'findings': []}
        editorial.write(job / 'source-coverage/result.json', result)
        editorial.write(job / 'source-coverage/meta.json', {'role': 'source_coverage',
            'status': 'complete', 'model': 'gpt-6-luna', 'reasoning': 'low',
            'result_hash': editorial.digest(result)})
        audit = {'source_id': SOURCE['id'],
            'source_hash': source_enrichment._research_source_hash(SOURCE),
            'mode': 'source_coverage_candidate', 'verified': True,
            'coverage_review_path': 'source-coverage',
            'coverage_result_hash': editorial.digest(result),
            'article_hash': editorial.digest(article), 'dossier_hash': editorial.digest(dossier),
            'citations': [{k: dossier['evidence'][0][k] for k in ('source', 'field', 'text')}]}
        editorial.write(job / 'source_audit.json', audit)
        return audit

    def test_candidate_coverage_audit_is_revalidated_for_completion_and_publish(self):
        job = source_enrichment.job_path(self.output, SOURCE['id'], '木')
        article, dossier = (editorial.read(job / 'source_article.json'),
                            editorial.read(job / 'source_dossier.json'))
        reviews = [editorial.make_review(role, 'pass', [], article, dossier,
                                         f'candidate-coverage-{role}')
                   for role in ('factual', 'readability')]
        editorial.write(job / 'article.json', article)
        editorial.write(job / 'dossier.json', dossier)
        editorial.write(job / 'reviews.json', reviews)
        audit = self._write_candidate_coverage_audit(job, article, dossier)
        from pipeline.source_adoption import valid_audit
        self.assertTrue(valid_audit(job, audit, article, dossier))
        with patch.object(source_enrichment, '_load_source_tools', return_value=LocalSources()):
            locator = LocalSources().locate_sources(SOURCE, '木', dossier)
            editorial.write(job / 'status.json', {'status': 'published', 'source_id': SOURCE['id'],
                'registry_source_hash': source_enrichment._research_source_hash(SOURCE),
                'locator_hash': source_enrichment._locator_hash(locator),
                'source_audit_hash': editorial.digest(audit),
                'article_hash': editorial.digest(article), 'dossier_hash': editorial.digest(dossier)})
            self.assertTrue(source_enrichment._published_matches(job, SOURCE, self.root))

            # The outer audit hash alone is insufficient: the coverage stage is rechecked.
            editorial.write(job / 'source-coverage/result.json',
                {'verdict': 'revise', 'evidence_ids': ['source:1'], 'findings': ['material omission']})
            self.assertFalse(source_enrichment._published_matches(job, SOURCE, self.root))

            state = editorial.read(job / 'status.json')
            state['status'] = 'approved'
            state['source_audit_hash'] = editorial.digest(audit)
            editorial.write(job / 'status.json', state)
            with self.assertRaisesRegex(ValueError, 'coverage receipt does not bind'):
                source_enrichment.publish_job(job, SOURCE, self.root)

    def test_metadata_only_issue_settings_preserve_legacy_published_identity(self):
        job = source_enrichment.job_path(self.output, SOURCE["id"], "木")
        article, dossier = editorial.read(job / "source_article.json"), editorial.read(job / "source_dossier.json")
        reviews = [editorial.make_review(role, "pass", [], article, dossier, f"legacy-{role}")
                   for role in ("factual", "readability")]
        editorial.write(job / "article.json", article)
        editorial.write(job / "dossier.json", dossier)
        editorial.write(job / "reviews.json", reviews)
        # Existing jobs stored a hash of the full registry object before issue
        # configuration was introduced. Keep that receipt bound to its snapshot.
        audit = {"verified": True, "source_hash": editorial.digest(SOURCE),
                     "citations": [{k: dossier["evidence"][0][k] for k in ("source", "field", "text")}]}
        editorial.write(job / "source_audit.json", audit)
        with patch.object(source_enrichment, "_load_source_tools", return_value=LocalSources()):
            locator = LocalSources().locate_sources(SOURCE, "木", dossier)
            editorial.write(job / "status.json", {"status": "published", "source_id": SOURCE["id"],
                "registry_source_hash": editorial.digest(SOURCE), "locator_hash": editorial.digest(locator),
                "source_audit_hash": editorial.digest(audit), "article_hash": editorial.digest(article),
                "dossier_hash": editorial.digest(dossier)})
            configured = {**SOURCE, "github_repo": "owner/repo",
                "tracking_issue_url": "https://github.com/owner/repo/issues/1",
                "issue_parent_number": 1, "issue_milestone": "Source-enrichment smoke",
                "issue_labels": ["scope:hsk1", "source:ziyuan"]}
            self.assertTrue(source_enrichment._published_matches(job, configured, self.root))
            self.assertNotIn("github_repo", source_enrichment.feedback(configured)["source_enrichment"]["source"])
            self.assertFalse(source_enrichment._published_matches(job,
                {**configured, "bibliography": "A different edition"}, self.root))

    def test_only_luna_low_runner_is_accepted(self):
        class WrongRunner:
            model = "other-model"
            reasoning = "high"

        with patch.object(source_enrichment, "_load_source_tools", return_value=LocalSources()):
            result = source_enrichment.run({"characters": ["木"]}, SOURCE, self.output,
                                           WrongRunner(), root=self.root)
        self.assertEqual(result[0]["status"], "failed")
        self.assertIn("gpt-6-luna with low", result[0]["error"])

    def test_scan_uncertainty_is_saved_for_coordinator_and_blocks_publish(self):
        job = source_enrichment.job_path(self.output, SOURCE["id"], "木")
        editorial.write(job / "round-0/followup/research-repair-1/result.json", {"gaps": [
            "[SCAN VERIFICATION REQUIRED] PDF page 123, span 鬼: OCR headword identity is unclear.",
            "[OCR CORRECTION REQUIRED] PDF page 124, span 木: confirm transposition.",
            "Sound comparison remains disputed."]})
        finding = source_enrichment._capture_scan_findings(job, SOURCE)
        self.assertTrue(finding["requires_coordinator_verification"])
        self.assertEqual(len(finding["findings"]), 2)
        state = {"status": "approved"}
        editorial.write(job / "status.json", state)
        with self.assertRaisesRegex(ValueError, "require coordinator verification"):
            source_enrichment.publish_job(job, SOURCE, self.root)

    def test_source_audit_requires_successful_hash_bound_research(self):
        job = source_enrichment.job_path(self.output, SOURCE["id"], "木")
        evidence = {"id": "X-book", "source": "字源", "field": "PDF page 123", "text": "A cited account."}
        result = {"evidence": [evidence]}
        stage = job / "initial-followup/research"
        editorial.write(stage / "result.json", result)
        dossier = {"evidence": [evidence]}
        editorial.write(job / "article.json", {"text": "A sourced claim", "evidence_ids": ["X-book"]})
        self.assertFalse(source_enrichment._capture_source_audit(job, SOURCE, dossier)["verified"])
        receipt = {"status": "complete", "role": "research", "model": "gpt-6-luna",
                   "reasoning": "low", "result_hash": editorial.digest(result),
                   "web_action_counts": {"search": 1}}
        for change in ({"status": "failed"}, {"result_hash": "altered"},
                       {"web_action_counts": {}}, {"model": "other"}):
            editorial.write(stage / "meta.json", {**receipt, **change})
            self.assertFalse(source_enrichment._capture_source_audit(job, SOURCE, dossier)["verified"])
        editorial.write(stage / "meta.json", receipt)
        audit = source_enrichment._capture_source_audit(job, SOURCE, dossier)
        self.assertTrue(audit["verified"])
        self.assertEqual(audit["citations"][0]["research_receipt_hash"], editorial.digest(receipt))
        editorial.write(job / "article.json", {"text": "No book citation", "evidence_ids": []})
        uncited = source_enrichment._capture_source_audit(job, SOURCE, dossier)
        self.assertFalse(uncited["verified"])
        self.assertEqual(uncited["consulted_citations"][0]["evidence_ids"], ["X-book"])
        foreign = {**evidence, "source": "香港教育局 字源考釋"}
        foreign_result = {"evidence": [foreign]}
        editorial.write(stage / "result.json", foreign_result)
        editorial.write(stage / "meta.json", {**receipt, "result_hash": editorial.digest(foreign_result)})
        editorial.write(job / "article.json", {"text": "A cited claim", "evidence_ids": ["X-book"]})
        self.assertFalse(source_enrichment._capture_source_audit(job, SOURCE, {"evidence": [foreign]})["verified"])

    def test_page_provenance_can_live_in_reader_friendly_source_details(self):
        self.assertTrue(source_enrichment._has_page_provenance({
            'source': '李學勤主編《字源》 (2012), PDF p.718', 'field': 'headword explanation'}))
        self.assertTrue(source_enrichment._has_page_provenance({'title': 'Book, printed p. 705'}))
        self.assertFalse(source_enrichment._has_page_provenance({'source': 'Book (2012)', 'field': 'headword'}))
        self.assertFalse(source_enrichment._book_identity_matches('香港教育局 字源考釋', SOURCE))

    def test_sync_publication_does_not_overwrite_confirmed_issue_hold(self):
        from types import SimpleNamespace
        job = self.root / 'sync-confirmed-issue'
        editorial.write(job / 'status.json', {'character':'木', 'status':'approved'})
        def sync(*args):
            editorial.write(job / 'status.json', {'character':'木', 'status':'needs_revision'})
            return {'status':'synced', 'editorial_hold':True}
        with patch.object(source_enrichment, '_triage_and_sync_issues', side_effect=sync), \
                patch.object(source_enrichment, '_publish_job_locked') as publisher:
            result = source_enrichment.sync_and_publish_job(job, {}, SimpleNamespace(), self.root)
        self.assertEqual(result['status'], 'needs_revision')
        self.assertEqual(editorial.read(job / 'status.json')['status'], 'needs_revision')
        publisher.assert_not_called()

    def test_confirmed_editorial_issue_holds_publication_without_changing_reviews(self):
        from pipeline import issues
        job = self.root / 'confirmed-issue-job'
        editorial.write(job / 'status.json', {'status':'approved'})
        editorial.write(job / 'reviews.json', [{'receipt':'preserve exact bytes'}])
        before = (job / 'reviews.json').read_bytes()
        finding = {'kind':'factual', 'key':'fixture:defect'}
        with patch.object(issues, 'triage_job', return_value=[finding]), \
                patch.object(issues, 'sync', return_value=[]):
            result = source_enrichment._triage_and_sync_issues(job, {'github_repo':'owner/repo'}, object())
        self.assertTrue(result['editorial_hold'])
        state = editorial.read(job / 'status.json')
        self.assertEqual(state['status'], 'needs_revision')
        self.assertEqual(state['stop_reason'], 'confirmed_issue_findings')
        self.assertEqual((job / 'reviews.json').read_bytes(), before)

    def test_uncited_book_integration_uses_current_research_and_fresh_reviews(self):
        job = self.root / 'citation-job'
        for name, value in [('article.json', ARTICLE_V2), ('dossier.json', DOSSIER),
                            ('reviews.json', []), ('status.json', {'status': 'needs_source_evidence'})]:
            editorial.write(job / name, value)
        changed = copy.deepcopy(ARTICLE_V2)
        changed['summary']['text'] += ' changed'
        audit = {'verified': False, 'consulted_citations': [{'evidence_ids': ['fixture-book']}]}
        def fixture_refine(article, dossier, stage, runner, revisions, feedback, research_first, edit_first,
                           approved_base):
            self.assertFalse(research_first)
            self.assertFalse(edit_first)
            self.assertEqual(feedback['current_uncited_book_records'], audit['consulted_citations'])
            self.assertEqual(approved_base, {'article': ARTICLE_V2, 'dossier': DOSSIER, 'reviews': []})
            for name, value in [('article.json', article), ('dossier.json', dossier), ('reviews.json', [])]:
                editorial.write(stage / name, value)
            return {'status': 'needs_revision'}
        with patch.object(editorial, 'refine', side_effect=fixture_refine) as refine, \
                patch.object(editorial, 'author_book_citations', return_value=changed), \
                patch.object(editorial, 'validate_reviews') as validate, \
                patch.object(source_enrichment, '_capture_source_audit', return_value=audit):
            state, result = source_enrichment._integrate_uncited_book_records(
                job, SOURCE, object(), {'status': 'needs_source_evidence'}, audit, {}, 2)
            self.assertEqual(state['status'], 'needs_revision')
            self.assertEqual(refine.call_count, 1)

    def test_unchanged_citation_integration_keeps_source_hold(self):
        job = self.root / 'unchanged-citation-job'
        for name, value in [('article.json', ARTICLE_V2), ('dossier.json', DOSSIER), ('reviews.json', [])]:
            editorial.write(job / name, value)
        before = (job / 'reviews.json').read_bytes()
        state = {'status': 'needs_source_evidence'}
        audit = {'verified': False, 'consulted_citations': [{'evidence_ids': ['fixture-book']}]}
        with patch.object(editorial, 'refine') as refine, \
                patch.object(editorial, 'author_book_citations', return_value=ARTICLE_V2), \
                patch.object(editorial, 'validate_reviews'):
            result, result_audit = source_enrichment._integrate_uncited_book_records(
                job, SOURCE, object(), state, audit, {}, 2)
        refine.assert_not_called()
        self.assertEqual(result, state)
        self.assertEqual(result_audit, audit)
        self.assertEqual((job / 'reviews.json').read_bytes(), before)
        self.assertFalse(editorial.read(job / 'citation-integration/completion.json')['source_adoption_verified'])

    def test_book_citation_author_can_only_change_known_citation_arrays(self):
        evidence_id = DOSSIER['evidence'][0]['id']
        class FixtureRunner:
            result = {'edits': [{'path': 'summary/evidence_ids', 'evidence_ids': [evidence_id]}],
                      'unsupported_records': []}
            def run(self, role, inputs, schema, directory):
                self.schema = schema
                self.inputs = inputs
                return self.result
        runner = FixtureRunner()
        result = editorial.author_book_citations(ARTICLE_V2, DOSSIER, [], self.root / 'citation-author', runner)
        self.assertEqual(result['summary']['text'], ARTICLE_V2['summary']['text'])
        self.assertEqual(result['summary']['evidence_ids'], [evidence_id])
        runner.result = {'edits': [{'path': 'summary/text', 'evidence_ids': [evidence_id]}],
                         'unsupported_records': []}
        with self.assertRaises(editorial.ValidationError):
            editorial.author_book_citations(ARTICLE_V2, DOSSIER, [], self.root / 'bad-path', runner)
        runner.result = {'edits': [{'path': 'summary/evidence_ids', 'evidence_ids': ['unknown-id']}],
                         'unsupported_records': []}
        with self.assertRaises(editorial.ValidationError):
            editorial.author_book_citations(ARTICLE_V2, DOSSIER, [], self.root / 'bad-id', runner)
        runner.result = {'edits': [], 'unsupported_records': []}
        editorial.author_book_citations(ARTICLE_V2, DOSSIER, [], self.root / 'scoped', runner,
            {'allowed_citation_edit_paths': ['summary/evidence_ids'],
             'citation_correction_instructions': 'Remove the unsupported book citation here.',
             'superseded_book_evidence_ids': [evidence_id]})
        self.assertEqual(list(runner.inputs['candidate_claims']), ['summary/evidence_ids'])
        self.assertEqual(runner.inputs['correction_instructions'], 'Remove the unsupported book citation here.')
        self.assertEqual(runner.inputs['superseded_book_evidence_ids'], [evidence_id])
        with self.assertRaisesRegex(ValueError, 'existing evidence_ids'):
            editorial.author_book_citations(ARTICLE_V2, DOSSIER, [], self.root / 'bad-scope', runner,
                                            {'allowed_citation_edit_paths': ['summary/text']})
            self.assertEqual(validate.call_count, 1)
            self.assertTrue(list((job / 'before-citation-integration').glob('*/reviews.json')))
            source_enrichment._integrate_uncited_book_records(
                job, SOURCE, object(), state, audit, {}, 2)
            self.assertEqual(refine.call_count, 1)

    def test_source_audit_does_not_certify_unretained_or_unpaged_mentions(self):
        job = source_enrichment.job_path(self.output, SOURCE["id"], "木")
        editorial.write(job / "initial-followup/research/result.json", {"evidence": [
            {"source": "字源", "field": "historical_components", "text": "The book discusses the graph."}]})
        dossier = editorial.read(job / "source_dossier.json")
        audit = source_enrichment._capture_source_audit(job, SOURCE, dossier)
        self.assertFalse(audit["verified"])
        self.assertEqual(audit["citations"], [])


if __name__ == "__main__":
    unittest.main()
