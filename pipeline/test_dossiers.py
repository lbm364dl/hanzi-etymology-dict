"""Protect the evidence boundary between source claims and inferred metadata."""
import json
from pathlib import Path
import tempfile
import unittest

from pipeline.dossiers import prepare


class DossierTests(unittest.TestCase):
    def test_traditional_sources_are_loaded_with_original_attribution(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "output").mkdir()
            records = [
                {"character": "愛", "etymology_notes": [{"source": "local", "text": "Traditional account."}]},
                {"character": "爱", "variants": {"traditional": "U+7231 U+611B U+611B"},
                 "etymology_notes": [{"source": "other", "text": "Inherited account.", "via_traditional": "愛"}]},
                {"character": "帮", "variants": {"traditional": "幫"}},
                {"character": "幫", "etymology_notes": [{"source": "local", "text": "Later record."}]},
            ]
            (root / "output/hanzi_etymology.jsonl").write_text("\n".join(map(json.dumps, records)))
            paths = prepare("爱帮", root)
            love, help_packet = [json.loads(p.read_text()) for p in paths]
            self.assertEqual([(e["text"], e["record_character"]) for e in love["evidence"]],
                             [("Inherited account.", "愛"), ("Traditional account.", "愛")])
            self.assertEqual(help_packet["evidence"][0]["record_character"], "幫")

    def test_related_form_and_inference_provenance(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "output").mkdir()
            records = [
                {"character": "国", "formation_details": {"phonetic": "玉", "inferred": True},
                 "etymology_notes": [{"source": "example", "text": "Simplified from 國."}]},
                {"character": "國", "etymology_notes": [{"source": "example", "text": "或 supplies sound."}],
                 "shuowen": {"explanation": "邦也。", "english": "Unreliable generated gloss"}},
            ]
            source = root / "output/hanzi_etymology.jsonl"
            source.write_text("\n".join(json.dumps(r) for r in records))
            path, = prepare("国", root)
            packet = json.loads(path.read_text())
            self.assertEqual(packet["character"], "国")
            traditional = [e for e in packet["evidence"] if e["record_character"] == "國"]
            self.assertEqual(len(traditional), 2)
            text = json.dumps(packet["evidence"])
            self.assertNotIn("inferred", text)
            self.assertNotIn("Unreliable generated gloss", text)
            self.assertTrue(packet["context"]["unverified_pipeline_metadata"]["formation_details"]["inferred"])
            original = path.read_bytes()
            prepare("国", root)
            self.assertEqual(original, path.read_bytes())

    def test_rebuild_preserves_external_research(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "output").mkdir()
            source = root / "output/hanzi_etymology.jsonl"
            source.write_text(json.dumps({"character": "木", "etymology_notes": [
                {"source": "local", "text": "A tree."}]}))
            path, = prepare("木", root)
            packet = json.loads(path.read_text())
            external = {"id": "X-external", "url": "https://example.org/tree", "text": "External finding."}
            packet["evidence"].append(external)
            packet["external_research"] = {"search_audit": [{"query": "tree origin"}], "gaps": []}
            path.write_text(json.dumps(packet))
            prepare("木", root)
            rebuilt = json.loads(path.read_text())
            self.assertEqual(rebuilt["evidence"][-1], external)
            self.assertEqual(rebuilt["external_research"], packet["external_research"])
            self.assertNotIn("No primary scholarship", rebuilt["context"]["provenance"])

    def test_missing_character_is_explicit(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "output").mkdir()
            (root / "output/hanzi_etymology.jsonl").write_text("")
            with self.assertRaisesRegex(ValueError, "No local record"):
                prepare("木", root)


if __name__ == "__main__":
    unittest.main()
