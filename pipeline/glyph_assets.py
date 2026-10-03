"""Download bounded historical-glyph snapshots and verify their reviewed bytes."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from urllib.error import HTTPError
import urllib.request
from urllib.parse import parse_qs, quote, unquote, urlencode, urlparse
import xml.etree.ElementTree as ET
from xml.parsers import expat

from pipeline.atomic_files import atomic_write_bytes, atomic_write_json, file_lock

ROOT = Path(__file__).resolve().parent.parent
MAX_BYTES = 8 * 1024 * 1024
MIME_EXTENSIONS = {"image/png": "png", "image/jpeg": "jpg", "image/gif": "gif",
                   "image/webp": "webp", "image/svg+xml": "svg"}


# Historical converters often emit a standard SVG declaration. These identifiers are
# recognized as metadata only: the parser must never fetch the referenced DTD.
SVG_DOCTYPES = {
    ("-//W3C//DTD SVG 20010904//EN", "http://www.w3.org/TR/2001/REC-SVG-20010904/DTD/svg10.dtd"),
    ("-//W3C//DTD SVG 1.0//EN", "http://www.w3.org/TR/2001/REC-SVG-20010904/DTD/svg10.dtd"),
    ("-//W3C//DTD SVG 1.1//EN", "http://www.w3.org/Graphics/SVG/1.1/DTD/svg11.dtd"),
}


def _check_svg_declarations(data):
    parser = expat.ParserCreate()
    def doctype(name, system, public, internal_subset):
        if name != "svg" or internal_subset or (public, system) not in SVG_DOCTYPES:
            raise ValueError("Glyph SVG has an unsupported document type or internal subset")
    def entity(*_args):
        raise ValueError("Glyph SVG cannot declare or resolve entities")
    parser.StartDoctypeDeclHandler = doctype
    parser.EntityDeclHandler = entity
    parser.ExternalEntityRefHandler = entity
    parser.SetParamEntityParsing(expat.XML_PARAM_ENTITY_PARSING_NEVER)
    try:
        parser.Parse(data, True)
    except expat.ExpatError as exc:
        raise ValueError("Glyph download is not supported standalone SVG XML") from exc


def image_mime(data):
    """Inspect bytes, never trust a web server's Content-Type or URL extension."""
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    if data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return "image/webp"
    # Refuse entity expansion and active/external SVG content. Preserve accepted bytes exactly.
    _check_svg_declarations(data)
    try:
        root = ET.fromstring(data)
    except ET.ParseError as exc:
        raise ValueError("Glyph download is not a supported image") from exc
    if root.tag not in ("svg", "{http://www.w3.org/2000/svg}svg"):
        raise ValueError("Glyph XML root is not SVG")
    for element in root.iter():
        if element.tag.rsplit("}", 1)[-1].lower() in ("script", "foreignobject"):
            raise ValueError("Glyph SVG contains active content")
        for key, value in element.attrib.items():
            local = key.rsplit("}", 1)[-1].lower()
            if local.startswith("on") or (local in ("href", "src") and not value.startswith("#")):
                raise ValueError("Glyph SVG contains active or external references")
            if "url(" in value.lower() and "url(#" not in value.lower():
                raise ValueError("Glyph SVG contains external CSS references")
        if element.tag.rsplit("}", 1)[-1].lower() == "style" and element.text:
            css = element.text.lower()
            if "@import" in css or ("url(" in css and "url(#" not in css):
                raise ValueError("Glyph SVG contains external CSS references")
    return "image/svg+xml"


def _url(value):
    address = urlparse(value)
    if address.scheme not in ("http", "https") or not address.netloc:
        raise ValueError("Glyph download requires an HTTP(S) URL")


