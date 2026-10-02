import copy
import fcntl
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
            findings = {'requires_coordinator_verification': True, 'findings': [{'key': 'rare-glyph'}]}
            article, dossier = {'character': '一'}, {'evidence': []}
            editorial.write(job / 'source_findings.json', findings)
            editorial.write(job / 'article.json', article)
            editorial.write(job / 'dossier.json', dossier)
            self.assertTrue(source_enrichment._source_findings_pending(job))
            result = {'findings': [{'key': 'rare-glyph', 'disposition': 'unresolved_identity_not_used'}]}
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
            self.assertFalse(source_enrichment._source_findings_pending(job))
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

    def test_cohort_selection_is_bounded_and_workers_are_capped(self):
        cohort = {"characters": ["木", "水", "火", "土"]}
        # Only 木 is canonical in the fixture; other entries fail preparation independently.
        result = source_enrichment.prepare(cohort, SOURCE, self.output, limit=2, root=self.root)
        self.assertEqual([row["status"] for row in result], ["prepared", "failed", "deferred", "deferred"])
        with self.assertRaisesRegex(ValueError, "between 1 and 3"):
            source_enrichment.run(cohort, SOURCE, self.output, object(), workers=4, root=self.root)

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
        self.assertEqual(captured['feedback']['additional_research_context'], extra_context)
        self.assertTrue(captured['feedback']['review_existing_glyphs'])
        self.assertEqual(editorial.read(job / 'research_context.json'), extra_context)
        self.assertEqual(len(captured['runner'].inherited_lock_fds), 1)
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
            editorial.write(job / "source_findings.json", {'requires_coordinator_verification': True,
                                                            'findings': [{'key': 'new-source-error'}]})
            self.assertFalse(source_enrichment._published_matches(job, SOURCE, self.root))
            (job / "source_findings.json").unlink()
            editorial.write(job / "status.json", {**editorial.read(job / "status.json"), "status": "approved"})
            with patch.object(LocalSources, 'locate_sources', return_value={'changed': 'page evidence'}):
                with self.assertRaisesRegex(ValueError, 'Source inputs changed'):
                    source_enrichment.publish_job(job, SOURCE, self.root)
            editorial.write(job / "status.json", {**editorial.read(job / "status.json"), "status": "published"})
            editorial.write(job / "status.json", {**editorial.read(job / "status.json"), "article_hash": "stale"})
            self.assertFalse(source_enrichment._published_matches(job, SOURCE, self.root))
            self.assertEqual(source_enrichment.status({"characters": ["木"]}, SOURCE, self.output,
                                                       self.root)[0]["status"], "stale")

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

    def test_uncited_book_integration_uses_current_research_and_fresh_reviews(self):
        job = self.root / 'citation-job'
        for name, value in [('article.json', ARTICLE_V2), ('dossier.json', DOSSIER),
                            ('reviews.json', []), ('status.json', {'status': 'needs_source_evidence'})]:
            editorial.write(job / name, value)
        audit = {'verified': False, 'consulted_citations': [{'evidence_ids': ['fixture-book']}]}
        def fixture_refine(article, dossier, stage, runner, revisions, feedback, research_first, edit_first):
            self.assertFalse(research_first)
            self.assertFalse(edit_first)
            self.assertEqual(feedback['current_uncited_book_records'], audit['consulted_citations'])
            for name, value in [('article.json', article), ('dossier.json', dossier), ('reviews.json', [])]:
                editorial.write(stage / name, value)
            return {'status': 'needs_revision'}
        with patch.object(editorial, 'refine', side_effect=fixture_refine) as refine, \
                patch.object(editorial, 'author_book_citations', return_value=ARTICLE_V2), \
                patch.object(editorial, 'validate_reviews') as validate, \
                patch.object(source_enrichment, '_capture_source_audit', return_value=audit):
            state, result = source_enrichment._integrate_uncited_book_records(
                job, SOURCE, object(), {'status': 'needs_source_evidence'}, audit, {}, 2)
            self.assertEqual(state['status'], 'needs_revision')
            self.assertEqual(refine.call_count, 1)

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
