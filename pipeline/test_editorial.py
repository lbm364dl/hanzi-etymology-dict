import copy
import gzip
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from pipeline.editorial import (Runner, ARTICLE_SCHEMA, REVIEW_SCHEMA, digest, make_review, publish,
                                run, validate_article, validate_published, write, enrich_dossier, validate_research, research_dossier, refine, add_learner, independent_review, annotate_forms, curate_glyphs, local_primary_readings, local_baxter_sagart_rows, local_glyph_hints, repair_reader_prose)
from pipeline.editorial import summarize_web_activity, parse_codex_events, validate_new_reader_style, reuse_glyphs_for_text_followup


class ResearchAuditURLSchemaTests(unittest.TestCase):
    def test_audit_requires_web_urls_but_allows_failed_lookup(self):
        from jsonschema import Draft202012Validator, ValidationError
        from pipeline.editorial import RESEARCH_SCHEMA
        validator = Draft202012Validator(RESEARCH_SCHEMA)
        result = {'evidence': [], 'gaps': [], 'search_audit': [
            {'query': 'actual lookup fixture', 'urls': [], 'outcome': 'Access failed'}]}
        validator.validate(result)
        for url in ('https://example.org/entry', 'http://example.org/entry'):
            result['search_audit'][0]['urls'] = [url]
            validator.validate(result)
        for url in ('file:///tmp/source.png', '/tmp/source.png', 'source.png'):
            result['search_audit'][0]['urls'] = [url]
            with self.assertRaises(ValidationError):
                validator.validate(result)


class NewReaderStyleTests(unittest.TestCase):
    def test_source_labels_and_workflow_remarks_are_rejected(self):
        dossier = {"evidence": [{"source": "漢語多功能字庫, CUHK"},
                                {"source": "李學勤主編《字源》"}]}
        article = {"summary": {"text": "Half is one of two equal parts."},
                   "meaning_history": {"senses": [{"text": "CUHK proposes a split meaning."}]}}
        with self.assertRaisesRegex(ValueError, "Source name 'CUHK'"):
            validate_new_reader_style(article, dossier)
        article["meaning_history"]["senses"][0]["text"] = "字源 calls it original."
        with self.assertRaisesRegex(ValueError, "Source name '字源'"):
            validate_new_reader_style(article, dossier)
        article["meaning_history"]["senses"][0]["text"] = "This dossier does not settle the date."
        with self.assertRaisesRegex(ValueError, "Workflow term"):
            validate_new_reader_style(article, dossier)
        article["meaning_history"]["senses"][0]["text"] = "The source check notes that the two graphs resemble each other."
        with self.assertRaisesRegex(ValueError, "Workflow term"):
            validate_new_reader_style(article, dossier)
        article["meaning_history"]["senses"][0]["text"] = "The source check does not establish a human-like shape."
        with self.assertRaisesRegex(ValueError, "Workflow term"):
            validate_new_reader_style(article, dossier)
        article["meaning_history"]["senses"][0]["text"] = "Early inscriptions show similar paired forms; the date is unresolved."
        validate_new_reader_style(article, dossier)

    def test_source_name_failure_gets_only_the_flagged_text_leaf_repaired(self):
        dossier = {"evidence": [{"source": "李學勤主編《字源》"}]}
        article = {
            "formation": {"text": "《字源》 reports two competing analyses.",
                          "evidence_ids": ["X-early-forms"]},
            "summary": {"text": "Learning is the current meaning.",
                        "evidence_ids": ["E-current"]},
        }

        class RepairRunner:
            def __init__(self):
                self.inputs = None

            def run(self, role, inputs, schema, directory):
                self.asserted_role = role
                self.inputs = inputs
                return {"edits": [{"field": "formation/text",
                                   "text": "Early forms have competing component analyses."}]}

        runner = RepairRunner()
        repaired = repair_reader_prose(article, dossier, Path("unused"), runner)
        self.assertEqual(runner.asserted_role, "prose_repair")
        self.assertEqual([item["field"] for item in runner.inputs["paragraphs"]], ["formation/text"])
        self.assertEqual(runner.inputs["paragraphs"][0]["evidence_ids"], ["X-early-forms"])
        self.assertEqual(repaired["formation"]["evidence_ids"], ["X-early-forms"])
        self.assertEqual(repaired["summary"], article["summary"])
        validate_new_reader_style(repaired, dossier)

    def test_actual_evidence_id_in_prose_is_rejected(self):
        article = {"formation": {"text": "An early proposal [X-source123].",
                                  "evidence_ids": ["X-source123"]}}
        dossier = {"evidence": [{"id": "X-source123", "source": "A source"}]}
        with self.assertRaisesRegex(ValueError, "Evidence IDs"):
            validate_new_reader_style(article, dossier)
        article["formation"]["text"] = "An early proposal."
        validate_new_reader_style(article, dossier)

    def test_clean_reader_text_does_not_invoke_prose_repair(self):
        article = {"summary": {"text": "Learning is the current meaning.",
                               "evidence_ids": ["E-current"]}}

        class NeverRunner:
            def run(self, *args, **kwargs):
                raise AssertionError("Clean reader text must not trigger repair")

        repaired = repair_reader_prose(article, {"evidence": []}, Path("unused"), NeverRunner())
        self.assertEqual(repaired, article)

    def test_failed_citation_repair_retries_without_mutating_evidence(self):
        article = {"formation": {"text": "A proposal [X-source123].",
                                  "evidence_ids": ["X-source123"], "certainty": "disputed"}}
        original = copy.deepcopy(article)
        dossier = {"evidence": [{"id": "X-source123", "source": "A source"}]}

        class FixtureRunner:
            def __init__(self):
                self.calls = []

            def run(self, role, inputs, schema, directory):
                self_schema = schema['properties']['edits']['items']['properties']['text']
                if 'pattern' in self_schema:
                    raise AssertionError('Do not send unsupported exclusion lookaround to the agent API')
                self.calls.append((copy.deepcopy(inputs), directory))
                text = "A proposal [X-source123]." if len(self.calls) == 1 else "A proposal."
                return {"edits": [{"field": "formation/text", "text": text}]}

        runner = FixtureRunner()
        repaired = repair_reader_prose(article, dossier, Path("unused"), runner)
        self.assertEqual(len(runner.calls), 2)
        self.assertIn("validation_error", runner.calls[1][0])
        self.assertEqual(runner.calls[1][1].name, "prose-repair-retry-1")
        self.assertEqual(article, original)
        self.assertEqual(repaired["formation"]["evidence_ids"], ["X-source123"])
        self.assertEqual(repaired["formation"]["certainty"], "disputed")
        validate_new_reader_style(repaired, dossier)

    def test_source_name_in_summary_text_is_repaired_without_touching_metadata(self):
        dossier = {"evidence": [{"source": "李學勤主編《字源》"}]}
        article = {
            "summary": {"text": "字源 calls the early form a learning graph.",
                        "evidence_ids": ["X-learning"]},
            "source_metadata": {"source_title": "字源", "evidence_ids": ["X-metadata"]},
        }

        class RepairRunner:
            def __init__(self):
                self.inputs = None

            def run(self, role, inputs, schema, directory):
                self.inputs = inputs
                return {"edits": [{"field": "summary/text",
                                   "text": "An early account treats learning as a proposed meaning."}]}

        runner = RepairRunner()
        repaired = repair_reader_prose(article, dossier, Path("unused"), runner)
        self.assertEqual([item["field"] for item in runner.inputs["paragraphs"]], ["summary/text"])
        self.assertEqual(repaired["summary"]["evidence_ids"], ["X-learning"])
        self.assertEqual(repaired["source_metadata"], article["source_metadata"])
        validate_new_reader_style(repaired, dossier)

    def test_text_followup_reuses_glyphs_only_without_visual_findings(self):
        feedback = {"reuse_existing_glyph_candidates": True}
        self.assertTrue(reuse_glyphs_for_text_followup(feedback, [
            {"findings": ["Correct a sound comparison citation."]}]))
        self.assertFalse(reuse_glyphs_for_text_followup(feedback, [
            {"findings": ["The glyph caption overstates its provenance."]}]))


class SiteArticleRefreshTests(unittest.TestCase):
    def test_refresh_preserves_legacy_fields_and_other_characters(self):
        from build_site import refresh_existing_site_articles
        with tempfile.TemporaryDirectory() as temp:
            archive = Path(temp) / "data.json.gz"
            original = [{"c": "半", "d": ["half"], "py": "bàn", "article": {"old": True}},
                        {"c": "教", "d": ["teach"], "py": "jiào"}]
            with gzip.open(archive, "wt", encoding="utf-8") as stream:
                json.dump(original, stream, ensure_ascii=False)
            self.assertEqual(refresh_existing_site_articles(archive, {"半": {"new": True}}), 2)
            with gzip.open(archive, "rt", encoding="utf-8") as stream:
                refreshed = json.load(stream)
            self.assertEqual(refreshed, [{"c": "半", "d": ["half"], "py": "bàn",
                                         "article": {"new": True}}, original[1]])
            with self.assertRaisesRegex(ValueError, "lack an approved source"):
                refresh_existing_site_articles(archive, {})


class ScopedRefinementTests(unittest.TestCase):
    def test_generated_edges_are_not_authored_array_protection_targets(self):
        from pipeline.editorial import apply_article_patch
        edge = {'id': 'sense', 'predicate': 'has_sense'}
        inputs = {'article': {'relationships': [edge]},
                  'feedback': {'preserve_array_items': {'relationships': [edge]}}}
        def never_invoke(*args):
            raise AssertionError('Reject incompatible generated-edge protection before agent work')
        with self.assertRaisesRegex(ValueError, 'Protect source sense/development records'):
            apply_article_patch('editor', inputs, {}, Path('unused'), never_invoke)

    def test_preserved_record_cannot_also_be_an_allowed_leaf_edit(self):
        from pipeline.editorial import apply_article_patch
        item = {'text': 'Preserved claim.', 'evidence_ids': ['E1']}
        inputs = {'article': {'history': [item]},
                  'feedback': {'allowed_edit_paths': ['history/0/text'],
                               'preserve_array_items': {'history': [item]}}}
        def never_invoke(*args):
            raise AssertionError('Contradictory coordinator packet must fail before agent work')
        with self.assertRaisesRegex(ValueError, 'targets a preserved array record'):
            apply_article_patch('editor', inputs, {}, Path('unused'), never_invoke)

    def test_exact_approved_base_scopes_fresh_reviews(self):
        dossier = {**copy.deepcopy(DOSSIER), "glyph_research": {"historical_glyphs": GLYPHS},
                   "glyph_assets": []}
        base = copy.deepcopy(ARTICLE_V2)
        reviews = [make_review(role, "pass", [], base, dossier, f"base-{role}")
                   for role in ("factual", "readability")]
        candidate = copy.deepcopy(base)
        candidate["summary"]["text"] = "A tree with branches."
        class Reviewer:
            model = "fake"
            def __init__(self): self.inputs = []
            def run(self, role, inputs, schema, directory):
                self.inputs.append((role, inputs))
                return {"verdict": "pass", "findings": []}
        with tempfile.TemporaryDirectory() as temp:
            reviewer = Reviewer()
            state = refine(candidate, dossier, temp, reviewer, 0, edit_first=False,
                           approved_base={"article": base, "dossier": dossier, "reviews": reviews})
            self.assertEqual(state["status"], "approved")
            self.assertEqual([role for role, _ in reviewer.inputs], ["factual", "readability"])
            self.assertEqual(reviewer.inputs[0][1]["review_scope"], "targeted_refinement")
            self.assertEqual(reviewer.inputs[0][1]["changed_paths"], ["article.summary.text"])
        altered = copy.deepcopy(dossier)
        altered["context"]["note"] = "changed"
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(ValueError, "Approved base dossier differs"):
                refine(candidate, altered, temp, Reviewer(), 0, edit_first=False,
                       approved_base={"article": base, "dossier": dossier, "reviews": reviews})

DOSSIER = {"character": "木", "context": {}, "evidence": [{"id": "source:1", "source": "test",
           "field": "etymology", "text": "A tree.", "kind": "source", "record_character": "木",
           "url": "https://example.org/tree", "title": "Tree form", "accessed_at": "2026-09-26"}],
           "external_research": {"search_audit": [{"query": "木 historical form", "urls": ["https://example.org/tree"],
                                                 "outcome": "Inspected tree form explanation."}], "gaps": []}}
RESEARCH = {"evidence": [{k: v for k, v in DOSSIER["evidence"][0].items() if k != "id"}],
            **DOSSIER["external_research"]}
ARTICLE = {"character": "木", "summary": {"text": "A tree.", "evidence_ids": ["source:1"]},
           "history": [], "uncertainties": [],
           "formation": {"type": "pictographic", "text": "A drawing of a tree.", "evidence_ids": ["source:1"]},
           "components": [{"form": "木", "origin_form": "", "roles": ["pictorial"], "form_status": "stylized",
                           "text": "The whole graph depicts a tree.", "evidence_ids": ["source:1"]}]}


GLYPHS = {"items": [], "limitations": [{"text": "Test fixture has no reusable historical image.", "evidence_ids": ["source:1"]}]}
GLYPH_RESEARCH = {**copy.deepcopy(RESEARCH), "historical_glyphs": GLYPHS}
ARTICLE_V2 = {**copy.deepcopy(ARTICLE), "schema_version": 2, "historical_glyphs": GLYPHS,
    "meaning_history": {"senses": [{"id": "木:tree", "gloss": "tree", "period": "dating unresolved",
        "status": "current", "certainty": "established", "text": "Tree.", "evidence_ids": ["source:1"]}], "developments": [], "limitations": []},
    "relationships": [{"id": "meaning:木:tree", "subject": {"kind": "character", "id": "木"},
        "predicate": "has_sense", "object": {"kind": "sense", "id": "木:tree"}, "context_character": "木",
        "certainty": "established", "text": "Tree.", "evidence_ids": ["source:1"]}]}

ARTICLE_V2["components"][0]["sound"] = []
ARTICLE_V2["components"][0]["origin_relation"] = "none"
ARTICLE_V2["components"][0]["scope_character"] = "木"
ARTICLE_V2["components"][0]["sound_limitation"] = None

ARTICLE_V2["relationships"].append({"id": "tree-picture", "subject": {"kind": "component", "id": "木"},
    "predicate": "pictorial_component_of", "object": {"kind": "character", "id": "木"},
    "context_character": "木", "certainty": "established", "text": "Whole tree picture.", "evidence_ids": ["source:1"]})

