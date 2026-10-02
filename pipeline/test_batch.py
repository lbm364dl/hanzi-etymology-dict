import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from pipeline import batch, editorial
from pipeline.test_editorial import ARTICLE_V2, DOSSIER, RESEARCH, GLYPH_RESEARCH, GLYPHS


class BatchTests(unittest.TestCase):
    def test_explicit_cohort_validation_and_pending_limit(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "cohort.json"
            editorial.write(path, {"characters": ["木", "木"]})
            with self.assertRaises(ValueError):
                batch.load_cohort(path)
            with patch("pipeline.batch.ready", side_effect=lambda c, root: c == "木"):
                self.assertEqual(batch.select_characters(["木", "水", "火"], 1), ["水"])
        with self.assertRaises(ValueError):
            batch.batch("status", {"characters": ["木"]}, "unused", workers=21)
        with patch("pipeline.batch.ready", return_value=True):
            self.assertEqual(batch.batch("status", {"characters": ["木"]}, "unused", workers=20),
                             [{"character": "木", "status": "ready"}])

    def test_bounded_command_run_failure_continuation_and_resume(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for char in ["木", "水", "火"]:
                dossier = {**copy.deepcopy(DOSSIER), "character": char}
                editorial.write(root / "content/dossiers" / f"{ord(char):04X}.json", dossier)
            script = root / "agent.py"
            count = root / "count"
            script.write_text('import sys,json,pathlib\n'
                f'sys.path.insert(0,{str(batch.ROOT)!r})\n'
                'from pipeline.test_editorial import ARTICLE_V2,RESEARCH,GLYPH_RESEARCH,GLYPHS\n'
                'role,output,count=sys.argv[1:]\n'
                'p=pathlib.Path(count);p.write_text(str(int(p.read_text())+1) if p.exists() else "1")\n'
                'inputs=json.JSONDecoder().raw_decode(sys.stdin.read().split("\\nINPUTS:\\n",1)[1])[0]\n'
                'if inputs["dossier"]["character"] == "水": raise RuntimeError("fixture failure")\n'
                'if role == "research": result=RESEARCH\n'
                'elif role == "glyph_research": result=GLYPH_RESEARCH\n'
                'elif role == "glyph_visual": result=GLYPHS\n'
                'elif role == "analysis": result={"supported_claims":[],"disagreements":[],"limitations":[]}\n'
                'elif role in ("writer","editor","revision"):\n'
                ' result={k:v for k,v in ARTICLE_V2.items() if k != "historical_glyphs"}\n'
                ' result["relationships"]=[r for r in result["relationships"] if r["predicate"] != "has_sense"]\n'
                'else: result={"verdict":"pass","findings":[]}\n'
                'pathlib.Path(output).write_text(json.dumps(result))\n')
            runner = editorial.Runner([sys.executable, str(script), "{role}", "{output}", str(count)], "fake")
            cohort = {"characters": ["木", "水", "火"]}
            output = root / "runs"
            results = batch.batch("run", cohort, output, runner, limit=2, root=root)
            self.assertEqual([r["status"] for r in results], ["approved", "failed"])
            self.assertFalse((output / "706B").exists())
            before = int(count.read_text())
            results = batch.batch("run", cohort, output, runner, limit=1, root=root)
            self.assertEqual(results[0]["status"], "approved")
            self.assertEqual(int(count.read_text()), before)
            batch.publish_job(output / "6728", root)
            self.assertTrue(batch.ready("木", root))
            self.assertTrue((root / "content/drafts/6728.json").exists())
            self.assertTrue((root / "content/provenance/6728.json").exists())
            self.assertEqual(len(batch.batch("status", cohort, output, root=root)), 3)
            # Re-publication archives the previous exact approved record.
            batch.publish_job(output / "6728", root)
            self.assertTrue(list((root / "content/review_history/batch/6728").rglob("entries/6728.json")))
            with self.assertRaises(ValueError):
                batch.publish_job(output / "6C34", root)

    def test_checkpoints_precede_work_and_retain_each_batch(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "runs"
            cohort = {"characters": ["木", "水", "火"]}
            def process(character, *_args):
                record = editorial.read(output / "batch-status.json")
                self.assertEqual(record["selected"], ["木", "水"])
                self.assertEqual(record["status"], "running")
                self.assertTrue((output / "batch-history" / record["batch_id"] / "0000.json").exists())
                return {"character": character, "status": "prepared"}
            with patch("pipeline.batch.ready", return_value=False), patch("pipeline.batch.process_character", side_effect=process):
                batch.batch("prepare", cohort, output, limit=2)
                first = editorial.read(output / "batch-status.json")
                snapshots = sorted((output / "batch-history" / first["batch_id"]).glob("*.json"))
                self.assertEqual([editorial.read(p)["completed"] for p in snapshots], [0, 1, 2, 2])
                self.assertEqual(first["status"], "completed")
                batch.batch("prepare", cohort, output, limit=2)
                second = editorial.read(output / "batch-status.json")
                self.assertNotEqual(first["batch_id"], second["batch_id"])
                self.assertEqual(len(list((output / "batch-history").iterdir())), 2)
                self.assertEqual(editorial.read(snapshots[-1]), first)

    def test_publication_preserves_complete_followup_research(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            job = root / "job"
            dossier = copy.deepcopy(DOSSIER)
            dossier["glyph_research"] = {"historical_glyphs": GLYPHS}
            added = {**dossier["evidence"][0], "id": "followup:1", "field": "followup",
                     "text": "An additional checked finding.", "url": "https://example.org/followup"}
            dossier["evidence"].append(added)
            audit = {"query": "targeted followup", "urls": [added["url"]], "outcome": "Inspected additional evidence."}
            dossier["external_research"]["search_audit"].append(audit)
            dossier["external_research"]["gaps"].append("Dating remains unresolved.")
            reviews = [editorial.make_review(role, "pass", [], ARTICLE_V2, dossier, role) for role in ("factual", "readability")]
            for name, value in (("status.json", {"status": "approved"}), ("article.json", ARTICLE_V2),
                                ("dossier.json", dossier), ("reviews.json", reviews), ("research/result.json", RESEARCH)):
                editorial.write(job / name, value)
            batch.publish_job(job, root)
            research = editorial.read(root / "content/research/6728.json")
            self.assertEqual(research["search_audit"], dossier["external_research"]["search_audit"])
            self.assertEqual(research["gaps"], dossier["external_research"]["gaps"])
            self.assertEqual(len(research["evidence"]), 2)
            self.assertEqual(research["evidence"][-1]["text"], added["text"])
            editorial.validate_research(research)
            retained = root / editorial.read(root / "content/provenance/6728.json")["retained_artifacts"]
            self.assertEqual(editorial.read(retained / "research/result.json"), RESEARCH)
            prior_reviews = editorial.read(retained / "reviews.json")
            editorial.write(retained / "obsolete-stage/result.json", {"old": True})
            editorial.write(job / "status.json", {"status": "approved"})
            changed_reviews = [editorial.make_review(role, "pass", [], ARTICLE_V2, dossier,
                               "fresh-" + role) for role in ("factual", "readability")]
            editorial.write(job / "reviews.json", changed_reviews)
            batch.publish_job(job, root)
            archives = list((root / "content/review_history/editorial_runs/6728").glob("*/reviews.json"))
            self.assertEqual(len(archives), 1)
            self.assertEqual(editorial.read(archives[0]), prior_reviews)
            self.assertEqual(editorial.read(retained / "reviews.json"), changed_reviews)
            self.assertFalse((retained / "obsolete-stage/result.json").exists())
            self.assertTrue((archives[0].parent / "obsolete-stage/result.json").exists())

    def test_publication_can_retire_an_unreferenced_evidence_record(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            job = root / "first"
            dossier = copy.deepcopy(DOSSIER)
            dossier["glyph_research"] = {"historical_glyphs": GLYPHS}
            unused = {**DOSSIER["evidence"][0], "id": "unused:1", "field": "unused",
                      "text": "This evidence is not cited by the entry."}
            dossier["evidence"].append(unused)
            reviews = [editorial.make_review(role, "pass", [], ARTICLE_V2, dossier, role)
                       for role in ("factual", "readability")]
            for name, value in (("status.json", {"status": "approved"}), ("article.json", ARTICLE_V2),
                                ("dossier.json", dossier), ("reviews.json", reviews)):
                editorial.write(job / name, value)
            batch.publish_job(job, root)

            repair = root / "repair"
            pruned = copy.deepcopy(dossier)
            pruned["evidence"] = [e for e in pruned["evidence"] if e["id"] != "unused:1"]
            reviews = [editorial.make_review(role, "pass", [], ARTICLE_V2, pruned, role)
                       for role in ("factual", "readability")]
            for name, value in (("status.json", {"status": "approved"}), ("article.json", ARTICLE_V2),
                                ("dossier.json", pruned), ("reviews.json", reviews)):
                editorial.write(repair / name, value)
            batch.publish_job(repair, root)
            self.assertNotIn("unused:1", {e["id"] for e in editorial.read(root / "content/dossiers/6728.json")["evidence"]})
            archived = list((root / "content/review_history/batch/6728").rglob("dossiers/6728.json"))
            self.assertEqual(len(archived), 1)
            self.assertIn("unused:1", {e["id"] for e in editorial.read(archived[0])["evidence"]})

    def test_prepare_does_not_rebuild_existing_dossier_or_snapshot(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            editorial.write(root / "content/dossiers/6728.json", DOSSIER)
            with patch("pipeline.batch.dossiers.prepare", side_effect=AssertionError("Unexpected rebuild")):
                packet = batch.prepare_job("木", root / "job", root)
                editorial.write(root / "content/dossiers/6728.json", {**DOSSIER, "context": {"new": True}})
                self.assertEqual(batch.prepare_job("木", root / "job", root), packet)


if __name__ == "__main__":
    unittest.main()
