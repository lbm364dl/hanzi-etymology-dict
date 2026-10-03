"""Contract tests for the safe OCR repair adapter.

The transaction tests inject an already-validated proof object at the adapter
boundary; they do not synthesize or claim any model review. Receipt parsing is
tested separately with invalid/tampered records, and all producer work occurs
in a disposable fixture edition with a mocked local corpus builder.
"""
import hashlib
import fcntl
import json
import re
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from pipeline import editorial, source_repairs


def _json_digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


class SourceRepairReceiptTests(unittest.TestCase):
    def test_rejects_unbound_or_malformed_verified_occurrences(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            verified = root / "verified-occurrences.json"
            editorial.write(verified, {"result": {"occurrences": []}})
            with self.assertRaisesRegex(ValueError, "missing required bindings"):
                source_repairs._validated_occurrence(verified, "p1")

    def test_rejects_receipt_result_that_differs_from_saved_review(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            stage = root / "ocr-check"
            review = stage / "review"
            review.mkdir(parents=True)
            proposal = {"id": "p1", "start": 2, "end": 3, "before": "兒", "after": "皃",
                        "context_before": "ab", "context_after": "cd"}
            provenance = {"source": "fixture"}
            occurrences = [proposal]
            result = {"occurrences": [{"id": "p1", "raw_text": "兒", "printed_text": "皃",
                                        "verdict": "confirmed_correction", "reason": "fixture pixels"}]}
            different = {"occurrences": []}
            record = {"provenance": provenance, "occurrences_hash": editorial.digest(occurrences),
                      "result": result, "result_hash": editorial.digest(result),
                      "review_directory": str(review), "model": "gpt-6-luna", "reasoning": "low",
                      "whole_page_reviewed": False}
            editorial.write(stage / "verified-occurrences.json", record)
            editorial.write(stage / "occurrences.json", {"provenance": provenance,
                                                           "occurrences": occurrences})
            editorial.write(review / "result.json", different)
            editorial.write(review / "meta.json", {"status": "complete", "role": "ocr_verification",
                                                     "model": "gpt-6-luna", "reasoning": "low",
                                                     "result_hash": editorial.digest(result)})
            with self.assertRaisesRegex(ValueError, "review result or metadata"):
                source_repairs._validated_occurrence(stage / "verified-occurrences.json", "p1")

    def test_unresolved_receipt_requires_null_identity_and_cannot_masquerade_as_literal_repair(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            stage = root / "unresolved"
            review = stage / "review"
            review.mkdir(parents=True)
            scan = root / "source.png"
            Image.new("RGB", (8, 8), (255, 255, 255)).save(scan)
            pixel_hash = hashlib.sha256(Image.open(scan).convert("RGB").tobytes()).hexdigest()
            text = "before兒after"
            start, end = text.index("兒"), text.index("兒") + 1
            provenance = {"raw_ocr_path": str(root / "ocr.json"),
                          "source_scan_path": str(scan), "pdf_page": 1,
                          "raw_text_sha256": hashlib.sha256(text.encode()).hexdigest(),
                          "ocr_evidence_sha256": "raw-fixture", "source_pixel_sha256": pixel_hash,
                          "overlay_sha256": None}
            proposal = {"id": "p1", "start": start, "end": end, "before": "兒", "after": None,
                        "anchor": "before", "context_before": "before",
                        "context_after": "after"}
            occurrences = [proposal]
            result = {"occurrences": [{"id": "p1", "raw_text": "兒", "printed_text": None,
                                       "verdict": "unresolved_identity",
                                       "reason": "Target differs from the named raw scalar; exact Unicode remains unresolved."}]}
            editorial.write(stage / "occurrences.json", {"provenance": provenance,
                                                           "occurrences": occurrences})
            editorial.write(review / "result.json", result)
            (review / "prompt.txt").write_text("Independent test receipt\nINPUTS:\n" + json.dumps(
                {"provenance": provenance, "occurrences": occurrences,
                 "feedback": {"source_scan_images": [{"path": str(scan), "pdf_page": 1,
                                                        "source_pixel_sha256": pixel_hash}]},
                 "attached_source_scans": [{"path": str(scan), "pdf_page": 1,
                                            "source_pixel_sha256": pixel_hash}]}, ensure_ascii=False),
                encoding="utf-8")
            editorial.write(review / "meta.json", {"status": "complete", "role": "ocr_verification",
                "model": "gpt-6-luna", "reasoning": "low", "fingerprint": "fixture-fingerprint",
                "agent_thread_ids": ["fixture-thread"], "result_hash": editorial.digest(result),
                "image_argument_manifest": [{"path": str(scan),
                    "sha256": hashlib.sha256(scan.read_bytes()).hexdigest()}]})
            verified = {"provenance": provenance, "occurrences_hash": editorial.digest(occurrences),
                        "result": result, "result_hash": editorial.digest(result),
                        "review_directory": str(review), "model": "gpt-6-luna", "reasoning": "low",
                        "whole_page_reviewed": False}
            editorial.write(stage / "verified-occurrences.json", verified)
            accepted = source_repairs._validated_occurrence(stage / "verified-occurrences.json", "p1",
                                                              expected_verdict="unresolved_identity")
            self.assertIsNone(accepted["observation"]["printed_text"])
            with self.assertRaisesRegex(ValueError, "OCR receipt must resolve as unsupported_raw_identity"):
                source_repairs._validated_occurrence(stage / "verified-occurrences.json", "p1",
                                                      expected_verdict="unsupported_raw_identity")
            with self.assertRaisesRegex(ValueError, "OCR receipt must resolve as confirmed_correction"):
                source_repairs._validated_occurrence(stage / "verified-occurrences.json", "p1")


class ProofArchivalTests(unittest.TestCase):
    def test_copy_proof_archives_exact_source_crop_attachments(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            review = root / "review"
            review.mkdir()
            proof_dir = root / "proof-source"
            proof_dir.mkdir()
            attached_crop = root / "target-crop.png"
            Image.new("RGB", (5, 7), (1, 2, 3)).save(attached_crop)
            for name, content in (("verified-occurrences.json", "{}"),
                                  ("occurrences.json", "{}")):
                path = proof_dir / name
                path.write_text(content, encoding="utf-8")
            (review / "result.json").write_text("{}", encoding="utf-8")
            editorial.write(review / "meta.json", {"image_argument_manifest": [{
                "path": str(attached_crop), "sha256": hashlib.sha256(attached_crop.read_bytes()).hexdigest()}]})
            (review / "prompt.txt").write_text("frozen input packet", encoding="utf-8")
            proof = {"verified_path": proof_dir / "verified-occurrences.json",
                     "occurrences_path": proof_dir / "occurrences.json",
                     "result_path": review / "result.json", "meta_path": review / "meta.json",
                     "review_dir": review}
            archived = source_repairs._copy_proof(proof, root / "archive")
            self.assertEqual(len(archived), 1)
            archived_path = Path(archived[0]["archive_path"])
            self.assertEqual(hashlib.sha256(archived_path.read_bytes()).hexdigest(), archived[0]["sha256"])
            self.assertEqual(archived_path.read_bytes(), attached_crop.read_bytes())


class ExistingRepairVerificationTests(unittest.TestCase):
    def test_exact_overlay_and_consumer_are_required_and_offset_tracks_prior_patches(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            overlay = {"patches": [
                {"start": 0, "end": 3, "before": "abc", "after": "x", "source_checked": True},
                {"start": 3, "end": 4, "before": "兒", "after": "皃", "source_checked": True}]}
            editorial.write(root / "ocr.json", {"evidence_sha256": "raw-fixture"})
            editorial.write(root / "ocr-corrections.json", overlay)
            effective = {"pdf_page_1based": 1, "source_sha256": "pixels-fixture",
                         "evidence_sha256": "effective-fixture", "ocr": {"text": "x皃"}}
            page = {**effective, "book_id": "book-fixture", "text": "x皃"}
            corpus = root / "corpus.jsonl"
            corpus.write_text(json.dumps(page, ensure_ascii=False), encoding="utf-8")
            source = {"book_id": "book-fixture", "producer_root": str(root),
                      "corpus_path": str(corpus)}
            check = {"key": "fixture", "pdf_page": 1, "producer_page_dir": str(root),
                     "raw_start": 3, "raw_end": 4, "before": "兒", "after": "皃"}
            with patch.object(source_repairs, "producer_effective", return_value=effective):
                receipt = source_repairs.verify(source, check)
                self.assertEqual(receipt["current_offset"], 1)
                self.assertEqual(set(receipt), set(check) | {"current_offset", "source_pixel_sha256",
                                                              "raw_evidence_sha256", "overlay_hash",
                                                              "effective_evidence_sha256"})
                with self.assertRaisesRegex(ValueError, "exact validated"):
                    source_repairs.verify(source, {**check, "before": "wrong"})
                corpus.write_text(json.dumps({**page, "text": "x兒"}), encoding="utf-8")
                with self.assertRaisesRegex(ValueError, "evidence differ"):
                    source_repairs.verify(source, check)


class TransactionFixtureTests(unittest.TestCase):
    def _fixture(self, root):
        producer = root / "producer"
        scripts = producer / "scripts"
        pages = producer / "research-ocr"
        scripts.mkdir(parents=True)
        for number, text in [(1, "start兒end"), (2, "unchanged page")]:
            page_dir = pages / f"page-{number:04d}"
            page_dir.mkdir(parents=True)
            image = page_dir / "source.png"
            Image.new("RGB", (8, 8), (255, 255, 255)).save(image)
            source_hash = hashlib.sha256(Image.open(image).convert("RGB").tobytes()).hexdigest()
            raw = {"schema_version": 1, "pdf_page_1based": number,
                   "source_sha256": source_hash, "request_cache_key": f"request-{number}",
                   "ocr": {"text": text, "glyphs": [], "uncertainties": []}}
            raw["evidence_sha256"] = _json_digest({k: raw[k] for k in
                                                    ("source_sha256", "request_cache_key", "ocr")})
            editorial.write(page_dir / "ocr.json", raw)

        correction_script = scripts / "research_corrections.py"
        correction_script.write_text('''
import copy, hashlib, json, re
from pathlib import Path
from PIL import Image
def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
def load_effective(root):
    root=Path(root); raw=json.loads((root/'ocr.json').read_text())
    if digest({k:raw[k] for k in ('source_sha256','request_cache_key','ocr')}) != raw['evidence_sha256']:
        raise ValueError('raw evidence hash mismatch')
    with Image.open(root/'source.png') as image:
        if hashlib.sha256(image.convert('RGB').tobytes()).hexdigest() != raw['source_sha256']:
            raise ValueError('source pixel hash mismatch')
    text=raw['ocr']['text']; overlay_path=root/'ocr-corrections.json'
    overlay=json.loads(overlay_path.read_text()) if overlay_path.exists() else {'patches': []}
    previous_end=0
    for patch in sorted(overlay['patches'], key=lambda p:p['start']):
        a,b=patch['start'],patch['end']
        if not previous_end <= a < b <= len(text) or text[a:b] != patch['before']:
            raise ValueError('invalid or overlapping fixture patch')
        if not patch.get('source_checked') or not patch.get('reason'):
            raise ValueError('fixture patch lacks source check')
        previous_end=b
    for patch in sorted(overlay['patches'], key=lambda p:p['start'], reverse=True):
        text=text[:patch['start']]+patch['after']+text[patch['end']:]
    result=copy.deepcopy(raw); result['ocr']['text']=text
    result['ocr']['glyphs'].extend(copy.deepcopy(overlay.get('add_glyphs', [])))
    result['ocr']['uncertainties'].extend(copy.deepcopy(overlay.get('added_uncertainties', [])))
    ids=[glyph['id'] for glyph in result['ocr']['glyphs']]
    refs=re.findall(r'\\[glyph:([^\\]]+)\\]',text)
    if len(ids)!=len(set(ids)) or set(ids)!=set(refs):
        raise ValueError('fixture producer has unbound glyph reference')
    result['original_evidence_sha256']=raw['evidence_sha256']
    result['evidence_sha256']=digest({k:result[k] for k in ('source_sha256','request_cache_key','ocr')})
    return result
def export_corrected(root):
    root=Path(root); value=load_effective(root)
    (root/'reading-corrected.md').write_text(value['ocr']['text']+'\\n')
    (root/'ocr-corrected.json').write_text(json.dumps(value,ensure_ascii=False,indent=2))
    return value
''', encoding="utf-8")
        corpus_script = scripts / "source_corpus.py"
        corpus_script.write_text('''
import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import research_corrections
p=argparse.ArgumentParser(); sub=p.add_subparsers(dest='cmd',required=True); b=sub.add_parser('build'); b.add_argument('--pages-root',required=True); b.add_argument('--output',required=True); a=p.parse_args()
rows=[]
for rawpath in sorted(Path(a.pages_root).rglob('ocr.json')):
    value=research_corrections.load_effective(rawpath.parent)
    rows.append({'book_id':'fixture-book','pdf_page_1based':value['pdf_page_1based'],'source_sha256':value['source_sha256'],'evidence_sha256':value['evidence_sha256'],'text':value['ocr']['text'],'glyph_assets':[{'id':g['id'],'kind':g.get('kind','historical_form'),'description':g['description']} for g in value['ocr']['glyphs']]})
output=Path(a.output); output.parent.mkdir(parents=True,exist_ok=True)
if (output.parent.parent/'BUILD_FAIL').exists():
    output.write_text('partial corpus\\n'); (output.parent/'books.json').write_text('{"fixture":"partial"}\\n'); raise SystemExit(9)
output.write_text(''.join(json.dumps(row,ensure_ascii=False)+'\\n' for row in rows))
(output.parent/'books.json').write_text('{"fixture":"rebuilt"}\\n')
print(json.dumps({'pages':len(rows)}))
''', encoding="utf-8")
        corpus = producer / "source-corpus" / "fixture-pages.jsonl"
        corpus.parent.mkdir()
        for number in [1, 2]:
            page_dir = pages / f"page-{number:04d}"
            raw = editorial.read(page_dir / "ocr.json")
            row = {"book_id": "fixture-book", "pdf_page_1based": number,
                   "source_sha256": raw["source_sha256"], "evidence_sha256": raw["evidence_sha256"],
                   "text": raw["ocr"]["text"], "glyph_assets": []}
            with corpus.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(row, ensure_ascii=False) + "\n")
        catalog = corpus.parent / "books.json"
        catalog.write_text('{"fixture":"old"}\n', encoding="utf-8")
        return producer, pages, corpus, catalog

    def _proof(self, root, producer, page_dir, *, occurrence_id="p1", verdict="confirmed_correction"):
        raw = editorial.read(page_dir / "ocr.json")
        text = raw["ocr"]["text"]
        start = text.index("兒")
        end = start + 1
        stage = root / "validated-proof-adapter-fixture"
        review = stage / "review"
        review.mkdir(parents=True)
        verified = stage / "verified-occurrences.json"
        occurrences_file = stage / "occurrences.json"
        result_path, meta_path = review / "result.json", review / "meta.json"
        proposal = {"id": occurrence_id, "start": start, "end": end,
                    "before": "兒", "after": "皃" if verdict == "confirmed_correction" else None,
                    "anchor": "start",
                    "context_before": text[max(0, start - 40):start],
                    "context_after": text[end:end + 40]}
        # This injected object is only the output of the validator boundary for
        # testing the transaction. It is deliberately not a model/review receipt.
        record = {"model": "test fixture", "reasoning": "test fixture",
                  "result_hash": "test-only", "provenance": {
                      "overlay_sha256": None, "raw_ocr_path": str(page_dir / "ocr.json"),
                      "source_scan_path": str(page_dir / "source.png"),
                      "raw_text_sha256": hashlib.sha256(text.encode()).hexdigest(),
                      "ocr_evidence_sha256": raw["evidence_sha256"],
                      "pdf_page": raw["pdf_page_1based"],
                      "source_pixel_sha256": raw["source_sha256"]}}
        observation = {"verdict": verdict, "printed_text": "皃" if verdict == "confirmed_correction" else None,
                       "reason": "fixture-bound observation"}
        return {"verified_path": verified, "occurrences_path": occurrences_file,
                "occurrences_record": {}, "occurrences": [proposal], "proposal": proposal,
                "observation": observation, "record": record,
                "review_dir": review, "result_path": result_path, "meta_path": meta_path}

    def test_apply_verified_is_atomic_preserves_raw_and_proves_other_pages_unchanged(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            producer, pages, corpus, catalog = self._fixture(root)
            page_dir = pages / "page-0001"
            source = {"id": "fixture-edition", "producer_root": str(producer),
                      "corpus_path": str(corpus), "pages_root": str(pages),
                      "book_id": "fixture-book", "python_executable": sys.executable}
            raw_hash = source_repairs._bytes_hash(page_dir / "ocr.json")
            old_rows = source_repairs._jsonl_pages(corpus)
            proof = self._proof(root, producer, page_dir)
            archive = root / "dictionary-research" / "producer-patches" / "fixture"
            with patch.object(source_repairs, "_validated_occurrence", return_value=proof), \
                    patch.object(source_repairs, "_copy_proof", return_value=[]):
                receipt = source_repairs.apply_verified(source, proof["verified_path"], "p1", page_dir,
                    pages, archive, current_overlay_sha256=None, timeout=20)
            self.assertEqual(receipt["unchanged_other_page_count"], 1)
            self.assertEqual(source_repairs._bytes_hash(page_dir / "ocr.json"), raw_hash)
            overlay = editorial.read(page_dir / "ocr-corrections.json")
            self.assertEqual([(p["before"], p["after"]) for p in overlay["patches"]], [("兒", "皃")])
            new_rows = source_repairs._jsonl_pages(corpus)
            self.assertEqual(new_rows[("fixture-book", 1)]["text"], "start皃end")
            self.assertEqual(new_rows[("fixture-book", 2)], old_rows[("fixture-book", 2)])
            self.assertEqual(editorial.read(catalog), {"fixture": "rebuilt"})
            transaction = editorial.read(Path(receipt["archive_path"]) / "transaction.json")
            self.assertEqual(transaction["status"], "complete")

    def test_unsupported_raw_identity_adds_reference_and_preserves_raw(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            producer, pages, corpus, catalog = self._fixture(root)
            page_dir = pages / "page-0001"
            source = {"id": "fixture-edition", "producer_root": str(producer),
                      "corpus_path": str(corpus), "pages_root": str(pages),
                      "book_id": "fixture-book", "python_executable": sys.executable}
            raw_hash = source_repairs._bytes_hash(page_dir / "ocr.json")
            old_rows = source_repairs._jsonl_pages(corpus)
            proof = self._proof(root, producer, page_dir, verdict="unsupported_raw_identity")
            archive = root / "dictionary-research" / "producer-patches" / "fixture"
            with patch.object(source_repairs, "_validated_occurrence", return_value=proof), \
                    patch.object(source_repairs, "_copy_proof", return_value=[]):
                receipt = source_repairs.apply_unidentified_printed_character(
                    source, proof["verified_path"], "p1", page_dir, pages, archive,
                    description="Unresolved printed token in the fixture paragraph after its anchor.",
                    uncertainty="The exact Unicode identity of the printed occurrence is unresolved.",
                    current_overlay_sha256=None, timeout=20)
            self.assertEqual(source_repairs._bytes_hash(page_dir / "ocr.json"), raw_hash)
            overlay = editorial.read(page_dir / "ocr-corrections.json")
            glyph = overlay["add_glyphs"][0]
            self.assertEqual(glyph["kind"], "unidentified_printed_character")
            marker = f"[glyph:{glyph['id']}]"
            self.assertEqual(overlay["patches"][0]["after"], marker)
            self.assertEqual(overlay["added_uncertainties"], [
                "The exact Unicode identity of the printed occurrence is unresolved."])
            new_rows = source_repairs._jsonl_pages(corpus)
            page = new_rows[("fixture-book", 1)]
            self.assertEqual(page["text"], f"start{marker}end")
            self.assertEqual(page["glyph_assets"][0]["kind"], "unidentified_printed_character")
            self.assertEqual(new_rows[("fixture-book", 2)], old_rows[("fixture-book", 2)])
            transaction = editorial.read(Path(receipt["archive_path"]) / "transaction.json")
            self.assertEqual(transaction["status"], "complete")
            self.assertEqual(transaction["new_occurrence"]["disposition"], "unsupported_raw_identity")
            self.assertEqual(transaction["new_occurrence"]["glyph_reference"]["id"], glyph["id"])

    def test_general_unresolved_identity_cannot_replace_raw_scalar_with_glyph_marker(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            producer, pages, corpus, _ = self._fixture(root)
            page_dir = pages / "page-0001"
            source = {"id": "fixture-edition", "producer_root": str(producer),
                      "corpus_path": str(corpus), "pages_root": str(pages),
                      "book_id": "fixture-book", "python_executable": sys.executable}
            proof = self._proof(root, producer, page_dir, verdict="unresolved_identity")
            before = corpus.read_bytes()
            def validate_expected(path, identity, *, expected_verdict):
                if proof["observation"]["verdict"] != expected_verdict:
                    raise ValueError(f"OCR receipt must resolve as {expected_verdict}")
                return proof
            with patch.object(source_repairs, "_validated_occurrence", side_effect=validate_expected), \
                    patch.object(source_repairs, "_copy_proof", return_value=[]):
                with self.assertRaisesRegex(ValueError, "must resolve as unsupported_raw_identity"):
                    source_repairs.apply_unidentified_printed_character(
                        source, proof["verified_path"], "p1", page_dir, pages, root / "archive",
                        description="Unresolved printed character.",
                        uncertainty="Exact identity remains unresolved.",
                        current_overlay_sha256=None, timeout=20)
            self.assertFalse((page_dir / "ocr-corrections.json").exists())
            self.assertEqual(corpus.read_bytes(), before)

    def test_new_verification_provenance_binds_raw_source_pixels_and_overlay(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            producer, pages, corpus, _ = self._fixture(root)
            source = {"id": "fixture-edition", "producer_root": str(producer),
                      "corpus_path": str(corpus), "book_id": "fixture-book",
                      "python_executable": sys.executable}
            page_dir = pages / "page-0001"
            bound = source_repairs.verification_provenance(source, page_dir)
            raw = editorial.read(page_dir / "ocr.json")
            self.assertEqual(bound["raw_text_sha256"], hashlib.sha256(raw["ocr"]["text"].encode()).hexdigest())
            self.assertEqual(bound["source_pixel_sha256"], raw["source_sha256"])
            self.assertIsNone(bound["overlay_sha256"])
            self.assertEqual(bound["pdf_page"], 1)

    def test_producer_lock_is_cross_process_and_scoped_to_registered_source(self):
        with tempfile.TemporaryDirectory() as temp:
            source = {"producer_root": str(Path(temp) / "producer"),
                      "corpus_path": str(Path(temp) / "pages.jsonl")}
            lock_path = source_repairs.producer_lock_path(source)
            code = ("import fcntl,sys; f=open(sys.argv[1],'a+b'); "
                    "exec('try:\\n fcntl.flock(f.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)\\n' "
                    "'except BlockingIOError:\\n print(\"locked\")\\n' "
                    "'else:\\n print(\"unlocked\"); raise SystemExit(2)')")
            with source_repairs.producer_lock(source):
                result = subprocess.run([sys.executable, "-c", code, str(lock_path)],
                                        capture_output=True, text=True, timeout=5)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("locked", result.stdout)

    def test_run_passes_lock_fds_to_child_that_outlives_coordinator(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = {"producer_root": str(root / "producer"),
                      "corpus_path": str(root / "pages.jsonl")}
            lock_path = source_repairs.producer_lock_path(source)
            signal_path = root / "child-ready"
            child_code = (
                "import os,sys,time; pid=os.fork(); "
                "(os.close(0),os.close(1),os.close(2),"
                "open(sys.argv[2],'w').write(str(os.getpid())),time.sleep(2)) if pid==0 "
                "else print('forked',flush=True)"
            )
            with source_repairs.producer_lock(source):
                source_repairs._run([sys.executable, "-c", child_code,
                                     str(lock_path), str(signal_path)], 5, "fixture child")
            deadline = __import__("time").monotonic() + 1
            while not signal_path.exists() and __import__("time").monotonic() < deadline:
                __import__("time").sleep(0.01)
            self.assertTrue(signal_path.exists(), "grandchild did not start")
            probe_code = (
                "import fcntl,sys; f=open(sys.argv[1],'a+b'); "
                "exec('try:\\n fcntl.flock(f.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)\\n' "
                "'except BlockingIOError:\\n print(\\\"locked\\\")\\n' "
                "'else:\\n print(\\\"unlocked\\\"); raise SystemExit(2)')"
            )
            probe = subprocess.run([sys.executable, "-c", probe_code, str(lock_path)],
                                   capture_output=True, text=True, timeout=5)
            self.assertEqual(probe.returncode, 0, probe.stderr)
            self.assertIn("locked", probe.stdout)
            deadline = __import__("time").monotonic() + 3
            while __import__("time").monotonic() < deadline:
                unlocked = subprocess.run([sys.executable, "-c", probe_code, str(lock_path)],
                                          capture_output=True, text=True, timeout=5)
                if "unlocked" in unlocked.stdout:
                    break
                __import__("time").sleep(0.05)
            self.assertIn("unlocked", unlocked.stdout)

    def test_run_timeout_kills_descendant_before_transaction_can_continue(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            marker = root / "descendant-mutated"
            code = (
                "import os,sys,time\n"
                "pid=os.fork()\n"
                "if pid == 0:\n"
                "    time.sleep(0.7)\n"
                "    open(sys.argv[1],'w').write('late write')\n"
                "    os._exit(0)\n"
                "time.sleep(10)\n"
            )
            started = time.monotonic()
            with self.assertRaisesRegex(TimeoutError, "exceeded 0.15 seconds"):
                source_repairs._run([sys.executable, "-c", code, str(marker)],
                                    0.15, "fixture timed producer")
            self.assertLess(time.monotonic() - started, 2.0)
            time.sleep(0.8)
            self.assertFalse(marker.exists(), "producer descendant survived timeout cleanup")

    def test_failed_producer_exit_kills_background_descendant(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            marker = root / "descendant-mutated"
            code = (
                "import os,sys,time\n"
                "pid=os.fork()\n"
                "if pid == 0:\n"
                "    os.close(0); os.close(1); os.close(2)\n"
                "    time.sleep(0.7)\n"
                "    open(sys.argv[1],'w').write('late write')\n"
                "    os._exit(0)\n"
                "os._exit(9)\n"
            )
            with self.assertRaisesRegex(RuntimeError, "Producer failed producer"):
                source_repairs._run([sys.executable, "-c", code, str(marker)],
                                    3, "failed producer")
            time.sleep(0.8)
            self.assertFalse(marker.exists(), "failed producer descendant survived cleanup")

    def test_current_overlay_drift_and_page_escape_fail_before_mutation(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            producer, pages, corpus, _ = self._fixture(root)
            page_dir = pages / "page-0001"
            source = {"id": "fixture-edition", "producer_root": str(producer),
                      "corpus_path": str(corpus), "book_id": "fixture-book",
                      "python_executable": sys.executable}
            proof = self._proof(root, producer, page_dir)
            proof["record"]["provenance"].pop("overlay_sha256")
            before_corpus = corpus.read_bytes()
            with patch.object(source_repairs, "_validated_occurrence", return_value=proof), \
                    patch.object(source_repairs, "_copy_proof", return_value=[]):
                with self.assertRaisesRegex(ValueError, "Expected current overlay hash"):
                    source_repairs.apply_verified(source, proof["verified_path"], "p1", page_dir,
                        pages, root / "archive", current_overlay_sha256=None, timeout=20)
                with self.assertRaises(ValueError):
                    source_repairs.apply_verified(source, proof["verified_path"], "p1", root,
                        pages, root / "archive", current_overlay_sha256=None, timeout=20)
            self.assertFalse((page_dir / "ocr-corrections.json").exists())
            self.assertEqual(corpus.read_bytes(), before_corpus)

    def test_existing_overlapping_patch_is_rejected_without_mutation(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            producer, pages, corpus, _ = self._fixture(root)
            page_dir = pages / "page-0001"
            raw = editorial.read(page_dir / "ocr.json")
            overlay = {"schema_version": 1, "parent_evidence_sha256": raw["evidence_sha256"],
                       "source_sha256": raw["source_sha256"], "patches": [
                           {"start": 5, "end": 6, "before": "兒", "after": "皃",
                            "source_checked": True, "reason": "previous exact repair"}]}
            overlay_path = page_dir / "ocr-corrections.json"
            editorial.write(overlay_path, overlay)
            source = {"id": "fixture-edition", "producer_root": str(producer),
                      "corpus_path": str(corpus), "pages_root": str(pages),
                      "book_id": "fixture-book", "python_executable": sys.executable}
            effective = source_repairs.producer_effective(source, page_dir)
            pages_now = source_repairs._jsonl_pages(corpus)
            page = pages_now[("fixture-book", 1)]
            page.update({"text": effective["ocr"]["text"],
                         "evidence_sha256": effective["evidence_sha256"]})
            rows = [page if (item["book_id"], item["pdf_page_1based"]) == ("fixture-book", 1) else item
                    for item in pages_now.values()]
            corpus.write_text("".join(json.dumps(item, ensure_ascii=False) + "\n" for item in rows),
                               encoding="utf-8")
            overlay_hash = source_repairs._bytes_hash(overlay_path)
            proof = self._proof(root, producer, page_dir)
            proof["record"]["provenance"]["overlay_sha256"] = overlay_hash
            before_overlay, before_corpus = overlay_path.read_bytes(), corpus.read_bytes()
            with patch.object(source_repairs, "_validated_occurrence", return_value=proof), \
                    patch.object(source_repairs, "_copy_proof", return_value=[]):
                with self.assertRaisesRegex(ValueError, "already present|overlaps"):
                    source_repairs.apply_verified(source, proof["verified_path"], "p1", page_dir,
                        pages, root / "archive", current_overlay_sha256=overlay_hash, timeout=20)
            self.assertEqual(overlay_path.read_bytes(), before_overlay)
            self.assertEqual(corpus.read_bytes(), before_corpus)

    def test_builder_failure_rolls_back_overlay_exports_corpus_and_catalog(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            producer, pages, corpus, catalog = self._fixture(root)
            page_dir = pages / "page-0001"
            source = {"id": "fixture-edition", "producer_root": str(producer),
                      "corpus_path": str(corpus), "pages_root": str(pages),
                      "book_id": "fixture-book", "python_executable": sys.executable}
            before_corpus, before_catalog = corpus.read_bytes(), catalog.read_bytes()
            (producer / "BUILD_FAIL").write_text("fail after partial build", encoding="utf-8")
            proof = self._proof(root, producer, page_dir)
            with patch.object(source_repairs, "_validated_occurrence", return_value=proof), \
                    patch.object(source_repairs, "_copy_proof", return_value=[]):
                with self.assertRaisesRegex(RuntimeError, "consumer corpus rebuild failed"):
                    source_repairs.apply_verified(source, proof["verified_path"], "p1", page_dir,
                        pages, root / "archive", current_overlay_sha256=None, timeout=20)
            self.assertFalse((page_dir / "ocr-corrections.json").exists())
            self.assertFalse((page_dir / "reading-corrected.md").exists())
            self.assertFalse((page_dir / "ocr-corrected.json").exists())
            self.assertEqual(corpus.read_bytes(), before_corpus)
            self.assertEqual(catalog.read_bytes(), before_catalog)
            transactions = list((root / "archive").glob("*/transaction.json"))
            self.assertEqual(len(transactions), 1)
            transaction = editorial.read(transactions[0])
            self.assertEqual(transaction["status"], "rolled_back")
            self.assertTrue(list((transactions[0].parent / "failed-after").rglob("*.jsonl")))

    def test_unresolved_glyph_builder_failure_rolls_back_reference_and_corpus(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            producer, pages, corpus, catalog = self._fixture(root)
            page_dir = pages / "page-0001"
            source = {"id": "fixture-edition", "producer_root": str(producer),
                      "corpus_path": str(corpus), "pages_root": str(pages),
                      "book_id": "fixture-book", "python_executable": sys.executable}
            before_raw, before_corpus, before_catalog = (
                source_repairs._bytes_hash(page_dir / "ocr.json"), corpus.read_bytes(), catalog.read_bytes())
            (producer / "BUILD_FAIL").write_text("fail after partial build", encoding="utf-8")
            proof = self._proof(root, producer, page_dir, verdict="unsupported_raw_identity")
            with patch.object(source_repairs, "_validated_occurrence", return_value=proof), \
                    patch.object(source_repairs, "_copy_proof", return_value=[]):
                with self.assertRaisesRegex(RuntimeError, "consumer corpus rebuild failed"):
                    source_repairs.apply_unidentified_printed_character(
                        source, proof["verified_path"], "p1", page_dir, pages, root / "archive",
                        description="An unresolved printed graph in the fixture paragraph.",
                        uncertainty="Its exact Unicode identity is unresolved.",
                        current_overlay_sha256=None, timeout=20)
            self.assertEqual(source_repairs._bytes_hash(page_dir / "ocr.json"), before_raw)
            self.assertFalse((page_dir / "ocr-corrections.json").exists())
            self.assertEqual(corpus.read_bytes(), before_corpus)
            self.assertEqual(catalog.read_bytes(), before_catalog)
            transaction_paths = list((root / "archive").glob("*/transaction.json"))
            self.assertEqual(len(transaction_paths), 1)
            transaction = editorial.read(transaction_paths[0])
            self.assertEqual(transaction["status"], "rolled_back")
            self.assertEqual(transaction["new_occurrence"]["disposition"], "unsupported_raw_identity")


if __name__ == "__main__":
    unittest.main()
