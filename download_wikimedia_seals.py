#!/usr/bin/env python3
"""
Download Shuowen seal script SVG files from Wikimedia Commons.

These are public domain historical character form images from two main categories:
  - "Shuowen seal script characters (SVG)" (~3,097 files)
  - "Shuowen seal script radicals" (~543 SVG files)

The script:
  1. Lists all SVG files in these categories via the Wikimedia Commons API.
  2. Downloads each SVG to output/glyphs/wikimedia_seal/.
  3. Extracts the Chinese character each file depicts (from filename or API metadata).
  4. Writes a manifest.json mapping filenames to characters.

Usage:
    python3 download_wikimedia_seals.py [--limit N] [--skip-download] [--offset N]

Options:
    --limit N          Max files to download (default: 500). Use 0 for no limit.
    --skip-download    Only build the file list and manifest; don't download SVGs.
    --offset N         Skip the first N files (useful for resuming).

The total corpus across both categories is ~3,600 SVG files. To download
everything, run:
    python3 download_wikimedia_seals.py --limit 0
"""

import argparse
import json
import os
import re
import sys
import time
import unicodedata
from pathlib import Path
from urllib.parse import unquote

import requests

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

API_URL = "https://commons.wikimedia.org/w/api.php"
USER_AGENT = (
    "HanziEtymologyDict/1.0 "
    "(https://github.com/user/hanzi-etymology-dict; research project) "
    "Python/requests"
)

OUTPUT_DIR = Path(__file__).resolve().parent / "output" / "glyphs" / "wikimedia_seal"

# Categories to harvest (only SVG-heavy ones)
CATEGORIES = [
    "Category:Shuowen seal script characters (SVG)",
    "Category:Shuowen seal script radicals",
]

# Delay between API / download requests (seconds) to be respectful
API_DELAY = 0.2
DOWNLOAD_DELAY = 0.15

# How many titles to batch in a single imageinfo request (API max is 50)
IMAGEINFO_BATCH = 50


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_session() -> requests.Session:
    """Create a requests session with an identifying User-Agent."""
    s = requests.Session()
    s.headers["User-Agent"] = USER_AGENT
    return s


def is_cjk_character(ch: str) -> bool:
    """Return True if *ch* is a single CJK unified ideograph (any block)."""
    cp = ord(ch)
    return any(
        lo <= cp <= hi
        for lo, hi in [
            (0x4E00, 0x9FFF),      # CJK Unified Ideographs
            (0x3400, 0x4DBF),      # CJK Ext A
            (0x20000, 0x2A6DF),    # CJK Ext B
            (0x2A700, 0x2B73F),    # CJK Ext C
            (0x2B740, 0x2B81F),    # CJK Ext D
            (0x2B820, 0x2CEAF),    # CJK Ext E
            (0x2CEB0, 0x2EBEF),    # CJK Ext F
            (0x30000, 0x3134F),    # CJK Ext G
            (0x31350, 0x323AF),    # CJK Ext H
            (0x2EBF0, 0x2F7FF),    # CJK Ext I  (Unicode 16)
            (0x3D000, 0x3FC3F),    # Shuowen-specific block (proposed)
            (0x2F00, 0x2FDF),      # Kangxi Radicals
            (0x2E80, 0x2EFF),      # CJK Radicals Supplement
        ]
    )


def extract_char_from_filename(filename: str) -> str | None:
    """
    Try to extract a Chinese character directly from the filename.

    Patterns handled:
      - "X-seal.svg"  (most common; X is one CJK character)
      - "Character X Seal.svg"
      - "Shuowen Seal Radical NNN.svg" -> cannot extract char from name alone
      - "ACC-sNNNNN.svg" -> cannot extract char from name alone
    """
    # Pattern: single CJK char followed by -seal.svg (or -seal-seal.svg, etc.)
    m = re.match(r"^(.+?)-seal(?:-seal)?\.svg$", filename, re.IGNORECASE)
    if m:
        candidate = m.group(1)
        # Accept if candidate is 1-2 CJK characters
        if 1 <= len(candidate) <= 2 and all(is_cjk_character(c) for c in candidate):
            return candidate

    # Pattern: "Character <Pinyin> Seal.svg" — no CJK in name
    # Pattern: "X Seal.svg" or "X Seal.gif/png"
    m = re.match(r"^(.+?)\s+[Ss]eal\.\w+$", filename)
    if m:
        candidate = m.group(1)
        if 1 <= len(candidate) <= 2 and all(is_cjk_character(c) for c in candidate):
            return candidate

    return None


