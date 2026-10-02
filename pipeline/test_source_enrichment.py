import copy
from pathlib import Path
import tempfile
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
    def test_locator_hash_ignores_only_redundant_pixel_metadata(self):
        located = {'source_scan_images': [{'pdf_page': 13, 'path': '/scan.png'}],
                   'source_leads': [{'candidates': [{'pdf_page_1based': 13, 'source_sha256': 'pixels'}]}]}
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
            editorial.write(job / 'source_resolution.json', {
                'findings_hash': editorial.digest(findings), 'article_hash': editorial.digest(article),
                'dossier_hash': editorial.digest(dossier), 'result_hash': editorial.digest(result),
                'model': 'gpt-6-luna', 'reasoning': 'low', 'review_path': 'source-resolution/result.json'})
            self.assertFalse(source_enrichment._source_findings_pending(job))
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

    def test_run_uses_source_locator_and_research_first_refine(self):
        job = source_enrichment.job_path(self.output, SOURCE["id"], "木")
        captured = {}

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
            research = copy.deepcopy(RESEARCH)
            research["evidence"] = [{key: value for key, value in source_evidence.items() if key != "id"}]
            editorial.write(Path(directory) / "initial-followup/research/result.json", research)
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
                                           FakeRunner(), root=self.root)
        self.assertEqual(result[0]["status"], "approved")
        self.assertTrue(captured["research_first"])
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
            audit = {"verified": True, "source_hash": editorial.digest(SOURCE), "citations": []}
            editorial.write(job / "source_audit.json", audit)
            editorial.write(job / "status.json", {"status": "published", "source_id": SOURCE["id"],
                "registry_source_hash": editorial.digest(SOURCE), "locator_hash": editorial.digest(loc),
                "source_audit_hash": editorial.digest(audit),
                "article_hash": editorial.digest(article), "dossier_hash": editorial.digest(dossier)})
            self.assertTrue(source_enrichment._published_matches(job, SOURCE, self.root))
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
        audit = {"verified": True, "source_hash": editorial.digest(SOURCE), "citations": []}
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
