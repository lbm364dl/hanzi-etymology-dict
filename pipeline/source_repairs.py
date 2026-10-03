"""Validate and transactionally apply scan-verified OCR literal repairs.

The adapter deliberately delegates OCR semantics to the registered producer's
``research_corrections`` loader and the producer's corpus builder.  It does not
edit the raw OCR response, and it does not turn a review result into page-wide
approval.
"""
from __future__ import annotations

from contextlib import contextmanager
import copy
import contextvars
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import uuid

from PIL import Image

from pipeline import editorial, ocr_verification


_INHERITED_LOCK_FDS = contextvars.ContextVar("source_repair_lock_fds", default=())


def _bytes_hash(path):
    path = Path(path)
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def _pixel_hash(path):
    with Image.open(path) as image:
        return hashlib.sha256(image.convert("RGB").tobytes()).hexdigest()


def _jsonl_pages(path):
    pages = {}
    with Path(path).open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, 1):
            if not line.strip():
                continue
            page = json.loads(line)
            key = (page.get("book_id"), page.get("pdf_page_1based"))
            if key in pages:
                raise ValueError(f"Duplicate consumer page identity at line {line_number}: {key}")
            pages[key] = page
    return pages


def producer_lock_path(source):
    """Return a stable lock path shared by every writer for a producer edition."""
    root = Path(source["producer_root"]).expanduser().resolve()
    identity = hashlib.sha256(os.fsencode(str(root))).hexdigest()
    lock_dir = Path(tempfile.gettempdir()) / "hanzi-source-repair-locks"
    lock_dir.mkdir(parents=True, exist_ok=True)
    return lock_dir / f"producer-{identity}.lock"


@contextmanager
def producer_lock(source):
    """Serialize producer edits and any writers of the same consumer corpus."""
    root_lock = producer_lock_path(source)
    corpus = Path(source["corpus_path"]).expanduser().resolve()
    corpus_id = hashlib.sha256(os.fsencode(str(corpus))).hexdigest()
    corpus_lock = root_lock.parent / f"corpus-{corpus_id}.lock"
    streams = []
    token = None
    try:
        # Stable ordering prevents deadlocks if a future transaction spans sources.
        for path in sorted({root_lock, corpus_lock}, key=lambda item: str(item)):
            stream = path.open("a+b")
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
            streams.append(stream)
        inherited = tuple(dict.fromkeys((*_INHERITED_LOCK_FDS.get(),
                                         *(stream.fileno() for stream in streams))))
        token = _INHERITED_LOCK_FDS.set(inherited)
        yield root_lock
    finally:
        if token is not None:
            _INHERITED_LOCK_FDS.reset(token)
        for stream in reversed(streams):
            # Closing this descriptor releases the flock when it is the last
            # reference. A child spawned with pass_fds retains the same open
            # file description and therefore keeps the lock after coordinator
            # death; issuing LOCK_UN here would release it for every holder.
            stream.close()


def _producer_script(source, name):
    root = Path(source["producer_root"]).expanduser().resolve()
    script = root / "scripts" / name
    if not script.is_file():
        raise ValueError(f"Registered producer is missing scripts/{name}")
    return root, script


def _run(command, timeout, what):
    """Run one producer command as an isolated group and reap it before return.

    Producers sometimes invoke helper processes. Killing only the CLI process on
    timeout would let those descendants keep mutating the overlay or consumer
    while the caller rolls back under its lock. A new session gives the adapter
    one process group to terminate while inherited flock descriptors remain
    open through cleanup.
    """
    process = None
    inherited_fds = tuple(fd for fd in _INHERITED_LOCK_FDS.get() if fd >= 0)
    try:
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   text=True, start_new_session=True, pass_fds=inherited_fds)
        stdout, stderr = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        if process is not None:
            _terminate_process_group(process)
        raise TimeoutError(f"Producer {what} exceeded {timeout} seconds") from exc
    except BaseException:
        if process is not None:
            _terminate_process_group(process)
        raise
    if process.returncode:
        detail = (stderr or stdout or "").strip()
        _terminate_process_group(process)
        raise RuntimeError(f"Producer {what} failed: {detail[-3000:]}")
    return subprocess.CompletedProcess(command, process.returncode, stdout, stderr)


