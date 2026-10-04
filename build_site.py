#!/usr/bin/env python3
"""Build the static site data for GitHub Pages (docs/ folder)."""

import json
import gzip
import argparse
from pathlib import Path


def load_articles(directory=Path("content/entries"), dossier_directory=None, expected_language=None):
    """Load approved prose for the exact character named by each file."""
    articles = {}
    for path in sorted(Path(directory).glob("*.json")):
        article = json.loads(path.read_text(encoding="utf-8"))
        if article.get("review", {}).get("status") != "approved":
            continue
        if expected_language is not None and article.get("language") != expected_language:
            raise ValueError(f"Authored entry language must be {expected_language!r}: {path}")
        character = article.get("character", "")
        if len(character) != 1 or path.stem != f"{ord(character):04X}":
            raise ValueError(f"Authored entry character does not match filename: {path}")
        from pipeline.editorial import validate_published
        dossier_path = (Path(dossier_directory) if dossier_directory is not None else Path(directory).parent / "dossiers") / path.name
        current_dossier = json.loads(dossier_path.read_text(encoding="utf-8")) if dossier_path.exists() else None
        validate_published(article, current_dossier=current_dossier)
        articles[character] = {key: value for key, value in article.items() if key != "dossier"}
        assets = article["dossier"].get("glyph_assets", [])
        if assets:
            articles[character]["display_glyphs"] = {
                asset["glyph_id"]: "glyphs/editorial/" + Path(asset["path"]).name for asset in assets
            }
    return articles


def refresh_existing_site_articles(site_path, articles):
    """Refresh approved articles while preserving the existing compiled legacy records."""
    site_path = Path(site_path)
    if not site_path.exists():
        raise FileNotFoundError(f"Existing site archive required: {site_path}")
    with gzip.open(site_path, "rt", encoding="utf-8") as stream:
        records = json.load(stream)
    if not isinstance(records, list):
        raise ValueError("Existing site archive must contain a list of character records")
    characters = [row.get("c") for row in records]
    if len(characters) != len(set(characters)):
        raise ValueError("Existing site archive contains duplicate characters")
    available = set(characters)
    missing = set(articles) - available
    if missing:
        raise ValueError(f"Approved articles lack a legacy site record: {sorted(missing)!r}")
    stale = {row["c"] for row in records if "article" in row} - set(articles)
    if stale:
        raise ValueError(f"Existing site articles lack an approved source: {sorted(stale)!r}")
    for row in records:
        if row["c"] in articles:
            row["article"] = articles[row["c"]]
    temporary = site_path.with_name(site_path.name + ".tmp")
    try:
        with gzip.open(temporary, "wt", encoding="utf-8") as stream:
            json.dump(records, stream, ensure_ascii=False, separators=(",", ":"))
        temporary.replace(site_path)
    finally:
        temporary.unlink(missing_ok=True)
    return len(records)


def refresh_articles_only():
    """Use existing site data when upstream legacy source files are unavailable."""
    import shutil
    articles = load_articles()
    site_path = Path("docs/data.json.gz")
    count = refresh_existing_site_articles(site_path, articles)
    for article in articles.values():
        for display_path in article.get("display_glyphs", {}).values():
            destination = Path("docs") / display_path
            source = Path("content/glyph-assets") / destination.name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
    print(f"Refreshed {len(articles)} approved articles in {count} existing site records")


def compute_kokuji_set():
    """Return set of chars that are Japan-only (kokuji): in KANJIDIC2 but absent
    from all Chinese-sphere national standards (G=PRC, T=Taiwan, H=HK, V=Vietnam)
    according to Unihan kIICore field."""
    kanji_path = Path("output/kanji_etymology.jsonl")
    iicore_path = Path("sources/unihan/Unihan_IRGSources.txt")
    if not kanji_path.exists() or not iicore_path.exists():
        return set()

    kanji_chars = set()
    with open(str(kanji_path), encoding="utf-8") as f:
        for line in f:
            kanji_chars.add(json.loads(line)["character"])

    iicore = {}
    with open(str(iicore_path), encoding="utf-8") as f:
        for line in f:
            if line.startswith("#") or not line.strip():
                continue
            parts = line.strip().split("\t")
            if len(parts) >= 3 and parts[1] == "kIICore":
                iicore[chr(int(parts[0][2:], 16))] = parts[2]

    chinese_sphere = set("GTHV")
    return {
        ch for ch in kanji_chars
        if ch in iicore and not any(c in chinese_sphere for c in iicore[ch])
    }


