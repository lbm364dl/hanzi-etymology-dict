"""Read-only dashboard inventory, compactness, and Linux process matching tests."""
import json
import hashlib
import os
from pathlib import Path
import tempfile
import unittest

from pipeline.dashboard_data import Collector


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


def proc_fixture(root, pid, output_path, rss_pages=12):
    proc = root / "proc" / str(pid)
    proc.mkdir(parents=True)
    args = ["codex", "exec", "-o", str(output_path), "--", "hidden-prompt-secret"]
    (proc / "cmdline").write_bytes(b"\0".join(arg.encode() for arg in args) + b"\0")
    fields = ["S"] + ["0"] * 21
    fields[21] = str(rss_pages)
    (proc / "stat").write_text(f"{pid} (codex) " + " ".join(fields))
    (root / "proc" / "meminfo").write_text(
        "MemTotal: 1000 kB\nMemAvailable: 400 kB\nSwapTotal: 200 kB\nSwapFree: 150 kB\n")
    return root / "proc"


class DashboardDataTests(unittest.TestCase):
    def test_snapshot_joins_queue_jobs_live_proc_source_and_issue_summaries(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            job = root / "runs" / "scale" / "ziyuan-2012" / "6728"
            stage = job / "round-0" / "research"
            save(job / "status.json", {"character": "木", "status": "running",
                                        "article_hash": "a" * 64, "dossier_hash": "d" * 64})
            save(job / "source.json", {"character": "木", "source_id": "ziyuan-2012",
                                        "registry_source": {"id": "ziyuan-2012"}})
            save(job / "article.json", {"character": "木"})
            save(job / "dossier.json", {"character": "木"})
            save(job / "source_audit.json", {"verified": False, "source_id": "ziyuan-2012",
                                               "consulted_citations": [{"page": 1}]})
            save(job / "source_findings.json", {"requires_coordinator_verification": True,
                 "findings": [{"key": "ziyuan-2012:6728:identity", "kind": "ocr",
                               "title": "Check a printed form", "details": "Candidate differs from scan.",
                               "verification": "Check original scan pixels.",
                               "evidence": ["private detail"]}]})
            save(job / "source_resolution.json", {"review_path": "source-resolution/result.json"})
            save(job / "source-resolution/result.json", {"findings": [
                {"key": "ziyuan-2012:6728:identity", "disposition": "unresolved_identity_not_used"}]})
            save(job / "source_resolution_validation.json", {"status": "complete"})
            save(job / "issue_sync.json", {"status": "synced"})
            save(job / "issue_receipts.json", {"issues": [{"number": 23,
                 "url": "https://github.com/owner/repo/issues/23", "key": "ziyuan-2012:6728:identity",
                 "state": "OPEN"}]})
            save(job / "reviews.json", [{"role": "factual", "verdict": "pass",
                 "article_hash": "a" * 64, "dossier_hash": "d" * 64}])
            save(stage / "meta.json", {"role": "research", "status": "running",
                 "model": "gpt-6-luna", "reasoning": "low", "started_at": 1000})
            (stage / "prompt.txt").write_text("hidden-prompt-secret")
            (stage / "stdout.log").write_text("hidden-output-secret")
            queue = job.parents[0] / "queue.json"
            save(queue, {"identity": {"root": str(root)}, "workers": 24, "agent_capacity": 12,
                "status": "running",
                "updated_at": "2026-10-03T00:00:00Z", "summary": {"running": 1},
                "jobs": {"木": {"status": "running", "attempts": 2,
                    "started_at": "2026-10-03T00:00:00Z", "result": {"job": str(job)}}}})
            proc_root = proc_fixture(root, 4242, stage / "result.json")
            now = [50.0]
            collector = Collector(root, cache_seconds=5, proc_root=proc_root, clock=lambda: now[0])

            snapshot = collector.snapshot()
            row = next(item for item in snapshot["jobs"] if item["character"] == "木")
            self.assertEqual(snapshot["queues"][0]["workers"], 24)
            self.assertEqual(snapshot["queues"][0]["agent_capacity"], 12)
            self.assertEqual(row["liveness"], "live")
            self.assertEqual(row["active_stages"][0]["role"], "research")
            self.assertEqual(row["active_stages"][0]["pid"], 4242)
            self.assertEqual(row["active_stages"][0]["rss_bytes"], 12 * 4096)
            current_article = {"character": "木"}
            expected_hash = hashlib.sha256(json.dumps(current_article, ensure_ascii=False,
                sort_keys=True, separators=(",", ":")).encode()).hexdigest()
            self.assertEqual(row["article_hash"], expected_hash)
            self.assertEqual(row["hashes"]["article_hash"], expected_hash[:12])
            self.assertFalse(row["reviews"][0]["current_pair"])
            self.assertEqual(row["reviews"][0]["path"], str(job.relative_to(root) / "reviews.json"))
            self.assertEqual(row["findings"][0]["details"], "Candidate differs from scan.")
            self.assertEqual(row["findings"][0]["verification"], "Check original scan pixels.")
            self.assertEqual(row["source_audit"], {"verified": False, "source_id": "ziyuan-2012",
                                                    "citation_count": 1})
            self.assertEqual(row["source_resolution"]["status"], "dispositions_recorded")
            self.assertEqual(row["issues"][0]["number"], 23)
            self.assertEqual(snapshot["process_totals"]["active_codex_agents"], 1)
            self.assertEqual(snapshot["process_totals"]["agent_capacity"], 12)
            self.assertEqual(snapshot["machine"]["memory_available_bytes"], 400 * 1024)
            serialized = json.dumps(snapshot, ensure_ascii=False)
            self.assertNotIn("hidden-prompt-secret", serialized)
            self.assertNotIn("hidden-output-secret", serialized)
            self.assertNotIn("private detail", serialized)
            self.assertNotIn("cmdline", serialized)

            # Once the process disappears, the still-running stage is explicitly
            # stale. A completed stage gets a different, non-stale state.
            for child in proc_root.iterdir():
                if child.is_dir():
                    for file in child.iterdir():
                        file.unlink()
                    child.rmdir()
            now[0] += 2
            stale = collector.snapshot()
            row = next(item for item in stale["jobs"] if item["character"] == "木")
            self.assertEqual(row["liveness"], "stale")
            save(stage / "meta.json", {"role": "research", "status": "complete",
                 "model": "gpt-6-luna", "reasoning": "low", "started_at": 1000,
                 "finished_at": 1010})
            save(job / "status.json", {"character": "木", "status": "approved"})
            save(queue, {"identity": {"root": str(root)}, "workers": 24, "status": "idle",
                "summary": {"approved": 1},
                "jobs": {"木": {"status": "approved", "attempts": 2,
                    "result": {"job": str(job)}}}})
            now[0] += 2
            completed = collector.snapshot()
            row = next(item for item in completed["jobs"] if item["character"] == "木")
            self.assertEqual(row["liveness"], "completed")
            self.assertEqual(row["last_stage"]["elapsed_seconds"], 10)

    def test_includes_legacy_jobs_repairs_coverage_and_refreshes_inventory_by_ttl(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            legacy = root / "runs" / "legacy" / "6728"
            save(legacy / "status.json", {"status": "approved", "updated_at": "today"})
            save(legacy / "article.json", {"character": "木"})
            save(legacy / "dossier.json", {"character": "木"})
            save(root / "research" / "producer-patches" / "p71" / "verification.json",
                 {"other_pages_unchanged": True, "ocr_text_changed": False,
                  "raw_file_hashes": {"71": "abc"}})
            save(root / "research" / "hsk1-source-completion-20261003.json",
                 {"source_id": "ziyuan-2012", "characters_total": 300,
                  "verified_source_complete": 29})
            now = [0.0]
            collector = Collector(root, cache_seconds=5, proc_root=root / "no-proc",
                                  clock=lambda: now[0])
            initial = collector.snapshot()
            self.assertEqual(initial["warnings"], [])
            self.assertTrue(any(row["source_id"] is None and row["character"] == "木"
                                for row in initial["jobs"]))
            self.assertEqual(initial["repairs"][0]["pdf_pages"], ["71"])
            self.assertEqual(initial["coverage"]["verified_source_complete"], 29)
            save(root / "runs" / "new" / "7231" / "status.json", {"status": "prepared"})
            save(root / "runs" / "new" / "7231" / "article.json", {"character": "爱"})
            self.assertFalse(any(row["character"] == "爱" for row in collector.snapshot()["jobs"]))
            now[0] += 6
            refreshed = collector.snapshot()
            self.assertTrue(any(row["character"] == "爱" for row in refreshed["jobs"]))

    def test_proc_arguments_outside_root_are_never_reported(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            proc_root = proc_fixture(root, 555, root.parent / "secret" / "result.json")
            collector = Collector(root, proc_root=proc_root)
            snapshot = collector.snapshot()
            self.assertEqual(snapshot["processes"], [])

    def test_waiting_for_agent_slot_is_not_reported_as_a_live_or_stale_process(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            job = root / "runs" / "scale" / "book" / "6728"
            save(job / "status.json", {"character": "木", "status": "running"})
            save(job / "source.json", {"character": "木", "source_id": "book"})
            save(job / "round-0" / "factual" / "meta.json", {
                "role": "factual", "status": "waiting_for_agent_slot", "model": "gpt-6-luna",
                "reasoning": "low", "agent_capacity": 12, "queued_at": 100,
                "slot_wait_seconds": 3.5})
            queue = job.parents[0] / "queue.json"
            save(queue, {"workers": 24, "agent_capacity": 12, "status": "running",
                "jobs": {"木": {"status": "running", "result": {"job": str(job)}}}})
            proc_root = root / "proc"
            proc_root.mkdir()
            (proc_root / "meminfo").write_text("MemTotal: 100 kB\nMemAvailable: 50 kB\n")
            snapshot = Collector(root, proc_root=proc_root).snapshot()
            row = next(item for item in snapshot["jobs"] if item["character"] == "木")
            self.assertEqual(row["liveness"], "waiting")
            self.assertEqual(row["active_stages"][0]["status"], "waiting_for_agent_slot")
            self.assertIsNone(row["active_stages"][0]["pid"])
            self.assertEqual(snapshot["process_totals"]["waiting_for_agent_slot"], 1)
            self.assertEqual(snapshot["process_totals"]["active_codex_agents"], 0)

    def test_nested_job_stages_belong_to_deepest_job_and_finished_elapsed_uses_finish_time(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            outer = root / "runs" / "nested" / "book" / "6728"
            inner = outer / "reviewed-authorship" / "6728"
            stage = inner / "round-0" / "readability"
            for folder, status in ((outer, "running"), (inner, "needs_revision")):
                save(folder / "status.json", {"character": "木", "status": status})
                save(folder / "source.json", {"character": "木", "source_id": "book"})
                save(folder / "article.json", {"character": "木"})
            save(stage / "meta.json", {"role": "readability", "status": "complete",
                 "model": "gpt-6-luna", "reasoning": "low", "started_at": 100,
                 "finished_at": 130})
            snapshot = Collector(root, proc_root=root / "no-proc").snapshot()
            outer_row = next(row for row in snapshot["jobs"] if row["path"] == outer.relative_to(root).as_posix())
            inner_row = next(row for row in snapshot["jobs"] if row["path"] == inner.relative_to(root).as_posix())
            self.assertEqual(outer_row["stage_count"], 0)
            self.assertEqual(inner_row["stage_count"], 1)
            self.assertEqual(inner_row["last_stage"]["elapsed_seconds"], 30)
            self.assertEqual(inner_row["hash_origins"], {"article_hash": "current_job",
                                                          "dossier_hash": "unavailable"})
            self.assertEqual(inner_row["hash_origin"], "mixed")

    def test_relative_queue_paths_resolve_from_dashboard_root_not_process_cwd(self):
        with tempfile.TemporaryDirectory() as temp, tempfile.TemporaryDirectory() as elsewhere:
            root = Path(temp)
            job = root / "runs" / "scale" / "book" / "6728"
            save(job / "status.json", {"character": "木", "status": "prepared"})
            save(job / "source.json", {"character": "木", "source_id": "book"})
            queue = job.parents[0] / "queue.json"
            save(queue, {"workers": 24, "jobs": {"木": {"status": "queued", "attempts": 4,
                "result": {"job": "runs/scale/book/6728"}}}})
            original = Path.cwd()
            try:
                os.chdir(elsewhere)
                snapshot = Collector(root, proc_root=root / "no-proc").snapshot()
            finally:
                os.chdir(original)
            row = next(row for row in snapshot["jobs"] if row["character"] == "木")
            self.assertEqual(row["queue"]["attempts"], 4)
            self.assertEqual(snapshot["queues"][0]["jobs"][0]["job"], "runs/scale/book/6728")

    def test_running_proc_without_running_meta_is_kept_as_deduplicated_orphan(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            job = root / "runs" / "orphan" / "book" / "6728"
            stage = job / "round-0" / "research"
            save(job / "status.json", {"character": "木", "status": "approved"})
            save(job / "source.json", {"character": "木", "source_id": "book"})
            save(stage / "meta.json", {"role": "research", "status": "complete"})
            proc_root = proc_fixture(root, 777, stage / "result.json", rss_pages=7)
            snapshot = Collector(root, proc_root=proc_root).snapshot()
            row = next(row for row in snapshot["jobs"] if row["character"] == "木")
            self.assertEqual(snapshot["process_totals"]["active_codex_agents"], 1)
            self.assertEqual(len(row["processes"]), 1)
            self.assertTrue(row["processes"][0]["orphan"])
            self.assertEqual(row["liveness"], "live")

    def test_nested_transaction_receipts_surface_patch_result_fields(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            transaction = root / "research" / "producer-patches" / "fix-1" / "transaction.json"
            save(transaction, {"status": "applied", "repairs": [{"pdf_page": 71,
                "before": "raw", "after": "corrected", "failed-after": "second attempt",
                "raw_unchanged": True, "unchanged_other_page_count": 1434}]})
            # Proof and before/after archives are omitted from inventory traversal.
            save(transaction.parent / "proof" / "large.json", {"huge": "ignored"})
            snapshot = Collector(root, proc_root=root / "no-proc").snapshot()
            repair = snapshot["repairs"][0]
            self.assertEqual(repair["status"], "applied")
            self.assertEqual(repair["pdf_pages"], ["71"])
            self.assertEqual(repair["events"][0]["after"], "corrected")
            self.assertEqual(repair["failed_after"], "second attempt")
            self.assertTrue(repair["raw_unchanged"])
            self.assertEqual(repair["unchanged_other_page_count"], 1434)

    def test_current_hashes_come_from_article_files_and_flag_stale_reviews(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            job = root / "runs" / "scale" / "book" / "6728"
            save(job / "source.json", {"character": "木", "source_id": "book",
                "article_hash": "b" * 64, "dossier_hash": "c" * 64})
            save(job / "status.json", {"status": "approved", "article_hash": "b" * 64,
                "dossier_hash": "c" * 64})
            article = {"character": "木", "meaning": "current article"}
            dossier = {"character": "木", "evidence": []}
            save(job / "article.json", article)
            save(job / "dossier.json", dossier)
            save(job / "reviews.json", [{"role": "factual", "verdict": "pass",
                "article_hash": "b" * 64, "dossier_hash": "c" * 64}])
            snapshot = Collector(root, proc_root=root / "no-proc").snapshot()
            row = next(row for row in snapshot["jobs"] if row["character"] == "木")
            expected_article = hashlib.sha256(json.dumps(article, ensure_ascii=False,
                sort_keys=True, separators=(",", ":")).encode()).hexdigest()
            expected_dossier = hashlib.sha256(json.dumps(dossier, ensure_ascii=False,
                sort_keys=True, separators=(",", ":")).encode()).hexdigest()
            self.assertEqual(row["article_hash"], expected_article)
            self.assertEqual(row["dossier_hash"], expected_dossier)
            self.assertEqual(row["hash_origin"], "current_job")
            self.assertFalse(row["reviews"][0]["current_pair"])
            self.assertEqual(row["reviews"][0]["path"], str(job.relative_to(root) / "reviews.json"))

    def test_unmatched_ocr_process_appears_as_standalone_with_page_provenance(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            stage = root / "runs" / "batch" / "ziyuan-2012" / "6728" / "ocr-verification-p71" / "review"
            save(stage / "meta.json", {"role": "ocr_verification", "status": "running",
                "model": "gpt-6-luna", "reasoning": "low", "started_at": 100})
            save(stage.parent / "occurrences.json", {"provenance": {"book": "字源, 2012",
                "source_id": "ziyuan-2012", "pdf_page": 71, "printed_page": 58,
                "scope": "One raw occurrence."}})
            proc_root = proc_fixture(root, 778, stage / "result.json", rss_pages=4)
            snapshot = Collector(root, proc_root=proc_root).snapshot()
            row = next(row for row in snapshot["jobs"] if row["type"] == "standalone_process")
            self.assertIsNone(row["character"])
            self.assertEqual(row["source_id"], "ziyuan-2012")
            self.assertEqual(row["page_label"], "p0071")
            self.assertEqual(row["source_provenance"]["printed_page"], 58)
            self.assertEqual(row["active_stages"][0]["role"], "ocr_verification")
            self.assertEqual(snapshot["process_totals"]["active_codex_agents"], 1)

    def test_recorded_coordination_is_exposed_without_claiming_liveness_or_approval(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            save(root / "runs" / "operations" / "coordination.json", {
                "status": "recorded", "updated_at": "2026-10-03T10:00:00Z",
                "tasks": [{"name": "dashboard", "status": "in_progress",
                           "owner": "root", "note": "Backend and UI work."}],
            })
            snapshot = Collector(root, proc_root=root / "no-proc").snapshot()
            self.assertEqual(snapshot["coordination"]["tasks"][0]["status"], "in_progress")
            self.assertIn("not evidence of agent liveness or approval",
                          snapshot["coordination"]["interpretation"])


if __name__ == "__main__":
    unittest.main()