def _terminate_process_group(process, grace_seconds=0.2):
    """Stop any remaining members of a producer command's process group."""
    if not _process_group_has_live_members(process.pid):
        return
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    if process.poll() is None:
        try:
            process.communicate(timeout=grace_seconds)
        except subprocess.TimeoutExpired:
            pass
    # Send KILL even when the direct child already exited: its descendants may
    # have closed the captured pipes but still be running in the same group.
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    if process.poll() is None:
        # Do not let transactional rollback race a still-running direct child.
        process.communicate()
    # The direct child is reaped by communicate(), but descendants are not our
    # waitable children. Wait until no live group member can still mutate files;
    # ignore zombies, which can no longer execute and are reaped by their parent.
    while _process_group_has_live_members(process.pid):
        time.sleep(0.01)


def _process_group_has_live_members(process_group_id):
    proc_root = Path("/proc")
    if proc_root.is_dir():
        for stat_path in proc_root.glob("[0-9]*/stat"):
            try:
                stat = stat_path.read_text(encoding="ascii")
                fields = stat[stat.rfind(")") + 1:].split()
                # Linux /proc/PID/stat: state is field 3, pgrp is field 5.
                state, group = fields[0], int(fields[2])
                if group == process_group_id and state not in {"Z", "X"}:
                    return True
            except (OSError, ValueError, IndexError):
                continue
        return False
    try:
        os.killpg(process_group_id, 0)
    except ProcessLookupError:
        return False
    return True


def producer_effective(source, directory, timeout=120, python_executable=None):
    """Load effective OCR in a child process to avoid cross-producer sys.path races."""
    root, script = _producer_script(source, "research_corrections.py")
    directory = Path(directory).expanduser().resolve()
    directory.relative_to(root)
    executable = python_executable or source.get("python_executable") or sys.executable
    code = (
        "import contextlib,json,sys\n"
        "sys.path.insert(0,sys.argv[1])\n"
        "with contextlib.redirect_stdout(sys.stderr):\n"
        "    import research_corrections\n"
        "    value=research_corrections.load_effective(sys.argv[2])\n"
        "print(json.dumps(value, "
        "ensure_ascii=False))"
    )
    completed = _run([executable, "-c", code, str(script.parent), str(directory)],
                     timeout, "effective OCR validation")
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise ValueError("Producer effective loader returned invalid JSON") from exc


def verification_provenance(source, producer_page_dir, provenance=None,
                            timeout=120, python_executable=None):
    """Bind new OCR-review inputs to the current raw page, pixels and overlay.

    Call before freezing ``pipeline.ocr_verification.verify`` inputs. The
    overlay SHA is a byte hash, or null when no page correction overlay exists.
    Legacy receipts are retained as-is; apply_verified requires this binding.
    """
    root = Path(source["producer_root"]).expanduser().resolve()
    directory = Path(producer_page_dir).expanduser().resolve()
    directory.relative_to(root)
    with producer_lock(source):
        raw_path, scan_path = directory / "ocr.json", directory / "source.png"
        raw = editorial.read(raw_path)
        effective = producer_effective(source, directory, timeout, python_executable)
        text = raw["ocr"]["text"]
        pixel_hash = _pixel_hash(scan_path)
        bound = {"raw_ocr_path": str(raw_path), "source_scan_path": str(scan_path),
                 "pdf_page": raw["pdf_page_1based"],
                 "raw_text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                 "ocr_evidence_sha256": raw["evidence_sha256"],
                 "source_pixel_sha256": pixel_hash,
                 "overlay_sha256": _bytes_hash(directory / "ocr-corrections.json")}
        if (pixel_hash != raw.get("source_sha256")
                or effective.get("source_sha256") != raw.get("source_sha256")
                or effective.get("pdf_page_1based") != raw.get("pdf_page_1based")):
            raise ValueError("Producer raw OCR, source pixels and effective page do not agree")
        combined = {**(provenance or {})}
        for key, value in bound.items():
            if key in combined and combined[key] != value:
                raise ValueError(f"Conflicting OCR provenance field: {key}")
            combined[key] = value
        return combined


