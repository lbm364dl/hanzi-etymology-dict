"""Tests for the character-scoped Xiaoxuetang query adapter."""
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.parse import parse_qs

from pipeline import xiaoxuetang


HTML = '''
<table>
<tr><td class="VariantListA"><img class="charValue" src="/ImageText2/ShowImage.ashx?text=%E9%9B%BB&amp;font=bronze&amp;size=72" alt="&0.96FB;" /><br />番生簋蓋(金)<br />西周晚期</td></tr>
<tr><td class="VariantListB"><img class="charValue" src="/ImageText2/ShowImage.ashx?text=%EE%B5%AF&amp;font=bronze&amp;size=72" alt="&103.E5EF;" /><br />帛乙3.5<br />戰國.楚</td></tr>
</table>
'''


class XiaoxuetangTests(unittest.TestCase):
    def test_form_parser_preserves_direct_image_and_exact_labels(self):
        with patch("pipeline.xiaoxuetang._rate_limited_post", return_value=HTML.encode()):
            result = xiaoxuetang.fetch_character("電")
        self.assertEqual(result["status"], "found")
        self.assertEqual(result["candidate_count"], 2)
        first = result["candidates"][0]
        self.assertEqual(first["query_character"], "電")
        self.assertEqual(first["source_labels"], ["番生簋蓋(金)", "西周晚期"])
        self.assertEqual(first["rendered_form"], "電")
        self.assertEqual(first["source_url"], xiaoxuetang.BASE_URL)
        self.assertEqual(first["rights_url"], xiaoxuetang.RIGHTS_URL)
        self.assertEqual(first["image_url"],
            "https://xiaoxue.iis.sinica.edu.tw/ImageText2/ShowImage.ashx?text=%E9%9B%BB&font=bronze&size=72")

    def test_post_uses_official_single_character_form(self):
        class Response(io.BytesIO):
            def geturl(self):
                return xiaoxuetang.RESULT_URL
            def __enter__(self):
                return self
            def __exit__(self, *_):
                self.close()
        captured = {}
        def fake_open(request, timeout):
            captured["request"] = request
            captured["timeout"] = timeout
            return Response(HTML.encode())
        with tempfile.TemporaryDirectory() as temp:
            with patch.object(xiaoxuetang, "_LOCK_PATH", Path(temp) / "query.lock"), \
                 patch.object(xiaoxuetang, "_BLOCK_PATH", Path(temp) / "unauthorized"), \
                 patch.object(xiaoxuetang, "urlopen", side_effect=fake_open):
                body = xiaoxuetang._rate_limited_post(b"EudcFontChar=%E9%9B%BB", timeout=12)
        request = captured["request"]
        self.assertEqual(request.full_url, xiaoxuetang.RESULT_URL)
        self.assertEqual(request.get_method(), "POST")
        self.assertEqual(parse_qs(request.data.decode())["EudcFontChar"], ["電"])
        self.assertEqual(captured["timeout"], 12)
        self.assertIn(b"VariantListA", body)

    def test_query_targets_prefer_one_recorded_traditional_form(self):
        dossier = {"character": "电", "context": {"unverified_pipeline_metadata": {
            "variants": {"traditional": "U+7535 U+96FB"}}}}
        self.assertEqual(xiaoxuetang.query_targets(dossier), ["電"])
        self.assertEqual(xiaoxuetang.query_targets({"character": "木", "context": {}}), ["木"])

    def test_per_character_outputs_are_cached_for_resumable_runs(self):
        dossier = {"character": "电", "context": {"unverified_pipeline_metadata": {
            "variants": {"traditional": "U+7535 U+96FB"}}}}
        def fake_fetch(character, timeout=30):
            return {"character": character, "status": "no_results", "candidates": [],
                    "accessed_at": "2026-09-26"}
        with tempfile.TemporaryDirectory() as temp:
            with patch("pipeline.xiaoxuetang.fetch_character", side_effect=fake_fetch) as fetch:
                first = xiaoxuetang.query_dossier(dossier, temp)
                second = xiaoxuetang.query_dossier(dossier, temp)
            self.assertEqual(fetch.call_count, 1)
            self.assertEqual([x["character"] for x in first["queries"]], ["電"])
            self.assertEqual(first, second)
            self.assertTrue((Path(temp) / "xiaoxuetang-query" / "96FB.json").exists())

    def test_network_failure_is_a_recorded_gap_not_a_failed_entry(self):
        with patch("pipeline.xiaoxuetang._rate_limited_post", side_effect=OSError("offline")):
            result = xiaoxuetang.fetch_character("木")
        self.assertEqual(result["status"], "unavailable")
        self.assertIn("offline", result["error"])
        self.assertEqual(result["candidates"], [])

    def test_unauthorized_response_pauses_later_automatic_queries(self):
        with tempfile.TemporaryDirectory() as temp:
            lock = Path(temp) / "query.lock"
            blocked = Path(temp) / "unauthorized"
            denied = HTTPError(xiaoxuetang.RESULT_URL, 401, "Unauthorized", {}, None)
            with patch.object(xiaoxuetang, "_LOCK_PATH", lock), \
                 patch.object(xiaoxuetang, "_BLOCK_PATH", blocked), \
                 patch.object(xiaoxuetang, "_REQUEST_INTERVAL_SECONDS", 0), \
                 patch.object(xiaoxuetang, "urlopen", side_effect=denied) as request:
                with self.assertRaises(HTTPError):
                    xiaoxuetang._rate_limited_post(b"EudcFontChar=%E9%9B%BB", timeout=1)
                self.assertTrue(blocked.exists())
                with self.assertRaisesRegex(PermissionError, "paused for one hour"):
                    xiaoxuetang._rate_limited_post(b"EudcFontChar=%E9%9B%BB", timeout=1)
                self.assertEqual(request.call_count, 1)

    def test_rejects_multi_character_queries(self):
        with self.assertRaisesRegex(ValueError, "exactly one character"):
            xiaoxuetang.fetch_character("電気")


if __name__ == "__main__":
    unittest.main()
