"""Fetch a small, character-scoped set of Xiaoxuetang glyph query results.

Xiaoxuetang's form-evolution interface is an HTML form that returns its results
after a single-character POST. Search engines and plain GET links expose only
the query form, which is why researchers can otherwise mistake an empty result
for missing coverage. This module stores only the queried labels and direct
image URLs; the normal research and visual-review stages still choose images.
"""
from __future__ import annotations

from datetime import date
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import tempfile
import time
from urllib.parse import parse_qs, urlencode, urljoin, urlparse
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from pipeline.atomic_files import atomic_write_text, file_lock


BASE_URL = "https://xiaoxue.iis.sinica.edu.tw/yanbian"
RESULT_URL = BASE_URL + "/PageResult/PageResult"
RIGHTS_URL = "https://xiaoxue.iis.sinica.edu.tw/License/License"
SOURCE_TITLE = "小學堂字形演變資料庫 — Academia Sinica"
USER_AGENT = "HanziEtymologyDict/1.0 (character-scoped research lookup)"
MAX_RESPONSE_BYTES = 2 * 1024 * 1024
MAX_CANDIDATES_PER_QUERY = 60
_LOCK_PATH = Path(tempfile.gettempdir()) / "hanzi-etymology-dict-xiaoxuetang.lock"
_BLOCK_PATH = Path(tempfile.gettempdir()) / "hanzi-etymology-dict-xiaoxuetang-unauthorized"
_REQUEST_INTERVAL_SECONDS = 2.0
_UNAUTHORIZED_COOLDOWN_SECONDS = 3600