def _verify_locked(source, check, timeout=120, python_executable=None):
    """Bind an already-applied repair while caller holds producer lock."""
    directory = Path(check["producer_page_dir"]).expanduser().resolve()
    root = Path(source["producer_root"]).expanduser().resolve()
    directory.relative_to(root)
    effective = producer_effective(source, directory, timeout, python_executable)
    raw = editorial.read(directory / "ocr.json")
    overlay_path = directory / "ocr-corrections.json"
    overlay = editorial.read(overlay_path)
    patches = overlay["patches"]
    matching = [p for p in patches if p["start"] == check["raw_start"]
                and p["end"] == check["raw_end"] and p["before"] == check["before"]
                and p["after"] == check["after"] and p.get("source_checked")]
    if len(matching) != 1 or effective["pdf_page_1based"] != check["pdf_page"]:
        raise ValueError("Applied repair must identify an exact validated producer patch")
    with Path(source["corpus_path"]).open(encoding="utf-8") as stream:
        pages = [json.loads(line) for line in stream if line.strip()]
    pages = [p for p in pages if p["pdf_page_1based"] == check["pdf_page"]]
    if len(pages) != 1:
        raise ValueError("Applied repair consumer page missing or duplicated")
    page = pages[0]
    if (page["book_id"] != source["book_id"]
            or page["evidence_sha256"] != effective["evidence_sha256"]
            or page["source_sha256"] != effective["source_sha256"]
            or page["text"] != effective["ocr"]["text"]):
        raise ValueError("Applied repair producer and consumer evidence differ")
    offset = check["raw_start"] + sum(len(p["after"]) - (p["end"] - p["start"])
                                    for p in patches if p["end"] <= check["raw_start"])
    if page["text"][offset:offset + len(check["after"])] != check["after"]:
        raise ValueError("Applied repair is absent from the current corpus occurrence")
    return {**check, "current_offset": offset,
            "source_pixel_sha256": effective["source_sha256"],
            "raw_evidence_sha256": raw["evidence_sha256"],
            "overlay_hash": editorial.digest(overlay),
            "effective_evidence_sha256": effective["evidence_sha256"]}


def verify(source, check):
    """Public serialized reader; retain the historical receipt's exact fields."""
    with producer_lock(source):
        return _verify_locked(source, check)


