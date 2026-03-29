#!/usr/bin/env python3
"""
Build Japanese kanji etymology database from multiple open sources.

Sources:
  1. KANJIDIC2 XML (EDRDG, CC BY-SA 4.0) -- readings, meanings, grade, stroke count
  2. davidluzgouveia/kanji-data (MIT) -- JLPT levels, WaniKani levels
  3. scriptin/kanji-frequency (CC BY 4.0) -- Japanese frequency ranking
  4. cjkvi-ids/ids-analysis.txt (GPLv2) -- Shuowen-based etymological decomposition
  5. output/hanzi_etymology.jsonl -- reuse Chinese etymology, phonology, glyph data

Run download_kanji_sources.py first to fetch sources 1-3.
"""

import json
import xml.etree.ElementTree as ET
from pathlib import Path

SOURCES_DIR = Path("sources")
OUTPUT_DIR = Path("output")
OUTPUT_DIR.mkdir(exist_ok=True)


# ---------------------------------------------------------------------------
# 1. KANJIDIC2
# ---------------------------------------------------------------------------
def parse_kanjidic2():
    print("[1/5] Parsing KANJIDIC2 XML...")
    fpath = SOURCES_DIR / "kanjidic2" / "kanjidic2.xml"
    if not fpath.exists():
        print("  Not found. Run: python download_kanji_sources.py")
        return {}

    chars = {}
    tree = ET.parse(str(fpath))
    root = tree.getroot()

    for char_el in root.findall("character"):
        ch = char_el.findtext("literal", "")
        if not ch:
            continue

        misc = char_el.find("misc")
        grade = stroke_count = freq_kanjidic = jlpt_old = None
        if misc is not None:
            g = misc.findtext("grade")
            grade = int(g) if g else None
            sc = misc.findtext("stroke_count")
            stroke_count = int(sc) if sc else None
            f = misc.findtext("freq")
            freq_kanjidic = int(f) if f else None
            j = misc.findtext("jlpt")
            jlpt_old = int(j) if j else None

        on_readings, kun_readings, nanori = [], [], []
        meanings_en = []

        rm_el = char_el.find("reading_meaning")
        if rm_el is not None:
            for rmg in rm_el.findall("rmgroup"):
                for r_el in rmg.findall("reading"):
                    r_type = r_el.get("r_type", "")
                    val = r_el.text or ""
                    if r_type == "ja_on":
                        on_readings.append(val)
                    elif r_type == "ja_kun":
                        kun_readings.append(val)
                for m_el in rmg.findall("meaning"):
                    if not m_el.get("m_lang"):  # no lang attr = English
                        meanings_en.append(m_el.text or "")
            for n_el in rm_el.findall("nanori"):
                if n_el.text:
                    nanori.append(n_el.text)

        chars[ch] = {
            "on": on_readings,
            "kun": kun_readings,
            "nanori": nanori,
            "meanings": meanings_en,
            "grade": grade,
            "stroke_count": stroke_count,
            "freq_kanjidic": freq_kanjidic,
            "jlpt_old": jlpt_old,
        }

    print(f"  Parsed {len(chars)} kanji")
    return chars


# ---------------------------------------------------------------------------
# 2. davidluzgouveia/kanji-data
# ---------------------------------------------------------------------------
def parse_kanji_data():
    print("[2/5] Parsing kanji-data (davidluzgouveia / MIT)...")
    fpath = SOURCES_DIR / "kanji-data" / "kanji.json"
    if not fpath.exists():
        print("  Not found. Run: python download_kanji_sources.py")
        return {}
    with open(str(fpath), "r", encoding="utf-8") as f:
        data = json.load(f)
    print(f"  Parsed {len(data)} kanji")
    return data


