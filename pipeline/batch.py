"""Explicit, bounded, resumable per-character editorial cohorts."""
from __future__ import annotations
import argparse
import fcntl
import hashlib
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import time
import json
from pathlib import Path
import shutil

from pipeline import dossiers, editorial

ROOT = editorial.ROOT


def load_cohort(path):
    cohort = editorial.read(path)
    characters = cohort.get("characters")
    if not isinstance(characters, list) or not characters or any(not isinstance(c, str) or len(c) != 1 for c in characters):
        raise ValueError("Cohort requires an explicit nonempty array of single characters")
    if len(characters) != len(set(characters)):
        raise ValueError("Cohort contains duplicate characters")
    return cohort


def ready(character, root=ROOT):
    name = f"{ord(character):04X}.json"
    entry_path = Path(root) / "content/entries" / name
    dossier_path = Path(root) / "content/dossiers" / name
    if not entry_path.exists() or not dossier_path.exists():
        return False
    try:
        article = editorial.validate_published(editorial.read(entry_path), editorial.read(dossier_path))
    except (ValueError, KeyError, OSError, editorial.ValidationError):
        return False
    if article.get("schema_version") != 2 or not article.get("learner"):
        return False
    return all(not c["origin_form"] or c["origin_form"] == c["form"] or
               c.get("origin_relation") in ("full_form", "earlier_form", "variant_form", "simplified_form", "uncertain")
               for c in article["components"])


def select_characters(characters, limit=None, root=ROOT):
    if limit is not None and limit < 1:
        raise ValueError("Limit must be positive")
    pending = [c for c in characters if not ready(c, root)]
    return pending if limit is None else pending[:limit]


def prepare_job(character, job, root=ROOT):
    job, root = Path(job), Path(root)
    if (job / "source_dossier.json").exists():
        packet = editorial.read(job / "source_dossier.json")
        editorial.validate_dossier(packet)
        if packet["character"] != character:
            raise ValueError("Existing job belongs to another character")
        return packet
    source = root / "content/dossiers" / f"{ord(character):04X}.json"
    if not source.exists():
        dossiers.prepare([character], root=root)
    packet = editorial.read(source)
    editorial.validate_dossier(packet)
    if packet["character"] != character:
        raise ValueError("Source dossier belongs to another character")
    editorial.write(job / "source_dossier.json", packet)
    editorial.write(job / "dossier.json", packet)
    editorial.write(job / "status.json", {"character": character, "status": "prepared",
                                           "dossier_hash": editorial.digest(packet)})
    return packet