def _validated_occurrence(verified_path, occurrence_id, *, expected_verdict="confirmed_correction"):
    """Validate all standard OCR-verification receipt and attachment bindings."""
    verified_path = Path(verified_path).expanduser().resolve()
    record = editorial.read(verified_path)
    required = {"provenance", "occurrences_hash", "result", "result_hash",
                "review_directory", "model", "reasoning", "whole_page_reviewed"}
    if not required <= set(record):
        raise ValueError("Verified OCR receipt is missing required bindings")
    if record["model"] != "gpt-6-luna" or record["reasoning"] != "low":
        raise ValueError("OCR repair requires a genuine Luna-low verification receipt")
    if record["whole_page_reviewed"] is not False:
        raise ValueError("OCR verification must remain occurrence-scoped")
    if editorial.digest(record["result"]) != record["result_hash"]:
        raise ValueError("Verified OCR result hash mismatch")
    review_dir = Path(record["review_directory"]).expanduser().resolve()
    if not review_dir.is_dir():
        raise ValueError("OCR review directory is missing")
    result_path, meta_path = review_dir / "result.json", review_dir / "meta.json"
    review_result, meta = editorial.read(result_path), editorial.read(meta_path)
    occurrences_path = verified_path.parent / "occurrences.json"
    occurrences_record = editorial.read(occurrences_path)
    occurrences = occurrences_record.get("occurrences")
    if (review_result != record["result"]
            or meta.get("status") != "complete"
            or meta.get("role") != "ocr_verification"
            or meta.get("model") != "gpt-6-luna"
            or meta.get("reasoning") != "low"
            or meta.get("result_hash") != record["result_hash"]):
        raise ValueError("OCR review result or metadata does not bind to verified receipt")
    if (not isinstance(meta.get("fingerprint"), str) or not meta["fingerprint"]
            or not isinstance(meta.get("agent_thread_ids"), list)
            or not meta["agent_thread_ids"]):
        raise ValueError("OCR review metadata lacks a completed agent execution receipt")
    prompt_text = (review_dir / "prompt.txt").read_text(encoding="utf-8")
    if "INPUTS:\n" not in prompt_text:
        raise ValueError("OCR review prompt is missing its frozen inputs")
    try:
        prompt_inputs = json.loads(prompt_text.rsplit("INPUTS:\n", 1)[1].strip())
    except json.JSONDecodeError as exc:
        raise ValueError("OCR review prompt inputs are malformed") from exc
    if (prompt_inputs.get("occurrences") != occurrences_record.get("occurrences")
            or prompt_inputs.get("provenance") != record["provenance"]):
        raise ValueError("OCR review prompt is not bound to the verified occurrence packet")
    supplied_scans = (prompt_inputs.get("feedback", {}).get("source_scan_images", [])
                      if isinstance(prompt_inputs.get("feedback"), dict) else [])
    attached_scans = prompt_inputs.get("attached_source_scans", [])
    source_path = record["provenance"].get("source_scan_path")
    source_pixel_hash = (record["provenance"].get("source_pixel_sha256")
                         or record["provenance"].get("source_rgb_sha256")
                         or record["provenance"].get("raw_ocr_source_sha256"))
    if (not any(scan.get("path") == source_path and
                scan.get("source_pixel_sha256") == source_pixel_hash for scan in supplied_scans)
            or not any(scan.get("path") == source_path and
                       scan.get("source_pixel_sha256") == source_pixel_hash for scan in attached_scans)):
        raise ValueError("OCR review did not attach the exact registered source scan pixels")
    image_manifest = meta.get("image_argument_manifest")
    if not isinstance(image_manifest, list) or not image_manifest:
        raise ValueError("OCR review has no actual image attachment manifest")
    for image in image_manifest:
        if not isinstance(image, dict):
            raise ValueError("OCR review image manifest entry is malformed")
        image_path = Path(image.get("path", "")).expanduser().resolve()
        if not image_path.is_file() or _bytes_hash(image_path) != image.get("sha256"):
            raise ValueError("OCR review image attachment changed after verification")
    if occurrences_record.get("provenance") != record["provenance"]:
        raise ValueError("OCR occurrence packet provenance differs from verified receipt")
    if editorial.digest(occurrences) != record["occurrences_hash"]:
        raise ValueError("OCR occurrence packet hash mismatch")
    ocr_verification.validate_result(record["result"], occurrences)
    occurrence_schema = copy.deepcopy(ocr_verification.OCCURRENCE)
    occurrence_schema["properties"]["id"] = {
        "type": "string", "enum": [item["id"] for item in occurrences]}
    occurrence_schema["properties"]["raw_text"] = {
        "type": "string", "enum": sorted({item["before"] for item in occurrences})}
    result_schema = {"type": "object", "additionalProperties": False,
                     "required": ["occurrences"], "properties": {
                         "occurrences": {"type": "array", "items": occurrence_schema,
                                         "minItems": len(occurrences),
                                         "maxItems": len(occurrences)}}}
    try:
        editorial.Draft202012Validator(result_schema).validate(record["result"])
    except editorial.ValidationError as exc:
        raise ValueError(f"OCR result violates the verification schema: {exc.message}") from exc
    if len([o for o in occurrences if o.get("id") == occurrence_id]) != 1:
        raise ValueError("Requested occurrence is absent or duplicated")
    proposal = next(o for o in occurrences if o["id"] == occurrence_id)
    reviewed = [o for o in record["result"].get("occurrences", []) if o["id"] == occurrence_id]
    if len(reviewed) != 1:
        raise ValueError("OCR result must include the requested occurrence exactly once")
    observation = reviewed[0]
    if observation["verdict"] != expected_verdict:
        raise ValueError(f"OCR receipt must resolve as {expected_verdict}")
    if observation["raw_text"] != proposal["before"]:
        raise ValueError("Reviewed raw literal does not match the exact proposed occurrence")
    if expected_verdict == "confirmed_correction":
        if (not isinstance(proposal.get("after"), str) or not proposal["after"]
                or proposal["after"] == proposal["before"]
                or observation["printed_text"] != proposal["after"]):
            raise ValueError("Reviewed literal does not match the exact proposed replacement")
    elif expected_verdict == "unresolved_identity":
        if proposal.get("after") is not None or observation["printed_text"] is not None:
            raise ValueError("Unresolved identity must not supply a guessed Unicode replacement")
    elif expected_verdict == "unsupported_raw_identity":
        if proposal.get("after") is not None or observation["printed_text"] is not None:
            raise ValueError("Unsupported raw identity must not supply a guessed Unicode replacement")
    else:
        raise ValueError("Unsupported OCR repair disposition")
    return {"verified_path": verified_path, "record": record,
            "occurrences_path": occurrences_path, "occurrences_record": occurrences_record,
            "occurrences": occurrences, "proposal": proposal, "observation": observation,
            "review_dir": review_dir, "result_path": result_path, "meta_path": meta_path}