# ---------------------------------------------------------------------------
# 3. scriptin/kanji-frequency
# ---------------------------------------------------------------------------
def parse_kanji_frequency():
    """scriptin/kanji-frequency -- CSV format, columns: character,frequency,..."""
    print("[3/5] Parsing kanji-frequency (scriptin / CC BY 4.0)...")
    import csv as _csv
    freq_dir = SOURCES_DIR / "kanji-frequency"
    for fname in [
        "aozora_characters.csv",
        "wikipedia_characters.csv",
        "news_characters.csv",
    ]:
        fpath = freq_dir / fname
        if not fpath.exists():
            continue
        freq_map = {}
        with open(str(fpath), "r", encoding="utf-8", newline="") as f:
            reader = _csv.reader(f)
            header = next(reader, None)
            # Detect character column (first col named 'character', 'kanji', or col index 0)
            char_col = 0
            if header:
                for i, h in enumerate(header):
                    if h.lower() in ("character", "kanji", "char"):
                        char_col = i
                        break
            rank = 1
            for row in reader:
                if not row or len(row) <= char_col:
                    continue
                ch = row[char_col].strip()
                if ch and len(ch) == 1:
                    freq_map[ch] = rank
                    rank += 1
        if freq_map:
            print(f"  Parsed {len(freq_map)} entries from {fname}")
            return freq_map

    print("  Not found. Run: python3 download_kanji_sources.py")
    return {}


# ---------------------------------------------------------------------------
# 4. cjkvi-ids/ids-analysis.txt
# ---------------------------------------------------------------------------
def parse_ids_analysis():
    print("[4/5] Parsing ids-analysis.txt (cjkvi / GPLv2)...")
    fpath = SOURCES_DIR / "cjkvi-ids" / "ids-analysis.txt"
    if not fpath.exists():
        print("  Not found in sources/cjkvi-ids/ids-analysis.txt")
        return {}
    chars = {}
    with open(str(fpath), "r", encoding="utf-8") as f:
        for line in f:
            if line.startswith("#") or not line.strip():
                continue
            parts = line.strip().split("\t")
            if len(parts) < 3:
                continue
            ch = parts[1]
            ids = parts[2]
            # Skip variant/simplified markers (←, →)
            if ids.startswith("←") or ids.startswith("→"):
                continue
            formation_note = parts[3] if len(parts) > 3 else ""
            # Strip annotation after #
            formation_note = formation_note.split("#")[0].strip()
            chars[ch] = {"ids": ids, "formation_note": formation_note}
    print(f"  Parsed {len(chars)} entries")
    return chars