def _commons_file_title(source_url):
    """Return the exact Commons File: title represented by a file page URL."""
    address = urlparse(source_url)
    if address.scheme not in ("http", "https") or address.hostname not in ("commons.wikimedia.org", "www.commons.wikimedia.org"):
        return None
    if address.path == "/w/index.php":
        title = parse_qs(address.query).get("title", [""])[0]
    elif address.path.startswith("/wiki/"):
        title = unquote(address.path.removeprefix("/wiki/"))
    else:
        return None
    return title if title.startswith("File:") else None


def _commons_original_url(source_url, timeout):
    """Resolve a failed Commons thumbnail through its cited file page and API."""
    title = _commons_file_title(source_url)
    if not title:
        raise ValueError("Wikimedia thumbnail fallback requires its exact Commons File: page")
    api = "https://commons.wikimedia.org/w/api.php?" + urlencode({
        "action": "query", "prop": "imageinfo", "iiprop": "url", "titles": title,
        "format": "json", "formatversion": "2"})
    request = urllib.request.Request(api, headers={"User-Agent": "HanziEtymologyDict/1.0 (research project)"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = json.loads(response.read(MAX_BYTES + 1))
    pages = payload.get("query", {}).get("pages", [])
    normalized_title = title.replace("_", " ").casefold()
    for page in pages:
        if page.get("title", "").replace("_", " ").casefold() != normalized_title:
            continue
        info = page.get("imageinfo", [])
        if info and isinstance(info[0].get("url"), str):
            original = info[0]["url"]
            _url(original)
            if urlparse(original).hostname != "upload.wikimedia.org":
                raise ValueError("Commons API returned an image outside upload.wikimedia.org")
            return original
    raise ValueError("Commons file page did not resolve to an original image")


def _download(url, timeout):
    request = urllib.request.Request(quote(url, safe=":/%?&=+#@,;!$'()*[]"), headers={
        "User-Agent": "HanziEtymologyDict/1.0 (https://github.com/user/hanzi-etymology-dict; research project) Python/requests"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        _url(response.geturl())
        return response.read(MAX_BYTES + 1)


def _verify_asset(asset, root):
    expected_keys = {"glyph_id", "source_url", "sha256", "mime_type", "path", "byte_length"}
    if set(asset) != expected_keys:
        raise ValueError("Invalid glyph asset manifest fields")
    _url(asset["source_url"])
    sha = asset["sha256"]
    if len(sha) != 64 or any(c not in "0123456789abcdef" for c in sha):
        raise ValueError("Invalid glyph asset hash")
    extension = MIME_EXTENSIONS.get(asset["mime_type"])
    expected = f"content/glyph-assets/{sha}.{extension}"
    if not extension or asset["path"] != expected:
        raise ValueError("Invalid glyph asset path or MIME type")
    path = root / expected
    if path.resolve().parent != (root / "content/glyph-assets").resolve() or path.is_symlink():
        raise ValueError("Glyph asset must be a local snapshot")
    if not path.is_file() or path.stat().st_size > MAX_BYTES:
        raise ValueError("Glyph asset missing or oversized")
    data = path.read_bytes()
    if len(data) != asset["byte_length"] or hashlib.sha256(data).hexdigest() != sha:
        raise ValueError("Glyph asset hash or length mismatch")
    if image_mime(data) != asset["mime_type"]:
        raise ValueError("Glyph asset MIME mismatch")
    return path


def validate_glyph_assets(dossier, root=ROOT):
    """Return glyph-id → verified local Path. No network requests are performed."""
    root = Path(root)
    glyphs = dossier.get("glyph_research", {}).get("historical_glyphs", {}).get("items", [])
    assets = dossier.get("glyph_assets", [])
    if not isinstance(assets, list) or len(assets) != len(glyphs):
        raise ValueError("Every selected glyph requires a local snapshot")
    expected = {g["id"]: g["image_url"] for g in glyphs}
    if len(expected) != len(glyphs):
        raise ValueError("Duplicate selected glyph IDs")
    paths = {}
    for asset in assets:
        glyph_id = asset.get("glyph_id")
        if glyph_id in paths or glyph_id not in expected or asset.get("source_url") != expected[glyph_id]:
            raise ValueError("Glyph asset differs from selected image")
        paths[glyph_id] = _verify_asset(asset, root)
    return paths


def snapshot_glyph_assets(dossier, previous_manifest=None, root=ROOT, timeout=30):
    """Return manifest, reusing verified snapshots; fail rather than silently omit images."""
    root = Path(root)
    selected = dossier["glyph_research"]["historical_glyphs"]["items"]
    previous = {(a.get("glyph_id"), a.get("source_url")): a for a in (previous_manifest or [])}
    result = []
    for glyph in selected:
        url = glyph["image_url"]
        _url(url)
        cached = previous.get((glyph["id"], url))
        if cached:
            try:
                _verify_asset(cached, root)
                result.append(cached)
                continue
            except (ValueError, OSError):
                pass
        try:
            data = _download(url, timeout)
        except HTTPError as exc:
            # Commons only accepts a published set of thumbnail sizes. If an agent
            # picked an unavailable size, retrieve the original from that exact
            # file page instead of guessing another thumb URL or failing the entry.
            parsed_image = urlparse(url)
            if (exc.code not in (400, 404) or parsed_image.hostname != "upload.wikimedia.org"
                    or "/thumb/" not in parsed_image.path):
                raise
            data = _download(_commons_original_url(glyph["source_url"], timeout), timeout)
        if not data or len(data) > MAX_BYTES:
            raise ValueError("Glyph image empty or exceeds 8 MiB limit")
        mime = image_mime(data)
        sha = hashlib.sha256(data).hexdigest()
        relative = f"content/glyph-assets/{sha}.{MIME_EXTENSIONS[mime]}"
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_bytes(path, data)
        result.append({"glyph_id": glyph["id"], "source_url": url, "sha256": sha,
                       "mime_type": mime, "path": relative, "byte_length": len(data)})
    validate_glyph_assets({**dossier, "glyph_assets": result}, root)
    return result


def render_glyph_images(dossier, root=ROOT):
    """Provide inspectable raster images; SVG previews derive from verified original bytes."""
    root = Path(root)
    originals = validate_glyph_assets(dossier, root)
    assets = {asset["glyph_id"]: asset for asset in dossier.get("glyph_assets", [])}
    result = {}
    for glyph_id, original in originals.items():
        asset = assets[glyph_id]
        if asset["mime_type"] != "image/svg+xml":
            result[glyph_id] = original
            continue
        import cairosvg
        preview = root / "content/glyph-previews" / (asset["sha256"] + ".png")
        receipt = preview.with_suffix(".json")
        with file_lock(preview.with_suffix(".lock")):
            identity = {"source_sha256": asset["sha256"], "renderer": "cairosvg",
                        "renderer_version": cairosvg.__version__, "output_width": 1000, "background": "white"}
            reusable = False
            if preview.is_file() and receipt.is_file() and not preview.is_symlink():
                try:
                    meta = json.loads(receipt.read_text())
                    data = preview.read_bytes()
                    reusable = (all(meta.get(k) == v for k, v in identity.items())
                                and meta.get("preview_sha256") == hashlib.sha256(data).hexdigest()
                                and image_mime(data) == "image/png")
                except (ValueError, OSError):
                    pass
            if not reusable:
                # Files have already passed the no-entity/no-external-resource SVG check.
                data = cairosvg.svg2png(bytestring=original.read_bytes(), output_width=1000,
                                        background_color="white")
                if len(data) > MAX_BYTES or image_mime(data) != "image/png":
                    raise ValueError("Glyph SVG preview is invalid or oversized")
                preview.parent.mkdir(parents=True, exist_ok=True)
                atomic_write_bytes(preview, data)
                atomic_write_json(receipt, {**identity,
                    "preview_sha256": hashlib.sha256(data).hexdigest()}, sort_keys=True)
        result[glyph_id] = preview
    return result