def _publish_job_locked(job, root, locked_character):
    """Archive replaced artifacts and retain real generation/review records before publication."""
    job, root = Path(job), Path(root)
    if editorial.read(job / "status.json").get("status") != "approved":
        raise ValueError("Only approved jobs can be published")
    article, dossier, reviews = [editorial.read(job / name) for name in ("article.json", "dossier.json", "reviews.json")]
    if article.get("character") != locked_character:
        raise ValueError("Publication character changed while acquiring its canonical lock")
    editorial.validate_reviews(article, dossier, reviews)
    name = f"{ord(article['character']):04X}.json"
    content = root / "content"
    current_path = content / "dossiers" / name

    # Source-enrichment jobs are based on a frozen published pair. Refuse to
    # publish if that pair changed since preparation, unless this exact candidate
    # is already canonical (safe idempotent retry after a completed publication).
    reviewed_baseline_hash = None
    source_path = job / "source.json"
    if source_path.is_file():
        source = editorial.read(source_path)
        baseline_article_hash = source.get("article_hash")
        baseline_dossier_hash = source.get("dossier_hash")
        snapshot_article_path, snapshot_dossier_path = job / "source_article.json", job / "source_dossier.json"
        if not snapshot_article_path.is_file() or not snapshot_dossier_path.is_file():
            raise ValueError("Source-enrichment job is missing its frozen canonical baseline")
        if (editorial.digest(editorial.read(snapshot_article_path)) != baseline_article_hash
                or editorial.digest(editorial.read(snapshot_dossier_path)) != baseline_dossier_hash):
            raise ValueError("Source-enrichment frozen baseline hash does not match its snapshot")
        current_entry_path = content / "entries" / name
        if not current_entry_path.is_file() or not current_path.is_file():
            raise ValueError("Source-enrichment canonical baseline is no longer published")
        current_dossier = editorial.read(current_path)
        current_entry = editorial.read(current_entry_path)
        # Published entry files include wrapper evidence, dossier, and review
        # receipts. Compare the exact validated article extracted from that
        # wrapper, matching the article hash frozen by source preparation.
        current_article = editorial.validate_published(current_entry, current_dossier)
        current_article_hash = editorial.digest(current_article)
        current_dossier_hash = editorial.digest(current_dossier)
        baseline_matches = (current_article_hash == baseline_article_hash
                            and current_dossier_hash == baseline_dossier_hash)
        exact_candidate = (current_article_hash == editorial.digest(article)
                           and current_dossier_hash == editorial.digest(dossier))
        if not baseline_matches and not exact_candidate:
            raise ValueError("Source-enrichment canonical baseline changed after job preparation")
        reviewed_baseline_hash = current_dossier_hash

    if current_path.exists():
        current = editorial.read(current_path)
        if not editorial.dossier_update_is_safe(current, dossier, article, reviewed_baseline_hash):
            raise ValueError("Current source dossier changed; review updated inputs before publishing")
    previous_path = content / "entries" / name
    if previous_path.exists():
        previous = editorial.read(previous_path)
        archive = content / "review_history" / "batch" / name[:-5] / editorial.digest(previous)
        for folder in ("entries", "dossiers", "drafts", "reviews", "research", "analyses", "provenance", "factual_reviews", "readability_reviews"):
            path = content / folder / name
            if path.exists():
                target = archive / folder / name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, target)
    retained = content / "editorial_runs" / name[:-5] / editorial.digest(article)
    # Unchanged prose may receive new research/reviews; preserve the previous receipt set.
    if retained.exists():
        manifest = {str(path.relative_to(retained)): hashlib.sha256(path.read_bytes()).hexdigest()
                    for path in sorted(retained.rglob("*")) if path.is_file()}
        prior = content / "review_history" / "editorial_runs" / name[:-5] / editorial.digest(manifest)
        if not prior.exists():
            shutil.copytree(retained, prior)
        shutil.rmtree(retained)
    # Keep exact model products/prompts/metadata; omit potentially large stdout/stderr logs.
    for path in job.rglob("*"):
        if path.is_file() and path.suffix in (".json", ".txt") and "attempts" not in path.relative_to(job).parts:
            target = retained / path.relative_to(job)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
    result = editorial.publish(article, dossier, reviews, content / "entries",
                               reviewed_baseline_hash=reviewed_baseline_hash)
    for folder, value in (("drafts", article), ("reviews", reviews)):
        editorial.write(content / folder / name, value)
    # The canonical research product represents all reviewed evidence and audits, including
    # glyph research and targeted follow-ups; original stage products remain retained above.
    complete_research = {
        "evidence": [{key: item[key] for key in editorial.EXTERNAL_EVIDENCE["required"]}
                     for item in dossier["evidence"] if item.get("url")],
        "search_audit": dossier["external_research"]["search_audit"],
        "gaps": dossier["external_research"]["gaps"]}
    editorial.validate_research(complete_research)
    editorial.write(content / "research" / name, complete_research)
    analysis_source = job / "analysis/result.json"
    if analysis_source.exists():
        editorial.write(content / "analyses" / name, editorial.read(analysis_source))
    for review in reviews:
        editorial.write(content / (review["role"] + "_reviews") / name, review)
    editorial.write(content / "provenance" / name, {"job": str(job.resolve()),
        "retained_artifacts": str(retained.relative_to(root)), "article_hash": editorial.digest(article),
        "dossier_hash": editorial.digest(dossier), "reviewers": [r["reviewer"] for r in reviews]})
    return result


def publish_job(job, root=ROOT):
    """Publish under a cross-process lock for this canonical character.

    Callers that also hold a job lock must acquire it first, then this canonical
    lock. Keeping that order avoids a job/canonical lock cycle across pipelines.
    """
    job, root = Path(job), Path(root)
    article_path = job / "article.json"
    if not article_path.is_file():
        raise ValueError("Publication job is missing its article")
    # This preliminary read selects the lock only; the candidate is re-read and
    # its character checked under the lock before any validation or mutation.
    character = editorial.read(article_path).get("character")
    if not isinstance(character, str) or len(character) != 1:
        raise ValueError("Publication article requires one character")
    lock_dir = root / "runs" / ".locks"
    lock_dir.mkdir(parents=True, exist_ok=True)
    lock_path = lock_dir / f"publish-{ord(character):04X}.lock"
    with lock_path.open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            return _publish_job_locked(job, root, character)
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def process_character(character, output, action, runner, root=ROOT, max_revisions=3, publish=False):
    job = Path(output) / f"{ord(character):04X}"
    try:
        packet = prepare_job(character, job, root)
        state = editorial.read(job / "status.json")
        if action == "run":
            if state.get("status") != "approved":
                state = editorial.run(packet, job, runner, max_revisions)
            else:
                editorial.validate_reviews(*[editorial.read(job / name) for name in ("article.json", "dossier.json", "reviews.json")])
        if action == "publish" or (action == "run" and publish and state.get("status") == "approved"):
            publish_job(job, root)
            return {"character": character, "status": "published", "job": str(job)}
        return {"character": character, "status": state["status"], "job": str(job)}
    except Exception as exc:
        result = {"character": character, "status": "failed", "job": str(job), "error": str(exc)}
        editorial.write(job / "batch_failure.json", result)
        return result