# ---------------------------------------------------------------------------
# 5. Chinese etymology DB
# ---------------------------------------------------------------------------
def load_chinese_db():
    print("[5/5] Loading Chinese etymology DB (for reuse)...")
    fpath = OUTPUT_DIR / "hanzi_etymology.jsonl"
    if not fpath.exists():
        print("  Not found. Run build_database.py first.")
        return {}
    chars = {}
    with open(str(fpath), "r", encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            ch = r.get("character", "")
            if ch:
                chars[ch] = r
    print(f"  Loaded {len(chars)} records")
    return chars


# ---------------------------------------------------------------------------
# Formation type extraction from ids-analysis notation
# ---------------------------------------------------------------------------
def extract_formation_from_ids_note(note):
    """Parse ids-analysis formation_note into formation_type."""
    if not note:
        return None
    if "象形" in note:
        return "pictographic"
    if "指事" in note:
        return "indicative"
    if "假借" in note:
        return "phonetic-loan"
    if "亦聲" in note:
        return "phono-semantic"  # component is both semantic and phonetic
    if "聲" in note:
        return "phono-semantic"
    return None


# ---------------------------------------------------------------------------
# Main build
# ---------------------------------------------------------------------------
def build():
    kanjidic = parse_kanjidic2()
    kanji_data = parse_kanji_data()
    freq_map = parse_kanji_frequency()
    ids_analysis = parse_ids_analysis()
    zh_db = load_chinese_db()

    print("\nBuilding kanji records...")
    records = []

    for ch, kd in kanjidic.items():
        kd2 = kanji_data.get(ch, {})
        zh = zh_db.get(ch, {})
        ida = ids_analysis.get(ch, {})

        # --- Readings ---
        on_readings = kd["on"]
        kun_readings = kd["kun"]
        nanori = kd["nanori"]

        # --- Definition ---
        # Prefer davidluzgouveia (cleaner), fall back to KANJIDIC2
        meanings = kd2.get("meanings") or kd["meanings"]
        definition = "; ".join(meanings[:5]) if meanings else ""

        # --- JLPT level (new scale: 1=N1 hardest, 5=N5 easiest) ---
        jlpt = kd2.get("jlpt_new") or kd2.get("jlpt_old")
        if not jlpt and kd.get("jlpt_old"):
            # Old JLPT had 4 levels (1-4); map approximately to new 5-level scale
            # Old 4 (easiest) ≈ New N4/N5; old 1 (hardest) ≈ New N1/N2
            old_to_new = {4: 4, 3: 3, 2: 2, 1: 1}
            jlpt = old_to_new.get(kd["jlpt_old"])

        # --- Grade & Joyo ---
        grade = kd2.get("grade") or kd.get("grade")
        # KANJIDIC2 grade: 1-6=elementary, 8=secondary joyo, 9=jinmeiyo
        joyo = grade is not None and 1 <= grade <= 8
        jinmeiyo = grade == 9

        # --- Frequency ---
        jfr = freq_map.get(ch) or kd.get("freq_kanjidic")

        # --- Stroke count ---
        stroke_count = kd2.get("strokes") or kd.get("stroke_count")

        # --- IDS decomposition ---
        # Chinese DB already has cjkvi-ids integrated; ids-analysis adds formation note
        ids = zh.get("ids") or zh.get("decomposition_ids") or ida.get("ids")

        # --- Formation type ---
        ft = zh.get("formation_type")
        if not ft and ida.get("formation_note"):
            ft = extract_formation_from_ids_note(ida["formation_note"])

        fd = zh.get("formation_details", {})

        # --- Etymology notes ---
        etym_notes = list(zh.get("etymology_notes", []))

        # Add ids-analysis formation note as etymology if it has content and no existing note
        if ida.get("formation_note") and not any(
            n.get("source") == "ids_analysis" for n in etym_notes
        ):
            note_text = ida["formation_note"]
            # Translate common patterns for readability
            note_text = note_text.replace("聲", " (phonetic)").replace("亦聲", " (phonosemantic)")
            note_text = note_text.replace("象形", "pictographic").replace("指事", "indicative")
            etym_notes.append({
                "source": "ids_analysis",
                "text": f"Etymological analysis: {note_text}",
            })

        record = {
            "character": ch,
            "codepoint": f"U+{ord(ch):04X}",
            "readings": {
                "japanese_on": " ".join(on_readings),
                "japanese_kun": " ".join(kun_readings),
                "nanori": " ".join(nanori),
                "mandarin": zh.get("readings", {}).get("mandarin", ""),
            },
            "definition": definition,
            "jlpt": jlpt,
            "grade": grade,
            "joyo": joyo,
            "jinmeiyo": jinmeiyo,
            "japanese_freq": jfr,
            "total_strokes": stroke_count,
            "formation_type": ft,
            "formation_details": fd,
            "ids": ids,
            "etymology_notes": etym_notes,
            "shuowen": zh.get("shuowen", {}),
            "historical_phonology": zh.get("historical_phonology", []),
            "guangyun": zh.get("guangyun", []),
            "local_glyphs": zh.get("local_glyphs", {}),
            "phonetic_family": zh.get("phonetic_family", []),
            "variants": zh.get("variants", {}),
            "radical_stroke": zh.get("radical_stroke", ""),
            "verification_status": zh.get("verification_status"),
            "confidence": zh.get("confidence"),
            "formation_type_conflict": zh.get("formation_type_conflict"),
        }
        records.append(record)

    # Sort by Japanese frequency rank (unranked at end)
    records.sort(key=lambda r: r.get("japanese_freq") or 99999)

    # Write JSONL
    outpath = OUTPUT_DIR / "kanji_etymology.jsonl"
    with open(str(outpath), "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    # Stats
    has_jlpt = sum(1 for r in records if r.get("jlpt"))
    has_joyo = sum(1 for r in records if r.get("joyo"))
    has_etym = sum(1 for r in records if r.get("etymology_notes"))
    has_ft = sum(1 for r in records if r.get("formation_type"))
    has_hp = sum(1 for r in records if r.get("historical_phonology"))
    has_sw = sum(1 for r in records if r.get("shuowen", {}).get("explanation"))

    print(f"\n  {len(records)} kanji records -> {outpath}")
    print(f"  JLPT data:        {has_jlpt}")
    print(f"  Joyo kanji:       {has_joyo}")
    print(f"  Etymology notes:  {has_etym}")
    print(f"  Formation type:   {has_ft}")
    print(f"  Historical phon:  {has_hp}")
    print(f"  Shuowen entry:    {has_sw}")
    print("\nNext: run python build_site.py")


if __name__ == "__main__":
    build()