def build_kanji(kokuji_set=None, articles=None):
    """Build kanji site data: output/kanji_etymology.jsonl -> docs/kanji_data.json.gz"""
    docs = Path("docs")
    docs.mkdir(exist_ok=True)
    # Shared canonical HSK 2021 character lists, independent of legacy HSK tags.
    hsk_levels = json.loads(Path("content/hsk-levels.json").read_text(encoding="utf-8"))
    (docs / "hsk-levels.json").write_text(json.dumps(hsk_levels, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    jlpt_path = Path("content/jlpt-levels.json")
    if jlpt_path.exists():
        jlpt_levels = json.loads(jlpt_path.read_text(encoding="utf-8"))
        (docs / "jlpt-levels.json").write_text(json.dumps(jlpt_levels, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    kokuji_set = kokuji_set or set()
    articles = load_articles(Path("content/ja/entries"), expected_language="ja") if articles is None else articles
    if any(article.get("language") != "ja" for article in articles.values()):
        raise ValueError("Japanese site articles must have language='ja'")

    fpath = Path("output/kanji_etymology.jsonl")
    if not fpath.exists():
        print("  output/kanji_etymology.jsonl not found, skipping (run build_kanji.py)")
        return

    print("Building kanji site data...")
    records = []
    with open(str(fpath), "r", encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            # Include every kanji that has at least a definition (all KANJIDIC2 entries do)
            if not r.get("definition"):
                continue

            compact = {"c": r["character"], "p": r.get("codepoint", "")}
            rd = r.get("readings", {})

            if rd.get("japanese_on"):  compact["jo"] = rd["japanese_on"]
            if rd.get("japanese_kun"): compact["jk"] = rd["japanese_kun"]
            if rd.get("nanori"):       compact["jn"] = rd["nanori"]
            if rd.get("mandarin"):     compact["py"] = rd["mandarin"]

            if r.get("definition"):     compact["d"] = r["definition"]
            if r.get("formation_type"): compact["ft"] = r["formation_type"]
            fd = r.get("formation_details", {})
            if fd.get("semantic"):  compact["sem"] = fd["semantic"]
            if fd.get("phonetic"):  compact["phon"] = fd["phonetic"]
            if r.get("ids"):        compact["ids"] = r["ids"]

            if r.get("etymology_notes"):
                compact["en"] = [
                    {"s": n["source"], "t": n["text"],
                     **({" v": n["via_traditional"]} if n.get("via_traditional") else {}),
                     **({"w": 1} if n.get("caveat") else {})}
                    for n in r["etymology_notes"][:5]
                ]

            sw = r.get("shuowen", {})
            if sw.get("explanation"):
                compact["sw"] = sw["explanation"]
                if sw.get("english"):           compact["swe"] = sw["english"]
                if sw.get("modern_correction"): compact["swc"] = sw["modern_correction"]
                if sw.get("pronunciation_fanqie"): compact["swf"] = sw["pronunciation_fanqie"]

            ph = r.get("historical_phonology", [])
            if ph: compact["hp"] = ph[:4]
            gy = r.get("guangyun", [])
            if gy: compact["gy"] = gy[:3]

            if r.get("formation_type_conflict"): compact["ftc"] = r["formation_type_conflict"]

            # Japanese-specific
            if r.get("jlpt") is not None:    compact["jlpt"] = r["jlpt"]
            if r.get("grade") is not None:   compact["grade"] = r["grade"]
            if r.get("joyo"):                compact["joyo"] = True
            if r.get("jinmeiyo"):            compact["jinmeiyo"] = True
            if r.get("japanese_freq"):       compact["jfr"] = r["japanese_freq"]
            if r.get("total_strokes"):       compact["str"] = r["total_strokes"]
            if r.get("radical_stroke"):      compact["rs"] = r["radical_stroke"]

            lg = r.get("local_glyphs", {})
            if lg: compact["lg"] = lg
            v = r.get("variants", {})
            if v: compact["var"] = v
            for key, short in [("phonetic_series", "ps"), ("semantic_series", "ss"),
                                ("phonetic_siblings", "psib"), ("semantic_siblings", "ssib")]:
                if r.get(key):
                    compact[short] = r[key][:30]
                    total_key = key + "_total"
                    if r.get(total_key): compact[short + "t"] = r[total_key]
            if r["character"] in kokuji_set: compact["kokuji"] = True

            if r["character"] in articles:
                compact["article"] = articles[r["character"]]
            records.append(compact)

    data = json.dumps(records, ensure_ascii=False, separators=(",", ":"))
    outpath = docs / "kanji_data.json.gz"
    with gzip.open(str(outpath), "wb") as f:
        f.write(data.encode("utf-8"))

    gz = outpath.stat().st_size
    print(f"  {len(records)} kanji records, {gz / 1024:.0f} KB gzipped -> {outpath}")


def main():
    print("Building site data for docs/...")
    docs = Path("docs")
    docs.mkdir(exist_ok=True)

    articles = load_articles()
    japanese_articles = load_articles(Path("content/ja/entries"), expected_language="ja")
    print(f"  Approved authored entries: {len(articles)}")
    print(f"  Approved Japanese authored entries: {len(japanese_articles)}")
    # Content-addressed snapshots are covered by each entry's reviewed dossier.
    import shutil
    for article in [*articles.values(), *japanese_articles.values()]:
        for display_path in article.get("display_glyphs", {}).values():
            destination = docs / display_path
            source = Path("content/glyph-assets") / destination.name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
    kokuji_set = compute_kokuji_set()
    print(f"  Kokuji set: {len(kokuji_set)} characters identified")

    records = []
    with open("output/hanzi_etymology.jsonl", "r", encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            if not (r.get("definitions") or r.get("etymology_notes") or r.get("formation_type")):
                continue

            compact = {"c": r["character"], "p": r.get("codepoint", "")}
            rd = r.get("readings", {})
            if rd.get("mandarin"): compact["py"] = rd["mandarin"]
            if rd.get("cantonese"): compact["ca"] = rd["cantonese"]
            if r.get("definitions"): compact["d"] = r["definitions"]
            if r.get("formation_type"): compact["ft"] = r["formation_type"]
            fd = r.get("formation_details", {})
            if fd.get("semantic"): compact["sem"] = fd["semantic"]
            if fd.get("phonetic"): compact["phon"] = fd["phonetic"]
            if r.get("ids") or r.get("decomposition_ids"):
                compact["ids"] = r.get("ids") or r.get("decomposition_ids")
            if r.get("etymology_notes"):
                compact["en"] = [
                    {"s": n["source"], "t": n["text"],
                     **({" v": n["via_traditional"]} if n.get("via_traditional") else {}),
                     **({"w": 1} if n.get("caveat") else {})}
                    for n in r["etymology_notes"][:5]
                ]
            sw = r.get("shuowen", {})
            if sw.get("explanation"):
                compact["sw"] = sw["explanation"]
                if sw.get("english"): compact["swe"] = sw["english"]
                if sw.get("modern_correction"): compact["swc"] = sw["modern_correction"]
                if sw.get("pronunciation_fanqie"): compact["swf"] = sw["pronunciation_fanqie"]
            ph = r.get("historical_phonology", [])
            if ph: compact["hp"] = ph[:4]
            gy = r.get("guangyun", [])
            if gy: compact["gy"] = gy[:3]
            if r.get("formation_type_conflict"): compact["ftc"] = r["formation_type_conflict"]
            if r.get("frequency_rank"): compact["fr"] = r["frequency_rank"]
            if r.get("hsk3_level"): compact["hsk"] = r["hsk3_level"]
            elif r.get("hsk_level"): compact["hsk"] = r["hsk_level"]
            if r.get("semantic_field"): compact["sf"] = r["semantic_field"]
            for key, short in [("phonetic_series", "ps"), ("semantic_series", "ss"),
                                ("phonetic_siblings", "psib"), ("semantic_siblings", "ssib")]:
                if r.get(key):
                    compact[short] = r[key][:30]
                    total_key = key + "_total"
                    if r.get(total_key): compact[short + "t"] = r[total_key]
            if r.get("sino_tibetan_cognates"): compact["stc"] = r["sino_tibetan_cognates"]
            lg = r.get("local_glyphs", {})
            if lg: compact["lg"] = lg
            kx = r.get("kangxi", {})
            if kx.get("fanqie_citations"): compact["kxf"] = kx["fanqie_citations"]
            if r.get("shuowen_accuracy"): compact["sa"] = r["shuowen_accuracy"]
            if r.get("total_strokes"): compact["str"] = r["total_strokes"]
            if r.get("radical_stroke"): compact["rs"] = r["radical_stroke"]
            v = r.get("variants", {})
            if v: compact["var"] = v
            for k, sk in [("japanese_on", "jo"), ("japanese_kun", "jk"),
                          ("korean", "ko"), ("vietnamese", "vi")]:
                if rd.get(k): compact[sk] = rd[k]
            if r["character"] in kokuji_set: compact["kokuji"] = True

            if r["character"] in articles:
                compact["article"] = articles[r["character"]]
            records.append(compact)

    data = json.dumps(records, ensure_ascii=False, separators=(",", ":"))
    with gzip.open(docs / "data.json.gz", "wb") as f:
        f.write(data.encode("utf-8"))

    import os
    import shutil
    gz = os.path.getsize(docs / "data.json.gz")
    print(f"  {len(records)} records, {gz/1024/1024:.1f} MB gzipped")

    # Copy Dong Chinese glyph SVGs if available
    dong_src = Path("output/glyphs/dong_chinese")
    dong_dst = docs / "glyphs" / "dong_chinese"
    if dong_src.exists():
        if dong_dst.exists():
            shutil.rmtree(dong_dst)
        shutil.copytree(dong_src, dong_dst)
        n_dirs = sum(1 for d in dong_dst.iterdir() if d.is_dir())
        print(f"  Copied {n_dirs} Dong Chinese glyph folders to docs/glyphs/")

    # Copy Wikimedia seal SVGs if available
    wm_src = Path("output/glyphs/wikimedia_seal")
    wm_dst = docs / "glyphs" / "wikimedia_seal"
    if wm_src.exists():
        if wm_dst.exists():
            shutil.rmtree(wm_dst)
        wm_dst.mkdir(parents=True)
        n = 0
        for svg in wm_src.glob("*.svg"):
            shutil.copy2(svg, wm_dst / svg.name)
            n += 1
        print(f"  Copied {n} Wikimedia seal SVGs to docs/glyphs/")


    build_kanji(kokuji_set, japanese_articles)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh-articles", action="store_true",
                        help="Refresh approved article overlays in existing docs data without legacy source files")
    args = parser.parse_args()
    if args.refresh_articles:
        refresh_articles_only()
    else:
        main()