def batch(action, cohort, output, runner=None, limit=10, workers=10, root=ROOT, max_revisions=3, publish=False):
    if action not in ("prepare", "run", "status", "publish"):
        raise ValueError("Unknown batch action")
    if action == "run" and runner is None:
        raise ValueError("Run requires an agent runner")
    if workers < 1 or workers > 20:
        raise ValueError("Workers must be between 1 and 20")
    characters = cohort["characters"]
    if action == "status":
        return [{"character": c, "status": "ready" if ready(c, root) else
                 (editorial.read(Path(output) / f"{ord(c):04X}" / "status.json").get("status", "unknown")
                  if (Path(output) / f"{ord(c):04X}" / "status.json").exists() else "pending")}
                for c in characters]
    if action == "publish":
        approved = [c for c in characters if (Path(output) / f"{ord(c):04X}" / "status.json").exists()
                    and editorial.read(Path(output) / f"{ord(c):04X}" / "status.json").get("status") == "approved"]
        selected = select_characters(approved, limit, root)
    else:
        selected = select_characters(characters, limit, root)
    output = Path(output)
    started = datetime.now(timezone.utc).isoformat()
    batch_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + f"-{time.time_ns()}"
    history = output / "batch-history" / batch_id
    results = {}
    record = {"batch_id": batch_id, "action": action, "status": "running", "started_at": started,
        "cohort_hash": editorial.digest(cohort), "selected": selected, "workers": workers,
        "publish_requested": publish or action == "publish", "max_revisions": max_revisions,
        "model": getattr(runner, "model", None), "reasoning": getattr(runner, "reasoning", None)}
    checkpoint = 0

    def save_checkpoint():
        nonlocal checkpoint
        record.update(updated_at=datetime.now(timezone.utc).isoformat(), completed=len(results),
                      pending=[c for c in selected if c not in results],
                      results=[results[c] for c in selected if c in results])
        editorial.write(history / f"{checkpoint:04d}.json", record)
        editorial.write(output / "batch-status.json", record)
        checkpoint += 1

    # Persist the exact bounded selection before any character job can start.
    save_checkpoint()
    try:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(process_character, c, output, action, runner, root, max_revisions, publish): c for c in selected}
            for future in as_completed(futures):
                results[futures[future]] = future.result()
                save_checkpoint()
        record["status"] = "completed_with_failures" if any(
            r["status"] in ("failed", "needs_revision") for r in results.values()) else "completed"
    except BaseException as exc:
        record.update(status="interrupted", error=str(exc))
        raise
    finally:
        record["finished_at"] = datetime.now(timezone.utc).isoformat()
        save_checkpoint()
    return [results[c] for c in selected]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["prepare", "run", "status", "publish"])
    parser.add_argument("cohort", type=Path)
    parser.add_argument("--output", type=Path, default=ROOT / "runs/hsk3-2021-level-1")
    parser.add_argument("--limit", type=int, default=10, help="Maximum characters needing work in this invocation (default: 10)")
    parser.add_argument("--workers", type=int, default=10, help="Parallel character jobs, from 1 to 20")
    parser.add_argument("--publish", action="store_true", help="Publish approved outputs after run")
    parser.add_argument("--model", default="gpt-6-luna")
    parser.add_argument("--reasoning", default="low")
    parser.add_argument("--timeout", type=int, default=600)
    parser.add_argument("--max-revisions", type=int, default=3)
    parser.add_argument("--command", default=json.dumps(editorial.DEFAULT_COMMAND))
    args = parser.parse_args()
    command = json.loads(args.command)
    if not isinstance(command, list) or not command or not all(isinstance(v, str) for v in command):
        parser.error("Command must be a nonempty JSON array of strings")
    if args.timeout <= 0 or args.max_revisions < 0:
        parser.error("Timeout must be positive and revision budget nonnegative")
    result = batch(args.action, load_cohort(args.cohort), args.output,
        editorial.Runner(command, args.model, args.timeout, args.reasoning), args.limit, args.workers,
        max_revisions=args.max_revisions, publish=args.publish)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if any(r["status"] in ("failed", "needs_revision") for r in result):
        raise SystemExit(2)


if __name__ == "__main__":
    main()
