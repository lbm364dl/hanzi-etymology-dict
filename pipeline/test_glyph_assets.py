import copy
import io
import json
from pathlib import Path
import tempfile
import unittest
from urllib.error import HTTPError
from unittest.mock import patch

from pipeline.glyph_assets import image_mime, snapshot_glyph_assets, validate_glyph_assets, render_glyph_images

SVG = b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"><path d="M0 0L10 10"/></svg>'
DOSSIER = {"glyph_research": {"historical_glyphs": {"items": [{"id": "tree", "image_url": "https://example.org/tree.svg"}]}}}

class Response(io.BytesIO):
    def __init__(self, data, url="https://example.org/tree.svg"):
        super().__init__(data)
        self.url = url

    def geturl(self):
        return self.url

class GlyphAssetTests(unittest.TestCase):
    def test_snapshot_reuse_and_tamper_detection(self):
        with tempfile.TemporaryDirectory() as root:
            with patch("urllib.request.urlopen", return_value=Response(SVG)) as download:
                assets = snapshot_glyph_assets(DOSSIER, root=root)
                download.assert_called_once()
            with patch("urllib.request.urlopen", side_effect=AssertionError("Network not allowed")):
                self.assertEqual(snapshot_glyph_assets(DOSSIER, assets, root), assets)
                paths = validate_glyph_assets({**DOSSIER, "glyph_assets": assets}, root)
            paths["tree"].write_bytes(SVG + b" ")
            with self.assertRaisesRegex(ValueError, "mismatch"):
                validate_glyph_assets({**DOSSIER, "glyph_assets": assets}, root)

    def test_svg_preview_uses_verified_original_and_recovers_corrupt_cache(self):
        with tempfile.TemporaryDirectory() as root:
            with patch("urllib.request.urlopen", return_value=Response(SVG)):
                assets = snapshot_glyph_assets(DOSSIER, root=root)
            dossier = {**DOSSIER, "glyph_assets": assets}
            previews = render_glyph_images(dossier, root)
            preview = previews["tree"]
            self.assertEqual(image_mime(preview.read_bytes()), "image/png")
            original_preview = preview.read_bytes()
            with patch("cairosvg.svg2png", side_effect=AssertionError("Unexpected rerender")):
                self.assertEqual(render_glyph_images(dossier, root), previews)
            preview.write_bytes(b"corrupt")
            render_glyph_images(dossier, root)
            self.assertEqual(preview.read_bytes(), original_preview)
            (Path(root) / assets[0]["path"]).write_bytes(b"changed")
            with self.assertRaises(ValueError):
                render_glyph_images(dossier, root)

    def test_reject_html_svg_entities_and_active_content(self):
        for data in [b"<html>Blocked</html>", b"<!DOCTYPE svg><svg/>",
                     b'<svg><script>alert(1)</script></svg>',
                     b'<svg><image href="https://example.org/other"/></svg>']:
            with self.assertRaises(ValueError):
                image_mime(data)
        self.assertEqual(image_mime(SVG), "image/svg+xml")

    def test_standard_svg_doctype_is_metadata_only_and_renders(self):
        declaration = b'<!DOCTYPE svg PUBLIC "-//W3C//DTD SVG 20010904//EN" "http://www.w3.org/TR/2001/REC-SVG-20010904/DTD/svg10.dtd">'
        original = b'<?xml version="1.0" standalone="no"?>' + declaration + SVG
        self.assertEqual(image_mime(original), "image/svg+xml")
        with tempfile.TemporaryDirectory() as root:
            with patch("urllib.request.urlopen", return_value=Response(original)):
                assets = snapshot_glyph_assets(DOSSIER, root=root)
            with patch("urllib.request.urlopen", side_effect=AssertionError("DTD must not be fetched")):
                dossier = {**DOSSIER, "glyph_assets": assets}
                originals = validate_glyph_assets(dossier, root)
                self.assertEqual(originals["tree"].read_bytes(), original)
                self.assertEqual(image_mime(render_glyph_images(dossier, root)["tree"].read_bytes()), "image/png")

    def test_svg_doctype_never_allows_entities_or_custom_external_dtd(self):
        invalid = [
            '<!DOCTYPE svg SYSTEM "https://example.org/evil.dtd"><svg/>',
            '<!DOCTYPE svg [<!ENTITY secret SYSTEM "file:///etc/passwd">]><svg>&secret;</svg>',
            '<!DOCTYPE svg [<!ENTITY % remote SYSTEM "https://example.org/evil.dtd">%remote;]><svg/>',
            '<!DOCTYPE svg PUBLIC "-//W3C//DTD SVG 20010904//EN" "http://www.w3.org/TR/2001/REC-SVG-20010904/DTD/svg10.dtd" [<!ENTITY x "expanded">]><svg>&x;</svg>',
            '<!DOCTYPE svg PUBLIC "-//W3C//DTD SVG 1.1//EN" "http://www.w3.org/Graphics/SVG/1.1/DTD/svg11.dtd"><svg>&undeclared;</svg>',
        ]
        for xml in invalid:
            for encoding in ("utf-8", "utf-16"):
                with self.assertRaises(ValueError):
                    image_mime(xml.encode(encoding))

    def test_manifest_is_bound_to_selection(self):
        with tempfile.TemporaryDirectory() as root:
            with patch("urllib.request.urlopen", return_value=Response(SVG)):
                assets = snapshot_glyph_assets(DOSSIER, root=root)
            for field, value in [("glyph_id", "other"), ("source_url", "https://other.org/image"),
                                 ("path", "../../outside.svg"), ("mime_type", "image/png")]:
                changed = copy.deepcopy(assets)
                changed[0][field] = value
                with self.assertRaises(ValueError):
                    validate_glyph_assets({**DOSSIER, "glyph_assets": changed}, root)

    def test_bounded_download_and_missing_asset(self):
        with tempfile.TemporaryDirectory() as root:
            with patch("pipeline.glyph_assets.MAX_BYTES", 20), patch("urllib.request.urlopen", return_value=Response(SVG)):
                with self.assertRaisesRegex(ValueError, "limit"):
                    snapshot_glyph_assets(DOSSIER, root=root)
            with self.assertRaisesRegex(ValueError, "requires a local snapshot"):
                validate_glyph_assets(DOSSIER, root)

    def test_invalid_commons_thumbnail_resolves_original_from_exact_file_page(self):
        thumbnail = "https://upload.wikimedia.org/wikipedia/commons/thumb/a/ab/%E6%9C%8D-oracle.svg/300px-%E6%9C%8D-oracle.svg.png"
        original = "https://upload.wikimedia.org/wikipedia/commons/a/ab/%E6%9C%8D-oracle.svg"
        commons_page = "https://commons.wikimedia.org/wiki/File:%E6%9C%8D-oracle.svg"
        dossier = {"glyph_research": {"historical_glyphs": {"items": [
            {"id": "fu-oracle", "image_url": thumbnail, "source_url": commons_page}]}}}
        api_result = {"query": {"pages": [{"title": "File:服-oracle.svg",
            "imageinfo": [{"url": original}]}]}}
        calls = []

        def urlopen(request, timeout=30):
            address = request.full_url
            calls.append(address)
            if address == thumbnail:
                raise HTTPError(address, 400, "Unavailable thumbnail size", {}, io.BytesIO(b"bad size"))
            if address.startswith("https://commons.wikimedia.org/w/api.php?"):
                return Response(json.dumps(api_result).encode(), address)
            if address == original:
                return Response(SVG, address)
            raise AssertionError(f"Unexpected URL: {address}")

        with tempfile.TemporaryDirectory() as root, patch("urllib.request.urlopen", side_effect=urlopen):
            assets = snapshot_glyph_assets(dossier, root=root)
            self.assertEqual(validate_glyph_assets({**dossier, "glyph_assets": assets}, root)["fu-oracle"].read_bytes(), SVG)
        self.assertEqual(len(calls), 3)
        self.assertIn(thumbnail, calls)
        self.assertIn(original, calls)
        self.assertEqual(assets[0]["source_url"], thumbnail)

if __name__ == "__main__":
    unittest.main()