class _ResultParser(HTMLParser):
    """Read only the glyph cells returned by the official one-character form."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.items: list[dict] = []
        self.current: dict | None = None

    def _finish(self):
        if self.current is not None:
            self.current["labels"] = [x for x in self.current["labels"] if x and x != "|"]
            if self.current["images"]:
                self.items.append(self.current)
            self.current = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "td" and attrs.get("class", "").startswith("VariantList"):
            self._finish()
            self.current = {"class": attrs["class"], "images": [], "labels": []}
            return
        if self.current is None:
            return
        if tag == "img" and attrs.get("class") == "charValue" and attrs.get("src"):
            self.current["images"].append({"src": attrs["src"], "alt": attrs.get("alt", "")})
        elif tag == "br":
            self.current["labels"].append("|")

    def handle_data(self, data):
        if self.current is not None and data.strip():
            self.current["labels"].append(data.strip())

    def handle_endtag(self, tag):
        if tag == "td" and self.current is not None:
            self._finish()


def _hanzi_codepoints(value: str) -> list[str]:
    return [chr(int(code, 16)) for code in re.findall(r"U\+([0-9A-Fa-f]{4,6})", value)
            if int(code, 16) <= 0x10FFFF]


def query_targets(dossier: dict) -> list[str]:
    """Prefer one locally recorded traditional form; otherwise query the entry form."""
    character = dossier.get("character")
    if not isinstance(character, str) or len(character) != 1:
        return []
    variants = dossier.get("context", {}).get("unverified_pipeline_metadata", {}).get("variants", {})
    traditional = variants.get("traditional", "") if isinstance(variants, dict) else ""
    related = [c for c in _hanzi_codepoints(traditional) if c != character]
    return [related[-1] if related else character]


def _rate_limited_post(data: bytes, timeout: int) -> bytes:
    """Serialize queries across batch workers and leave a short gap between requests."""
    import fcntl

    _LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _LOCK_PATH.open("a+", encoding="ascii") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        if _BLOCK_PATH.exists():
            blocked_for = time.time() - _BLOCK_PATH.stat().st_mtime
            if blocked_for < _UNAUTHORIZED_COOLDOWN_SECONDS:
                raise PermissionError("Xiaoxuetang returned HTTP 401; automatic queries are paused for one hour")
            _BLOCK_PATH.unlink(missing_ok=True)
        lock.seek(0)
        try:
            previous = float(lock.read().strip() or "0")
        except ValueError:
            previous = 0.0
        delay = _REQUEST_INTERVAL_SECONDS - (time.time() - previous)
        if delay > 0:
            time.sleep(delay)
        request = Request(RESULT_URL, data=data, headers={
            "User-Agent": USER_AGENT,
            "Referer": BASE_URL,
            "X-Requested-With": "XMLHttpRequest",
            "Content-Type": "application/x-www-form-urlencoded",
        })
        try:
            with urlopen(request, timeout=timeout) as response:
                final_url = response.geturl()
                if urlparse(final_url).hostname != "xiaoxue.iis.sinica.edu.tw":
                    raise ValueError("Xiaoxuetang query redirected outside its official domain")
                data = response.read(MAX_RESPONSE_BYTES + 1)
        except HTTPError as exc:
            if exc.code == 401:
                _BLOCK_PATH.write_text(str(time.time()), encoding="ascii")
            raise
        lock.seek(0)
        lock.truncate()
        lock.write(str(time.time()))
        lock.flush()
        fcntl.flock(lock.fileno(), fcntl.LOCK_UN)
    if len(data) > MAX_RESPONSE_BYTES:
        raise ValueError("Xiaoxuetang query response exceeds 2 MiB")
    return data


def fetch_character(character: str, timeout: int = 30) -> dict:
    """Query one character through Xiaoxuetang's official form, without mirroring it."""
    if not isinstance(character, str) or len(character) != 1:
        raise ValueError("Xiaoxuetang lookup requires exactly one character")
    form = urlencode({"ZiOrder": "", "EudcFontChar": character,
                      "PageNo": "", "ImageSize": "72"}).encode("utf-8")
    try:
        html = _rate_limited_post(form, timeout).decode("utf-8", "replace")
    except Exception as exc:
        return {"character": character, "status": "unavailable", "error": f"{type(exc).__name__}: {exc}",
                "source_url": BASE_URL, "rights_url": RIGHTS_URL, "candidates": []}

    parser = _ResultParser()
    parser.feed(html)
    parser.close()
    parser._finish()
    candidates = []
    for index, item in enumerate(parser.items[:MAX_CANDIDATES_PER_QUERY], 1):
        labels = item["labels"]
        for image in item["images"]:
            image_url = urljoin(BASE_URL + "/", image["src"])
            if urlparse(image_url).hostname != "xiaoxue.iis.sinica.edu.tw":
                continue
            query = parse_qs(urlparse(image_url).query)
            rendered_form = query.get("text", [""])[0]
            candidates.append({
                "id": f"xiaoxuetang-{ord(character):X}-{index}",
                "query_character": character,
                "rendered_form": rendered_form,
                "source_labels": labels,
                "image_url": image_url,
                "source_url": BASE_URL,
                "source_title": SOURCE_TITLE,
                "rights": "CC0 1.0; applies to this queried glyph image and its glyph attributes",
                "rights_url": RIGHTS_URL,
            })
    return {"character": character, "status": "found" if candidates else "no_results",
            "source_url": BASE_URL, "rights_url": RIGHTS_URL,
            "candidate_count": len(candidates), "truncated": len(parser.items) > MAX_CANDIDATES_PER_QUERY,
            "candidates": candidates, "accessed_at": date.today().isoformat()}


def query_dossier(dossier: dict, directory: Path | str, timeout: int = 30) -> dict:
    """Fetch/cache at most the entry form and its recorded traditional counterpart."""
    root = Path(directory) / "xiaoxuetang-query"
    root.mkdir(parents=True, exist_ok=True)
    queries = []
    for character in query_targets(dossier):
        path = root / f"{ord(character):04X}.json"
        with file_lock(path.with_suffix(".lock")):
            if path.exists():
                try:
                    cached = json.loads(path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    cached = None
                if (isinstance(cached, dict) and cached.get("character") == character
                        and cached.get("status") in {"found", "no_results"}):
                    queries.append(cached)
                    continue
            result = fetch_character(character, timeout=timeout)
            atomic_write_text(path, json.dumps(result, ensure_ascii=False, indent=2) + "\n")
        queries.append(result)
    candidates = [candidate for query in queries for candidate in query.get("candidates", [])]
    return {"entry_character": dossier.get("character"), "source": SOURCE_TITLE,
            "source_url": BASE_URL, "rights_url": RIGHTS_URL, "queries": queries,
            "candidates": candidates,
            "instructions": "These are a narrowly requested per-character output from the official form query. Labels are transcribed exactly and are not normalized dates. Select only useful forms; cite and snapshot only selected images."}