def _bind_to_source(proof, source, page_dir, current_overlay_sha256):
    provenance = proof["record"]["provenance"]
    page_dir = Path(page_dir).expanduser().resolve()
    root = Path(source["producer_root"]).expanduser().resolve()
    page_dir.relative_to(root)
    raw_path = (page_dir / "ocr.json").resolve()
    scan_path = (page_dir / "source.png").resolve()
    if Path(provenance.get("raw_ocr_path", "")).expanduser().resolve() != raw_path:
        raise ValueError("OCR receipt raw path does not identify this producer page")
    if Path(provenance.get("source_scan_path", "")).expanduser().resolve() != scan_path:
        raise ValueError("OCR receipt scan path does not identify this producer page")
    if ("overlay_sha256" not in provenance
            or provenance["overlay_sha256"] != current_overlay_sha256):
        raise ValueError("OCR receipt is not bound to the expected current overlay hash")
    raw = editorial.read(raw_path)
    proposal = proof["proposal"]
    text = raw["ocr"]["text"]
    start, end = proposal.get("start"), proposal.get("end")
    if (type(start) is not int or type(end) is not int or not 0 <= start < end <= len(text)
            or text[start:end] != proposal["before"]):
        raise ValueError("OCR proposal span does not match current raw OCR text")
    context_before = text[max(0, start - 40):start]
    context_after = text[end:end + 40]
    anchor = proposal.get("anchor")
    if (proposal.get("context_before") != context_before
            or proposal.get("context_after") != context_after
            or not isinstance(anchor, str) or not anchor or anchor not in context_before):
        raise ValueError("OCR proposal context does not match current raw OCR text")
    if (provenance.get("raw_text_sha256") != hashlib.sha256(text.encode("utf-8")).hexdigest()
            or provenance.get("ocr_evidence_sha256") != raw.get("evidence_sha256")
            or provenance.get("pdf_page") != raw.get("pdf_page_1based")
            or provenance.get("source_pixel_sha256") != raw.get("source_sha256")
            or _pixel_hash(scan_path) != raw.get("source_sha256")):
        raise ValueError("OCR receipt raw text, page or source pixel hashes are stale")
    if current_overlay_sha256 != _bytes_hash(page_dir / "ocr-corrections.json"):
        raise ValueError("Current producer overlay changed before locked validation")
    return raw, text, start, end


def _atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                     prefix=path.name + ".", delete=False) as stream:
        temp_path = Path(stream.name)
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    temp_path.replace(path)


def _snapshot(path, target_dir, label):
    path = Path(path)
    present = path.is_file()
    entry = {"path": str(path), "present": present,
             "sha256": _bytes_hash(path) if present else None}
    if present:
        dest = Path(target_dir) / label
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, dest)
        entry["archive_path"] = str(dest)
    return entry


def _restore_snapshot(entry):
    path = Path(entry["path"])
    if not entry["present"]:
        path.unlink(missing_ok=True)
        return
    backup = Path(entry["archive_path"])
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix=path.name + ".rollback.",
                                     delete=False) as stream:
        temp_path = Path(stream.name)
        stream.write(backup.read_bytes())
        stream.flush()
        os.fsync(stream.fileno())
    temp_path.replace(path)


def _copy_proof(proof, archive):
    proof_dir = Path(archive) / "proof"
    proof_dir.mkdir(parents=True, exist_ok=True)
    files = [proof["verified_path"], proof["occurrences_path"], proof["result_path"],
             proof["meta_path"]]
    for path in files:
        try:
            relative = path.relative_to(proof["verified_path"].parent)
        except ValueError:
            relative = Path("review") / path.name
        destination = proof_dir / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, destination)
    # Retain the full original review packet, including the exact prompt and schema.
    review_dest = proof_dir / "review"
    if review_dest.exists():
        shutil.rmtree(review_dest)
    shutil.copytree(proof["review_dir"], review_dest)
    meta = editorial.read(proof["meta_path"])
    attachments = []
    for index, item in enumerate(meta.get("image_argument_manifest", []), 1):
        source = Path(item["path"]).expanduser().resolve()
        if not source.is_file() or _bytes_hash(source) != item.get("sha256"):
            raise ValueError("OCR proof attachment changed before transaction archival")
        destination = proof_dir / "attachments" / f"{index:02d}-{source.name}"
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        attachments.append({"source_path": str(source), "archive_path": str(destination),
                            "sha256": item["sha256"]})
    return attachments


def _build_corpus(source, pages_root, timeout, python_executable=None):
    root, script = _producer_script(source, "source_corpus.py")
    pages_root = Path(pages_root).expanduser().resolve()
    pages_root.relative_to(root)
    corpus = Path(source["corpus_path"]).expanduser().resolve()
    executable = python_executable or source.get("python_executable") or sys.executable
    completed = _run([executable, str(script), "build", "--pages-root", str(pages_root),
                      "--output", str(corpus)], timeout, "consumer corpus rebuild")
    return {"stdout": completed.stdout[-2000:], "stderr": completed.stderr[-2000:],
            "pages_root": str(pages_root), "corpus_path": str(corpus)}