def extract_char_from_categories(categories_str: str) -> str | None:
    """
    Extract the depicted character from the pipe-separated Categories string
    returned by the Wikimedia extmetadata API.

    For ACC files the categories typically include the bare character, e.g.:
        "一|ACC needing decomposition|...|Shuowen seal script characters (SVG)"

    We look for entries that are exactly one CJK character.
    """
    if not categories_str:
        return None

    for part in categories_str.split("|"):
        part = part.strip()
        if len(part) == 1 and is_cjk_character(part):
            return part

    return None


def extract_char_from_description(desc_html: str) -> str | None:
    """
    Fall-back: pull the character from the ImageDescription HTML.

    Typical pattern:
        '...depicting the character 一 in the ...'
    """
    if not desc_html:
        return None
    m = re.search(r"depicting the character\s+(.)\s", desc_html)
    if m and is_cjk_character(m.group(1)):
        return m.group(1)
    return None


# ---------------------------------------------------------------------------
# API interaction
# ---------------------------------------------------------------------------

def list_category_files(session: requests.Session, category: str) -> list[dict]:
    """
    Return all File:-namespace members of *category*, paginating as needed.

    Each element is a dict with keys: title, pageid.
    """
    results = []
    params = {
        "action": "query",
        "list": "categorymembers",
        "cmtitle": category,
        "cmtype": "file",
        "cmlimit": 500,
        "format": "json",
    }

    while True:
        time.sleep(API_DELAY)
        r = session.get(API_URL, params=params)
        r.raise_for_status()
        data = r.json()

        for m in data.get("query", {}).get("categorymembers", []):
            results.append({"title": m["title"], "pageid": m["pageid"]})

        cont = data.get("continue")
        if cont and "cmcontinue" in cont:
            params["cmcontinue"] = cont["cmcontinue"]
        else:
            break

    return results


def fetch_imageinfo_batch(
    session: requests.Session, titles: list[str]
) -> dict[str, dict]:
    """
    For a batch of File: titles, return {title: {url, character}} via the
    imageinfo API.
    """
    results: dict[str, dict] = {}
    params = {
        "action": "query",
        "titles": "|".join(titles),
        "prop": "imageinfo",
        "iiprop": "url|extmetadata",
        "format": "json",
    }

    time.sleep(API_DELAY)
    r = session.get(API_URL, params=params)
    r.raise_for_status()
    data = r.json()

    for _pid, page in data.get("query", {}).get("pages", {}).items():
        title = page.get("title", "")
        ii_list = page.get("imageinfo", [])
        if not ii_list:
            continue
        ii = ii_list[0]
        url = ii.get("url", "")
        ext = ii.get("extmetadata", {})

        cats_str = ext.get("Categories", {}).get("value", "")
        desc_str = ext.get("ImageDescription", {}).get("value", "")

        # Try multiple strategies to find the character
        filename = title.replace("File:", "")
        char = (
            extract_char_from_filename(filename)
            or extract_char_from_categories(cats_str)
            or extract_char_from_description(desc_str)
        )

        results[title] = {"url": url, "character": char}

    return results


