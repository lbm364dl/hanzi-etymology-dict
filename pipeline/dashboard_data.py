"""Read-only, compact dashboard snapshots for editorial/source work."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import time


_SKIP_DIRS = {"attempts", "issue-bodies", "frozen-input-recovery", ".locks", "__pycache__"}
_SOURCE_REPORT = re.compile(r".*source-completion.*\.json$")


def _read(path, warnings, default=None):
    try:
        with Path(path).open(encoding="utf-8") as stream:
            return json.load(stream)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        if warnings is not None:
            if len(warnings) < 50:
                warnings.append({"path": str(path), "error_type": type(exc).__name__})
        return default


def _read_optional(path, warnings):
    return _read(path, warnings, None) if Path(path).is_file() else None


def _relative(path, root):
    try:
        return Path(path).relative_to(root).as_posix()
    except (ValueError, OSError):
        try:
            return Path(path).resolve().relative_to(root).as_posix()
        except (ValueError, OSError):
            return str(Path(path))


def _resolve_job_path(path, root):
    value = Path(path)
    if not value.is_absolute():
        value = Path(root) / value
    return value.resolve()


def _compact(value, limit=420):
    if not isinstance(value, str):
        return None
    value = " ".join(value.split())
    return value if len(value) <= limit else value[:limit - 1] + "…"


def _canonical_hash(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
        separators=(",", ":")).encode()).hexdigest()


def _character_from(path, source, warnings):
    if isinstance(source, dict):
        char = source.get("character")
        if isinstance(char, str) and len(char) == 1:
            return char
    for name in ("article.json", "dossier.json", "source_article.json", "source_dossier.json"):
        value = _read_optional(path / name, warnings)
        char = value.get("character") if isinstance(value, dict) else None
        if isinstance(char, str) and len(char) == 1:
            return char
    match = re.fullmatch(r"[0-9A-Fa-f]{4,6}", Path(path).name)
    if match:
        try:
            value = chr(int(match.group(), 16))
            if len(value) == 1:
                return value
        except (ValueError, OverflowError):
            pass
    return None


def _parse_time(value):
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
        except ValueError:
            return None
    return None


def _proc_records(proc_root, root):
    """Return only Codex processes whose -o target is inside this repository."""
    proc_root, root = Path(proc_root), Path(root).resolve()
    processes, seen_pids, reliable = {}, set(), proc_root.is_dir()
    if not reliable:
        return processes, False
    page_size = os.sysconf("SC_PAGE_SIZE")
    for entry in proc_root.iterdir():
        if not entry.name.isdigit():
            continue
        try:
            raw = (entry / "cmdline").read_bytes()
            args = [part.decode("utf-8", "replace") for part in raw.split(b"\0") if part]
            if not args:
                continue
            output = None
            for index, arg in enumerate(args[:-1]):
                if arg == "-o":
                    output = args[index + 1]
                    break
            if not output:
                continue
            output_path = Path(output)
            if not output_path.is_absolute():
                output_path = root / output_path
            output_path = output_path.resolve()
            output_path.relative_to(root)
            if output_path.name != "result.json":
                continue
            executable = Path(args[0]).name.lower()
            codex_cli = executable in {"codex", "codex.exe"}
            node_wrapper = (executable in {"node", "nodejs"}
                and any("codex" in Path(arg).name.lower() for arg in args[1:4]))
            codex_stage_command = "exec" in args and "--output-schema" in args
            if not (codex_cli or node_wrapper or codex_stage_command):
                continue
            stat = (entry / "stat").read_text(encoding="ascii")
            end_comm = stat.rfind(")")
            fields = stat[end_comm + 1:].split()
            rss_bytes = int(fields[21]) * page_size if len(fields) > 21 else None
            pid = int(entry.name)
            if pid in seen_pids:
                continue
            seen_pids.add(pid)
            processes[str(output_path)] = {"pid": pid, "rss_bytes": rss_bytes,
                "output_path": _relative(output_path, root), "_absolute_output_path": str(output_path)}
        except (FileNotFoundError, ProcessLookupError):
            continue
        except PermissionError:
            reliable = False
        except (OSError, ValueError, IndexError):
            continue
    return processes, reliable


class Collector:
    """Cache directory inventory briefly while reading live metadata on each snapshot."""

    def __init__(self, root, cache_seconds=5.0, proc_root="/proc", clock=time.monotonic):
        self.root = Path(root).resolve()
        self.cache_seconds = max(0.0, float(cache_seconds))
        self.proc_root = Path(proc_root)
        self._clock = clock
        self._inventory_at = 0.0
        self._inventory = None
        self._snapshot_at = 0.0
        self._snapshot_cache = None
        self._file_cache = {}

    def _read_cached(self, path, warnings, default=None):
        path = Path(path)
        try:
            stat = path.stat()
        except OSError as exc:
            if warnings is not None and len(warnings) < 50:
                warnings.append({"path": str(path), "error_type": type(exc).__name__})
            return default, None
        signature = (stat.st_mtime_ns, stat.st_size)
        saved = self._file_cache.get(path)
        if saved and saved[:2] == signature:
            return saved[2], stat
        value = _read(path, warnings, default)
        if len(self._file_cache) > 30000:
            self._file_cache.clear()
        self._file_cache[path] = (*signature, value)
        return value, stat

    def _read_optional_cached(self, path, warnings):
        if not Path(path).is_file():
            return None
        value, _ = self._read_cached(path, warnings, None)
        return value

    def _document_hash(self, path, warnings):
        if not Path(path).is_file():
            return None
        value, stat = self._read_cached(path, warnings, None)
        if not isinstance(value, (dict, list)) or stat is None:
            return None
        signature = (stat.st_mtime_ns, stat.st_size)
        cache_key = (Path(path), signature)
        cached = getattr(self, "_hash_cache", None)
        if cached is None:
            self._hash_cache = {}
            cached = self._hash_cache
        if cache_key not in cached:
            cached[cache_key] = _canonical_hash(value)
            if len(cached) > 10000:
                cached.clear()
                cached[cache_key] = _canonical_hash(value)
        return cached[cache_key]

    def _scan_inventory(self):
        jobs, stages, queues = set(), [], []
        for base in (self.root / "runs", self.root / "content" / "source_coverage"):
            if not base.is_dir():
                continue
            for directory, names, files in os.walk(base):
                names[:] = sorted(name for name in names if name not in _SKIP_DIRS and not name.startswith("."))
                folder = Path(directory)
                if "queue.json" in files:
                    queues.append(folder / "queue.json")
                if "meta.json" in files:
                    stages.append(folder / "meta.json")
                if "source.json" in files or ("status.json" in files and
                        any(name in files for name in ("article.json", "dossier.json",
                                                       "source_article.json", "source_dossier.json"))):
                    jobs.add(folder)
        return {"jobs": sorted(jobs), "stages": sorted(stages), "queues": sorted(queues),
                "repairs": self._scan_repair_dirs()}

    def _scan_repair_dirs(self):
        base = self.root / "research" / "producer-patches"
        if not base.is_dir():
            return []
        repairs = {path for path in base.iterdir() if path.is_dir() and any(
            (path / name).is_file() for name in
            ("verification.json", "applied-producer-receipt.json", "validation.json"))}
        for directory, names, files in os.walk(base):
            names[:] = [name for name in names if name not in {"proof", "before", "after", "failed-after"}
                        and not name.startswith(".")]
            if "transaction.json" in files:
                repairs.add(Path(directory))
        return sorted(repairs)

    def _stage_index(self, stage_paths, job_paths):
        """Assign each stage once to its nearest discovered job ancestor."""
        known = {Path(path) for path in job_paths}
        indexed = {path: [] for path in known}
        for stage in stage_paths:
            parent = Path(stage).parent
            while parent != self.root and self.root in parent.parents:
                if parent in known:
                    indexed[parent].append(Path(stage))
                    break
                parent = parent.parent
        return indexed

    def _get_inventory(self):
        now = self._clock()
        if self._inventory is None or now - self._inventory_at >= self.cache_seconds:
            self._inventory = self._scan_inventory()
            self._inventory_at = now
        return self._inventory

    def _machine(self):
        total = available = swap_total = swap_free = None
        try:
            values = {}
            for line in (self.proc_root / "meminfo").read_text().splitlines():
                key, _, value = line.partition(":")
                fields = value.strip().split()
                if fields and fields[0].isdigit():
                    values[key] = int(fields[0]) * (1024 if len(fields) > 1 and fields[1] == "kB" else 1)
            total, available = values.get("MemTotal"), values.get("MemAvailable")
            swap_total, swap_free = values.get("SwapTotal"), values.get("SwapFree")
        except OSError:
            pass
        try:
            load = list(os.getloadavg())
        except (AttributeError, OSError):
            load = []
        return {"cpu_threads": os.cpu_count(), "load": load,
                "memory_total_bytes": total, "memory_available_bytes": available,
                "swap_total_bytes": swap_total,
                "swap_used_bytes": max(0, swap_total - swap_free)
                    if swap_total is not None and swap_free is not None else None}

    def _queue_rows(self, inventory, warnings):
        queues, linked = [], {}
        for path in inventory["queues"]:
            raw = self._read_cached(path, warnings, {})[0]
            identity = raw.get("identity") or {}
            source_id = path.parent.name
            rows = []
            for character, record in (raw.get("jobs") or {}).items():
                result = record.get("result") or {}
                job_path = result.get("job") or record.get("job")
                if job_path:
                    resolved = _resolve_job_path(job_path, self.root)
                    linked[(str(resolved), source_id)] = {
                        "status": record.get("status", result.get("status", "unknown")),
                        "attempts": record.get("attempts", 0),
                        "started_at": record.get("started_at"),
                        "finished_at": record.get("finished_at"),
                        "attention_required": bool(result.get("attention_required")),
                    }
                rows.append({"character": character, "status": record.get("status", "unknown"),
                             "attempts": record.get("attempts", 0),
                             "job": _relative(_resolve_job_path(job_path, self.root), self.root)
                                    if job_path else None,
                             "attention_required": bool(result.get("attention_required"))})
            queues.append({"path": _relative(path, self.root), "source_id": source_id,
                           "workers": raw.get("workers"), "agent_capacity": raw.get("agent_capacity"),
                           "status": raw.get("status", "unknown"),
                           "updated_at": raw.get("updated_at"), "summary": raw.get("summary", {}),
                           "jobs": rows, "root_matches": identity.get("root") in (None, str(self.root))})
        return queues, linked

    def _stage_rows(self, job, stage_paths, process_map, proc_reliable, warnings, now):
        metas = []
        for path in stage_paths:
            meta, file_stat = self._read_cached(path, warnings, {})
            if not isinstance(meta, dict):
                continue
            output_path = path.parent / "result.json"
            process = process_map.get(str(output_path))
            state = meta.get("status", "unknown")
            if state == "running":
                liveness = "live" if process else "stale" if proc_reliable else "unknown"
            elif state == "waiting_for_agent_slot":
                liveness = "waiting"
            elif state == "complete":
                liveness = "completed"
            else:
                liveness = "unknown"
            started = meta.get("started_at")
            waiting = state == "waiting_for_agent_slot"
            elapsed_start = _parse_time(meta.get("queued_at") if waiting else started)
            finished_epoch = _parse_time(meta.get("finished_at"))
            elapsed_end = (finished_epoch if state == "complete" and finished_epoch is not None else now)
            modified = file_stat.st_mtime if file_stat else 0
            row = {"role": meta.get("role"), "status": state, "model": meta.get("model"),
                   "reasoning": meta.get("reasoning"), "path": _relative(path.parent, self.root),
                   "pid": process.get("pid") if process else None,
                   "rss_bytes": process.get("rss_bytes") if process else None,
                   "agent_capacity": meta.get("agent_capacity"),
                   "slot_wait_seconds": meta.get("slot_wait_seconds"),
                   "started_at": started, "queued_at": meta.get("queued_at"),
                   "finished_at": meta.get("finished_at"),
                   "elapsed_seconds": max(0, elapsed_end - elapsed_start)
                       if elapsed_start is not None else None,
                   "updated_at": datetime.fromtimestamp(modified, timezone.utc).isoformat()
                       if modified else None,
                   "liveness": liveness}
            metas.append((modified, row,
                          str(output_path), process))
        metas.sort(key=lambda item: (item[0], item[1]["path"]))
        active = [row for _, row, _, _ in metas
                  if row["status"] in ("running", "waiting_for_agent_slot")]
        latest = metas[-1][1] if metas else None
        process_rows = []
        for _, row, output, process in metas:
            if process and row["status"] == "running":
                process_rows.append({key: process[key] for key in ("pid", "rss_bytes", "output_path")}
                                    | {"job_path": _relative(job, self.root),
                                       "character": None, "source_id": None,
                                       "stage": row["path"], "role": row["role"],
                                       "model": row["model"], "reasoning": row["reasoning"],
                                       "liveness": "live", "orphan": False})
        return active, len(metas), latest, process_rows

    def _standalone_process_row(self, process, now, warnings):
        """Represent an in-repository verifier process with no source job row."""
        output = Path(process["_absolute_output_path"])
        stage_dir = output.parent
        meta = self._read_optional_cached(stage_dir / "meta.json", warnings) or {}
        if not isinstance(meta, dict):
            meta = {}
        occurrences = None
        for folder in (stage_dir, *list(stage_dir.parents)[:8]):
            candidate = folder / "occurrences.json"
            occurrences = self._read_optional_cached(candidate, warnings)
            if isinstance(occurrences, dict):
                break
        provenance = occurrences.get("provenance", {}) if isinstance(occurrences, dict) else {}
        if not isinstance(provenance, dict):
            provenance = {}
        source_id = provenance.get("source_id")
        if not source_id and isinstance(occurrences, dict):
            for folder in (stage_dir, *list(stage_dir.parents)[:8]):
                if re.fullmatch(r"[0-9A-Fa-f]{4,6}", folder.name):
                    source_id = folder.parent.name
                    break
        page = provenance.get("pdf_page")
        if page is None:
            match = re.search(r"page-(\d{3,4})", str(provenance.get("source_scan_path", "")))
            page = int(match.group(1)) if match else None
        stage_status = meta.get("status") or "running"
        if stage_status not in ("running", "waiting_for_agent_slot"):
            stage_status = "running"  # The matching process is direct evidence it is still active.
        started = meta.get("started_at")
        start_epoch = _parse_time(started)
        stage = {"role": meta.get("role"), "status": stage_status,
            "model": meta.get("model"), "reasoning": meta.get("reasoning"),
            "path": _relative(stage_dir, self.root), "pid": process.get("pid"),
            "rss_bytes": process.get("rss_bytes"), "started_at": started,
            "finished_at": None, "elapsed_seconds": max(0, now - start_epoch) if start_epoch else None,
            "updated_at": None, "liveness": "live"}
        proof = {key: provenance.get(key) for key in
                 ("book", "pdf_page", "printed_page", "source_scan_path", "scope")
                 if provenance.get(key) is not None}
        process_row = {key: process[key] for key in ("pid", "rss_bytes", "output_path")}
        process_row.update({"job_path": None, "character": None, "source_id": source_id,
            "stage": stage["path"], "role": stage["role"], "model": stage["model"],
            "reasoning": stage["reasoning"], "liveness": "live", "orphan": True,
            "pdf_page": page})
        label = f"p{int(page):04d}" if isinstance(page, (int, float)) else None
        return {"id": f"standalone:{process.get('pid')}:{_relative(stage_dir, self.root)}",
            "type": "standalone_process", "path": _relative(stage_dir, self.root),
            "character": None, "source_id": source_id, "page_label": label,
            "source_provenance": proof, "status": stage_status, "updated_at": started,
            "active_stages": [stage], "stage_count": 1, "last_stage": stage,
            "liveness": "live", "reviews": [], "findings": [], "issues": [],
            "processes": [process_row], "article_hash": None, "dossier_hash": None,
            "hash_origin": "unavailable", "hash_origins": {"article_hash": "unavailable",
                "dossier_hash": "unavailable"}, "hashes": {"article_hash": None, "dossier_hash": None}}

    def _job_row(self, path, stage_paths, queue_state, process_map, proc_reliable, warnings, now):
        source = self._read_optional_cached(path / "source.json", warnings) or {}
        state = self._read_optional_cached(path / "status.json", warnings) or {}
        character = _character_from(path, source, warnings)
        if character is None:
            return None
        registered = source.get("registry_source") or {}
        source_id = source.get("source_id") or registered.get("id")
        queue_state = queue_state or {}
        status = state.get("status") or queue_state.get("status", "unknown")
        active, stage_count, latest, process_rows = self._stage_rows(
            path, stage_paths, process_map, proc_reliable, warnings, now)
        for process in process_rows:
            process["character"] = character
            process["source_id"] = source_id
        liveness = ("live" if any(row["liveness"] == "live" for row in active)
                    else "stale" if any(row["liveness"] == "stale" for row in active)
                    else "waiting" if any(row["liveness"] == "waiting" for row in active)
                    else "unknown" if status == "running" or queue_state.get("status") == "running"
                    else "completed" if latest and latest.get("liveness") == "completed"
                    else "idle")
        current_article_hash = self._document_hash(path / "article.json", warnings)
        current_dossier_hash = self._document_hash(path / "dossier.json", warnings)
        source_article_hash = self._document_hash(path / "source_article.json", warnings)
        source_dossier_hash = self._document_hash(path / "source_dossier.json", warnings)
        article_hash = current_article_hash or source_article_hash or source.get("article_hash") or state.get("article_hash")
        dossier_hash = current_dossier_hash or source_dossier_hash or source.get("dossier_hash") or state.get("dossier_hash")
        article_origin = "current_job" if current_article_hash else "source_baseline" if article_hash else "unavailable"
        dossier_origin = "current_job" if current_dossier_hash else "source_baseline" if dossier_hash else "unavailable"
        hash_origins = {"article_hash": article_origin, "dossier_hash": dossier_origin}
        hash_origin = (next(iter(set(hash_origins.values()))) if len(set(hash_origins.values())) == 1
                       else "mixed")
        reviews_raw = self._read_optional_cached(path / "reviews.json", warnings) or []
        reviews = [{k: review.get(k) for k in ("role", "verdict", "article_hash", "dossier_hash")}
                   | {"path": _relative(path / "reviews.json", self.root),
                      "current_pair": bool(article_origin == "current_job" and dossier_origin == "current_job"
                       and review.get("article_hash") == article_hash
                       and review.get("dossier_hash") == dossier_hash)}
                   for review in reviews_raw if isinstance(review, dict)] if isinstance(reviews_raw, list) else []
        findings_doc = self._read_optional_cached(path / "source_findings.json", warnings) or {}
        resolution_binding = self._read_optional_cached(path / "source_resolution.json", warnings) or {}
        review_rel = Path(resolution_binding.get("review_path", "source-resolution/result.json"))
        review_path = (path / review_rel).resolve() if not review_rel.is_absolute() else review_rel.resolve()
        try:
            review_path.relative_to(path.resolve())
        except ValueError:
            warnings.append({"path": _relative(review_path, self.root),
                             "error_type": "source_resolution_path_outside_job"})
            resolution = {}
        else:
            resolution = self._read_optional_cached(review_path, warnings) or {}
        resolution_validation = self._read_optional_cached(path / "source_resolution_validation.json", warnings) or {}
        dispositions = {item.get("key"): item.get("disposition")
                       for item in resolution.get("findings", []) if isinstance(item, dict)}
        findings = [{"path": _relative(path / "source_findings.json", self.root),
                     "key": item.get("key"), "kind": item.get("kind"),
                     "title": _compact(item.get("title")),
                     "details": _compact(item.get("details")),
                     "verification": _compact(item.get("verification")),
                     "status": dispositions.get(item.get("key"), "pending_verification")}
                    for item in findings_doc.get("findings", []) if isinstance(item, dict)]
        audit = self._read_optional_cached(path / "source_audit.json", warnings) or {}
        issue_sync = self._read_optional_cached(path / "issue_sync.json", warnings) or {}
        receipt = self._read_optional_cached(path / "issue_receipts.json", warnings) or {}
        issue_rows = issue_sync.get("issues") or receipt.get("issues") or []
        issues = [{"number": item.get("number"), "url": item.get("url"), "key": item.get("key"),
                   "status": item.get("state", "unknown")}
                  for item in issue_rows if isinstance(item, dict)]
        hashes = {"article_hash": article_hash, "dossier_hash": dossier_hash}
        short_hashes = {key: value[:12] if isinstance(value, str) else None
                        for key, value in hashes.items()}
        return {"id": f"{source_id or 'local'}:{ord(character):04X}:{_relative(path, self.root)}",
                "path": _relative(path, self.root), "character": character,
                "source_id": source_id, "status": status,
                "updated_at": (state.get("updated_at") or state.get("published_at")
                    or queue_state.get("finished_at") or (latest or {}).get("finished_at")
                    or (latest or {}).get("started_at") or (latest or {}).get("updated_at")),
                "active_stages": active, "stage_count": stage_count,
                "last_stage": latest, "liveness": liveness,
                "reviews": reviews, "findings": findings, "issues": issues,
                "issue_sync_status": issue_sync.get("status", state.get("issue_sync_status")),
                "source_audit": {"verified": audit.get("verified"),
                    "source_id": audit.get("source_id"),
                    "citation_count": len(audit.get("consulted_citations", audit.get("citations", [])) or [])},
                "source_resolution": {
                    "status": ("pending" if findings_doc.get("requires_coordinator_verification")
                               and not resolution.get("findings") else
                               "rejected" if resolution_validation.get("status") == "rejected" else
                               "dispositions_recorded" if resolution.get("findings") else "not_required"),
                    "validation_status": resolution_validation.get("status"),
                    "recorded_dispositions": dispositions},
                "article_hash": hashes["article_hash"], "dossier_hash": hashes["dossier_hash"],
                "hash_origin": hash_origin, "hash_origins": hash_origins, "hashes": short_hashes,
                "queue": {key: queue_state.get(key) for key in
                    ("status", "attempts", "started_at", "finished_at", "attention_required")
                    if key in queue_state},
                "processes": process_rows}

    def _repairs(self, inventory, warnings):
        rows = []
        for path in inventory["repairs"]:
            verification = _read(path / "verification.json", None, {}) or {}
            applied = _read(path / "applied-producer-receipt.json", None, {}) or {}
            validation = _read(path / "validation.json", None, {}) or {}
            transaction_path = path / "transaction.json"
            transaction = _read(transaction_path, None, {}) or {} if transaction_path.is_file() else {}
            receipt = transaction or applied or verification
            events = []
            def find_value(value, keys):
                if isinstance(value, dict):
                    for key in keys:
                        if key in value and isinstance(value[key], (str, int, float, bool, type(None))):
                            return value[key]
                    for child in value.values():
                        found = find_value(child, keys)
                        if found is not None:
                            return found
                elif isinstance(value, list):
                    for child in value:
                        found = find_value(child, keys)
                        if found is not None:
                            return found
                return None
            def collect(value):
                if isinstance(value, dict):
                    event = {}
                    for key in ("pdf_page", "pdf_page_1based", "page", "before", "after",
                                "failed_after", "failed-after", "status", "raw_unchanged", "raw_file_unchanged",
                                "other_pages_unchanged", "unchanged_other_page_count"):
                        if key in value and isinstance(value[key], (str, int, float, bool, type(None))):
                            event[key] = value[key]
                    if any(key in event for key in ("before", "after", "failed_after", "failed-after",
                                                     "pdf_page", "pdf_page_1based", "page")):
                        events.append(event)
                    for child in value.values():
                        collect(child)
                elif isinstance(value, list):
                    for child in value:
                        collect(child)
            collect(transaction)
            page_values = set(str(x) for x in receipt.get("raw_file_hashes", {}).keys())
            for event in events:
                page = event.get("pdf_page_1based", event.get("pdf_page", event.get("page")))
                if page is not None:
                    page_values.add(str(page))
            if not page_values:
                for key in ("pdf_page_1based", "pdf_page", "page"):
                    if receipt.get(key) is not None:
                        page_values.add(str(receipt[key]))
            status = (find_value(transaction, ("status", "transaction_status"))
                      or receipt.get("status") or validation.get("status") or
                      ("recorded" if any(path.iterdir()) else "empty"))
            rows.append({"path": _relative(path, self.root), "status": status,
                         "receipt_path": _relative(transaction_path if transaction else
                             path / ("applied-producer-receipt.json" if applied else "verification.json"),
                             self.root),
                         "pdf_pages": sorted(page_values), "events": events,
                         "before": find_value(transaction, ("before",)) or receipt.get("before"),
                         "after": find_value(transaction, ("after",)) or receipt.get("after"),
                         "failed_after": find_value(transaction, ("failed_after", "failed-after")),
                         "raw_unchanged": find_value(transaction,
                             ("raw_unchanged", "raw_file_unchanged", "raw_unchanged_status"))
                             if transaction else receipt.get("raw_unchanged",
                                 receipt.get("raw_file_unchanged", verification.get("raw_file_hash_unchanged"))),
                         "ocr_text_changed": verification.get("ocr_text_changed"),
                         "other_pages_unchanged": find_value(transaction, ("other_pages_unchanged",))
                             if transaction else verification.get("other_pages_unchanged"),
                         "unchanged_other_page_count": find_value(transaction,
                             ("unchanged_other_page_count", "unchanged_other_pages"))
                             if transaction else verification.get("unchanged_other_page_count")})
        return rows

    def _coverage(self, warnings):
        research = self.root / "research"
        reports = [p for p in research.iterdir() if p.is_file() and _SOURCE_REPORT.fullmatch(p.name)] \
            if research.is_dir() else []
        if not reports:
            return {"status": "missing", "reports": []}
        reports.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        selected = reports[:10]
        newest = _read(reports[0], warnings, {}) or {}
        report_rows = []
        for path in selected:
            report = _read(path, warnings, {}) or {}
            report_rows.append({"path": _relative(path, self.root), "source_id": report.get("source_id"),
                "verified_source_complete": report.get("verified_source_complete"),
                "characters_total": report.get("characters_total")})
        return {"status": "available", "latest_path": _relative(reports[0], self.root),
                "source_id": newest.get("source_id"),
                "verified_source_complete": newest.get("verified_source_complete"),
                "characters_total": newest.get("characters_total"),
                "generated_at": datetime.fromtimestamp(reports[0].stat().st_mtime,
                    timezone.utc).isoformat(),
                "reports": report_rows}

    def _coordination(self, warnings):
        path = self.root / "runs" / "operations" / "coordination.json"
        value = _read_optional(path, warnings)
        if not isinstance(value, dict):
            return None
        tasks = value.get("tasks", value.get("work", []))
        if isinstance(tasks, dict):
            tasks = [{"name": key, **(item if isinstance(item, dict) else {"status": item})}
                     for key, item in tasks.items()]
        if not isinstance(tasks, list):
            tasks = []
        return {"status": value.get("status", "recorded"),
                "updated_at": value.get("updated_at"),
                "tasks": [{key: task.get(key) for key in
                    ("name", "task", "status", "owner", "updated_at", "path", "note")
                    if key in task} for task in tasks if isinstance(task, dict)],
                "source": _relative(path, self.root),
                "interpretation": "Recorded coordination text/status only; not evidence of agent liveness or approval."}

    def snapshot(self):
        now_mono = self._clock()
        if self._snapshot_cache is not None and now_mono - self._snapshot_at < 1.0:
            # Caller mutation must not alter the cached service response.
            return json.loads(json.dumps(self._snapshot_cache, ensure_ascii=False))
        inventory = self._get_inventory()
        warnings = []
        queues, linked = self._queue_rows(inventory, warnings)
        process_map, proc_reliable = _proc_records(self.proc_root, self.root)
        candidates = set(inventory["jobs"])
        for queue_path in inventory["queues"]:
            queue = self._read_cached(queue_path, warnings, {})[0] or {}
            for record in (queue.get("jobs") or {}).values():
                job_path = (record.get("result") or {}).get("job") or record.get("job")
                if job_path:
                    resolved = _resolve_job_path(job_path, self.root)
                    if resolved == self.root or self.root in resolved.parents:
                        candidates.add(resolved)
        stage_index = self._stage_index(inventory["stages"], candidates)
        rows = []
        processes = []
        row_by_path = {}
        for path in sorted(candidates):
            source = _read_optional(path / "source.json", warnings) or {}
            source_id = source.get("source_id") or (source.get("registry_source") or {}).get("id")
            queue_state = linked.get((str(path.resolve()), source_id or path.parent.name))
            if queue_state is None:
                queue_state = next((value for (saved_path, _source), value in linked.items()
                                    if saved_path == str(path.resolve())), None)
            row = self._job_row(path, stage_index.get(path.resolve(), []), queue_state,
                                process_map, proc_reliable, warnings, time.time())
            if row is not None:
                rows.append(row)
                row_by_path[str(path.resolve())] = row
        seen_pids = set()
        for row in rows:
            for process in row["processes"]:
                if process["pid"] not in seen_pids:
                    seen_pids.add(process["pid"])
                    processes.append(process)
        # A Codex process can outlive or precede its running meta checkpoint.
        # Keep it visible as an orphan process instead of losing real capacity.
        for process in process_map.values():
            if process["pid"] in seen_pids:
                continue
            output = Path(process["_absolute_output_path"])
            parent = output.parent.resolve()
            owner = None
            while parent != self.root and self.root in parent.parents:
                owner = row_by_path.get(str(parent))
                if owner:
                    break
                parent = parent.parent
            orphan = {key: process[key] for key in ("pid", "rss_bytes", "output_path")}
            orphan.update({"job_path": owner["path"] if owner else None,
                "character": owner["character"] if owner else None,
                "source_id": owner["source_id"] if owner else None,
                "stage": _relative(output.parent, self.root), "role": None, "model": None,
                "reasoning": None, "liveness": "live", "orphan": True})
            processes.append(orphan)
            seen_pids.add(process["pid"])
            if owner:
                owner["processes"].append(orphan)
                owner["liveness"] = "live"
            else:
                rows.append(self._standalone_process_row(process, time.time(), warnings))
        result = {"generated_at": datetime.now(timezone.utc).isoformat(),
                  "root": str(self.root), "machine": self._machine(), "queues": queues,
                  "jobs": rows, "repairs": self._repairs(inventory, warnings),
                  "coverage": self._coverage(warnings), "coordination": self._coordination(warnings),
                  "processes": processes,
                  "process_totals": {"active_codex_agents": len(processes),
                      "rss_bytes": sum(row.get("rss_bytes") or 0 for row in processes),
                      "waiting_for_agent_slot": sum(
                          stage.get("status") == "waiting_for_agent_slot"
                          for row in rows for stage in row["active_stages"]),
                      "queued_jobs": sum(1 for queue in queues for row in queue["jobs"]
                                          if row["status"] == "queued"),
                      "workers": sum(queue.get("workers") or 0 for queue in queues),
                      "agent_capacity": max((queue.get("agent_capacity") or 0 for queue in queues),
                                             default=0)},
                  "warnings": warnings}
        self._snapshot_cache, self._snapshot_at = result, now_mono
        return json.loads(json.dumps(result, ensure_ascii=False))