def apply_verified(source, verified_occurrences_path, occurrence_id,
                   producer_page_dir, pages_root, archive_dir, *, current_overlay_sha256,
                   timeout=300, python_executable=None):
    """Validate and apply one repair under the producer-wide crossprocess lock."""
    if timeout <= 0:
        raise ValueError("timeout must be positive")
    # Lock before loading/validating current proof bindings or reading mutable producer state.
    with producer_lock(source):
        return _apply_verified_locked(source, verified_occurrences_path, occurrence_id,
                                      producer_page_dir, pages_root, archive_dir,
                                      current_overlay_sha256=current_overlay_sha256,
                                      timeout=timeout, python_executable=python_executable)


def apply_unidentified_printed_character(source, verified_occurrences_path, occurrence_id,
                                         producer_page_dir, pages_root, archive_dir, *,
                                         description, uncertainty,
                                         current_overlay_sha256, timeout=300,
                                         python_executable=None):
    """Replace an unsupported OCR scalar with the producer's page-bound glyph reference.

    The independent occurrence receipt must say ``unsupported_raw_identity`` and
    leave ``printed_text`` null. This is distinct from ordinary uncertainty: it
    records that the visible graph does not support the raw scalar. The transaction adds the producer-native
    ``unidentified_printed_character`` record and uncertainty; it never guesses a
    Unicode scalar.  Raw ``ocr.json`` and the original OCR evidence remain intact.
    """
    if timeout <= 0:
        raise ValueError("timeout must be positive")
    if not isinstance(description, str) or not description.strip():
        raise ValueError("An unresolved printed glyph needs a visual/context description")
    if not isinstance(uncertainty, str) or not uncertainty.strip():
        raise ValueError("An unresolved printed glyph needs an explicit uncertainty")
    with producer_lock(source):
        return _apply_verified_locked(
            source, verified_occurrences_path, occurrence_id, producer_page_dir,
            pages_root, archive_dir, current_overlay_sha256=current_overlay_sha256,
            timeout=timeout, python_executable=python_executable,
            unresolved_reference={"description": description.strip(),
                                  "uncertainty": uncertainty.strip()})