def download_file(session: requests.Session, url: str, dest: Path) -> bool:
    """Download a single file. Return True on success."""
    try:
        time.sleep(DOWNLOAD_DELAY)
        r = session.get(url, timeout=30)
        r.raise_for_status()
        dest.write_bytes(r.content)
        return True
    except Exception as e:
        print(f"  ERROR downloading {url}: {e}", file=sys.stderr)
        return False


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Download Shuowen seal script SVGs from Wikimedia Commons."
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=500,
        help="Max files to download (0 = unlimited, default 500).",
    )
    parser.add_argument(
        "--skip-download",
        action="store_true",
        help="List files and build manifest without downloading.",
    )
    parser.add_argument(
        "--offset",
        type=int,
        default=0,
        help="Skip the first N files (for resuming).",
    )
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    session = make_session()

    # ------------------------------------------------------------------
    # Step 1: List all SVG files across categories
    # ------------------------------------------------------------------
    print("=== Step 1: Listing files from Wikimedia Commons categories ===")
    all_files: list[dict] = []
    seen_titles: set[str] = set()

    for cat in CATEGORIES:
        print(f"  Querying {cat} ...")
        members = list_category_files(session, cat)
        for m in members:
            if m["title"] not in seen_titles:
                # Only keep SVG files
                if m["title"].lower().endswith(".svg"):
                    all_files.append(m)
                    seen_titles.add(m["title"])
        print(f"    Found {len(members)} files ({len(all_files)} unique SVGs so far)")

    total_available = len(all_files)
    print(f"\n  Total unique SVG files found: {total_available}")

    # Apply offset
    if args.offset > 0:
        all_files = all_files[args.offset:]
        print(f"  After offset {args.offset}: {len(all_files)} remaining")

    # Apply limit
    effective_limit = args.limit if args.limit > 0 else len(all_files)
    work_files = all_files[:effective_limit]
    print(f"  Will process: {len(work_files)} files")

    if effective_limit < len(all_files):
        remaining = len(all_files) - effective_limit
        print(f"  NOTE: {remaining} more files available. Re-run with --limit 0 to get all,")
        print(f"        or --offset {args.offset + effective_limit} to continue from here.")

    # ------------------------------------------------------------------
    # Step 2: Fetch image URLs and metadata in batches
    # ------------------------------------------------------------------
    print("\n=== Step 2: Fetching image URLs and metadata ===")
    file_info: dict[str, dict] = {}  # title -> {url, character}

    titles = [f["title"] for f in work_files]
    for i in range(0, len(titles), IMAGEINFO_BATCH):
        batch = titles[i : i + IMAGEINFO_BATCH]
        batch_info = fetch_imageinfo_batch(session, batch)
        file_info.update(batch_info)
        done = min(i + IMAGEINFO_BATCH, len(titles))
        print(f"  Metadata fetched: {done}/{len(titles)}", end="\r")

    print(f"  Metadata fetched: {len(file_info)}/{len(titles)}           ")

    # ------------------------------------------------------------------
    # Step 3: Download SVGs
    # ------------------------------------------------------------------
    downloaded = 0
    skipped = 0
    errors = 0

    if not args.skip_download:
        print("\n=== Step 3: Downloading SVG files ===")
        for idx, title in enumerate(titles, 1):
            info = file_info.get(title)
            if not info or not info.get("url"):
                errors += 1
                continue

            filename = title.replace("File:", "")
            dest = OUTPUT_DIR / filename

            if dest.exists():
                skipped += 1
                if idx % 50 == 0:
                    print(f"  Progress: {idx}/{len(titles)} (downloaded={downloaded}, skipped={skipped})")
                continue

            ok = download_file(session, info["url"], dest)
            if ok:
                downloaded += 1
            else:
                errors += 1

            if idx % 50 == 0:
                print(f"  Progress: {idx}/{len(titles)} (downloaded={downloaded}, skipped={skipped})")

        print(f"  Done: {downloaded} downloaded, {skipped} already existed, {errors} errors")
    else:
        print("\n=== Step 3: Skipping downloads (--skip-download) ===")

    # ------------------------------------------------------------------
    # Step 4: Build manifest
    # ------------------------------------------------------------------
    print("\n=== Step 4: Building manifest.json ===")
    manifest: dict[str, dict] = {}
    mapped_count = 0

    for title, info in file_info.items():
        filename = title.replace("File:", "")
        entry = {
            "filename": filename,
            "character": info.get("character"),
            "url": info.get("url", ""),
        }
        manifest[filename] = entry
        if info.get("character"):
            mapped_count += 1

    manifest_path = OUTPUT_DIR / "manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    print(f"  Manifest written to {manifest_path}")

    # ------------------------------------------------------------------
    # Step 5: Summary
    # ------------------------------------------------------------------
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"  Total SVG files found across categories:  {total_available}")
    print(f"  Files processed in this run:              {len(work_files)}")
    if not args.skip_download:
        print(f"  Downloaded:                               {downloaded}")
        print(f"  Already existed (skipped):                {skipped}")
        print(f"  Errors:                                   {errors}")
    print(f"  Mapped to a specific character:            {mapped_count}")
    print(f"  Could not map to character:                {len(work_files) - mapped_count}")
    print(f"  Manifest:  {manifest_path}")
    print(f"  SVG dir:   {OUTPUT_DIR}")

    if effective_limit < total_available:
        print(f"\n  To download the full set ({total_available} files):")
        print(f"    python3 {Path(__file__).name} --limit 0")


if __name__ == "__main__":
    main()