ARTICLE_V2["learner"] = {
    "overview": {"text": "木 represents a tree.", "evidence_ids": ["source:1"]},
    "components": [{"component_index": 0, "text": "The whole form pictures a tree.", "evidence_ids": ["source:1"]}],
    "takeaway": None}


class EditorialTests(unittest.TestCase):
    def test_chinese_text_refinement_reuses_verified_glyph_selection(self):
        class ResearchOnlyRunner:
            def run(self, role, inputs, schema, directory):
                if role != "research":
                    raise AssertionError(f"Unexpected glyph stage: {role}")
                return copy.deepcopy(RESEARCH)

        dossier = copy.deepcopy(DOSSIER)
        dossier["context"]["target_language"] = "zh"
        dossier["glyph_research"] = {"historical_glyphs": copy.deepcopy(GLYPHS)}
        dossier["glyph_assets"] = []
        with tempfile.TemporaryDirectory() as temp:
            result = research_dossier(dossier, temp, ResearchOnlyRunner(),
                {"reuse_existing_glyph_candidates": True})
            self.assertEqual(result["glyph_research"], dossier["glyph_research"])
            self.assertEqual(result["glyph_assets"], [])
            self.assertTrue((Path(temp) / "dossier.json").exists())

    def test_codex_jsonl_keeps_unicode_line_separator_inside_result(self):
        event = {"type": "item.completed", "item": {"id": "web-1", "type": "web_search",
                 "action": {"type": "search", "queries": ["學 字源"]},
                 "results": [{"snippet": "before\u2028after"}]}}
        events = parse_codex_events(json.dumps(event, ensure_ascii=False) + "\n")
        self.assertEqual(len(events), 1)
        self.assertEqual(summarize_web_activity(events)["web_search_calls"], 1)

    def test_completed_web_search_keeps_started_action_when_completion_says_other(self):
        events = [
            {"type": "item.started", "item": {"id": "web-1", "type": "web_search",
                "action": {"type": "search", "queries": ["學 字源"]}}},
            {"type": "item.completed", "item": {"id": "web-1", "type": "web_search",
                "action": {"type": "other"}, "results": [{"url": "https://example.org"}]}}
        ]
        self.assertEqual(summarize_web_activity(events), {
            "web_tool_events": 1, "web_action_counts": {"search": 1},
            "web_search_calls": 1, "web_search_queries": ["學 字源"]})

    def test_started_web_search_without_completion_does_not_count(self):
        events = [{"type": "item.started", "item": {"id": "web-1", "type": "web_search",
                   "action": {"type": "search", "queries": ["學 字源"]}}}]
        self.assertEqual(summarize_web_activity(events)["web_search_calls"], 0)

    def test_research_scan_attachment_hash_changes_cache(self):
        from pipeline.editorial import RESEARCH_SCHEMA
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            scan = root / "scan.png"
            scan.write_bytes(b"original scan")
            script = root / "agent.py"
            script.write_text('import sys,json,pathlib\n'
                              f'pathlib.Path(sys.argv[1]).write_text({json.dumps(json.dumps(RESEARCH))})\n')
            runner = Runner([sys.executable, str(script), "{output}"], "fake")
            inputs = {"dossier": DOSSIER, "feedback": {"source_scan_images": [
                {"path": str(scan), "pdf_page": 277, "printed_page": 265}]}}
            job = root / "research"
            runner.run("research", inputs, RESEARCH_SCHEMA, job)
            first = json.loads((job / "meta.json").read_text())["fingerprint"]
            prompt = (job / "prompt.txt").read_text()
            self.assertIn('"attached_source_scans"', prompt)
            self.assertIn('"pdf_page": 277', prompt)
            scan.write_bytes(b"changed scan")
            runner.run("research", inputs, RESEARCH_SCHEMA, job)
            second = json.loads((job / "meta.json").read_text())["fingerprint"]
            self.assertNotEqual(first, second)

    def test_factual_review_receives_source_scan_metadata(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            scan = root / "scan.png"
            scan.write_bytes(b"source pixels")
            script = root / "agent.py"
            script.write_text('import sys,json,pathlib\n'
                              'pathlib.Path(sys.argv[1]).write_text(json.dumps({"verdict":"pass","findings":[]}))\n')
            runner = Runner([sys.executable, str(script), "{output}"], "fake")
            runner.run("factual", {"article": ARTICLE, "dossier": DOSSIER,
                "source_scan_images": [{"path": str(scan), "pdf_page": 277}]},
                REVIEW_SCHEMA, root / "factual")
            prompt = (root / "factual/prompt.txt").read_text()
            inputs = json.JSONDecoder().raw_decode(prompt.split("\nINPUTS:\n", 1)[1])[0]
            self.assertEqual(inputs["attached_source_scans"][0]["attachment_index"], 1)
            self.assertEqual(inputs["attached_source_scans"][0]["pdf_page"], 277)
            self.assertEqual(inputs["attached_images"], [])

    def test_top_level_research_scans_reach_codex_image_arguments(self):
        from pipeline.editorial import RESEARCH_SCHEMA
        import hashlib
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            scans = [root / 'page-277.png', root / 'page-278.png']
            for index, scan in enumerate(scans): scan.write_bytes(f'scan {index}'.encode())
            argv_path = root / 'argv.json'
            # Test-only executable: records transport arguments, without invoking a model.
            script = root / 'codex'
            script.write_text(f'#!{sys.executable}\nimport sys,json,pathlib\n'
                f'pathlib.Path({str(argv_path)!r}).write_text(json.dumps(sys.argv[1:]))\n'
                f'pathlib.Path(sys.argv[sys.argv.index("-o")+1]).write_text({json.dumps(json.dumps(RESEARCH))})\n'
                'print(json.dumps({"type":"item.completed","item":{"type":"web_search",'
                '"action":{"type":"search","queries":["test-only transport fixture"]}}}))\n')
            script.chmod(0o755)
            runner = Runner([str(script), 'exec', '-o', '{output}', '-'], 'fake')
            job = root / 'research'
            runner.run('research', {'dossier': DOSSIER, 'source_scan_images': [
                {'path': str(scan), 'pdf_page': 277 + index}
                for index, scan in enumerate(scans)]}, RESEARCH_SCHEMA, job)
            argv = json.loads(argv_path.read_text())
            at = argv.index('--image')
            self.assertEqual(argv[at+1:at+3], list(map(str, scans)))
            packet = json.JSONDecoder().raw_decode(
                (job / 'prompt.txt').read_text().split('\nINPUTS:\n', 1)[1])[0]
            records = packet['attached_source_scans']
            self.assertEqual([r['attachment_index'] for r in records], [1, 2])
            self.assertEqual([r['pdf_page'] for r in records], [277, 278])
            self.assertEqual([r['sha256'] for r in records], [
                hashlib.sha256(scan.read_bytes()).hexdigest() for scan in scans])
            receipt = json.loads((job / 'meta.json').read_text())
            self.assertEqual(receipt['image_argument_manifest'], [
                {'path': str(scan), 'sha256': hashlib.sha256(scan.read_bytes()).hexdigest()}
                for scan in scans])

    def test_source_pixel_hash_is_distinct_from_attachment_file_hash(self):
        import hashlib
        from PIL import Image
        from pipeline.editorial import source_scan_attachments
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'scan.png'
            pixels = Image.new('RGB', (8, 8), 'white')
            expected = hashlib.sha256(pixels.tobytes()).hexdigest()
            scan = {'path': str(path), 'pdf_page': 1, 'source_pixel_sha256': expected}
            pixels.save(path, compress_level=0)
            first = source_scan_attachments([scan])[1][0]
            pixels.save(path, compress_level=9)
            second = source_scan_attachments([scan])[1][0]
            self.assertNotEqual(first['sha256'], second['sha256'])
            self.assertEqual(first['pixel_sha256'], second['pixel_sha256'])
            self.assertNotEqual(first['sha256'], first['pixel_sha256'])
            pixels.putpixel((0, 0), (0, 0, 0))
            pixels.save(path)
            with self.assertRaisesRegex(ValueError, 'decoded pixel hash') as failure:
                source_scan_attachments([scan])
            self.assertIn(str(path), str(failure.exception))
            self.assertIn('PDF page 1', str(failure.exception))
            self.assertIn(f'expected {expected}', str(failure.exception))
            self.assertIn(hashlib.sha256(pixels.tobytes()).hexdigest(), str(failure.exception))

    def test_local_glyph_leads_are_scoped_existing_files_and_unverified(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            folder = root / "output/glyphs/wikimedia_seal"
            folder.mkdir(parents=True)
            records = {}
            for filename, character in [("牛-seal.svg", "牛"),
                                        ("金 seal.svg", "金"),
                                        ("木-seal.svg", "木"),
                                        ("missing.svg", "牛")]:
                records[filename] = {"filename": filename, "character": character,
                                     "url": "https://example.org/" + filename}
                if filename != "missing.svg":
                    (folder / filename).write_text("<svg/>")
            write(folder / "manifest.json", records)
            inputs = {"character": "牛", "components": [{"scope_character": "金"}],
                      "text": "木 mentioned only in prose is not a requested graph."}
            original = copy.deepcopy(inputs)
            with patch("pipeline.editorial.ROOT", root):
                packet = local_glyph_hints(inputs)
            self.assertEqual({c["character"] for c in packet["candidates"]}, {"牛", "金"})
            self.assertEqual(len(packet["candidates"]), 2)
            self.assertIn("unverified", packet["task"])
            self.assertFalse(any("license" in c for c in packet["candidates"]))
            self.assertTrue(any("%E9%87%91%20seal.svg" in c["source_url"] for c in packet["candidates"]))
            self.assertEqual(inputs, original)
            with patch("pipeline.editorial.ROOT", root):
                filtered = local_glyph_hints({**inputs, "failed_image_candidates": [
                    {"image_url": "https://example.org/牛-seal.svg"}]})
            self.assertEqual([c["character"] for c in filtered["candidates"]], ["金"])

    def test_primary_reading_packet_keeps_exact_forms_and_scoped_host(self):
        inputs = {"article": {"character": "妈", "components": [
            {"form": "未", "origin_form": "", "scope_character": "妹"},
            {"form": "☃", "scope_character": "妹"}]}}
        original = copy.deepcopy(inputs)
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "Unihan_Readings.txt"
            source.write_text("U+672A\tkMandarin\twèi\nU+59B9\tkMandarin\tmèi\nU+5988\tkMandarin\tmā\n")
            with patch("pipeline.editorial.default_unihan_readings_path", return_value=source):
                packet = local_primary_readings(inputs)
        self.assertEqual(packet["unihan"]["rows"], {"未": "wèi", "妹": "mèi", "妈": "mā"})
        self.assertEqual(packet["unihan"]["field"], "kMandarin")
        self.assertEqual(inputs, original)

    def test_historical_primary_rows_preserve_notation_and_multiple_readings(self):
        with tempfile.TemporaryDirectory() as temp:
            for index, delimiter in enumerate(("\t", "\\t")):
                path = Path(temp) / f"table-{index}.tsv"
                lines = [("zi", "py", "MC", "OC", "gloss"),
                         ("路", "lù", "luH", "*Cə.rˤak-s ", "road"),
                         ("路", "fixture", "alternative", "*other", "fixture alternate")]
                path.write_text("\n".join(delimiter.join(row) for row in lines))
                rows = local_baxter_sagart_rows(str(path))
                self.assertEqual(rows["路"][0]["OC"], "*Cə.rˤak-s")
                self.assertEqual(rows["路"][0]["MC"], "luH")
                self.assertEqual(len(rows["路"]), 2)

    def setUp(self):
        # The production pipeline makes one or two official per-character
        # Xiaoxuetang form queries. Keep editorial unit tests offline; the
        # source adapter has independent request/parser tests.
        self.xiaoxuetang_patch = patch("pipeline.editorial.query_xiaoxuetang",
            return_value={"entry_character": "木", "queries": [], "candidates": []})
        self.xiaoxuetang_patch.start()
        self.addCleanup(self.xiaoxuetang_patch.stop)

    def reviews(self, article=ARTICLE, dossier=DOSSIER):
        return [make_review(role, "pass", [], article, dossier, role) for role in ["factual", "readability"]]

    def test_assembly_strips_transport_citation_aliases_from_prose(self):
        from pipeline.editorial import assemble_article
        article = copy.deepcopy(ARTICLE_V2)
        article["summary"]["text"] += " (ref032, ref034)"
        before_ids = article["summary"]["evidence_ids"][:]
        result = assemble_article(article, {**DOSSIER, "glyph_research": {"historical_glyphs": GLYPHS}})
        self.assertNotIn("ref032", result["summary"]["text"])
        self.assertEqual(result["summary"]["evidence_ids"], before_ids)

    def test_assembly_namespaces_senses_and_preserves_authored_links(self):
        from pipeline.editorial import assemble_article
        article = copy.deepcopy(ARTICLE_V2)
        original = article["meaning_history"]["senses"][0]
        original["id"] = "foreign:tree"
        second = {**copy.deepcopy(original), "id": "wood"}
        article["meaning_history"]["senses"].append(second)
        article["meaning_history"]["developments"] = [{"from_sense": "foreign:tree", "to_sense": "wood", "type": "extension", "certainty": "probable", "text": "A proposed extension.", "evidence_ids": ["source:1"]}]
        before = copy.deepcopy(article)
        result = assemble_article(article, {**DOSSIER, "glyph_research": {"historical_glyphs": GLYPHS}})
        self.assertEqual(article, before)
        self.assertEqual([s["id"] for s in result["meaning_history"]["senses"]], ["木:foreign:tree", "木:wood"])
        self.assertEqual(result["meaning_history"]["senses"][0]["text"], original["text"])
        change = result["meaning_history"]["developments"][0]
        self.assertEqual((change["from_sense"], change["to_sense"]), ("木:foreign:tree", "木:wood"))
        edge = next(r for r in result["relationships"] if r["predicate"] == "sense_developed_into")
        self.assertEqual(edge["subject"]["id"], change["from_sense"])
        self.assertEqual(edge["object"]["id"], change["to_sense"])

    def test_chinese_targeted_patch_preserves_unaffected_fields(self):
        from pipeline.editorial import apply_article_patch, WRITER_SCHEMA
        article = copy.deepcopy(ARTICLE_V2)
        before = copy.deepcopy(article)
        def invoke(role, inputs, schema, directory):
            self.assertEqual(role, 'article_patch')
            branches = inputs['article_contract']['relationship_branches']
            predicates = {p for branch in branches for p in branch['predicates']}
            self.assertIn('semantic_component_of', predicates)
            self.assertNotIn('_component_of', predicates)
            self.assertNotIn('unknown_component_of', predicates)
            self.assertTrue(any(branch['subject_kind'] == 'component' and
                                branch['object_kind'] == 'character' for branch in branches))
            return {'edits': [{'path': 'summary/text', 'value_json': 'Trees and wood.'},
                              {'path': 'summary/evidence_ids', 'value_json': '["ref001"]'}]}
        result = apply_article_patch('revision', {'article': article, 'dossier': {**DOSSIER,
            'glyph_research': {'historical_glyphs': article['historical_glyphs']}}},
                                     WRITER_SCHEMA, Path('/unused'), invoke)
        self.assertEqual(result['summary']['text'], 'Trees and wood.')
        self.assertEqual(result['summary']['evidence_ids'], ['source:1'])
        self.assertEqual(result['components'], before['components'])
        self.assertEqual(result['relationships'], before['relationships'])
        self.assertEqual(article, before)

    def test_array_patch_trailing_sibling_fields_are_rejected_with_exact_target_feedback(self):
        from pipeline.editorial import apply_article_patch, WRITER_SCHEMA
        article = copy.deepcopy(ARTICLE_V2)
        before = copy.deepcopy(article)
        calls = []
        def invoke(role, inputs, schema, directory):
            calls.append(inputs)
            if len(calls) == 1:
                return {'edits': [{'path': 'meaning_history/senses',
                                  'value_json': '[],"developments":[]'}]}
            self.assertIn('Invalid JSON replacement at meaning_history/senses',
                          inputs['validation_findings'][0])
            self.assertIn('one complete array value', inputs['validation_findings'][0])
            self.assertEqual(inputs['article']['meaning_history'], before['meaning_history'])
            return {'edits': [{'path': 'meaning_history/senses',
                              'value_json': json.dumps(before['meaning_history']['senses'])}]}
        dossier = {**DOSSIER, 'glyph_research': {'historical_glyphs': article['historical_glyphs']}}
        result = apply_article_patch('revision', {'article': article, 'dossier': dossier},
                                     WRITER_SCHEMA, Path('/unused'), invoke)
        self.assertEqual(len(calls), 2)
        self.assertEqual(result['meaning_history'], before['meaning_history'])
        self.assertEqual(article, before)

    def test_indexed_citation_patch_expands_transport_alias(self):
        from pipeline.editorial import apply_article_patch, WRITER_SCHEMA
        article = copy.deepcopy(ARTICLE_V2)
        dossier = {**DOSSIER, 'glyph_research': {'historical_glyphs': article['historical_glyphs']}}
        dossier['evidence'] = [*DOSSIER['evidence'], {**DOSSIER['evidence'][0], 'id': 'source:2'}]
        calls = []
        def invoke(role, inputs, schema, directory):
            calls.append(role)
            return {'edits': [{'path': 'summary/evidence_ids/0', 'value_json': '"ref002"'}]}
        result = apply_article_patch('revision', {'article': article, 'dossier': dossier},
                                     WRITER_SCHEMA, Path('/unused'), invoke)
        self.assertEqual(calls, ['article_patch'])
        self.assertEqual(result['summary']['evidence_ids'][0], 'source:2')
        self.assertEqual(article, ARTICLE_V2)

    def test_array_removal_preserves_other_supported_records(self):
        from pipeline.editorial import apply_article_patch, WRITER_SCHEMA
        article = copy.deepcopy(ARTICLE_V2)
        kept = [{'text': 'A tree form.', 'evidence_ids': [DOSSIER['evidence'][0]['id']]}]
        removed = {'text': 'An unused image file.', 'evidence_ids': ['E1']}
        article['history'] = [removed, *kept]
        dossier = {**DOSSIER, 'glyph_research': {'historical_glyphs': article['historical_glyphs']}}
        calls = []
        def invoke(role, inputs, schema, directory):
            calls.append(inputs)
            self.assertEqual(inputs['article_contract']['preserve_array_items']['history'], kept)
            if len(calls) == 1:
                return {'edits': [{'path': 'history', 'value_json': '[]'}]}
            self.assertIn('protected array records', inputs['validation_findings'][0])
            self.assertEqual(inputs['article']['history'], article['history'])
            return {'edits': [{'path': 'history', 'value_json': json.dumps(kept)}]}
        result = apply_article_patch('revision', {'article': article, 'dossier': dossier,
            'allowed_edit_paths': ['history'], 'preserve_array_items': {'history': kept}},
            WRITER_SCHEMA, Path('/unused'), invoke)
        self.assertEqual(len(calls), 2)
        self.assertEqual(result['history'], kept)
        self.assertEqual(article['history'][0], removed)

    def test_targeted_patch_repairs_semantic_validation_before_review(self):
        from pipeline.editorial import apply_article_patch, WRITER_SCHEMA
        article = copy.deepcopy(ARTICLE_V2)
        dossier = {**DOSSIER, 'glyph_research': {'historical_glyphs': article['historical_glyphs']}}
        calls = []
        def invoke(role, inputs, schema, directory):
            calls.append(inputs)
            if len(calls) == 1:
                return {'edits': [{'path': 'components/0/origin_relation',
                                  'value_json': '"earlier_form"'}]}
            self.assertIn('origin_relation', inputs['validation_findings'][0])
            self.assertEqual(inputs['article']['components'][0]['origin_relation'], 'earlier_form')
            return {'edits': [{'path': 'components/0/origin_relation', 'value_json': '"none"'}]}
        result = apply_article_patch('revision', {'article': article, 'dossier': dossier},
                                     WRITER_SCHEMA, Path('/unused'), invoke)
        self.assertEqual(len(calls), 2)
        self.assertEqual(result['components'], article['components'])

    def test_targeted_patch_defers_learner_length_to_narrow_repair(self):
        from pipeline.editorial import apply_article_patch, WRITER_SCHEMA
        article = copy.deepcopy(ARTICLE_V2)
        dossier = {**DOSSIER, 'glyph_research': {'historical_glyphs': article['historical_glyphs']}}
        long_text = ' '.join(['tree'] * 31)
        calls = []
        def invoke(role, inputs, schema, directory):
            calls.append(role)
            return {'edits': [{'path': 'learner/components/0/text', 'value_json': long_text}]}
        result = apply_article_patch('revision', {'article': article, 'dossier': dossier},
                                     WRITER_SCHEMA, Path('/unused'), invoke)
        self.assertEqual(calls, ['article_patch'])
        self.assertEqual(result['learner']['components'][0]['text'], long_text)

    def test_editor_inputs_exclude_harness_derived_edges(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            script = root / "agent.py"
            script.write_text('import sys,json,pathlib\npathlib.Path(sys.argv[1]).write_text(json.dumps({"verdict":"pass","findings":[]}))\n')
            runner = Runner([sys.executable, str(script), "{output}"], "fake")
            article = copy.deepcopy(ARTICLE_V2)
            before = copy.deepcopy(article)
            runner.run("editor", {"article": article, "dossier": DOSSIER}, REVIEW_SCHEMA, root / "editor")
            prompt = (root / "editor/prompt.txt").read_text()
            inputs = json.JSONDecoder().raw_decode(prompt.split("\nINPUTS:\n", 1)[1])[0]
            self.assertEqual(article, before)
            self.assertTrue(any(r["predicate"] == "has_sense" for r in article["relationships"]))
            self.assertFalse(any(r["predicate"] == "has_sense" for r in inputs["article"]["relationships"]))
            self.assertTrue(any(r["predicate"] == "pictorial_component_of" for r in inputs["article"]["relationships"]))
            self.assertEqual(inputs["article"]["meaning_history"]["senses"][0]["id"], article["meaning_history"]["senses"][0]["id"])

    def test_targeted_patch_maps_current_sense_identity_to_zero_based_paths(self):
        from pipeline.editorial import apply_article_patch, WRITER_SCHEMA
        article = copy.deepcopy(ARTICLE_V2)
        first = article['meaning_history']['senses'][0]
        second = {**copy.deepcopy(first), 'id': '木:secondary', 'gloss': 'secondary use'}
        article['meaning_history']['senses'].append(second)
        dossier = {**copy.deepcopy(DOSSIER), 'glyph_research': {'historical_glyphs': GLYPHS}}
        for reverse in (False, True):
            current = copy.deepcopy(article)
            if reverse:
                current['meaning_history']['senses'].reverse()
            before = copy.deepcopy(current)
            expected = current['meaning_history']['senses'][1]
            def invoke(role, inputs, schema, directory):
                targets = inputs['article_contract']['array_item_targets']
                self.assertEqual(targets, {'meaning_history/senses/1': {
                    'zero_based_index': 1, 'id': expected['id'], 'gloss': expected['gloss']}})
                return {'edits': [{'path': 'meaning_history/senses/1/text',
                                   'value_json': '"Scoped replacement."'}]}
            with tempfile.TemporaryDirectory() as temp:
                result = apply_article_patch('revision', {
                    'article': current, 'dossier': dossier,
                    'allowed_edit_paths': ['meaning_history/senses/1/text']},
                    WRITER_SCHEMA, temp, invoke)
            self.assertEqual(result['meaning_history']['senses'][1]['id'], expected['id'])
            self.assertEqual(result['meaning_history']['senses'][0],
                             before['meaning_history']['senses'][0])
            self.assertEqual(current, before)

    def test_targeted_patch_rejects_generated_edge_edits_and_repairs_source_sense(self):
        from pipeline.editorial import apply_article_patch, WRITER_SCHEMA, assemble_article
        article = copy.deepcopy(ARTICLE_V2)
        dossier = {**copy.deepcopy(DOSSIER), 'glyph_research': {'historical_glyphs': GLYPHS}}
        original = copy.deepcopy(article)
        calls = []
        def invoke(role, inputs, schema, directory):
            calls.append(inputs)
            paths = schema['properties']['edits']['items']['properties']['path']['enum']
            for i, edge in enumerate(article['relationships']):
                if edge['predicate'] == 'has_sense':
                    self.assertNotIn(f'relationships/{i}/certainty', paths)
            if len(calls) == 1:
                edges = copy.deepcopy(article['relationships'])
                next(e for e in edges if e['predicate'] == 'has_sense')['certainty'] = 'disputed'
                return {'edits': [{'path': 'relationships', 'value_json': json.dumps(edges)}]}
            self.assertIn('meaning_history', inputs['validation_findings'][0])
            self.assertEqual(inputs['article']['relationships'], article['relationships'])
            return {'edits': [
                {'path': 'meaning_history/senses/0/certainty', 'value_json': '"disputed"'}]}
        with tempfile.TemporaryDirectory() as temp:
            result = apply_article_patch('revision', {'article': article, 'dossier': dossier},
                                         WRITER_SCHEMA, temp, invoke)
        assembled = assemble_article(result, dossier)
        self.assertEqual(assembled['meaning_history']['senses'][0]['certainty'], 'disputed')
        edge = next(e for e in assembled['relationships'] if e['predicate'] == 'has_sense')
        self.assertEqual(edge['certainty'], 'disputed')
        self.assertEqual(article, original)
        self.assertEqual(len(calls), 2)

    def test_targeted_patch_accepts_empty_authored_edges_and_regenerates_senses(self):
        from pipeline.editorial import apply_article_patch, WRITER_SCHEMA, assemble_article
        article = copy.deepcopy(ARTICLE_V2)
        dossier = {**copy.deepcopy(DOSSIER), 'glyph_research': {'historical_glyphs': GLYPHS}}
        calls = []
        def invoke(role, inputs, schema, directory):
            calls.append(inputs)
            self.assertEqual(inputs['article_contract']['patch_value_kinds']['summary'], 'object')
            self.assertEqual(inputs['article_contract']['patch_value_kinds']['summary/text'], 'string')
            return {'edits': [{'path': 'relationships', 'value_json': '[]'}]}
        result = apply_article_patch('revision', {'article': article, 'dossier': dossier},
                                     WRITER_SCHEMA, Path('/unused'), invoke)
        assembled = assemble_article(result, dossier)
        validate_article(assembled, dossier)
        self.assertTrue(assembled['relationships'])
        self.assertTrue(all(edge['predicate'] in ('has_sense', 'sense_developed_into',
            'phonetic_loan_for') for edge in assembled['relationships']))
        self.assertEqual(len(calls), 1)
        self.assertEqual(article, ARTICLE_V2)

    def test_disputed_role_hypothesis_does_not_assert_a_known_role(self):
        dossier = {**copy.deepcopy(DOSSIER), "glyph_research": {"historical_glyphs": GLYPHS}}
        article = copy.deepcopy(ARTICLE_V2)
        article["components"][0].update(roles=["unknown"], form_status="disputed")
        article["relationships"][1].update(predicate="semantic_component_of", certainty="disputed")
        validate_article(article, dossier)
        article["relationships"][1]["certainty"] = "established"
        with self.assertRaises(ValueError):
            validate_article(article, dossier)

    def test_v2_references_selection_and_graph_agreement(self):
        dossier = {**copy.deepcopy(DOSSIER), "glyph_research": {"historical_glyphs": GLYPHS}}
        validate_article(ARTICLE_V2, dossier)
        changes = [
            lambda a: a["meaning_history"]["senses"][0].update(id="tree"),
            lambda a: a["relationships"][0]["object"].update(id="木:invented"),
            lambda a: a["relationships"][0].update(context_character="水"),
            lambda a: a["relationships"].pop(0),
            lambda a: a["relationships"][1].update(predicate="phonetic_component_of"),
            lambda a: a["historical_glyphs"].update(limitations=[]),
            lambda a: a["historical_glyphs"]["limitations"][0].update(text="Changed selection"),
            lambda a: a["meaning_history"]["senses"][0].update(evidence_ids=["invented"]),
        ]
        for change in changes:
            article = copy.deepcopy(ARTICLE_V2)
            change(article)
            with self.assertRaises(ValueError):
                validate_article(article, dossier)
        with tempfile.TemporaryDirectory() as temp:
            entry = json.loads(publish(ARTICLE_V2, dossier,
                self.reviews(ARTICLE_V2, dossier), Path(temp) / "entries").read_text())
            self.assertEqual(validate_published(entry), ARTICLE_V2)
            entry["meaning_history"]["senses"][0]["gloss"] = "tampered"
            with self.assertRaises(ValueError):
                validate_published(entry)

    def test_v2_allows_graph_level_form_history_without_fake_component_cards(self):
        dossier = copy.deepcopy(DOSSIER)
        dossier["character"] = "开"
        dossier["evidence"][0]["record_character"] = "开"
        dossier["evidence"][0]["text"] = "开 is the standardized simplified form corresponding to 開."
        dossier["glyph_research"] = {"historical_glyphs": copy.deepcopy(GLYPHS)}
        article = copy.deepcopy(ARTICLE_V2)
        article["character"] = "开"
        article["summary"] = {"text": "开 is the standard simplified form of 開.", "evidence_ids": ["source:1"]}
        article["formation"] = {"type": "derived", "text": "The simplified graph corresponds to 開.",
                                 "evidence_ids": ["source:1"]}
        article["components"] = []
        article["meaning_history"]["senses"] = [{"id": "开:open", "gloss": "open", "period": "current",
            "status": "current", "certainty": "established", "text": "开 means open.",
            "evidence_ids": ["source:1"]}]
        article["relationships"] = [
            {"id": "sense", "subject": {"kind": "character", "id": "开"},
             "object": {"kind": "sense", "id": "开:open"}, "predicate": "has_sense",
             "context_character": "开", "certainty": "established", "text": "开 means open.",
             "evidence_ids": ["source:1"]},
            {"id": "simplified-form", "subject": {"kind": "character", "id": "开"},
             "object": {"kind": "character", "id": "開"}, "predicate": "simplified_from",
             "context_character": "开", "certainty": "established",
             "text": "开 is the standardized simplified counterpart of 開.",
             "evidence_ids": ["source:1"]}]
        article["learner"] = {"overview": {"text": "开 is the simplified form of 開.",
            "evidence_ids": ["source:1"]}, "components": [], "takeaway": None}
        validate_article(article, dossier)

        self_component = {"form": "开", "origin_form": "開", "origin_relation": "simplified_form",
            "roles": ["replacement"], "form_status": "simplified", "scope_character": "开",
            "sound": [], "sound_limitation": None, "text": "Whole-character change.",
            "evidence_ids": ["source:1"]}
        article["components"] = [self_component]
        article["learner"]["components"] = [{"component_index": 0, "text": "Whole-character change.",
                                               "evidence_ids": ["source:1"]}]
        with self.assertRaisesRegex(ValueError, "distinct whole-character form relation is not an internal component"):
            validate_article(article, dossier)

    def test_semantic_validation_routes_to_bounded_revision(self):
        class FixingRunner:
            model = "fake"
            def run(self, role, inputs, schema, directory):
                if role == "editor":
                    return copy.deepcopy(inputs["article"])
                if role == "research":
                    return copy.deepcopy(RESEARCH)
                if role == "glyph_research":
                    return copy.deepcopy(GLYPH_RESEARCH)
                if role == "glyph_visual":
                    return copy.deepcopy(inputs["dossier"]["glyph_research"]["historical_glyphs"])
                if role == "revision_plan":
                    return {"action": "research", "reason": "Fixture requires additional research."}
                if role == "analysis":
                    return {"supported_claims": [], "disagreements": [], "limitations": []}
                if role == "writer":
                    article = copy.deepcopy(ARTICLE_V2)
                    article["relationships"][1]["object"]["id"] = "水"
                    return article
                if role == "revision":
                    assert inputs["reviews"][0]["role"] == "validation"
                    return copy.deepcopy(ARTICLE_V2)
                return {"verdict": "pass", "findings": []}
        with tempfile.TemporaryDirectory() as root:
            state = run(DOSSIER, root, FixingRunner(), max_revisions=1)
            self.assertEqual(state["status"], "approved")
            self.assertTrue((Path(root) / "round-0/invalid-article.json").exists())
            self.assertEqual(len(json.loads((Path(root) / "reviews.json").read_text())), 2)
        with tempfile.TemporaryDirectory() as root:
            state = run(DOSSIER, root, FixingRunner(), max_revisions=0)
            self.assertEqual(state["status"], "needs_revision")
            self.assertEqual(json.loads((Path(root) / "reviews.json").read_text()), [])

    def test_review_can_repair_upstream_glyph_selection(self):
        revised_glyphs = copy.deepcopy(GLYPHS)
        revised_glyphs["limitations"][0]["text"] = "Corrected image-selection limitation."
        class UpstreamRunner:
            model = "fake"
            def run(self, role, inputs, schema, directory):
                if role == "editor":
                    return copy.deepcopy(inputs["article"])
                if role == "research":
                    return copy.deepcopy(RESEARCH)
                if role == "glyph_research":
                    result = copy.deepcopy(GLYPH_RESEARCH)
                    if "reviews" in inputs:
                        result["historical_glyphs"] = revised_glyphs
                    return result
                if role == "glyph_visual":
                    return copy.deepcopy(inputs["dossier"]["glyph_research"]["historical_glyphs"])
                if role == "revision_plan":
                    return {"action": "research", "reason": "Fixture requires additional research."}
                if role == "analysis":
                    return {"supported_claims": [], "disagreements": [], "limitations": []}
                if role in ("writer", "revision"):
                    article = copy.deepcopy(ARTICLE_V2)
                    article["historical_glyphs"] = copy.deepcopy(inputs["dossier"]["glyph_research"]["historical_glyphs"])
                    return article
                if role == "factual" and inputs["article"]["historical_glyphs"] == GLYPHS:
                    return {"verdict": "revise", "findings": ["Correct the glyph-selection limitation."]}
                return {"verdict": "pass", "findings": []}
        with tempfile.TemporaryDirectory() as root:
            self.assertEqual(run(DOSSIER, root, UpstreamRunner(), 1)["status"], "approved")
            article = json.loads((Path(root) / "article.json").read_text())
            dossier = json.loads((Path(root) / "dossier.json").read_text())
            self.assertEqual(article["historical_glyphs"], revised_glyphs)
            self.assertEqual(dossier["glyph_research"]["historical_glyphs"], revised_glyphs)
            reviews = json.loads((Path(root) / "reviews.json").read_text())
            self.assertTrue(all(r["dossier_hash"] == digest(dossier) for r in reviews))

    def test_glyph_research_aliases_and_visual_selection_integrity(self):
        class VisualRunner:
            model = "fake"
            tamper = False
            def run(self, role, inputs, schema, directory):
                if role == "editor":
                    return copy.deepcopy(inputs["article"])
                if role == "research":
                    return copy.deepcopy(RESEARCH)
                if role == "glyph_research":
                    result = copy.deepcopy(GLYPH_RESEARCH)
                    result["historical_glyphs"]["limitations"][0]["evidence_ids"] = ["new:1"]
                    return result
                if role == "glyph_visual":
                    result = copy.deepcopy(inputs["dossier"]["glyph_research"]["historical_glyphs"])
                    assert result["limitations"][0]["evidence_ids"][0].startswith("X-")
                    if self.tamper:
                        result["items"] = [{**{k: "fixture" for k in
                            ("id", "caption", "alt", "selection_reason", "period")}, "evidence_ids": ["source:1"]}]
                    return result
                raise AssertionError(role)
        with tempfile.TemporaryDirectory() as root:
            runner = VisualRunner()
            dossier = research_dossier(DOSSIER, root, runner)
            self.assertTrue(dossier["glyph_research"]["historical_glyphs"]["limitations"][0]["evidence_ids"][0].startswith("X-"))
            runner.tamper = True
            with self.assertRaisesRegex(ValueError, "candidate glyph IDs"):
                research_dossier(DOSSIER, root, runner)

    def test_xiaoxuetang_query_is_available_to_glyph_research(self):
        supplied = {"entry_character": "木", "queries": [], "candidates": [
            {"id": "xiao-1", "query_character": "木", "source_labels": ["商代"],
             "image_url": "https://xiaoxue.iis.sinica.edu.tw/ImageText2/ShowImage.ashx?text=x"}]}
        seen = {}
        class LookupRunner:
            model = "fake"
            def run(self, role, inputs, schema, directory):
                if role == "research":
                    return copy.deepcopy(RESEARCH)
                if role == "glyph_research":
                    seen.update(inputs)
                    return copy.deepcopy(GLYPH_RESEARCH)
                if role == "glyph_visual":
                    return copy.deepcopy(inputs["dossier"]["glyph_research"]["historical_glyphs"])
                raise AssertionError(role)
        with tempfile.TemporaryDirectory() as root:
            with patch("pipeline.editorial.query_xiaoxuetang", return_value=supplied):
                research_dossier(DOSSIER, root, LookupRunner())
            self.assertEqual(seen["xiaoxuetang_query"], supplied)
            saved = json.loads((Path(root) / "xiaoxuetang-query.json").read_text())
            self.assertEqual(saved["candidates"][0]["id"], "xiao-1")

    def test_invalid_glyph_evidence_alias_gets_a_targeted_retry(self):
        class AliasRepairRunner:
            model = "fake"
            glyph_calls = 0
            def run(self, role, inputs, schema, directory):
                if role == "research":
                    return copy.deepcopy(RESEARCH)
                if role == "glyph_research":
                    self.glyph_calls += 1
                    if self.glyph_calls == 1:
                        result = copy.deepcopy(GLYPH_RESEARCH)
                        result["historical_glyphs"]["limitations"][0]["evidence_ids"] = ["new:2"]
                        return result
                    self.asserted = inputs["acquisition_findings"]["reason"]
                    return copy.deepcopy(GLYPH_RESEARCH)
                if role == "glyph_visual":
                    return copy.deepcopy(inputs["dossier"]["glyph_research"]["historical_glyphs"])
                raise AssertionError(role)
        runner = AliasRepairRunner()
        with tempfile.TemporaryDirectory() as root:
            result = research_dossier(DOSSIER, root, runner)
            self.assertEqual(runner.glyph_calls, 2)
            self.assertEqual(runner.asserted, "Invalid glyph evidence references")
            failure = json.loads((Path(root) / "glyph-reference-failure-1.json").read_text())
            self.assertIn("new:2", failure["error"])
            self.assertEqual(result["glyph_research"]["historical_glyphs"], GLYPHS)

    def test_candidate_download_failures_get_bounded_agent_repairs(self):
        class RepairRunner:
            model = "fake"
            calls = 0
            def run(self, role, inputs, schema, directory):
                if role == "editor":
                    return copy.deepcopy(inputs["article"])
                if role == "research":
                    return copy.deepcopy(RESEARCH)
                if role == "glyph_research":
                    self.calls += 1
                    if self.calls > 1:
                        assert "404" in inputs["acquisition_findings"]["error"], repr(inputs.get("acquisition_findings"))
                        assert "glyph_research" not in inputs["dossier"]
                        assert "Do not return any listed failed candidate ID" in inputs["acquisition_task"]
                    result = copy.deepcopy(GLYPH_RESEARCH)
                    result["historical_glyphs"]["items"] = [{**{k: "fixture" for k in
                        ("id", "source_title", "period", "tradition", "caption", "alt", "selection_reason", "rights")},
                        "id": f"fixture-{self.calls}",
                        "image_url": "https://example.org/" + ("wrong.png" if self.calls == 1 else f"actual-{self.calls}.png"),
                        "source_url": "https://example.org/source", "rights_url": "https://example.org/license",
                        "evidence_ids": ["source:1"]}]
                    return result
                if role == "glyph_visual":
                    return copy.deepcopy(GLYPHS)
                raise AssertionError(role)
        with tempfile.TemporaryDirectory() as root:
            runner = RepairRunner()
            attempted_urls = []
            def snapshot(dossier, previous):
                attempted_urls.append(dossier["glyph_research"]["historical_glyphs"]["items"][0]["image_url"])
                if len(attempted_urls) == 1:
                    raise OSError("HTTP 404")
                return []
            with patch("pipeline.editorial.snapshot_glyph_assets", side_effect=snapshot):
                research_dossier(DOSSIER, root, runner)
            self.assertEqual(attempted_urls, ["https://example.org/wrong.png", "https://example.org/actual-2.png"])
            failure = json.loads((Path(root) / "glyph-acquisition-failure-1.json").read_text())
            self.assertEqual(failure["candidates"][0]["image_url"], "https://example.org/wrong.png")
            self.assertEqual(runner.calls, 2)
        with tempfile.TemporaryDirectory() as root:
            runner = RepairRunner()
            with patch("pipeline.editorial.snapshot_glyph_assets", side_effect=OSError("HTTP 404")):
                with self.assertRaises(OSError):
                    research_dossier(DOSSIER, root, runner)
            self.assertEqual(runner.calls, 3)
            self.assertFalse((Path(root) / "dossier.json").exists())

    def test_glyph_retry_retains_failures_from_all_prior_attempts(self):
        class RetryRunner:
            model = "fake"
            calls = 0
            def run(self, role, inputs, schema, directory):
                if role == "research":
                    return copy.deepcopy(RESEARCH)
                if role == "glyph_research":
                    self.calls += 1
                    if self.calls == 3:
                        self_outer.assertEqual({x["image_url"] for x in inputs["failed_image_candidates"]},
                            {"https://example.org/a.png", "https://example.org/b.png"})
                    letter = "b" if self.calls == 2 else "a"
                    candidate = {**{k: "fixture" for k in
                        ("source_title", "period", "tradition", "caption", "alt", "selection_reason", "rights")},
                        "id": letter, "image_url": f"https://example.org/{letter}.png",
                        "source_url": "https://example.org/source", "rights_url": "https://example.org/license",
                        "evidence_ids": ["source:1"]}
                    return {**copy.deepcopy(RESEARCH),
                            "historical_glyphs": {"items": [candidate], "limitations": []}}
                raise AssertionError(role)
        self_outer = self
        attempts = []
        def snapshot(dossier, previous):
            attempts.append(dossier["glyph_research"]["historical_glyphs"]["items"][0]["image_url"])
            raise OSError("HTTP 404")
        with tempfile.TemporaryDirectory() as root:
            with patch("pipeline.editorial.snapshot_glyph_assets", side_effect=snapshot):
                with self.assertRaisesRegex(ValueError, "already failed"):
                    research_dossier(DOSSIER, root, RetryRunner())
        self.assertEqual(attempts, ["https://example.org/a.png", "https://example.org/b.png"])

    def test_previously_failed_glyph_candidate_is_not_downloaded_again(self):
        original = {"id": "blocked-image", "image_url": "https://example.org/blocked.png",
            "source_url": "https://example.org/file/blocked", "source_title": "Blocked source",
            "period": "Shang", "tradition": "oracle-style redraw", "caption": "A redraw.",
            "alt": "A historical glyph redraw.", "selection_reason": "Shows the graph.",
            "rights": "CC0", "rights_url": "https://example.org/license", "evidence_ids": ["source:1"]}
        alternate = {**original, "id": "alternate-image", "image_url": "https://example.org/alternate.png",
                     "source_url": "https://example.org/file/alternate"}

        class CandidateRunner:
            model = "fake"
            calls = 0
            def run(self, role, inputs, schema, directory):
                if role == "research":
                    return copy.deepcopy(RESEARCH)
                if role == "glyph_research":
                    self.calls += 1
                    if self.calls == 2:
                        assert inputs["acquisition_findings"]["reason"] == "Failed image candidates must be excluded"
                        assert "Do not return any listed failed candidate ID" in inputs["acquisition_task"]
                    candidate = alternate if self.calls == 3 else original
                    return {**copy.deepcopy(RESEARCH),
                        "historical_glyphs": {"items": [copy.deepcopy(candidate)], "limitations": []}}
                if role == "glyph_visual":
                    items = inputs["dossier"]["glyph_research"]["historical_glyphs"]["items"]
                    return {"items": [{key: item[key] for key in
                        ("id", "caption", "alt", "selection_reason", "evidence_ids", "period")} for item in items],
                        "limitations": []}
                raise AssertionError(role)

        runner = CandidateRunner()
        attempted_urls = []
        def snapshot(dossier, previous):
            selected = dossier["glyph_research"]["historical_glyphs"]["items"][0]
            attempted_urls.append(selected["image_url"])
            if len(attempted_urls) == 1:
                raise OSError("HTTP Error 401: Unauthorized")
            return []

        with tempfile.TemporaryDirectory() as root:
            with patch("pipeline.editorial.snapshot_glyph_assets", side_effect=snapshot), \
                 patch("pipeline.editorial.validate_glyph_assets", return_value={}):
                result = research_dossier(DOSSIER, root, runner)
            self.assertEqual(runner.calls, 3)
            self.assertEqual(attempted_urls, [original["image_url"], alternate["image_url"]])
            failure = json.loads((Path(root) / "glyph-acquisition-reuse-failure-2.json").read_text())
            self.assertEqual(failure["candidates"][0]["id"], "blocked-image")
            selected = result["glyph_research"]["historical_glyphs"]["items"]
            self.assertEqual([item["id"] for item in selected], ["alternate-image"])

    def test_refine_edits_before_new_style_gate_and_requires_fresh_reviews(self):
        class RefiningRunner:
            model = "fake"
            calls = []
            reject = False
            def run(self, role, inputs, schema, directory):
                self.calls.append(role)
                if role == "editor":
                    self.feedback_seen = inputs.get("feedback")
                    return copy.deepcopy(ARTICLE_V2)
                if role in ("factual", "readability"):
                    return {"verdict": "revise", "findings": ["Needs work"]} if self.reject else {"verdict": "pass", "findings": []}
                raise AssertionError("Unnecessary initial stage: " + role)
        dossier = {**copy.deepcopy(DOSSIER), "glyph_research": {"historical_glyphs": GLYPHS}, "glyph_assets": []}
        old = copy.deepcopy(ARTICLE_V2)
        old["meaning_history"]["senses"][0]["text"] = "The dossier describes a tree."
        with self.assertRaisesRegex(ValueError, "dossier"):
            validate_article(old, dossier)
        with tempfile.TemporaryDirectory() as root:
            runner = RefiningRunner()
            runner.calls = []
            state = refine(old, dossier, root, runner, 0, feedback=["Explain the tree directly."])
            self.assertEqual(runner.feedback_seen, ["Explain the tree directly."])
            self.assertEqual(json.loads((Path(root) / "source_feedback.json").read_text()), runner.feedback_seen)
            self.assertEqual(state["status"], "approved")
            self.assertEqual(runner.calls, ["editor", "factual", "readability"])
            self.assertEqual(json.loads((Path(root) / "source_article.json").read_text()), old)
            revised = json.loads((Path(root) / "article.json").read_text())
            reviews = json.loads((Path(root) / "reviews.json").read_text())
            self.assertTrue(all(r["article_hash"] == digest(revised) for r in reviews))
            self.assertFalse((Path(root) / "entries").exists())
        with tempfile.TemporaryDirectory() as root:
            runner = RefiningRunner()
            runner.reject = True
            state = refine(old, dossier, root, runner, 0)
            self.assertEqual(state["status"], "needs_revision")
            with self.assertRaises(ValueError):
                publish(ARTICLE_V2, dossier, json.loads((Path(root) / "reviews.json").read_text()), Path(root) / "entries")
        with tempfile.TemporaryDirectory() as root:
            runner = RefiningRunner()
            runner.calls = []
            state = refine(copy.deepcopy(ARTICLE_V2), dossier, root, runner, 0,
                           edit_first=False)
            self.assertEqual(state["status"], "approved")
            self.assertEqual(runner.calls, ["factual", "readability"])
        for change in [lambda a: a.update(character="水"),
                       lambda a: a["summary"].update(evidence_ids=["invented"])]:
            invalid = copy.deepcopy(old)
            change(invalid)
            with tempfile.TemporaryDirectory() as root:
                runner = RefiningRunner()
                runner.calls = []
                with self.assertRaises(ValueError):
                    refine(invalid, dossier, root, runner)
                self.assertEqual(runner.calls, [])
                self.assertEqual(json.loads((Path(root) / "status.json").read_text())["status"], "failed")

    def test_validation_repairs_curated_glyph_prose_before_revision(self):
        class GlyphRepairRunner:
            model = "fake"
            calls = []
            def run(self, role, inputs, schema, directory):
                self.calls.append(role)
                if role in ("editor", "revision"):
                    return copy.deepcopy(ARTICLE_V2)
                if role == "glyph_visual":
                    assert "validation_findings" in inputs
                    return copy.deepcopy(GLYPHS)
                if role in ("factual", "readability"):
                    assert inputs["article"]["historical_glyphs"] == GLYPHS
                    return {"verdict": "pass", "findings": []}
                raise AssertionError("Unexpected stage: " + role)
        glyphs = copy.deepcopy(GLYPHS)
        glyphs["limitations"][0]["text"] = "The dossier does not establish the date."
        dossier = {**copy.deepcopy(DOSSIER), "glyph_research": {"historical_glyphs": glyphs}, "glyph_assets": []}
        article = copy.deepcopy(ARTICLE_V2)
        article["historical_glyphs"] = glyphs
        with tempfile.TemporaryDirectory() as root:
            runner = GlyphRepairRunner()
            runner.calls = []
            state = refine(article, dossier, root, runner, 1)
            self.assertEqual(state["status"], "approved")
            self.assertEqual(runner.calls, ["editor", "glyph_visual", "revision", "factual", "readability"])
            final_dossier = json.loads((Path(root) / "dossier.json").read_text())
            self.assertEqual(final_dossier["glyph_research"]["historical_glyphs"], GLYPHS)
            self.assertEqual(state["dossier_hash"], digest(final_dossier))
            self.assertTrue((Path(root) / "round-0/invalid-article.json").exists())
            reviews = json.loads((Path(root) / "reviews.json").read_text())
            self.assertTrue(all(r["dossier_hash"] == digest(final_dossier) for r in reviews))

    def test_learner_citations_coverage_length_and_backward_hashes(self):
        dossier = {**copy.deepcopy(DOSSIER), "glyph_research": {"historical_glyphs": GLYPHS}}
        validate_article(ARTICLE_V2, dossier)
        brief = copy.deepcopy(ARTICLE_V2)
        brief["learner"]["overview"]["text"] = "word " * 41
        validate_article(brief, dossier)  # Small overruns of the editorial target remain reviewable.
        too_long = copy.deepcopy(ARTICLE_V2)
        too_long["learner"]["overview"]["text"] = "word " * 46
        with self.assertRaisesRegex(ValueError, "Cut lower-priority details.*aim for 40 words"):
            validate_article(too_long, dossier)
        for change in [lambda a: a["learner"]["overview"].update(evidence_ids=["invented"]),
                       lambda a: a["learner"]["components"][0].update(component_index=1),
                       lambda a: a["learner"]["components"].append(copy.deepcopy(a["learner"]["components"][0])),
                       lambda a: a["learner"]["components"][0].update(text="word " * 31),
                       lambda a: a["learner"].update(takeaway={"text": "word " * 41, "evidence_ids": ["source:1"]}),
                       lambda a: a["learner"]["overview"].update(text="The dossier says tree.")]:
            article = copy.deepcopy(ARTICLE_V2)
            change(article)
            with self.assertRaises(ValueError):
                validate_article(article, dossier)
        with tempfile.TemporaryDirectory() as root:
            for has_learner in (False, True):
                article = copy.deepcopy(ARTICLE_V2)
                if not has_learner:
                    article.pop("learner")
                entry = json.loads(publish(article, dossier, self.reviews(article, dossier), Path(root) / "entries").read_text())
                self.assertEqual(validate_published(entry), article)
                self.assertEqual(entry["review"]["article_hash"], digest(article))
                if has_learner:
                    entry["learner"]["overview"]["text"] = "Changed learner prose."
                    with self.assertRaises(ValueError):
                        validate_published(entry)

    def test_chinese_glyph_feedback_recurates_existing_candidates_without_reacquiring(self):
        dossier = copy.deepcopy(DOSSIER)
        dossier["context"]["target_language"] = "zh"
        dossier["glyph_research"] = {"historical_glyphs": copy.deepcopy(GLYPHS)}
        dossier["glyph_assets"] = []

        class Runner:
            def __init__(self):
                self.roles = []
            def run(self, role, inputs, schema, directory):
                self.roles.append(role)
                if role == "research":
                    return copy.deepcopy(RESEARCH)
                if role == "glyph_visual":
                    self.visual_inputs = inputs
                    return {"items": [], "limitations": copy.deepcopy(GLYPHS["limitations"])}
                raise AssertionError(f"Glyph refresh unexpectedly invoked {role}")

        runner = Runner()
        with tempfile.TemporaryDirectory() as temp:
            result = research_dossier(dossier, Path(temp), runner,
                {"reuse_existing_glyph_candidates": True, "review_existing_glyphs": True,
                 "reviews": [{"findings": ["Correct glyph caption provenance."]}]})
        self.assertEqual(runner.roles, ["research", "glyph_visual"])
        self.assertEqual(runner.visual_inputs["reviews"][0]["findings"],
                         ["Correct glyph caption provenance."])
        self.assertEqual(result["glyph_assets"], [])
        self.assertEqual(result["glyph_research"]["historical_glyphs"]["items"], [])

    def test_refine_routes_explicit_glyph_feedback_to_existing_visual_candidates(self):
        dossier = copy.deepcopy(DOSSIER)
        dossier["context"]["target_language"] = "zh"
        dossier["glyph_research"] = {"historical_glyphs": copy.deepcopy(GLYPHS)}
        dossier["glyph_assets"] = []

        class Runner:
            model = "fake"
            def __init__(self):
                self.visual_context = None
            def run(self, role, inputs, schema, directory):
                if role == "research":
                    return copy.deepcopy(RESEARCH)
                if role == "glyph_visual":
                    self.visual_context = inputs
                    return {"items": [], "limitations": copy.deepcopy(GLYPHS["limitations"])}
                if role == "editor":
                    return copy.deepcopy(inputs["article"])
                if role in ("factual", "readability"):
                    return {"verdict": "pass", "findings": []}
                raise AssertionError(role)

        runner = Runner()
        feedback = {"reuse_existing_glyph_candidates": True,
                    "review_existing_glyphs": True,
                    "findings": ["Correct the displayed glyph caption's specimen attribution."]}
        with tempfile.TemporaryDirectory() as temp:
            state = refine(ARTICLE_V2, dossier, Path(temp), runner, max_revisions=0,
                           feedback=feedback, research_first=True)
        self.assertEqual(state["status"], "approved")
        self.assertEqual(runner.visual_context["feedback"], feedback)
        self.assertEqual(runner.visual_context["review_existing_glyphs"], True)

    def test_learner_requires_current_components_with_historical_cards_optional(self):
        from pipeline.structured import validate_learner
        from pipeline.editorial import validate_sections
        article = copy.deepcopy(ARTICLE_V2)
        historical = copy.deepcopy(article['components'][0])
        historical['scope_character'] = '林'
        article['components'].append(historical)
        validate_learner(article, DOSSIER, validate_sections)
        card = {**copy.deepcopy(article['learner']['components'][0]), 'component_index': 1}
        article['learner']['components'].append(card)
        validate_learner(article, DOSSIER, validate_sections)
        article['learner']['components'] = [card]
        with self.assertRaisesRegex(ValueError, 'current-form component'):
            validate_learner(article, DOSSIER, validate_sections)
        article['learner']['components'] = [card, card]
        with self.assertRaisesRegex(ValueError, 'current-form component'):
            validate_learner(article, DOSSIER, validate_sections)

    def test_learner_repair_packet_requires_only_current_host_components(self):
        from pipeline import editorial
        article = copy.deepcopy(ARTICLE_V2)
        historical = copy.deepcopy(article['components'][0])
        historical['scope_character'] = '林'
        article['components'].append(historical)
        article['learner']['components'] = [{**copy.deepcopy(article['learner']['components'][0]),
                                             'component_index': 1}]
        metadata_before = copy.deepcopy(article['components'])

        class LearnerRunner:
            def run(self, role, inputs, schema, directory):
                self.inputs = inputs
                return {"overview": copy.deepcopy(ARTICLE_V2["learner"]["overview"]),
                        "components": [copy.deepcopy(ARTICLE_V2["learner"]["components"][0])],
                        "takeaway": None}

        runner = LearnerRunner()
        context = {'verified_reviews': [{'role': 'readability', 'verdict': 'revise',
                    'findings': ['Preserve the distinction between the current and historical host.']}]}
        repaired = editorial.repair_learner_length(article, DOSSIER, Path("unused"), runner, context)
        self.assertEqual(runner.inputs['required_correction_context'], context)
        self.assertIn('instead of reverting a correction', runner.inputs['task'])
        self.assertEqual(runner.inputs["required_component_indices"], [0])
        self.assertEqual(repaired["components"], metadata_before)
        self.assertEqual([c["component_index"] for c in repaired["learner"]["components"]], [0])
        from pipeline.structured import validate_learner
        validate_learner(repaired, DOSSIER, editorial.validate_sections)

    def test_add_learner_freezes_detail_and_needs_both_new_passes(self):
        class LearnerRunner:
            model = "fake"
            calls = []
            reject_first = True
            def run(self, role, inputs, schema, directory):
                self.calls.append(role)
                assert inputs["review_scope"] == "added_learner"
                assert "base_approval" in inputs
                if role == "learner":
                    if inputs["reviews"]:
                        assert inputs["reviews"][1]["verdict"] == "revise"
                    return copy.deepcopy(ARTICLE_V2["learner"])
                if "proposed_review" in inputs:
                    return copy.deepcopy(inputs["proposed_review"])
                if role == "readability" and self.reject_first:
                    self.reject_first = False
                    return {"verdict": "revise", "findings": ["Clarify the learner explanation."]}
                if role in ("factual", "readability"):
                    return {"verdict": "pass", "findings": []}
                raise AssertionError(role)
        dossier = {**copy.deepcopy(DOSSIER), "glyph_research": {"historical_glyphs": GLYPHS}}
        base = copy.deepcopy(ARTICLE_V2)
        base.pop("learner")
        with tempfile.TemporaryDirectory() as root:
            entry = json.loads(publish(base, dossier, self.reviews(base, dossier), Path(root) / "entries").read_text())
            runner = LearnerRunner()
            runner.calls = []
            job = Path(root) / "job"
            self.assertEqual(add_learner(entry, job, runner, 1)["status"], "approved")
            article = json.loads((job / "article.json").read_text())
            self.assertEqual({k: v for k, v in article.items() if k != "learner"}, base)
            self.assertEqual(json.loads((job / "dossier.json").read_text()), dossier)
            self.assertEqual(runner.calls, ["learner", "factual", "readability", "readability", "learner", "factual", "readability"])
            reviews = json.loads((job / "reviews.json").read_text())
            self.assertTrue(all(r["article_hash"] == digest(article) for r in reviews))
            self.assertNotEqual(reviews, entry["review"]["reviews"])
            self.assertFalse((job / "entries").exists())
            runner = LearnerRunner()
            job = Path(root) / "rejected"
            self.assertEqual(add_learner(entry, job, runner, 0)["status"], "needs_revision")
            with self.assertRaises(ValueError):
                publish(article, dossier, json.loads((job / "reviews.json").read_text()), Path(root) / "rejected-entries")
            tampered = copy.deepcopy(entry)
            tampered["summary"]["text"] = "Changed without review."
            with self.assertRaises(ValueError):
                add_learner(tampered, Path(root) / "invalid", runner)

    def test_no_correction_needed_verdict_requires_a_real_contract_review(self):
        class ContractRunner:
            model = "fake"
            calls = []
            keep_invalid = False
            def run(self, role, inputs, schema, directory):
                self.calls.append(Path(directory).name)
                if len(self.calls) == 1:
                    return {"verdict": "revise", "findings": ["Check the stated reading."]}
                if len(self.calls) == 2 or self.keep_invalid:
                    return {"verdict": "revise", "findings": ["The stated reading is correct; no correction needed."]}
                return {"verdict": "pass", "findings": []}
        with tempfile.TemporaryDirectory() as root:
            runner = ContractRunner()
            result = independent_review("factual", ARTICLE_V2, DOSSIER, Path(root), runner)
            self.assertEqual(result["verdict"], "pass")
            self.assertEqual(runner.calls, ["factual", "factual-verification", "factual-contract-repair"])
            self.assertIn("factual-contract-repair", result["reviewer"])
        with tempfile.TemporaryDirectory() as root:
            runner = ContractRunner()
            runner.calls = []
            runner.keep_invalid = True
            with self.assertRaisesRegex(ValueError, "must contain required changes"):
                independent_review("factual", ARTICLE_V2, DOSSIER, Path(root), runner)
            self.assertEqual(len(runner.calls), 3)

    def test_no_reading_correction_required_receives_fresh_contract_review(self):
        class ContractRunner:
            model = "fake"
            def __init__(self, finding):
                self.finding, self.calls = finding, []
            def run(self, role, inputs, schema, directory):
                self.calls.append(Path(directory).name)
                if len(self.calls) < 3:
                    return {"verdict": "revise", "findings": [self.finding]}
                return {"verdict": "pass", "findings": []}
        for finding in ("No reading correction is required.", "No clarification is required.",
                        "Retain these scoped cards; no removal is required.",
                        "The current omission is not a required correction.",
                        "No change to this sense or its generated has_sense edge is required."):
            with self.subTest(finding=finding), tempfile.TemporaryDirectory() as root:
                runner = ContractRunner(finding)
                result = independent_review("readability", ARTICLE_V2, DOSSIER, Path(root), runner)
                self.assertEqual(result["verdict"], "pass")
                self.assertEqual(runner.calls, ["readability", "readability-verification", "readability-contract-repair"])
                self.assertIn("contract-repair", result["reviewer"])

    def test_proposed_corrections_require_independent_verification(self):
        class VerifyingRunner:
            model = "fake"
            verified = {"verdict": "pass", "findings": []}
            calls = []
            def run(self, role, inputs, schema, directory):
                self.calls.append(inputs)
                assert inputs["review_scope"] == "added_learner"
                if "proposed_review" not in inputs:
                    return {"verdict": "revise", "findings": ["Alleged mismatch"]}
                assert inputs["proposed_review"]["verdict"] == "revise"
                write(Path(directory) / "meta.json", {"agent_thread_ids": ["actual-verifier-thread"]})
                return copy.deepcopy(self.verified)
        for verdict in ("pass", "revise"):
            with tempfile.TemporaryDirectory() as root:
                runner = VerifyingRunner()
                runner.calls = []
                runner.verified = {"verdict": verdict, "findings": [] if verdict == "pass" else ["Supported concrete correction"]}
                receipt = independent_review("factual", ARTICLE, DOSSIER, root, runner,
                    {"review_scope": "added_learner", "base_approval": {"status": "approved"}})
                self.assertEqual(len(runner.calls), 2)
                self.assertEqual(receipt["verdict"], verdict)
                self.assertIn("actual-verifier-thread", receipt["reviewer"])
                self.assertEqual(receipt["article_hash"], digest(ARTICLE))
                self.assertTrue((Path(root) / "factual/proposed-review.json").exists())
                self.assertTrue((Path(root) / "factual-verification/verified-review.json").exists())
                self.assertEqual(runner.calls[0]["article"], runner.calls[1]["article"])

    def test_verifier_instructions_distinguish_priority_from_date_and_specimen_identity(self):
        class Verifier:
            model = "fake"
            def __init__(self):
                self.calls = []
            def run(self, role, inputs, schema, directory):
                self.calls.append(inputs)
                return ({"verdict": "revise", "findings": ["Check priority and glyph provenance."]}
                        if len(self.calls) == 1 else {"verdict": "pass", "findings": []})

        with tempfile.TemporaryDirectory() as root:
            verifier = Verifier()
            independent_review("factual", ARTICLE_V2, DOSSIER, Path(root), verifier)
            instruction = verifier.calls[1]["verification_task"]
            self.assertIn("positive claim of priority", instruction)
            self.assertIn("unknown precise date alone does not disqualify", instruction)
            self.assertIn("image-to-specimen link is verified", instruction)

    def test_form_annotation_preserves_legacy_prose_and_requires_reviews(self):
        class Annotator:
            model = "fake"
            reject = False
            def run(self, role, inputs, schema, directory):
                assert inputs["review_scope"] == "component_form_relations"
                if role == "form_annotation":
                    return {"components": [{"component_index": 0, "origin_relation": "none", "evidence_ids": ["source:1"]}]}
                if "proposed_review" in inputs:
                    return inputs["proposed_review"]
                return {"verdict": "revise", "findings": ["Unsupported classification"]} if self.reject else {"verdict": "pass", "findings": []}
        with tempfile.TemporaryDirectory() as root:
            entry = json.loads(publish(ARTICLE, DOSSIER, self.reviews(), Path(root) / "entries").read_text())
            self.assertEqual(validate_published(entry), ARTICLE)
            runner = Annotator()
            job = Path(root) / "annotations"
            self.assertEqual(annotate_forms(entry, job, runner, 0)["status"], "approved")
            article = json.loads((job / "article.json").read_text())
            self.assertEqual(article["components"][0].pop("origin_relation"), "none")
            self.assertEqual(article, ARTICLE)
            self.assertEqual(json.loads((job / "dossier.json").read_text()), DOSSIER)
            receipts = json.loads((job / "reviews.json").read_text())
            self.assertEqual({r["role"] for r in receipts}, {"factual", "readability"})
            runner.reject = True
            self.assertEqual(annotate_forms(entry, Path(root) / "rejected", runner, 0)["status"], "needs_revision")
        for relation in ("full_form", "earlier_form", "variant_form", "simplified_form", "uncertain"):
            article = copy.deepcopy(ARTICLE)
            article["components"][0].update(origin_form="水", origin_relation=relation)
            validate_article(article, DOSSIER)
        for origin, relation in (("", "earlier_form"), ("木", "full_form"), ("水", "none")):
            article = copy.deepcopy(ARTICLE)
            article["components"][0].update(origin_form=origin, origin_relation=relation)
            with self.assertRaises(ValueError):
                validate_article(article, DOSSIER)

    def test_verified_revision_plan_routes_edit_and_research_with_fresh_reviews(self):
        class PlanningRunner:
            model = "fake"
            action = "edit"
            calls = []
            def run(self, role, inputs, schema, directory):
                self.calls.append(role)
                if role == "editor":
                    return copy.deepcopy(inputs["article"])
                if role == "revision_plan":
                    assert inputs["verified_reviews"][0]["verdict"] == "revise"
                    return {"action": self.action, "reason": "Fixture routing decision based on evidence."}
                if role == "revision":
                    revised = copy.deepcopy(ARTICLE_V2)
                    revised["summary"]["text"] = "木 depicts a tree."
                    return revised
                if role in ("factual", "readability"):
                    if inputs["article"]["summary"] == ARTICLE_V2["summary"] and role == "factual":
                        return {"verdict": "revise", "findings": ["Clarify the tree account."]}
                    return {"verdict": "pass", "findings": []}
                raise AssertionError(role)
        dossier = {**copy.deepcopy(DOSSIER), "glyph_research": {"historical_glyphs": GLYPHS}}
        for action in ("edit", "research"):
            with tempfile.TemporaryDirectory() as root:
                runner = PlanningRunner()
                runner.action, runner.calls = action, []
                with patch("pipeline.editorial.research_dossier", return_value=copy.deepcopy(dossier)) as research:
                    state = refine(ARTICLE_V2, dossier, root, runner, 1)
                    self.assertEqual(research.call_count, 1 if action == "research" else 0)
                self.assertEqual(state["status"], "approved")
                self.assertEqual(runner.calls, ["editor", "factual", "factual", "readability", "revision_plan", "revision", "factual", "readability"])
                self.assertEqual(json.loads((Path(root) / "round-0/revision_plan/decision.json").read_text())["action"], action)
                article = json.loads((Path(root) / "article.json").read_text())
                receipts = json.loads((Path(root) / "reviews.json").read_text())
                self.assertTrue(all(r["article_hash"] == digest(article) and r["verdict"] == "pass" for r in receipts))

    def test_refine_can_supplement_citable_evidence_before_editing(self):
        dossier = {**copy.deepcopy(DOSSIER), "glyph_research": {"historical_glyphs": copy.deepcopy(GLYPHS)}}
        updated = copy.deepcopy(dossier)
        updated["evidence"].append({**copy.deepcopy(DOSSIER["evidence"][0]), "id": "source:2",
                                    "text": "A newly inspected record supports the tree picture."})
        class EvidenceRunner:
            model = "fake"
            def run(self, role, inputs, schema, directory):
                assert inputs["dossier"] == updated
                if role == "editor":
                    article = copy.deepcopy(inputs["article"])
                    article["summary"]["evidence_ids"] = ["source:2"]
                    return article
                if role in ("factual", "readability"):
                    assert inputs["article"]["summary"]["evidence_ids"] == ["source:2"]
                    return {"verdict": "pass", "findings": []}
                raise AssertionError(role)
        with tempfile.TemporaryDirectory() as root:
            with patch("pipeline.editorial.research_dossier", return_value=updated) as research:
                state = refine(ARTICLE_V2, dossier, root, EvidenceRunner(), 0,
                               {"findings": ["Missing a citable primary record."]}, research_first=True)
                self.assertEqual(research.call_count, 1)
            self.assertEqual(state["status"], "approved")
            self.assertTrue(state["initial_research"])
            self.assertEqual(state["dossier_hash"], digest(updated))
            receipts = json.loads((Path(root) / "reviews.json").read_text())
            self.assertTrue(all(r["dossier_hash"] == digest(updated) for r in receipts))

    def test_repaired_learner_reaches_review_without_another_copy_edit(self):
        dossier = {**copy.deepcopy(DOSSIER), "glyph_research": {"historical_glyphs": copy.deepcopy(GLYPHS)}}
        class RepairRunner:
            model = "fake"
            edits = 0
            reviewed = []
            def run(self, role, inputs, schema, directory):
                if role == "editor":
                    self.edits += 1
                    article = copy.deepcopy(inputs["article"])
                    article["formation"]["type"] = "phonosemantic"
                    return article
                if role == "revision":
                    article = copy.deepcopy(inputs["article"])
                    article["formation"] = copy.deepcopy(ARTICLE_V2["formation"])
                    article["learner"]["overview"]["text"] = "木 pictures a tree."
                    return article
                if role in ("factual", "readability"):
                    self.reviewed.append(copy.deepcopy(inputs["article"]))
                    return {"verdict": "pass", "findings": []}
                raise AssertionError(role)
        with tempfile.TemporaryDirectory() as root:
            runner = RepairRunner()
            runner.reviewed = []
            state = refine(ARTICLE_V2, dossier, root, runner, 1)
            self.assertEqual(state["status"], "approved")
            self.assertEqual(runner.edits, 1)
            self.assertEqual(len(runner.reviewed), 2)
            self.assertTrue(all(a["learner"]["overview"]["text"] == "木 pictures a tree."
                                and a["formation"] == ARTICLE_V2["formation"] for a in runner.reviewed))
            article = json.loads((Path(root) / "article.json").read_text())
            receipts = json.loads((Path(root) / "reviews.json").read_text())
            self.assertTrue(all(r["verdict"] == "pass" and r["article_hash"] == digest(article) for r in receipts))

    def test_workflow_prose_is_repaired_with_metadata_and_citations_frozen_then_reviewed(self):
        dossier = {**copy.deepcopy(DOSSIER), "glyph_research": {"historical_glyphs": copy.deepcopy(GLYPHS)}}
        class ProseRunner:
            model = "fake"
            calls = []
            def run(self, role, inputs, schema, directory):
                self.calls.append(role)
                if role == "editor":
                    article = copy.deepcopy(inputs["article"])
                    article["summary"]["text"] = "This dossier describes a tree."
                    return article
                if role == "prose_repair":
                    self.original = copy.deepcopy(inputs["article"])
                    self_outer.assertEqual([p["field"] for p in inputs["paragraphs"]], ["summary/text"])
                    return {"edits": [{"field": "summary/text", "text": "A tree."}]}
                if role in ("factual", "readability"):
                    expected = copy.deepcopy(self.original)
                    expected["summary"]["text"] = "A tree."
                    self_outer.assertEqual(inputs["article"], expected)
                    return {"verdict": "pass", "findings": []}
                raise AssertionError("Unnecessary whole-entry rewrite: " + role)
        self_outer = self
        with tempfile.TemporaryDirectory() as root:
            runner = ProseRunner()
            state = refine(ARTICLE_V2, dossier, root, runner, 0)
            self.assertEqual(state["status"], "approved")
            self.assertEqual(runner.calls, ["editor", "prose_repair", "factual", "readability"])
            article = json.loads((Path(root) / "article.json").read_text())
            receipts = json.loads((Path(root) / "reviews.json").read_text())
            self.assertTrue(all(r["article_hash"] == digest(article) for r in receipts))

    def test_overlong_learner_is_repaired_without_rewriting_expert_and_reviewed(self):
        dossier = {**copy.deepcopy(DOSSIER), "glyph_research": {"historical_glyphs": copy.deepcopy(GLYPHS)}}
        class LengthRunner:
            model = "fake"
            calls = []
            def run(self, role, inputs, schema, directory):
                self.calls.append(role)
                if role == "editor":
                    article = copy.deepcopy(inputs["article"])
                    article["learner"]["overview"]["text"] = "tree " * 46
                    return article
                if role == "learner":
                    self.expert = copy.deepcopy({k:v for k,v in inputs["article"].items() if k != "learner"})
                    learner = copy.deepcopy(inputs["article"]["learner"])
                    learner["overview"]["text"] = "木 pictures a tree."
                    return learner
                if role in ("factual", "readability"):
                    current = inputs["article"]
                    self_outer.assertEqual({k:v for k,v in current.items() if k != "learner"}, self.expert)
                    self_outer.assertEqual(current["learner"]["overview"]["text"], "木 pictures a tree.")
                    return {"verdict": "pass", "findings": []}
                raise AssertionError("Unnecessary full rewrite: " + role)
        self_outer = self
        with tempfile.TemporaryDirectory() as root:
            runner = LengthRunner()
            state = refine(ARTICLE_V2, dossier, root, runner, 0)
            self.assertEqual(state["status"], "approved")
            self.assertEqual(runner.calls, ["editor", "learner", "factual", "readability"])

    def test_glyph_review_correction_reaches_curator_and_fresh_approval(self):
        corrected = {"items": [], "limitations": [{"text": "No verifiable historical glyph is available.",
                                                   "evidence_ids": ["source:1"]}]}
        dossier = {**copy.deepcopy(DOSSIER), "glyph_research": {"historical_glyphs": copy.deepcopy(GLYPHS)},
                   "glyph_assets": []}
        class GlyphReviewRunner:
            model = "fake"
            curated = False
            def run(self, role, inputs, schema, directory):
                if role in ("editor", "revision"):
                    return copy.deepcopy(inputs["article"])
                if role == "revision_plan":
                    return {"action": "edit", "reason": "The existing evidence supports a clearer glyph limitation."}
                if role == "glyph_visual":
                    self.curated = True
                    return copy.deepcopy(corrected)
                if role in ("factual", "readability"):
                    if inputs["article"]["historical_glyphs"] != corrected and role == "factual":
                        return {"verdict": "revise", "findings": ["historical_glyphs.limitations needs a reader-facing explanation."]}
                    return {"verdict": "pass", "findings": []}
                raise AssertionError(role)
        with tempfile.TemporaryDirectory() as root:
            runner = GlyphReviewRunner()
            state = refine(ARTICLE_V2, dossier, root, runner, 1)
            self.assertEqual(state["status"], "approved")
            self.assertTrue(runner.curated)
            article = json.loads((Path(root) / "article.json").read_text())
            updated = json.loads((Path(root) / "dossier.json").read_text())
            self.assertEqual(article["historical_glyphs"], corrected)
            self.assertEqual(updated["glyph_research"]["historical_glyphs"], corrected)
            receipts = json.loads((Path(root) / "reviews.json").read_text())
            self.assertTrue(all(r["verdict"] == "pass" and r["article_hash"] == digest(article)
                                and r["dossier_hash"] == digest(updated) for r in receipts))

    def test_visual_selection_repairs_preserve_candidates_and_reject_persistent_ids(self):
        candidate = {**{k: "fixture" for k in ("id", "source_title", "period", "tradition", "caption", "alt", "selection_reason", "rights")},
            "id": "actual_oracle", "image_url": "https://example.org/original.svg", "source_url": "https://example.org/source",
            "rights_url": "https://example.org/license", "evidence_ids": ["source:1"]}
        dossier = {**copy.deepcopy(DOSSIER), "glyph_research": {"historical_glyphs": {"items": [candidate], "limitations": []}},
                   "glyph_assets": [{"glyph_id": "actual_oracle", "source_url": candidate["image_url"], "sha256": "unchanged-snapshot"}]}
        class VisualRepairRunner:
            model = "fake"
            persistent = False
            seen = []
            def run(self, role, inputs, schema, directory):
                assert inputs["dossier"] == dossier
                self.seen.append((copy.deepcopy(inputs), Path(directory)))
                item = {k: candidate[k] for k in ("id", "caption", "alt", "selection_reason", "evidence_ids", "period")}
                if len(self.seen) == 1 or self.persistent:
                    item["id"] = "obsolete_candidate"
                else:
                    assert inputs["allowed_ids"] == ["actual_oracle"]
                    assert inputs["previous_invalid_selection"]["items"][0]["id"] == "obsolete_candidate"
                    item["caption"] = "Corrected supported caption."
                    item["period"] = "Modern redraw in oracle-script style."
                return {"items": [item], "limitations": []}
        with tempfile.TemporaryDirectory() as root:
            runner = VisualRepairRunner()
            runner.seen = []
            with patch("pipeline.editorial.validate_glyph_assets", return_value={}):
                result = curate_glyphs(dossier, Path(root) / "glyph_visual", runner)
            self.assertEqual(len(runner.seen), 2)
            self.assertEqual([path.name for _, path in runner.seen], ["glyph_visual", "glyph_visual-repair-1"])
            self.assertEqual(result["glyph_assets"], dossier["glyph_assets"])
            result_item = result["glyph_research"]["historical_glyphs"]["items"][0]
            self.assertEqual({k: v for k, v in result_item.items() if k not in {"caption", "period"}}, {k: v for k, v in candidate.items() if k not in {"caption", "period"}})
            self.assertEqual(result_item["period"], "Modern redraw in oracle-script style.")
            self.assertTrue((Path(root) / "glyph_visual/invalid-selection.json").exists())
            self.assertEqual(dossier["glyph_research"]["historical_glyphs"]["items"][0]["caption"], "fixture")
        with tempfile.TemporaryDirectory() as root:
            runner = VisualRepairRunner()
            runner.seen, runner.persistent = [], True
            with self.assertRaisesRegex(ValueError, "unknown IDs.*obsolete_candidate.*allowed IDs.*actual_oracle"):
                curate_glyphs(dossier, Path(root) / "glyph_visual", runner)
            self.assertEqual(len(runner.seen), 3)
            self.assertTrue((Path(root) / "glyph_visual-repair-2/validation.json").exists())

    def test_unknown_missing_refs_and_character_fail(self):
        for change in [lambda a: a["summary"].update(evidence_ids=["invented"]),
                       lambda a: a["summary"].update(evidence_ids=[]),
                       lambda a: a.update(character="水")]:
            article = copy.deepcopy(ARTICLE)
            change(article)
            with self.assertRaises(Exception):
                validate_article(article, DOSSIER)

    def test_component_citations_and_phonosemantic_roles(self):
        for target in ["formation", "components"]:
            article = copy.deepcopy(ARTICLE)
            paragraph = article[target][0] if target == "components" else article[target]
            paragraph["evidence_ids"] = ["invented"]
            with self.assertRaises(ValueError):
                validate_article(article, DOSSIER)
        article = copy.deepcopy(ARTICLE)
        article["formation"]["type"] = "phonosemantic"
        with self.assertRaisesRegex(ValueError, "semantic or pictorial"):
            validate_article(article, DOSSIER)
        article["components"][0]["roles"] = ["semantic", "phonetic"]
        article["components"][0]["sound"] = [{
            "component_form": "木", "component_reading": "mù", "character_reading": "mù",
            "system": "Mandarin (test fixture)", "text": "Fixture comparison.", "evidence_ids": ["source:1"]}]
        validate_article(article, DOSSIER)
        article["components"][0]["roles"] = ["pictorial", "phonetic"]
        validate_article(article, DOSSIER)
        article["components"][0]["roles"] = ["empty", "phonetic"]
        with self.assertRaisesRegex(ValueError, "semantic or pictorial"):
            validate_article(article, DOSSIER)
        article["formation"]["type"] = "derived"
        article["components"][0]["roles"] = ["empty"]
        validate_article(article, DOSSIER)

    def test_sound_components_require_readings_and_citations(self):
        article = copy.deepcopy(ARTICLE)
        article["formation"]["type"] = "mixed"
        component = article["components"][0]
        component["roles"] = ["phonetic"]
        with self.assertRaisesRegex(ValueError, "pronunciation comparison"):
            validate_article(article, DOSSIER)
        comparison = {"component_form": "木", "component_reading": "mù", "character_reading": "mù",
                      "system": "Mandarin (test fixture)", "text": "Fixture comparison.",
                      "evidence_ids": ["source:1"]}
        component["sound"] = [comparison]
        validate_article(article, DOSSIER)
        for field, value in [("component_reading", " "), ("character_reading", " "),
                             ("system", " "), ("evidence_ids", ["unknown"])]:
            changed = copy.deepcopy(article)
            changed["components"][0]["sound"][0][field] = value
            with self.assertRaises(ValueError):
                validate_article(changed, DOSSIER)

    def test_research_required_audited_and_repeat_merge_stable(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(Exception):
                publish(ARTICLE, {**DOSSIER, "external_research": {}}, self.reviews(), Path(temp) / "entries")
        no_additions = {"evidence": [], "search_audit": RESEARCH["search_audit"],
                        "gaps": ["No reliable component account found."]}
        validate_research(no_additions)
        with self.assertRaises(ValueError):
            validate_research({**no_additions, "gaps": []})
        invalid = copy.deepcopy(RESEARCH)
        invalid["evidence"][0]["url"] = "invented reference"
        with self.assertRaises(ValueError):
            validate_research(invalid)
        once = enrich_dossier(DOSSIER, RESEARCH)
        twice = enrich_dossier(once, RESEARCH)
        self.assertEqual(once, twice)
        self.assertTrue(once["evidence"][-1]["id"].startswith("X-"))
        later = copy.deepcopy(RESEARCH)
        later["evidence"][0]["accessed_at"] = "2026-09-27"
        self.assertEqual(enrich_dossier(once, later), once)

    def test_local_unihan_rows_cannot_be_emitted_as_external_evidence(self):
        item = copy.deepcopy(RESEARCH["evidence"][0])
        item.update(source="Local checkout: sources/unihan/Unihan_Readings.txt",
                    field="kMandarin row", kind="local_dataset_crosscheck",
                    text="Exact local kMandarin row: U+4E29 jiū.",
                    record_character="丩",
                    url="https://www.unicode.org/cgi-bin/GetUnihanData.pl?codepoint=4E29",
                    title="Unihan lookup for 丩")
        with self.assertRaisesRegex(ValueError, "Local Unihan row checks are validation inputs"):
            enrich_dossier(DOSSIER, {**RESEARCH, "evidence": [item]})

    def test_false_negative_unihan_row_audit_is_rejected(self):
        from pipeline import structured
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "Unihan_Readings.txt"
            path.write_text("U+4E29\tkMandarin\tjiū\n", encoding="utf-8")
            research = copy.deepcopy(RESEARCH)
            research["gaps"] = ["The Unihan file has no kMandarin row for U+4E29."]
            with patch("pipeline.editorial.default_unihan_readings_path", return_value=path):
                with self.assertRaisesRegex(ValueError, "exact local row is 'jiū'"):
                    enrich_dossier(DOSSIER, research)

    def test_local_rows_not_presented_as_external_is_not_a_missing_row_claim(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "Unihan_Readings.txt"
            path.write_text("U+8166\tkMandarin\tnǎo\n", encoding="utf-8")
            research = copy.deepcopy(RESEARCH)
            research["gaps"] = [
                "The lookup for U+8166 could not be opened. Local Unihan kMandarin "
                "rows were checked separately; those rows are not presented as "
                "externally verified Unicode records."
            ]
            with patch("pipeline.editorial.default_unihan_readings_path", return_value=path):
                result = enrich_dossier(DOSSIER, research)
            self.assertEqual(result["external_research"]["gaps"], research["gaps"])

    def test_invalid_local_path_source_url_gets_bounded_research_repair(self):
        class ResearchRepairRunner:
            model = "fake"
            research_calls = []
            def run(self, role, inputs, schema, directory):
                if role == "research":
                    self.research_calls.append((copy.deepcopy(inputs), Path(directory)))
                    if len(self.research_calls) == 1:
                        invalid = copy.deepcopy(RESEARCH)
                        invalid["evidence"][0]["url"] = "sources/baxter-sagart/baxtersagart.tsv"
                        return invalid
                    assert inputs["previous_research"]["evidence"][0]["url"].startswith("sources/")
                    assert "real official HTTP(S) page" in inputs["research_task"]
                    assert "HTTP(S) URL" in inputs["research_validation_findings"][0]
                    return copy.deepcopy(RESEARCH)
                if role == "glyph_research":
                    return copy.deepcopy(GLYPH_RESEARCH)
                if role == "glyph_visual":
                    return copy.deepcopy(GLYPHS)
                raise AssertionError(role)

        runner = ResearchRepairRunner()
        with tempfile.TemporaryDirectory() as temp:
            result = research_dossier(DOSSIER, temp, runner)
            self.assertEqual(len(runner.research_calls), 2)
            self.assertEqual(runner.research_calls[0][1].name, "research")
            self.assertEqual(runner.research_calls[1][1].name, "research-repair-1")
            failure = json.loads((Path(temp) / "research/validation.json").read_text())
            self.assertIn("actual HTTP(S) URL", failure["findings"][0])
            self.assertEqual(result["evidence"][-1]["url"], "https://example.org/tree")

    def test_failed_research_stops_before_analysis(self):
        class NoResearchRunner:
            model = "fake"
            def run(self, role, inputs, schema, directory):
                if role == "editor":
                    return copy.deepcopy(inputs["article"])
                if role != "research":
                    raise AssertionError("Writing continued after failed research")
                return {"evidence": [], "search_audit": RESEARCH["search_audit"], "gaps": []}
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(ValueError, "unresolved gaps"):
                run(DOSSIER, temp, NoResearchRunner())
            self.assertEqual(json.loads((Path(temp) / "status.json").read_text())["status"], "failed")
            self.assertFalse((Path(temp) / "article.json").exists())

    def test_publication_does_not_overwrite_changed_source_inputs(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            current = copy.deepcopy(DOSSIER)
            current["context"] = {"updated": True}
            path = root / "dossiers" / "6728.json"
            write(path, current)
            with self.assertRaisesRegex(ValueError, "Current source dossier changed"):
                publish(ARTICLE, DOSSIER, self.reviews(), root / "entries")
            self.assertEqual(json.loads(path.read_text()), current)

    def test_publication_preserves_current_external_evidence(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            path = root / "dossiers" / "6728.json"
            for difference in ["changed", "added"]:
                current = copy.deepcopy(DOSSIER)
                if difference == "changed":
                    current["evidence"][0]["text"] = "A newer external finding."
                else:
                    current["evidence"].append({**current["evidence"][0], "id": "X-new"})
                write(path, current)
                if difference == "changed":
                    with self.assertRaisesRegex(ValueError, "Current source dossier changed"):
                        publish(ARTICLE, DOSSIER, self.reviews(), root / "entries")
                    self.assertEqual(json.loads(path.read_text()), current)
                    self.assertFalse((root / "entries" / "6728.json").exists())
                else:
                    # A new, unused record may be retired by the reviewed incoming dossier.
                    publish(ARTICLE, DOSSIER, self.reviews(), root / "entries")
                    self.assertEqual(json.loads(path.read_text()), DOSSIER)
                    self.assertTrue((root / "entries" / "6728.json").exists())
                    (root / "entries" / "6728.json").unlink()
            write(path, DOSSIER)
            enriched = enrich_dossier(DOSSIER, RESEARCH)
            publish(ARTICLE, enriched, self.reviews(dossier=enriched), root / "entries")
            self.assertEqual(json.loads(path.read_text()), enriched)

    def test_publish_exact_approved_inputs_only(self):
        with tempfile.TemporaryDirectory() as temp:
            path = publish(ARTICLE, DOSSIER, self.reviews(), Path(temp) / "entries")
            self.assertEqual(json.loads(path.read_text())["review"]["status"], "approved")
            for stale in ["article", "dossier", "failed", "missing", "same_reviewer"]:
                article, dossier, reviews = copy.deepcopy(ARTICLE), copy.deepcopy(DOSSIER), self.reviews()
                if stale == "article":
                    article["summary"]["text"] = "Changed"
                elif stale == "dossier":
                    dossier["evidence"][0]["text"] = "Changed"
                elif stale == "failed":
                    reviews[0].update(verdict="revise", findings=["Unsupported"])
                elif stale == "missing":
                    reviews.pop()
                else:
                    reviews[1]["reviewer"] = reviews[0]["reviewer"]
                with self.assertRaises(ValueError, msg=stale):
                    publish(article, dossier, reviews, Path(temp) / "entries")

    def test_published_tampering_and_changed_dossier_fail(self):
        with tempfile.TemporaryDirectory() as temp:
            entry = json.loads(publish(ARTICLE, DOSSIER, self.reviews(), Path(temp) / "entries").read_text())
            self.assertEqual(validate_published(entry, DOSSIER), ARTICLE)
            for section in ["summary", "evidence", "dossier", "review"]:
                changed = copy.deepcopy(entry)
                if section == "summary":
                    changed["summary"]["text"] = "Tampered"
                elif section == "evidence":
                    changed["evidence"][0]["text"] = "Tampered"
                elif section == "dossier":
                    changed["dossier"]["context"]["new"] = "Tampered"
                else:
                    changed["review"]["reviews"][0]["article_hash"] = "Tampered"
                with self.assertRaises(ValueError):
                    validate_published(changed)
            with self.assertRaises(ValueError):
                validate_published(entry, {**DOSSIER, "context": {"new": True}})

    def test_reviews_without_selected_glyphs_receive_empty_image_manifest(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            script = root / "agent.py"
            script.write_text('import sys,json,pathlib\n'
                              'prompt=sys.stdin.read()\n'
                              'inputs=json.JSONDecoder().raw_decode(prompt.split("INPUTS:\\n",1)[1])[0]\n'
                              'assert inputs["attached_images"] == []\n'
                              'pathlib.Path(sys.argv[1]).write_text(json.dumps({"verdict":"pass","findings":[]}))\n')
            runner = Runner([sys.executable, str(script), "{output}"], "fake")
            for role in ("factual", "readability"):
                result = runner.run(role, {"dossier": DOSSIER, "article": ARTICLE}, REVIEW_SCHEMA, root / role)
                self.assertEqual(result["verdict"], "pass")

    def test_cache_includes_inputs_schema_and_model(self):
        with tempfile.TemporaryDirectory() as temp:
            job = Path(temp) / "job"
            counter = Path(temp) / "count"
            script = Path(temp) / "agent.py"
            script.write_text('import sys,json,pathlib\n'
                              'count=pathlib.Path(sys.argv[2])\n'
                              'count.write_text(str(int(count.read_text())+1) if count.exists() else "1")\n'
                              f'pathlib.Path(sys.argv[1]).write_text({json.dumps(json.dumps(ARTICLE))})\n')
            runner = Runner([sys.executable, str(script), "{output}", str(counter)], "model-a")
            runner.run("writer", DOSSIER, ARTICLE_SCHEMA, job)
            runner.run("writer", DOSSIER, ARTICLE_SCHEMA, job)
            self.assertEqual(counter.read_text(), "1")
            runner.run("writer", {**DOSSIER, "new": True}, ARTICLE_SCHEMA, job)
            runner.model = "model-b"
            runner.run("writer", {**DOSSIER, "new": True}, ARTICLE_SCHEMA, job)
            runner.run("writer", {**DOSSIER, "new": True}, {**ARTICLE_SCHEMA, "title": "changed"}, job)
            self.assertEqual(counter.read_text(), "4")
            self.assertEqual(len(list((job / "attempts").iterdir())), 3)
            tampered = copy.deepcopy(ARTICLE)
            tampered["summary"]["text"] = "Changed on disk"
            write(job / "result.json", tampered)
            result = runner.run("writer", {**DOSSIER, "new": True}, {**ARTICLE_SCHEMA, "title": "changed"}, job)
            self.assertEqual(result, ARTICLE)
            self.assertEqual(counter.read_text(), "5")

    def test_failed_output_not_reused_and_timeout_recorded(self):
        with tempfile.TemporaryDirectory() as temp:
            job = Path(temp)
            runner = Runner([sys.executable, "-c", "import time; time.sleep(10)"], "fake", timeout=.05)
            with self.assertRaises(Exception):
                runner.run("writer", DOSSIER, ARTICLE_SCHEMA, job)
            self.assertEqual(json.loads((job / "meta.json").read_text())["status"], "failed")

    def test_successful_revision_is_reviewed_and_published(self):
        revised = copy.deepcopy(ARTICLE_V2)
        revised["summary"]["text"] = "木 depicts a tree."
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            script = root / "agent.py"
            script.write_text(
                "import sys,json,pathlib\n"
                "role,output=sys.argv[1:]\n"
                "inputs=json.JSONDecoder().raw_decode(sys.stdin.read().split('\\nINPUTS:\\n',1)[1])[0]\n"
                f"original=json.loads({json.dumps(json.dumps(ARTICLE_V2))})\n"
                f"revised=json.loads({json.dumps(json.dumps(revised))})\n"
                f"research=json.loads({json.dumps(json.dumps(RESEARCH))})\n"
                f"glyphs=json.loads({json.dumps(json.dumps(GLYPH_RESEARCH))})\n"
                "if role == 'research':\n"
                "    result=research\n"
                "elif role == 'glyph_research':\n"
                "    result=glyphs\n"
                "elif role == 'glyph_visual':\n"
                "    result=inputs['dossier']['glyph_research']['historical_glyphs']\n"
                "elif role == 'revision_plan':\n"
                "    result={'action':'edit','reason':'Existing evidence supports the wording correction.'}\n"
                "elif role == 'analysis':\n"
                "    result={'supported_claims': [], 'disagreements': [], 'limitations': []}\n"
                "elif role == 'editor':\n"
                "    result={k:v for k,v in inputs['article'].items() if k != 'historical_glyphs'}\n"
                "    result['relationships']=[r for r in result['relationships'] if r['predicate'] not in ('has_sense','sense_developed_into','phonetic_loan_for')]\n"
                "elif role == 'writer':\n"
                "    result={k:v for k,v in original.items() if k != 'historical_glyphs'}\n"
                "    result['relationships']=[r for r in result['relationships'] if r['predicate'] != 'has_sense']\n"
                "elif role == 'revision':\n"
                "    assert inputs['reviews'][0]['verdict'] == 'revise'\n"
                "    result={k:v for k,v in revised.items() if k != 'historical_glyphs'}\n"
                "    result['relationships']=[r for r in result['relationships'] if r['predicate'] != 'has_sense']\n"
                "elif role == 'factual' and inputs['article']['summary'] == original['summary']:\n"
                "    result={'verdict': 'revise', 'findings': ['Explain the graphic relationship.']}\n"
                "else:\n"
                "    result={'verdict': 'pass', 'findings': []}\n"
                "pathlib.Path(output).write_text(json.dumps(result))\n"
            )
            runner = Runner([sys.executable, str(script), "{role}", "{output}"], "fake")
            job = root / "job"
            state = run(DOSSIER, job, runner, max_revisions=1)
            self.assertEqual(state["status"], "approved")
            self.assertEqual(state["revision"], 1)
            article = json.loads((job / "article.json").read_text())
            reviews = json.loads((job / "reviews.json").read_text())
            self.assertEqual(sorted(article["relationships"], key=lambda r:r["id"]), sorted(revised["relationships"], key=lambda r:r["id"]))
            revised = article
            for role in ["factual", "readability"]:
                prompt = (job / "round-1" / role / "prompt.txt").read_text()
                self.assertEqual(json.JSONDecoder().raw_decode(prompt.split("\nINPUTS:\n", 1)[1])[0]["article"], revised)
            self.assertTrue(all(r["article_hash"] == digest(revised) for r in reviews))
            enriched = json.loads((job / "dossier.json").read_text())
            entry = json.loads(publish(article, enriched, reviews, root / "entries").read_text())
            self.assertEqual(validate_published(entry, enriched), revised)
            self.assertEqual(json.loads((root / "dossiers" / "6728.json").read_text()), enriched)
            with self.assertRaises(ValueError):
                publish(ARTICLE, enriched, reviews, root / "entries")

    def test_site_loader_rejects_stale_dossier_and_malformed_approval(self):
        from build_site import load_articles
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            entries = root / "entries"
            entry_path = publish(ARTICLE, DOSSIER, self.reviews(), entries)
            dossier_path = root / "dossiers" / entry_path.name
            write(dossier_path, DOSSIER)
            self.assertEqual(load_articles(entries)["木"]["summary"], ARTICLE["summary"])
            write(dossier_path, {**DOSSIER, "context": {"changed": True}})
            with self.assertRaisesRegex(ValueError, "current dossier"):
                load_articles(entries)
            write(dossier_path, DOSSIER)
            malformed = json.loads(entry_path.read_text())
            del malformed["review"]["reviews"]
            write(entry_path, malformed)
            with self.assertRaises(KeyError):
                load_articles(entries)

    def test_revision_is_bounded_and_never_approved_implicitly(self):
        class FakeRunner:
            model = "fake"
            def run(self, role, inputs, schema, directory):
                if role == "editor":
                    return copy.deepcopy(inputs["article"])
                if role == "research":
                    return copy.deepcopy(RESEARCH)
                if role == "glyph_research":
                    return copy.deepcopy(GLYPH_RESEARCH)
                if role == "glyph_visual":
                    return copy.deepcopy(inputs["dossier"]["glyph_research"]["historical_glyphs"])
                if role == "revision_plan":
                    return {"action": "research", "reason": "Fixture requires additional research."}
                if role == "analysis":
                    return {"supported_claims": [], "disagreements": [], "limitations": []}
                if role in ("writer", "revision"):
                    return copy.deepcopy(ARTICLE_V2)
                return {"verdict": "revise", "findings": ["Unsupported claim"]}
        with tempfile.TemporaryDirectory() as temp:
            state = run(DOSSIER, temp, FakeRunner(), max_revisions=1)
            self.assertEqual(state["status"], "needs_revision")
            self.assertEqual(state["revision"], 1)
            with self.assertRaises(ValueError):
                publish(ARTICLE, DOSSIER, json.loads((Path(temp) / "reviews.json").read_text()), Path(temp) / "entries")


if __name__ == "__main__":
    unittest.main()