def _apply_verified_locked(source, verified_occurrences_path, occurrence_id,
                           producer_page_dir, pages_root, archive_dir, *, current_overlay_sha256,
                           timeout=300, python_executable=None, unresolved_reference=None):
    """Apply one verified exact-literal correction as a producer/corpus transaction.

    ``current_overlay_sha256`` is the observed byte hash (or ``None`` if the
    page has no correction overlay) recorded in the OCR review provenance.  The
    producer-root lock is held from revalidation through the shared corpus build.
    All modified files and the genuine review packet are archived before mutation;
    failures restore the previous overlay, exports, corpus and catalog.
    """
    if timeout <= 0:
        raise ValueError("timeout must be positive")
    root = Path(source["producer_root"]).expanduser().resolve()
    corpus = Path(source["corpus_path"]).expanduser().resolve()
    page_dir = Path(producer_page_dir).expanduser().resolve()
    pages_root = Path(pages_root).expanduser().resolve()
    page_dir.relative_to(root)
    pages_root.relative_to(root)
    proof = _validated_occurrence(
        verified_occurrences_path, occurrence_id,
        expected_verdict="unsupported_raw_identity" if unresolved_reference else "confirmed_correction")
    overlay_path = page_dir / "ocr-corrections.json"
    if ("overlay_sha256" not in proof["record"]["provenance"]
            or current_overlay_sha256 != proof["record"]["provenance"]["overlay_sha256"]):
        raise ValueError("Expected current overlay hash does not match OCR receipt provenance")
    archive_root = Path(archive_dir).expanduser().resolve()
    archive_root.mkdir(parents=True, exist_ok=True)
    transaction_id = f"ocr-repair-{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}-{uuid.uuid4().hex[:12]}"
    archive = archive_root / transaction_id
    archive.mkdir()
    proof_attachments = _copy_proof(proof, archive) or []

    raw, raw_text, start, end = _bind_to_source(
        proof, source, page_dir, current_overlay_sha256)
    effective_before = producer_effective(source, page_dir, timeout, python_executable)
    if (effective_before.get("pdf_page_1based") != proof["record"]["provenance"].get("pdf_page")
            or effective_before.get("source_sha256") != raw.get("source_sha256")):
        raise ValueError("Producer effective page does not match OCR receipt")
    reference_record = None
    if unresolved_reference:
        used_ids = {glyph.get("id") for glyph in effective_before["ocr"].get("glyphs", [])}
        number = 1
        while f"p{number:03d}" in used_ids:
            number += 1
        glyph_id = f"p{number:03d}"
        marker = f"[glyph:{glyph_id}]"
        reference_record = {"id": glyph_id, "kind": "unidentified_printed_character",
                            "description": unresolved_reference["description"]}
        patch_after = marker
    else:
        patch_after = proof["proposal"]["after"]
    old_rows = _jsonl_pages(corpus)
    page_key = (source["book_id"], raw["pdf_page_1based"])
    if page_key not in old_rows:
        raise ValueError("Current source corpus is missing the target producer page")
    old_page = old_rows[page_key]
    if (old_page.get("source_sha256") != effective_before.get("source_sha256")
            or old_page.get("evidence_sha256") != effective_before.get("evidence_sha256")
            or old_page.get("text") != effective_before["ocr"]["text"]):
        raise ValueError("Pre-repair consumer record differs from producer effective OCR")

    overlay = editorial.read(overlay_path) if overlay_path.is_file() else {
        "schema_version": 1, "parent_evidence_sha256": raw["evidence_sha256"],
        "source_sha256": raw["source_sha256"], "patches": []}
    if (overlay.get("parent_evidence_sha256") != raw["evidence_sha256"]
            or overlay.get("source_sha256") != raw["source_sha256"]):
        raise ValueError("Current correction overlay is stale for raw OCR/source")
    patches = overlay.get("patches")
    if not isinstance(patches, list):
        raise ValueError("Producer correction overlay patches must be an array")
    for prior in patches:
        pstart, pend = prior.get("start"), prior.get("end")
        if type(pstart) is not int or type(pend) is not int:
            raise ValueError("Existing producer patch has invalid offsets")
        if start < pend and pstart < end:
            if (pstart, pend, prior.get("before"), prior.get("after")) == (
                    start, end, proof["proposal"]["before"], patch_after):
                raise ValueError("The verified correction is already present in producer overlay")
            raise ValueError("Verified correction overlaps an existing producer patch")
    patch = {"start": start, "end": end, "before": proof["proposal"]["before"],
             "after": patch_after, "source_checked": True,
             "reason": proof["observation"]["reason"],
             "reviewers": [f"{proof['record']['model']}:{proof['record']['reasoning']}:{occurrence_id}"],
             "verification": {"verified_occurrences_sha256": _bytes_hash(proof["verified_path"]),
                              "result_hash": proof["record"]["result_hash"],
                              "occurrence_id": occurrence_id}}
    new_overlay = copy.deepcopy(overlay)
    new_overlay["patches"] = sorted([*patches, patch], key=lambda item: item["start"])
    if reference_record:
        existing_added = new_overlay.setdefault("add_glyphs", [])
        if any(item.get("id") == reference_record["id"] for item in existing_added):
            raise ValueError("Unresolved glyph reference ID already exists in producer overlay")
        existing_added.append(reference_record)
        new_overlay.setdefault("added_uncertainties", []).append(unresolved_reference["uncertainty"])

    pages_catalog = corpus.parent / "books.json"
    mutable = [overlay_path, page_dir / "reading-corrected.md", page_dir / "ocr-corrected.json",
               corpus, pages_catalog]
    before_dir = archive / "before"
    snapshots = [_snapshot(path, before_dir, f"files/{index:02d}-{path.name}")
                 for index, path in enumerate(mutable)]
    raw_hash_before = _bytes_hash(page_dir / "ocr.json")
    transaction = {"schema_version": 1, "transaction_id": transaction_id,
                   "status": "started", "source_id": source.get("id"),
                   "producer_root": str(root), "producer_page_dir": str(page_dir),
                   "pdf_page": raw["pdf_page_1based"], "raw_ocr_sha256": raw_hash_before,
                   "current_overlay_sha256": current_overlay_sha256,
                   "new_occurrence": {"id": occurrence_id, "start": start, "end": end,
                                      "before": patch["before"], "after": patch["after"],
                                      "disposition": "unsupported_raw_identity" if reference_record else "confirmed_correction",
                                      "glyph_reference": reference_record},
                   "archived_review_attachments": proof_attachments,
                   "before": snapshots}
    editorial.write(archive / "transaction.json", transaction)
    try:
        _atomic_json(overlay_path, new_overlay)
        effective_after = producer_effective(source, page_dir, timeout, python_executable)
        expected_text = raw_text
        for prior in sorted(new_overlay["patches"], key=lambda item: item["start"], reverse=True):
            expected_text = expected_text[:prior["start"]] + prior["after"] + expected_text[prior["end"]:]
        if effective_after["ocr"]["text"] != expected_text:
            raise ValueError("Producer effective loader did not apply the verified literal")
        current_offset = start + sum(len(prior["after"]) - (prior["end"] - prior["start"])
                                     for prior in new_overlay["patches"] if prior["end"] <= start)
        if (effective_after["ocr"]["text"][current_offset:current_offset + len(patch["after"])]
                != patch["after"]):
            raise ValueError("Producer effective text does not contain the exact verified occurrence")
        if reference_record:
            actual_glyphs = [item for item in effective_after["ocr"].get("glyphs", [])
                             if item.get("id") == reference_record["id"]]
            if actual_glyphs != [reference_record]:
                raise ValueError("Producer effective OCR omitted the unidentified printed-character record")
        export_script = _producer_script(source, "research_corrections.py")[1]
        executable = python_executable or source.get("python_executable") or sys.executable
        export_code = (
            "import sys; sys.path.insert(0,sys.argv[1]); "
            "import research_corrections; "
            "research_corrections.export_corrected(sys.argv[2])"
        )
        _run([executable, "-c", export_code, str(export_script.parent), str(page_dir)],
             timeout, "corrected page export")
        build_record = _build_corpus(source, pages_root, timeout, python_executable)
        if _bytes_hash(page_dir / "ocr.json") != raw_hash_before:
            raise ValueError("Raw OCR changed during the repair transaction")
        new_rows = _jsonl_pages(corpus)
        if set(old_rows) != set(new_rows):
            raise ValueError("Consumer corpus page identities changed during rebuild")
        changed_other = [key for key in old_rows if key != page_key and old_rows[key] != new_rows[key]]
        if changed_other:
            raise ValueError(f"Unrelated consumer pages changed during rebuild: {changed_other[:5]}")
        applied = _verify_locked(source, {"key": occurrence_id, "pdf_page": raw["pdf_page_1based"],
                                           "producer_page_dir": str(page_dir), "raw_start": start,
                                           "raw_end": end, "before": patch["before"],
                                           "after": patch["after"]}, timeout, python_executable)
        if reference_record:
            current_page = new_rows[page_key]
            referenced_assets = [item for item in current_page.get("glyph_assets", [])
                                 if item.get("id") == reference_record["id"]]
            if (len(referenced_assets) != 1
                    or referenced_assets[0].get("kind") != "unidentified_printed_character"):
                raise ValueError("Rebuilt consumer omitted the occurrence's unresolved glyph reference")
            applied["glyph_reference"] = {"id": reference_record["id"],
                                           "kind": reference_record["kind"],
                                           "consumer_asset": referenced_assets[0]}
        after_dir = archive / "after"
        after_snapshots = [_snapshot(path, after_dir, f"files/{index:02d}-{path.name}")
                           for index, path in enumerate(mutable)]
        transaction.update({"status": "complete", "producer_load_effective": {
            "source_sha256": effective_after.get("source_sha256"),
            "evidence_sha256": effective_after.get("evidence_sha256"),
            "text_sha256": hashlib.sha256(effective_after["ocr"]["text"].encode()).hexdigest()},
            "consumer_build": build_record, "repair_validation": applied,
            "unchanged_other_page_count": len(new_rows) - 1, "after": after_snapshots})
        editorial.write(archive / "transaction.json", transaction)
        return {"transaction_id": transaction_id, "archive_path": str(archive),
                "repair": applied, "after": transaction["producer_load_effective"],
                "consumer_build": build_record,
                "unchanged_other_page_count": len(new_rows) - 1}
    except BaseException as exc:
        failed_after = [_snapshot(path, archive / "failed-after",
                                  f"files/{index:02d}-{path.name}")
                        for index, path in enumerate(mutable)]
        rollback_errors = []
        for item in reversed(snapshots):
            try:
                _restore_snapshot(item)
            except BaseException as restore_exc:  # retain every failure in the transaction record
                rollback_errors.append(f"{item['path']}: {restore_exc}")
        transaction.update({"status": "rolled_back" if not rollback_errors else "rollback_failed",
                            "failure": f"{type(exc).__name__}: {exc}",
                            "rollback_errors": rollback_errors, "failed_after": failed_after})
        editorial.write(archive / "transaction.json", transaction)
        raise
