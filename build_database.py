#!/usr/bin/env python3
"""
Build a unified Chinese character etymology database from multiple open sources.

Sources integrated:
  1. Make Me a Hanzi (LGPL v3) -- etymology types, IDS decomposition
  2. Dong Chinese / chinese-lexicon (CC BY-SA 4.0) -- component function tags
  3. Unicode Unihan (Unicode ToS) -- readings, definitions, radical-stroke
  4. CJKVI-IDS (GPLv2) -- Ideographic Description Sequences
  5. CJK Decomposition Data (MIT) -- structural decomposition
  6. Shuowen Jiezi digitized (Apache 2.0) -- classical etymology
  7. Kangxi Dictionary (MIT) -- definitions
  8. Baxter-Sagart (free academic) -- Old/Middle Chinese reconstructions
  9. Wiktionary/kaikki.org (CC BY-SA 3.0) -- etymology narratives
 10. CC-CEDICT (CC BY-SA 4.0) -- definitions
 11. EVOBC metadata -- historical glyph availability
"""

import json
import csv
import re
import sqlite3
from collections import defaultdict
from pathlib import Path

# Pinyin tone mark -> number conversion
_TONE_MAP = {}
for _vowel, _toned in [
    ('a', 'āáǎà'), ('e', 'ēéěè'), ('i', 'īíǐì'),
    ('o', 'ōóǒò'), ('u', 'ūúǔù'), ('v', 'ǖǘǚǜ'), ('ü', 'ǖǘǚǜ'),
]:
    for _tone, _ch in enumerate(_toned, 1):
        _TONE_MAP[_ch] = (_vowel, _tone)

def pinyin_to_numbered(py):
    """Convert tone-marked pinyin to numbered: 'shàng' -> 'shang4'."""
    if not py:
        return ""
    tone = 5  # neutral
    result = []
    for ch in py:
        if ch in _TONE_MAP:
            vowel, tone = _TONE_MAP[ch]
            result.append(vowel)
        else:
            result.append(ch)
    return "".join(result) + (str(tone) if tone < 5 else "")

SOURCES_DIR = Path("sources")
OUTPUT_DIR = Path("output")
OUTPUT_DIR.mkdir(exist_ok=True)

# ---------------------------------------------------------------------------
# Formation type normalization & extraction
# ---------------------------------------------------------------------------
FORMATION_TYPE_CANONICAL = {
    "pictophonetic": "phono-semantic",
    "pictographic": "pictographic",
    "ideographic": "ideographic",
    "phono-semantic": "phono-semantic",
    "pictographic/ideographic": "pictographic",
    "compound-ideographic": "ideographic",
    "mixed-iconic": "ideographic",
}

# Patterns to extract formation type from Wiktionary etymology text
WIKTIONARY_FORMATION_PATTERNS = [
    (r"[Pp]hono-semantic compound\b|形聲|形声", "phono-semantic"),
    (r"[Pp]ictogram\b|象形", "pictographic"),
    (r"[Ii]deogrammic compound\b|會意|会意", "ideographic"),
    (r"[Ss]imple ideograph|指事", "indicative"),
    (r"[Pp]honetic loan\b|假借", "phonetic-loan"),
    (r"[Dd]erivative cognate|轉注|转注", "derivative-cognate"),
]

def extract_wiktionary_formation_type(etym_text):
    """Extract formation type from Wiktionary etymology text using known patterns."""
    if not etym_text:
        return None
    for pattern, ftype in WIKTIONARY_FORMATION_PATTERNS:
        if re.search(pattern, etym_text):
            return ftype
    return None

def extract_shuowen_formation_type(explanation):
    """Extract formation type hints from Shuowen explanation text."""
    if not explanation:
        return None
    # Strip radical declarations -- "凡X之屬皆从X" is not a formation claim
    core = re.sub(r'凡.{1,3}之屬皆从.{1,3}[。]?', '', explanation)
    # 从X, Y聲 = phono-semantic compound (形聲)
    if re.search(r'聲[。，]|聲$', core) and '从' in core:
        return "phono-semantic"
    # 象形 or 象X之形 = pictographic (use regex, not string literal)
    if '象形' in core or re.search(r'象.+之形', core):
        return "pictographic"
    # 指事 = indicative
    if '指事' in core:
        return "indicative"
    # 从X从Y (no 聲) = ideographic compound (need 2+ 从 in the core text)
    from_count = len(re.findall(r'从', core))
    if from_count >= 2 and '聲' not in core:
        return "ideographic"
    # Single 从X = semantic derivation (ideographic)
    if from_count == 1 and '聲' not in core:
        return "ideographic"
    return None

def normalize_formation_type(ftype):
    """Normalize formation type to canonical form."""
    if not ftype:
        return None
    return FORMATION_TYPE_CANONICAL.get(ftype, ftype)

def compute_confidence(record):
    """Compute a confidence score (0-100) for the etymology of a character."""
    score = 0

    # Number of etymology sources (max 30 points)
    etym_sources = set()
    for note in record.get("etymology_notes", []):
        etym_sources.add(note.get("source", ""))
    score += min(len(etym_sources) * 10, 30)

    # Formation type agreement across sources (max 25 points)
    formation_claims = record.get("_formation_claims", {})
    if formation_claims:
        normalized = [normalize_formation_type(v) for v in formation_claims.values() if v]
        normalized = [n for n in normalized if n]
        if normalized:
            most_common = max(set(normalized), key=normalized.count)
            agreement_ratio = normalized.count(most_common) / len(normalized)
            score += int(agreement_ratio * 25)

    # Shuowen entry exists (10 points)
    if record.get("shuowen"):
        score += 10

    # Baxter-Sagart exists (10 points)
    if record.get("historical_phonology"):
        score += 10

    # Historical glyphs exist (10 points)
    glyphs = record.get("historical_glyphs", {})
    if glyphs.get("image_count", 0) > 0:
        era_count = len(glyphs.get("eras_available", []))
        score += min(era_count * 2, 10)

    # Has decomposition (5 points)
    if record.get("ids") or record.get("decomposition_ids"):
        score += 5

    # Has definitions (5 points)
    if record.get("definitions"):
        score += 5

    # Has readings (5 points)
    if record.get("readings"):
        score += 5

    return min(score, 100)

# ---------------------------------------------------------------------------
# 1. Unihan
# ---------------------------------------------------------------------------
def parse_unihan():
    """Parse Unihan database files into per-character dicts."""
    print("[1/11] Parsing Unihan database...")
    chars = defaultdict(dict)
    unihan_dir = SOURCES_DIR / "unihan"

    files_to_parse = [
        "Unihan_Readings.txt",
        "Unihan_RadicalStrokeCounts.txt",
        "Unihan_Variants.txt",
        "Unihan_DictionaryLikeData.txt",
        "Unihan_IRGSources.txt",
    ]

    fields_we_want = {
        "kDefinition", "kMandarin", "kCantonese", "kJapaneseOn", "kJapaneseKun",
        "kKorean", "kVietnamese", "kHanyuPinyin", "kTang",
        "kRSUnicode", "kTotalStrokes", "kPhonetic",
        "kSemanticVariant", "kTraditionalVariant", "kSimplifiedVariant",
        "kSpecializedSemanticVariant", "kCompatibilityVariant",
        "kIICore",
    }

    for fname in files_to_parse:
        fpath = unihan_dir / fname
        if not fpath.exists():
            print(f"  Warning: {fpath} not found, skipping")
            continue
        with open(fpath, "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith("#") or not line.strip():
                    continue
                parts = line.strip().split("\t", 2)
                if len(parts) < 3:
                    continue
                codepoint, prop, value = parts
                if prop not in fields_we_want:
                    continue
                # Convert U+XXXX to character
                cp = int(codepoint[2:], 16)
                ch = chr(cp)
                chars[ch][prop] = value

    print(f"  Parsed {len(chars)} unique characters from Unihan")
    return dict(chars)


# ---------------------------------------------------------------------------
# 2. Make Me a Hanzi
# ---------------------------------------------------------------------------
def parse_makemeahanzi():
    """Parse Make Me a Hanzi dictionary.txt."""
    print("[2/11] Parsing Make Me a Hanzi...")
    chars = {}
    fpath = SOURCES_DIR / "makemeahanzi" / "dictionary.txt"
    if not fpath.exists():
        print(f"  Warning: {fpath} not found")
        return chars
    with open(fpath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            entry = json.loads(line)
            ch = entry.get("character", "")
            if ch:
                chars[ch] = {
                    "definition": entry.get("definition", ""),
                    "pinyin": entry.get("pinyin", []),
                    "decomposition": entry.get("decomposition", ""),
                    "radical": entry.get("radical", ""),
                    "etymology": entry.get("etymology"),  # may be None
                }
    print(f"  Parsed {len(chars)} characters from Make Me a Hanzi")
    return chars


# ---------------------------------------------------------------------------
# 3. Dong Chinese etymology (from pre-extracted JSON via Node.js)
# ---------------------------------------------------------------------------
def parse_dong_chinese():
    """Parse Dong Chinese etymology from pre-extracted JSON (via extract_dong_chinese.mjs)."""
    print("[3/11] Parsing Dong Chinese etymology...")
    chars = {}
    fpath = SOURCES_DIR / "chinese-lexicon" / "dong_etymologies.json"
    if not fpath.exists():
        print(f"  Warning: {fpath} not found. Run: node extract_dong_chinese.mjs")
        return chars

    with open(fpath, "r", encoding="utf-8") as f:
        raw = json.load(f)

    for ch, etym in raw.items():
        components = etym.get("components", [])
        comp_types = [c.get("type", "") for c in components]
        has_sound = "sound" in comp_types
        has_meaning = "meaning" in comp_types
        has_iconic = "iconic" in comp_types

        entry = {
            "notes": etym.get("notes", ""),
            "definition": etym.get("definition", ""),
            "components": components,
        }

        if has_sound and has_meaning:
            entry["type"] = "phono-semantic"
            for c in components:
                if c.get("type") == "meaning":
                    entry["semantic"] = c.get("char", "")
                elif c.get("type") == "sound":
                    entry["phonetic"] = c.get("char", "")
        elif has_meaning and not has_sound and not has_iconic:
            entry["type"] = "compound-ideographic"
        elif has_iconic and not has_sound and not has_meaning:
            entry["type"] = "pictographic/ideographic"
        elif has_iconic:
            entry["type"] = "mixed-iconic"
        else:
            entry["type"] = "other"

        chars[ch] = entry

    print(f"  Parsed {len(chars)} characters from Dong Chinese")
    return chars


# ---------------------------------------------------------------------------
# 4. CJKVI-IDS
# ---------------------------------------------------------------------------
def parse_cjkvi_ids():
    """Parse CJKVI-IDS ids.txt for Ideographic Description Sequences."""
    print("[4/11] Parsing CJKVI-IDS...")
    chars = {}
    fpath = SOURCES_DIR / "cjkvi-ids" / "ids.txt"
    if not fpath.exists():
        print(f"  Warning: {fpath} not found")
        return chars
    with open(fpath, "r", encoding="utf-8") as f:
        for line in f:
            if line.startswith("#") or not line.strip():
                continue
            parts = line.strip().split("\t")
            if len(parts) >= 3:
                ch = parts[1]
                ids = parts[2]
                # Some entries have multiple IDS variants separated by tab
                chars[ch] = ids
    print(f"  Parsed {len(chars)} IDS entries from CJKVI-IDS")
    return chars


# ---------------------------------------------------------------------------
# 5. CJK Decomposition Data
# ---------------------------------------------------------------------------
def parse_cjk_decomp():
    """Parse cjk-decomp.txt."""
    print("[5/11] Parsing CJK Decomposition Data...")
    chars = {}
    fpath = SOURCES_DIR / "cjk-decomp" / "cjk-decomp.txt"
    if not fpath.exists():
        print(f"  Warning: {fpath} not found")
        return chars
    with open(fpath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            # Format: char:type(components) or codepoint:type(components)
            colon_idx = line.index(":")
            char_part = line[:colon_idx]
            decomp = line[colon_idx + 1:]
            # Only include actual Unicode characters (not numeric codepoints)
            if len(char_part) == 1:
                chars[char_part] = decomp
    print(f"  Parsed {len(chars)} entries from CJK Decomposition Data")
    return chars


# ---------------------------------------------------------------------------
# 6. Shuowen Jiezi
# ---------------------------------------------------------------------------
def parse_shuowen():
    """Parse digitized Shuowen Jiezi JSON files."""
    print("[6/11] Parsing Shuowen Jiezi...")
    chars = {}
    shuowen_dir = SOURCES_DIR / "shuowen" / "data"
    if not shuowen_dir.exists():
        print(f"  Warning: {shuowen_dir} not found")
        return chars

    for fpath in sorted(shuowen_dir.glob("*.json"), key=lambda p: int(p.stem)):
        with open(fpath, "r", encoding="utf-8") as f:
            try:
                entry = json.load(f)
            except json.JSONDecodeError:
                continue
        ch = entry.get("wordhead", "")
        if not ch:
            continue
        chars[ch] = {
            "explanation": entry.get("explanation", ""),
            "radical": entry.get("radical", ""),
            "pronunciation": entry.get("pronunciation", ""),
            "pinyin": entry.get("pinyin_full", ""),
            "seal_character": entry.get("seal_character", ""),
            "components": entry.get("components", []),
            "xuan_note": entry.get("xuan_note", ""),
            "kai_note": entry.get("kai_note", ""),
            "duan_notes": entry.get("duan_notes", []),
            "variants": [
                {"wordhead": v.get("wordhead", ""), "explanation": v.get("explanation", "")}
                for v in entry.get("variants", [])
            ],
        }

    print(f"  Parsed {len(chars)} characters from Shuowen Jiezi")
    return chars


# ---------------------------------------------------------------------------
# 7. Kangxi Dictionary
# ---------------------------------------------------------------------------
def parse_kangxi():
    """Parse Kangxi Dictionary XLSX file."""
    print("[7/11] Parsing Kangxi Dictionary...")
    chars = {}
    fpath = SOURCES_DIR / "kangxi-dictionary" / "kx_full.xlsx"
    if not fpath.exists():
        print(f"  Warning: {fpath} not found")
        return chars

    try:
        import openpyxl
    except ImportError:
        print("  Warning: openpyxl not installed, skipping Kangxi. Install with: pip install openpyxl")
        return chars

    wb = openpyxl.load_workbook(fpath, read_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        return chars

    # Try to identify header row
    header = rows[0]
    # Columns: 繁體(0) 簡體(1) 字典路徑(2) 集1(3) 集2(4) 部首(5) 筆劃數(6) 康熙字典解釋(7)
    for row in rows[1:]:
        if row and row[0] and isinstance(row[0], str) and len(row[0]) == 1:
            ch = row[0]
            entry = {}
            if len(row) > 1 and row[1]:
                entry["simplified"] = str(row[1])
            if len(row) > 3 and row[3]:
                entry["radical"] = str(row[3])
            if len(row) > 5 and row[5]:
                entry["radical_char"] = str(row[5])
            if len(row) > 6 and row[6]:
                entry["stroke_count"] = row[6]
            if len(row) > 7 and row[7]:
                entry["explanation"] = str(row[7])
            chars[ch] = entry

    wb.close()
    print(f"  Parsed {len(chars)} characters from Kangxi Dictionary")
    return chars


# ---------------------------------------------------------------------------
# 8. Baxter-Sagart Old Chinese
# ---------------------------------------------------------------------------
def parse_baxter_sagart():
    """Parse Baxter-Sagart Old Chinese reconstruction TSV."""
    print("[8/11] Parsing Baxter-Sagart...")
    chars = defaultdict(list)
    fpath = SOURCES_DIR / "baxter-sagart" / "baxtersagart.tsv"
    if not fpath.exists():
        print(f"  Warning: {fpath} not found")
        return dict(chars)

    with open(fpath, "r", encoding="utf-8") as f:
        reader = csv.reader(f, delimiter="\t")
        header = next(reader, None)
        if not header:
            return dict(chars)
        for row in reader:
            if len(row) < 6:
                continue
            ch = row[0].strip()
            if not ch or len(ch) != 1:
                continue
            entry = {
                "pinyin": row[1].strip() if len(row) > 1 else "",
                "middle_chinese": row[2].strip() if len(row) > 2 else "",
                "old_chinese": row[4].strip() if len(row) > 4 else "",
                "gloss": row[5].strip() if len(row) > 5 else "",
                "gsr": row[6].strip() if len(row) > 6 else "",
            }
            chars[ch].append(entry)

    print(f"  Parsed {len(chars)} unique characters ({sum(len(v) for v in chars.values())} entries) from Baxter-Sagart")
    return dict(chars)


# ---------------------------------------------------------------------------
# 9. Wiktionary (kaikki.org)
# ---------------------------------------------------------------------------
def parse_wiktionary():
    """Parse Wiktionary Chinese JSONL for etymology data on single characters."""
    print("[9/11] Parsing Wiktionary etymology data...")
    chars = defaultdict(list)
    fpath = SOURCES_DIR / "wiktionary" / "kaikki.org-dictionary-Chinese.jsonl"
    if not fpath.exists():
        print(f"  Warning: {fpath} not found")
        return dict(chars)

    with open(fpath, "r", encoding="utf-8") as f:
        for line in f:
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            word = entry.get("word", "")
            # Only single CJK characters
            if len(word) != 1:
                continue
            cp = ord(word)
            if not (0x4E00 <= cp <= 0x9FFF or 0x3400 <= cp <= 0x4DBF or
                    0x20000 <= cp <= 0x2A6DF or 0xF900 <= cp <= 0xFAFF):
                continue

            etym_text = entry.get("etymology_text", "")
            pos = entry.get("pos", "")

            # Collect glosses
            glosses = []
            for sense in entry.get("senses", []):
                for g in sense.get("glosses", []):
                    glosses.append(g)

            # Extract OC/MC pronunciations from sounds field
            oc_zhengzhang = None
            oc_baxter_sagart = None
            mc_baxter_sagart = None
            for s in entry.get("sounds", []):
                tags = s.get("tags", [])
                zh_pron = s.get("zh_pron", "")
                if not zh_pron:
                    continue
                if "Old-Chinese" in tags and "Zhengzhang" in tags:
                    oc_zhengzhang = zh_pron.strip("/ ")
                elif "Old-Chinese" in tags and "Baxter-Sagart" in tags:
                    oc_baxter_sagart = zh_pron.strip("/ ")
                elif "Middle-Chinese" in tags and "Baxter-Sagart" in tags:
                    mc_baxter_sagart = zh_pron.strip("/ ")

            record = {}
            if etym_text:
                record["etymology_text"] = etym_text
            if glosses:
                record["glosses"] = glosses
            if pos:
                record["pos"] = pos
            if oc_zhengzhang:
                record["oc_zhengzhang"] = oc_zhengzhang
            if oc_baxter_sagart:
                record["oc_baxter_sagart"] = oc_baxter_sagart
            if mc_baxter_sagart:
                record["mc_baxter_sagart"] = mc_baxter_sagart

            if record:
                chars[word].append(record)

    print(f"  Parsed {len(chars)} unique characters from Wiktionary")
    return dict(chars)


# ---------------------------------------------------------------------------
# 10. CC-CEDICT
# ---------------------------------------------------------------------------
def parse_cedict():
    """Parse CC-CEDICT for definitions."""
    print("[10/11] Parsing CC-CEDICT...")
    chars = defaultdict(list)
    fpath = SOURCES_DIR / "cedict" / "cedict_1_0_ts_utf-8_mdbg.txt"
    if not fpath.exists():
        print(f"  Warning: {fpath} not found")
        return dict(chars)

    with open(fpath, "r", encoding="utf-8") as f:
        for line in f:
            if line.startswith("#") or not line.strip():
                continue
            # Format: Traditional Simplified [pinyin] /def1/def2/
            m = re.match(r'^(\S+)\s+(\S+)\s+\[([^\]]+)\]\s+/(.+)/$', line.strip())
            if not m:
                continue
            trad, simp, pinyin, defs = m.groups()
            # Only single characters
            if len(trad) == 1:
                chars[trad].append({
                    "traditional": trad,
                    "simplified": simp,
                    "pinyin": pinyin,
                    "definitions": defs.split("/"),
                })
            if len(simp) == 1 and simp != trad:
                chars[simp].append({
                    "traditional": trad,
                    "simplified": simp,
                    "pinyin": pinyin,
                    "definitions": defs.split("/"),
                })

    print(f"  Parsed {len(chars)} unique single characters from CC-CEDICT")
    return dict(chars)


# ---------------------------------------------------------------------------
# 11. EVOBC metadata
# ---------------------------------------------------------------------------
def parse_evobc():
    """Parse EVOBC metadata for historical glyph availability."""
    print("[11/11] Parsing EVOBC metadata...")
    chars = {}
    kv_path = SOURCES_DIR / "evobc" / "Key&Value.json"
    list_path = SOURCES_DIR / "evobc" / "List_of_EVOBC.json"

    if not kv_path.exists():
        print(f"  Warning: {kv_path} not found")
        return chars

    with open(kv_path, "r", encoding="utf-8") as f:
        key_value = json.load(f)

    era_names = {
        0: "oracle_bone",
        1: "bronze_inscription",
        2: "spring_autumn",
        3: "warring_states",
        4: "seal_script",
        5: "clerical_script",
    }

    if list_path.exists():
        with open(list_path, "r", encoding="utf-8") as f:
            evobc_list = json.load(f)
        for entry in evobc_list:
            ch = entry.get("Character", "")
            if not ch:
                continue
            images = entry.get("images", [])
            eras_present = set()
            for img in images:
                era = img.get("era")
                if era is not None:
                    eras_present.add(era_names.get(era, f"era_{era}"))
            chars[ch] = {
                "evobc_id": entry.get("ID", ""),
                "image_count": len(images),
                "eras": sorted(eras_present),
            }
    else:
        # Fallback: just use Key&Value.json
        for evobc_id, ch in key_value.items():
            chars[ch] = {"evobc_id": evobc_id, "image_count": 0, "eras": []}

    print(f"  Parsed {len(chars)} characters from EVOBC metadata")
    return chars


# ---------------------------------------------------------------------------
# 12. NK2028 Guangyun (Middle Chinese phonology)
# ---------------------------------------------------------------------------
def parse_guangyun():
    """Parse NK2028 Guangyun CSV for Middle Chinese phonological data."""
    print("[12/15] Parsing NK2028 Guangyun...")
    chars = defaultdict(list)
    fpath = SOURCES_DIR / "nk2028" / "tshet-uinh-data" / "韻書" / "廣韻.csv"
    if not fpath.exists():
        print(f"  Warning: {fpath} not found")
        return dict(chars)

    with open(fpath, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            ch = row.get("字頭", "").strip()
            if not ch or len(ch) != 1:
                continue
            entry = {
                "phonological_position": row.get("音韻地位", ""),
                "fanqie": row.get("反切", ""),
                "gloss": row.get("釋義", "")[:200],  # truncate long glosses
            }
            chars[ch].append(entry)

    # Deduplicate: keep unique phonological positions per character
    deduped = {}
    for ch, entries in chars.items():
        seen = set()
        unique = []
        for e in entries:
            pos = e["phonological_position"]
            if pos not in seen:
                seen.add(pos)
                unique.append(e)
        deduped[ch] = unique

    print(f"  Parsed {len(deduped)} unique characters from Guangyun")
    return deduped


# ---------------------------------------------------------------------------
# 13. ytenx Old Chinese reconstruction (Zhengzhang Shangfang system)
# ---------------------------------------------------------------------------
def parse_ytenx_oc():
    """Parse ytenx Old Chinese reconstruction data."""
    print("[13/15] Parsing ytenx Old Chinese reconstructions...")
    chars = defaultdict(list)
    fpath = SOURCES_DIR / "ytenx" / "ytenx" / "sync" / "dciangx" / "DrienghTriang.txt"
    if not fpath.exists():
        print(f"  Warning: {fpath} not found")
        return dict(chars)

    with open(fpath, "r", encoding="utf-8") as f:
        header_line = f.readline()
        # Fields: 字 廣韻聲 廣韻韻 聲調 等 重紐 開合 上字 下字 聲符 韻部 韻部細分 擬音 ...
        for line in f:
            parts = line.strip().split(" ")
            if len(parts) < 13:
                continue
            ch = parts[0]
            if len(ch) != 1:
                continue
            entry = {
                "guangyun_initial": parts[1],
                "guangyun_rhyme": parts[2],
                "tone": parts[3],
                "division": parts[4],
                "open_closed": parts[6] if len(parts) > 6 else "",
                "phonetic_component": parts[9] if len(parts) > 9 else "",
                "rhyme_group": parts[10] if len(parts) > 10 else "",
                "old_chinese_zhengzhang": parts[12] if len(parts) > 12 else "",
            }
            # Only add if there's a reconstruction
            if entry["old_chinese_zhengzhang"]:
                chars[ch].append(entry)

    print(f"  Parsed {len(chars)} unique characters from ytenx Old Chinese")
    return dict(chars)


# ---------------------------------------------------------------------------
# 14. Character frequency (hanziDB)
# ---------------------------------------------------------------------------
def parse_frequency():
    """Parse character frequency ranking from hanziDB."""
    print("[14/16] Parsing character frequency data...")
    chars = {}
    fpath = SOURCES_DIR / "frequency" / "hanziDB.csv"
    if not fpath.exists():
        print(f"  Warning: {fpath} not found")
        return chars

    with open(fpath, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            ch = row.get("character", "").strip()
            if not ch or len(ch) != 1:
                continue
            try:
                rank = int(row.get("frequency_rank", 0))
            except ValueError:
                continue
            hsk = row.get("hsk_level", "")
            chars[ch] = {
                "frequency_rank": rank,
                "hsk_level": int(hsk) if hsk and hsk.isdigit() else None,
            }

    print(f"  Parsed {len(chars)} characters with frequency data")
    return chars


# ---------------------------------------------------------------------------
# 15. AnimCJK (HSK 3.0 levels + frequency tier)
# ---------------------------------------------------------------------------
def parse_animcjk():
    """Parse AnimCJK dictionary for HSK 3.0 levels and frequency tiers."""
    print("[15/17] Parsing AnimCJK data...")
    chars = {}
    fpath = SOURCES_DIR / "animcjk" / "dictionaryZhHans.txt"
    if not fpath.exists():
        print(f"  Warning: {fpath} not found")
        return chars

    with open(fpath, "r", encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            ch = d.get("character", "")
            if len(ch) != 1:
                continue
            entry = {}
            sets = d.get("set", [])
            # Extract HSK 3.0 level
            for s in sets:
                if s.startswith("hsk3"):
                    try:
                        entry["hsk3_level"] = int(s[3:])
                    except ValueError:
                        pass
            # Extract frequency tier
            if "frequent2500" in sets:
                entry["frequency_tier"] = "top_2500"
            elif "lessFrequent1000" in sets:
                entry["frequency_tier"] = "3500_plus"
            elif "commonNotFrequent" in sets or "commonNotHsk3NorFrequent" in sets:
                entry["frequency_tier"] = "common"
            if entry:
                chars[ch] = entry

    print(f"  Parsed {len(chars)} characters from AnimCJK")
    return chars


# ---------------------------------------------------------------------------
# 16. Unihan kPhonetic classes
# ---------------------------------------------------------------------------
def parse_phonetic_classes():
    """Parse Unihan kPhonetic field into phonetic family groupings."""
    print("[16/18] Parsing Unihan kPhonetic classes...")
    char_to_classes = {}
    class_to_chars = defaultdict(list)
    fpath = SOURCES_DIR / "unihan" / "Unihan_DictionaryLikeData.txt"
    if not fpath.exists():
        print(f"  Warning: {fpath} not found")
        return char_to_classes, class_to_chars

    with open(fpath, "r", encoding="utf-8") as f:
        for line in f:
            if "kPhonetic" not in line or line.startswith("#"):
                continue
            parts = line.strip().split("\t")
            if len(parts) < 3 or parts[1] != "kPhonetic":
                continue
            cp = int(parts[0][2:], 16)
            ch = chr(cp)
            classes = [c.rstrip("*") for c in parts[2].split()]
            char_to_classes[ch] = classes
            for cls in classes:
                class_to_chars[cls].append(ch)

    print(f"  Parsed {len(char_to_classes)} characters in {len(class_to_chars)} phonetic classes")
    return char_to_classes, class_to_chars


# ---------------------------------------------------------------------------
# 17. Sagart Sino-Tibetan cognates
# ---------------------------------------------------------------------------
def parse_sino_tibetan_cognates():
    """Parse pre-built Chinese-to-cognate mapping from Sagart CLDF data."""
    print("[17/18] Parsing Sino-Tibetan cognate data...")
    chars = defaultdict(list)
    fpath = SOURCES_DIR / "stedt" / "sagartst" / "chinese_cognates.json"
    if not fpath.exists():
        print(f"  Warning: {fpath} not found (run cognate extraction first)")
        return dict(chars)

    with open(fpath, "r", encoding="utf-8") as f:
        entries = json.load(f)

    for entry in entries:
        ch = entry.get("char", "")
        if len(ch) == 1:
            chars[ch].append({
                "concept": entry.get("concept", ""),
                "cognacy_set": entry.get("cognacy_set", ""),
                "cognate_count": entry.get("cognate_count", 0),
                "sample_cognates": entry.get("sample_cognates", [])[:3],
            })

    print(f"  Parsed {len(chars)} characters with Sino-Tibetan cognate data")
    return dict(chars)


# ---------------------------------------------------------------------------
# Shuowen phonetic extraction
# ---------------------------------------------------------------------------
def extract_shuowen_phonetic(explanation):
    """Extract phonetic component from Shuowen explanation text.

    Handles patterns:
      从X Y聲    -- standard phono-semantic
      从X，Y聲   -- with comma
      从X从Y，Z聲 -- two semantic + one phonetic
      从X Y省聲  -- abbreviated phonetic
      从X Y亦聲  -- component serves both roles
    The phonetic is always the single character immediately before 聲/省聲/亦聲.
    """
    if not explanation or '聲' not in explanation or '从' not in explanation:
        return None
    m = re.search(r'(\w)(省聲|亦聲|聲)', explanation)
    if m:
        phonetic = m.group(1)
        if len(phonetic) == 1 and phonetic not in ('之', '其', '而', '从'):
            return phonetic
    return None


# ---------------------------------------------------------------------------
# Local glyph manifest loading
# ---------------------------------------------------------------------------
def load_glyph_manifests():
    """Load local SVG glyph manifests (Dong Chinese + Wikimedia seal).

    Returns two dicts, both keyed by character:
      dong_glyphs[char] = ["oracle", "bronze", "seal", ...]
      wikimedia_glyphs[char] = ["ACC-s00123.svg", ...]
    Gracefully returns empty dicts if manifests are missing.
    """
    dong_glyphs = {}
    wm_glyphs = defaultdict(list)

    dong_path = OUTPUT_DIR / "glyphs" / "dong_chinese" / "manifest.json"
    if dong_path.exists():
        with open(dong_path, "r", encoding="utf-8") as f:
            dong_manifest = json.load(f)
        for ch, scripts in dong_manifest.items():
            dong_glyphs[ch] = sorted(scripts.keys())
        print(f"  Loaded Dong Chinese glyph manifest: {len(dong_glyphs)} characters")
    else:
        print(f"  Dong Chinese glyph manifest not found at {dong_path}, skipping")

    wm_path = OUTPUT_DIR / "glyphs" / "wikimedia_seal" / "manifest.json"
    if wm_path.exists():
        with open(wm_path, "r", encoding="utf-8") as f:
            wm_manifest = json.load(f)
        for fname, info in wm_manifest.items():
            ch = info.get("character", "")
            if ch:
                wm_glyphs[ch].append(fname)
        # Sort filenames for deterministic output
        for ch in wm_glyphs:
            wm_glyphs[ch] = sorted(wm_glyphs[ch])
        print(f"  Loaded Wikimedia seal glyph manifest: {len(wm_glyphs)} characters")
    else:
        print(f"  Wikimedia seal glyph manifest not found at {wm_path}, skipping")

    return dong_glyphs, dict(wm_glyphs)


# ---------------------------------------------------------------------------
# Merge all sources into unified records
# ---------------------------------------------------------------------------
def merge_all(unihan, mmah, dong, cjkvi_ids, cjk_decomp, shuowen,
              kangxi, baxter_sagart, wiktionary, cedict, evobc,
              guangyun, ytenx_oc, frequency, animcjk, st_cognates):
    """Merge all parsed sources into a single dict keyed by character."""
    print("\nMerging all sources...")

    # Load local glyph manifests
    dong_glyphs, wikimedia_glyphs = load_glyph_manifests()

    # Load Shuowen translations (if available)
    shuowen_translations = {}
    sw_trans_path = OUTPUT_DIR / "shuowen_translations.json"
    if sw_trans_path.exists():
        with open(sw_trans_path, "r", encoding="utf-8") as f:
            shuowen_translations = json.load(f)
        print(f"  Loaded Shuowen translations: {len(shuowen_translations)} entries")

    # Start with the Unihan universe -- every character known to Unicode
    all_chars = set(unihan.keys())
    # Add characters from other sources too
    for source in [mmah, dong, cjkvi_ids, cjk_decomp, shuowen,
                   kangxi, baxter_sagart, wiktionary, cedict, evobc,
                   guangyun, ytenx_oc, frequency, animcjk, st_cognates]:
        all_chars.update(source.keys())

    print(f"  Total unique characters across all sources: {len(all_chars)}")

    # Semantic field mapping from radical/semantic component -> meaning category
    RADICAL_SEMANTICS = {
        "水": "water/liquid", "氵": "water/liquid", "冫": "ice/cold",
        "火": "fire/heat", "灬": "fire/heat",
        "木": "wood/tree", "艹": "plant/grass", "⺾": "plant/grass", "禾": "grain/crop",
        "竹": "bamboo", "⺮": "bamboo", "米": "rice/grain",
        "金": "metal", "钅": "metal", "釒": "metal",
        "土": "earth/ground", "石": "stone", "山": "mountain",
        "日": "sun/day/time", "月": "moon/month", "⺼": "flesh/body",
        "心": "heart/emotion", "忄": "heart/emotion",
        "手": "hand/action", "扌": "hand/action", "又": "hand",
        "足": "foot/walk", "⻊": "foot/walk", "辵": "movement", "辶": "movement",
        "口": "mouth/speech", "言": "speech/language", "讠": "speech/language",
        "目": "eye/seeing", "見": "seeing", "见": "seeing",
        "耳": "ear/hearing",
        "人": "person", "亻": "person", "女": "woman/female", "子": "child",
        "食": "food/eating", "饣": "food/eating", "飠": "food/eating",
        "衣": "clothing", "衤": "clothing",
        "刀": "knife/cutting", "刂": "knife/cutting",
        "弓": "bow/weapon", "戈": "weapon", "矢": "arrow",
        "馬": "horse/animal", "犬": "dog/animal", "犭": "animal",
        "牛": "cattle", "羊": "sheep/animal",
        "魚": "fish", "鳥": "bird", "鱼": "fish", "鸟": "bird",
        "虫": "insect/creature",
        "貝": "money/value", "贝": "money/value",
        "車": "vehicle", "车": "vehicle", "舟": "boat",
        "糸": "silk/thread", "纟": "silk/thread",
        "玉": "jade/gem",
        "阜": "hill/mound",
        "雨": "rain/weather", "风": "wind", "風": "wind",
        "疒": "illness/disease",
        "示": "spirit/ritual", "礻": "spirit/ritual",
        "���": "door/gate", "门": "door/gate",
        "宀": "roof/building", "广": "building",
        "力": "force/strength",
        "田": "field/agriculture",
        "网": "net", "罒": "net",
        "皮": "skin/leather", "革": "leather",
        "骨": "bone", "肉": "flesh/body",
        "酉": "wine/fermentation", "鬼": "ghost/spirit",
        "頁": "head/face", "页": "head/face",
    }

    # Pre-compute: Kangxi radical number -> radical character mapping
    kangxi_radical_chars = "一丨丶丿乙亅二亠人儿入八冂冖冫几凵刀力勹匕匚匸十卜卩厂厶又口囗土士夂夊夕大女子宀寸小尢尸屮山巛工己巾干幺广廴廾弋弓彐彡彳心戈戶手支攴文斗斤方无日曰月木欠止歹殳毋比毛氏气水火爪父爻爿片牙牛犬玄玉瓜瓦甘生用田疋疒癶白皮皿目矛矢石示禸禾穴立竹米糸缶网羊羽老而耒耳聿肉臣自至臼舌舛舟艮色艸虍虫血行衣襾見角言谷豆豕豸貝赤走足身車辛辰辵邑酉釆里金長門阜隶隹雨靑非面革韋韭音頁風飛食首香馬骨高髟鬥鬯鬲鬼魚鳥鹵鹿麥麻黃黍黑黹黽鼎鼓鼠鼻齊齒龍龜龠"
    kangxi_num_to_char = {}
    for i, rc in enumerate(kangxi_radical_chars):
        kangxi_num_to_char[i + 1] = rc
    # Also build reverse: radical char -> number
    kangxi_char_to_num = {v: k for k, v in kangxi_num_to_char.items()}
    # Common radical variants -> canonical radical
    radical_variants = {
        "亻": "人", "氵": "水", "扌": "手", "忄": "心", "犭": "犬",
        "礻": "示", "衤": "衣", "饣": "食", "钅": "金", "纟": "糸",
        "讠": "言", "贝": "貝", "车": "車", "鱼": "魚", "齿": "齒",
        "飠": "食", "灬": "火", "攵": "攴", "辶": "辵", "阝": "邑",
        "刂": "刀", "卩": "卩", "⺮": "竹", "⺾": "艸", "⺼": "肉",
        "罒": "网", "⻊": "足", "月": "肉",  # 月 is often 肉 as component
    }

    # Pre-compute radical numbers from Unihan for phonetic inference
    char_to_radical_num = {}
    for ch_key, u_data in unihan.items():
        rs = u_data.get("kRSUnicode", "")
        if rs:
            try:
                char_to_radical_num[ch_key] = int(rs.split(".")[0])
            except ValueError:
                pass

    merged = {}
    inferred_phonetic_count = 0
    shuowen_phonetic_count = 0
    local_glyph_count = 0
    for ch in sorted(all_chars):
        record = {"character": ch, "codepoint": f"U+{ord(ch):04X}"}

        # --- Unihan data ---
        u = unihan.get(ch, {})
        if u:
            record["definitions"] = u.get("kDefinition", "")
            record["readings"] = {}
            if "kMandarin" in u:
                record["readings"]["mandarin"] = u["kMandarin"]
            if "kCantonese" in u:
                record["readings"]["cantonese"] = u["kCantonese"]
            if "kJapaneseOn" in u:
                record["readings"]["japanese_on"] = u["kJapaneseOn"]
            if "kJapaneseKun" in u:
                record["readings"]["japanese_kun"] = u["kJapaneseKun"]
            if "kKorean" in u:
                record["readings"]["korean"] = u["kKorean"]
            if "kVietnamese" in u:
                record["readings"]["vietnamese"] = u["kVietnamese"]
            if "kTang" in u:
                record["readings"]["tang"] = u["kTang"]
            if "kRSUnicode" in u:
                record["radical_stroke"] = u["kRSUnicode"]
            if "kTotalStrokes" in u:
                record["total_strokes"] = u["kTotalStrokes"]
            if "kPhonetic" in u:
                record["phonetic_class"] = u["kPhonetic"]
            # Variants
            variants = {}
            if "kTraditionalVariant" in u:
                variants["traditional"] = u["kTraditionalVariant"]
            if "kSimplifiedVariant" in u:
                variants["simplified"] = u["kSimplifiedVariant"]
            if "kSemanticVariant" in u:
                variants["semantic"] = u["kSemanticVariant"]
            if variants:
                record["variants"] = variants

        # Track formation type claims from each source for conflict detection
        formation_claims = {}

        # --- Make Me a Hanzi ---
        m = mmah.get(ch)
        if m:
            if not record.get("definitions") and m.get("definition"):
                record["definitions"] = m["definition"]
            record["decomposition_ids"] = m.get("decomposition", "")
            if m.get("etymology"):
                etym = m["etymology"]
                mmah_type = etym.get("type", "")
                if mmah_type:
                    formation_claims["makemeahanzi"] = mmah_type
                if etym.get("type") == "pictophonetic":
                    record["formation_details"] = {
                        "semantic": etym.get("semantic", ""),
                        "phonetic": etym.get("phonetic", ""),
                    }
                if etym.get("hint"):
                    record.setdefault("etymology_notes", []).append({
                        "source": "makemeahanzi",
                        "text": etym["hint"],
                    })

        # --- Dong Chinese ---
        d = dong.get(ch)
        if d:
            if d.get("type"):
                formation_claims["dong_chinese"] = d["type"]
            if d.get("semantic"):
                if "formation_details" not in record:
                    record["formation_details"] = {}
                record["formation_details"]["semantic"] = d["semantic"]
            if d.get("phonetic"):
                if "formation_details" not in record:
                    record["formation_details"] = {}
                record["formation_details"]["phonetic"] = d["phonetic"]
            if d.get("notes"):
                record.setdefault("etymology_notes", []).append({
                    "source": "dong_chinese",
                    "text": d["notes"],
                })
            if d.get("definition") and not record.get("definitions"):
                record["definitions"] = d["definition"]

        # --- CJKVI-IDS ---
        ids = cjkvi_ids.get(ch)
        if ids:
            record["ids"] = ids
            if "decomposition_ids" not in record:
                record["decomposition_ids"] = ids

        # --- CJK Decomposition ---
        decomp = cjk_decomp.get(ch)
        if decomp:
            record["cjk_decomp"] = decomp

        # --- Shuowen Jiezi ---
        sw = shuowen.get(ch)
        if sw:
            record["shuowen"] = {
                "explanation": sw.get("explanation", ""),
                "radical": sw.get("radical", ""),
                "pronunciation_fanqie": sw.get("pronunciation", ""),
                "seal_character": sw.get("seal_character", ""),
                "components": sw.get("components", []),
            }
            if sw.get("xuan_note"):
                record["shuowen"]["xuan_note"] = sw["xuan_note"]
            if sw.get("kai_note"):
                record["shuowen"]["kai_note"] = sw["kai_note"]
            if sw.get("duan_notes"):
                record["shuowen"]["duan_notes"] = sw["duan_notes"]
            if sw.get("variants"):
                record["shuowen"]["variants"] = sw["variants"]
            # Add English translation if available
            sw_trans = shuowen_translations.get(ch, "")
            if sw_trans:
                record["shuowen"]["english"] = sw_trans
            # Extract formation type from Shuowen explanation
            sw_ftype = extract_shuowen_formation_type(sw.get("explanation", ""))
            if sw_ftype:
                formation_claims["shuowen_jiezi"] = sw_ftype
            # Add Shuowen explanation as an etymology note
            if sw.get("explanation"):
                record.setdefault("etymology_notes", []).append({
                    "source": "shuowen_jiezi",
                    "text": sw["explanation"],
                    "caveat": "Classical source (~100 AD). Some etymologies may be incorrect by modern scholarship.",
                })

        # --- Kangxi ---
        kx = kangxi.get(ch)
        if kx:
            record["kangxi"] = {}
            kx_expl = kx.get("explanation", "")
            if kx_expl:
                record["kangxi"]["explanation"] = kx_expl
                # Extract fanqie readings from Kangxi citations
                # Patterns: 【唐韻】德紅切 【集韻】都籠切 【廣韻】...切
                kangxi_fanqie = []
                for m in re.finditer(r'【([^】]+)】(\S{2})切', kx_expl):
                    source = m.group(1)
                    fanqie = m.group(2)
                    kangxi_fanqie.append({"source": source, "fanqie": fanqie})
                if kangxi_fanqie:
                    record["kangxi"]["fanqie_citations"] = kangxi_fanqie
                # Extract Shuowen citation within Kangxi
                sw_cite = re.search(r'【說文】(.{1,60}?)(?:。|　|又|$)', kx_expl)
                if sw_cite:
                    record["kangxi"]["shuowen_citation"] = sw_cite.group(1)
            if kx.get("radical"):
                record["kangxi"]["radical"] = kx["radical"]

        # --- Baxter-Sagart ---
        bs = baxter_sagart.get(ch)
        if bs:
            record["historical_phonology"] = []
            for entry in bs:
                rec = {}
                if entry.get("old_chinese"):
                    rec["old_chinese"] = entry["old_chinese"]
                if entry.get("middle_chinese"):
                    rec["middle_chinese"] = entry["middle_chinese"]
                if entry.get("gloss"):
                    rec["gloss"] = entry["gloss"]
                if entry.get("gsr"):
                    rec["gsr"] = entry["gsr"]
                if rec:
                    record["historical_phonology"].append(rec)

        # --- Wiktionary ---
        wikt = wiktionary.get(ch)
        if wikt:
            # Collect unique etymology texts
            seen_etyms = set()
            wikt_ftype_found = False
            for entry in wikt:
                etym = entry.get("etymology_text", "")
                if etym and etym not in seen_etyms:
                    seen_etyms.add(etym)
                    record.setdefault("etymology_notes", []).append({
                        "source": "wiktionary",
                        "text": etym,
                    })
                    # Extract formation type from Wiktionary text
                    if not wikt_ftype_found:
                        wikt_ftype = extract_wiktionary_formation_type(etym)
                        if wikt_ftype:
                            formation_claims["wiktionary"] = wikt_ftype
                            wikt_ftype_found = True
                # Collect glosses we don't already have
                for g in entry.get("glosses", []):
                    if not record.get("definitions"):
                        record["definitions"] = g

                # Collect OC/MC pronunciations from Wiktionary sounds
                if entry.get("oc_zhengzhang"):
                    if "historical_phonology" not in record:
                        record["historical_phonology"] = []
                    # Avoid duplicates
                    existing_zz = {p.get("old_chinese_zhengzhang")
                                   for p in record["historical_phonology"]
                                   if p.get("source") == "zhengzhang"}
                    if entry["oc_zhengzhang"] not in existing_zz:
                        record["historical_phonology"].append({
                            "old_chinese_zhengzhang": entry["oc_zhengzhang"],
                            "source": "zhengzhang_wikt",
                        })
                if entry.get("oc_baxter_sagart"):
                    if "historical_phonology" not in record:
                        record["historical_phonology"] = []
                    existing_bs = {p.get("old_chinese")
                                   for p in record["historical_phonology"]
                                   if p.get("old_chinese")}
                    if entry["oc_baxter_sagart"] not in existing_bs:
                        record["historical_phonology"].append({
                            "old_chinese": entry["oc_baxter_sagart"],
                            "source": "baxter_sagart_wikt",
                        })
                if entry.get("mc_baxter_sagart"):
                    if "historical_phonology" not in record:
                        record["historical_phonology"] = []
                    existing_mc = {p.get("middle_chinese")
                                   for p in record["historical_phonology"]
                                   if p.get("middle_chinese")}
                    if entry["mc_baxter_sagart"] not in existing_mc:
                        record["historical_phonology"].append({
                            "middle_chinese": entry["mc_baxter_sagart"],
                            "source": "baxter_sagart_wikt",
                        })

        # --- CC-CEDICT ---
        ce = cedict.get(ch)
        if ce:
            cedict_defs = []
            for entry in ce:
                for d_text in entry.get("definitions", []):
                    if d_text not in cedict_defs:
                        cedict_defs.append(d_text)
            if cedict_defs:
                record["cedict_definitions"] = cedict_defs
                if not record.get("definitions"):
                    record["definitions"] = "; ".join(cedict_defs[:3])
            # Get trad/simp mapping
            if ce[0].get("traditional") and ce[0].get("simplified"):
                if ce[0]["traditional"] != ce[0]["simplified"]:
                    if "variants" not in record:
                        record["variants"] = {}
                    if ch == ce[0]["traditional"]:
                        record["variants"].setdefault("simplified", ce[0]["simplified"])
                    elif ch == ce[0]["simplified"]:
                        record["variants"].setdefault("traditional", ce[0]["traditional"])

        # --- EVOBC ---
        ev = evobc.get(ch)
        if ev:
            record["historical_glyphs"] = {
                "evobc_id": ev.get("evobc_id", ""),
                "image_count": ev.get("image_count", 0),
                "eras_available": ev.get("eras", []),
            }

        # --- Guangyun Middle Chinese ---
        gy = guangyun.get(ch)
        if gy:
            if "guangyun" not in record:
                record["guangyun"] = []
            for entry in gy:
                phon_pos = entry.get("phonological_position", "")
                fanqie = entry.get("fanqie", "")
                record["guangyun"].append({
                    "phonological_position": phon_pos,
                    "fanqie": fanqie,
                })
                # Also add to historical_phonology as MC data
                if phon_pos:
                    if "historical_phonology" not in record:
                        record["historical_phonology"] = []
                    record["historical_phonology"].append({
                        "middle_chinese_guangyun": phon_pos,
                        "fanqie": fanqie,
                        "source": "guangyun",
                    })

        # --- ytenx Old Chinese (Zhengzhang Shangfang) ---
        yt = ytenx_oc.get(ch)
        if yt:
            if "historical_phonology" not in record:
                record["historical_phonology"] = []
            for entry in yt:
                oc_zz = entry.get("old_chinese_zhengzhang", "")
                if oc_zz:
                    record["historical_phonology"].append({
                        "old_chinese_zhengzhang": oc_zz,
                        "rhyme_group": entry.get("rhyme_group", ""),
                        "source": "zhengzhang",
                    })
                # Use phonetic component from ytenx if we don't already have one
                phon_comp = entry.get("phonetic_component", "")
                if phon_comp and len(phon_comp) == 1 and phon_comp != ch:
                    if "formation_details" not in record:
                        record["formation_details"] = {}
                    if not record["formation_details"].get("phonetic_component_ytenx"):
                        record["formation_details"]["phonetic_component_ytenx"] = phon_comp

        # --- Frequency ---
        freq = frequency.get(ch)
        if freq:
            record["frequency_rank"] = freq["frequency_rank"]
            if freq.get("hsk_level"):
                record["hsk_level"] = freq["hsk_level"]

        # --- AnimCJK HSK 3.0 + frequency tier ---
        acjk = animcjk.get(ch)
        if acjk:
            if acjk.get("hsk3_level"):
                record["hsk3_level"] = acjk["hsk3_level"]
            if acjk.get("frequency_tier"):
                record["frequency_tier"] = acjk["frequency_tier"]

        # --- Semantic field ---
        # Try explicit semantic component first, fall back to Kangxi radical
        sem_comp = record.get("formation_details", {}).get("semantic", "")
        if sem_comp and sem_comp in RADICAL_SEMANTICS:
            record["semantic_field"] = RADICAL_SEMANTICS[sem_comp]
        elif not sem_comp:
            # Use Kangxi radical
            rad_num = char_to_radical_num.get(ch)
            if rad_num:
                rad_char = kangxi_num_to_char.get(rad_num, "")
                if rad_char in RADICAL_SEMANTICS:
                    record["semantic_field"] = RADICAL_SEMANTICS[rad_char]

        # --- Sino-Tibetan cognates ---
        stc = st_cognates.get(ch)
        if stc:
            record["sino_tibetan_cognates"] = stc

        # --- Phonetic family built in post-merge pass (see below) ---

        # --- Extract phonetic from Shuowen for phono-semantic chars missing it ---
        if sw and not record.get("formation_details", {}).get("phonetic"):
            sw_phonetic = extract_shuowen_phonetic(sw.get("explanation", ""))
            if sw_phonetic and sw_phonetic != ch:
                if "formation_details" not in record:
                    record["formation_details"] = {}
                record["formation_details"]["phonetic"] = sw_phonetic
                record["formation_details"]["phonetic_source"] = "shuowen"
                shuowen_phonetic_count += 1

        # --- Infer phonetic/semantic components from IDS + radical ---
        # Only infer for characters already classified as phono-semantic,
        # or characters with enough strokes to plausibly be compounds (>= 5 strokes)
        details = record.get("formation_details", {})
        is_phono_semantic = any(
            normalize_formation_type(fc) == "phono-semantic"
            for fc in formation_claims.values()
        ) if formation_claims else False
        total_strokes_val = 0
        try:
            total_strokes_val = int(record.get("total_strokes", "0").split()[0])
        except (ValueError, IndexError):
            pass
        should_infer = (not details.get("phonetic") and
                        (is_phono_semantic or total_strokes_val >= 6))
        if should_infer:
            ids_str = record.get("ids", "") or record.get("decomposition_ids", "")
            # Binary decomposition: ⿰AB, ⿱AB, ⿸AB, ⿹AB, ⿺AB, ⿵AB
            if len(ids_str) == 3 and ids_str[0] in "⿰⿱⿸⿹⿺⿵":
                comp_a, comp_b = ids_str[1], ids_str[2]
                rad_num = char_to_radical_num.get(ch)
                if rad_num:
                    rad_char = kangxi_num_to_char.get(rad_num, "")
                    # Check if either component is the radical (or its variant)
                    a_is_radical = (comp_a == rad_char or
                                   radical_variants.get(comp_a) == rad_char or
                                   comp_a in radical_variants and kangxi_char_to_num.get(radical_variants[comp_a]) == rad_num)
                    b_is_radical = (comp_b == rad_char or
                                   radical_variants.get(comp_b) == rad_char or
                                   comp_b in radical_variants and kangxi_char_to_num.get(radical_variants[comp_b]) == rad_num)

                    if a_is_radical and not b_is_radical:
                        if "formation_details" not in record:
                            record["formation_details"] = {}
                        record["formation_details"]["semantic"] = comp_a
                        record["formation_details"]["phonetic"] = comp_b
                        record["formation_details"]["inferred"] = True
                        inferred_phonetic_count += 1
                    elif b_is_radical and not a_is_radical:
                        if "formation_details" not in record:
                            record["formation_details"] = {}
                        record["formation_details"]["semantic"] = comp_b
                        record["formation_details"]["phonetic"] = comp_a
                        record["formation_details"]["inferred"] = True
                        inferred_phonetic_count += 1

        # --- Formation type resolution with conflict detection ---
        record["_formation_claims"] = formation_claims  # temp for confidence calc
        if formation_claims:
            # Normalize all claims
            normalized_claims = {}
            for src, ftype in formation_claims.items():
                n = normalize_formation_type(ftype)
                if n:
                    normalized_claims[src] = n

            # Determine consensus
            if normalized_claims:
                type_counts = defaultdict(list)
                for src, n in normalized_claims.items():
                    type_counts[n].append(src)

                # Pick the type with most support; prefer modern sources
                # "other" should lose to any definitive classification
                SOURCE_PRIORITY = {
                    "dong_chinese": 4,     # most carefully curated
                    "wiktionary": 3,       # community-reviewed
                    "makemeahanzi": 2,      # good but less detailed
                    "shuowen_jiezi": 1,    # classical, often wrong
                }
                best_type = None
                best_score = -1
                for ftype, src_list in type_counts.items():
                    score = len(src_list) * 10  # count matters
                    score += sum(SOURCE_PRIORITY.get(s, 0) for s in src_list)
                    # Penalize "other" and "mixed-iconic" heavily
                    if ftype in ("other", "mixed-iconic"):
                        score -= 50
                    if score > best_score:
                        best_score = score
                        best_type = ftype

                record["formation_type"] = best_type

                # Detect conflicts -- only between definitive claims
                # "other" means uncertain, not a real classification
                definitive_claims = {
                    src: t for src, t in normalized_claims.items()
                    if t not in ("other", "mixed-iconic")
                }
                if definitive_claims:
                    unique_types = set(definitive_claims.values())
                    # Collapse "indicative" and "ideographic" (both are non-phonetic)
                    collapsed = set()
                    for t in unique_types:
                        if t in ("indicative", "ideographic"):
                            collapsed.add("ideographic")
                        elif t in ("phonetic-loan", "derivative-cognate"):
                            collapsed.add(t)
                        else:
                            collapsed.add(t)

                    if len(collapsed) > 1:
                        record["formation_type_conflict"] = {
                            src: normalize_formation_type(ft)
                            for src, ft in formation_claims.items()
                        }

        # --- Source tracking ---
        sources = []
        if ch in unihan:
            sources.append("unihan")
        if ch in mmah:
            sources.append("makemeahanzi")
        if ch in dong:
            sources.append("dong_chinese")
        if ch in cjkvi_ids:
            sources.append("cjkvi_ids")
        if ch in cjk_decomp:
            sources.append("cjk_decomp")
        if ch in shuowen:
            sources.append("shuowen_jiezi")
        if ch in kangxi:
            sources.append("kangxi")
        if ch in baxter_sagart:
            sources.append("baxter_sagart")
        if ch in wiktionary:
            sources.append("wiktionary")
        if ch in cedict:
            sources.append("cedict")
        if ch in evobc:
            sources.append("evobc")
        if ch in guangyun:
            sources.append("guangyun")
        if ch in ytenx_oc:
            sources.append("ytenx_oc")
        record["sources"] = sources
        record["source_count"] = len(sources)

        # --- Local glyph SVGs ---
        local_glyphs = {}
        if ch in dong_glyphs:
            local_glyphs["dong_chinese"] = dong_glyphs[ch]
        if ch in wikimedia_glyphs:
            local_glyphs["wikimedia_seal"] = wikimedia_glyphs[ch]
        if local_glyphs:
            record["local_glyphs"] = local_glyphs

        # --- Fill formation type gaps for common characters ---
        # If a character has no formation type but has IDS decomposition with
        # 2 components and a Kangxi radical, try to classify it
        if not record.get("formation_type"):
            ids_str = record.get("ids", "") or record.get("decomposition_ids", "")
            if len(ids_str) == 3 and ids_str[0] in "⿰⿱⿸⿹⿺⿵":
                comp_a, comp_b = ids_str[1], ids_str[2]
                rad_num = char_to_radical_num.get(ch)
                if rad_num:
                    rad_char = kangxi_num_to_char.get(rad_num, "")
                    a_is_rad = (comp_a == rad_char or
                                radical_variants.get(comp_a) == rad_char)
                    b_is_rad = (comp_b == rad_char or
                                radical_variants.get(comp_b) == rad_char)
                    # If one component is the radical and the other isn't,
                    # check if the non-radical component appears as a
                    # phonetic in other characters (i.e. is productive)
                    non_rad = comp_b if a_is_rad else (comp_a if b_is_rad else None)
                    if non_rad and (a_is_rad != b_is_rad):
                        # Could be ideographic compound
                        total_strokes_val = 0
                        try:
                            total_strokes_val = int(
                                record.get("total_strokes", "0").split()[0])
                        except (ValueError, IndexError):
                            pass
                        if total_strokes_val >= 6:
                            record["formation_type"] = "ideographic"
                            record["formation_type_inferred"] = True

        # --- Shuowen accuracy flag ---
        # Compare Shuowen's formation claim against modern consensus
        if record.get("shuowen") and record.get("formation_type"):
            sw_expl = record["shuowen"].get("explanation", "")
            sw_type = extract_shuowen_formation_type(sw_expl)
            modern_type = normalize_formation_type(record["formation_type"])
            if sw_type and modern_type:
                sw_norm = normalize_formation_type(sw_type)
                # Collapse indicative/ideographic for comparison
                def _collapse(t):
                    return "ideographic" if t in ("indicative", "ideographic") else t
                if _collapse(sw_norm) == _collapse(modern_type):
                    record["shuowen_accuracy"] = "confirmed"
                else:
                    # Only flag as error if modern sources (not just Shuowen) inform the type
                    modern_etym_srcs = set(n.get("source", "") for n in record.get("etymology_notes", [])) - {"shuowen_jiezi"}
                    if modern_etym_srcs:
                        record["shuowen_accuracy"] = "corrected"
                        record["shuowen"]["modern_correction"] = {
                            "shuowen_says": sw_norm,
                            "modern_says": modern_type,
                        }

        # --- Verification status ---
        # Based on how many independent modern sources provide etymology data.
        # A conflict doesn't disqualify -- it just means sources disagree on type,
        # not that the etymology is unverified.
        etym_sources = set(n.get("source", "") for n in record.get("etymology_notes", []))
        modern_etym_sources = etym_sources - {"shuowen_jiezi"}

        if len(modern_etym_sources) >= 2:
            record["verification_status"] = "cross-verified"
        elif len(modern_etym_sources) == 1:
            record["verification_status"] = "single-source"
        elif "shuowen_jiezi" in etym_sources:
            record["verification_status"] = "classical-only"
        elif record.get("etymology_notes"):
            record["verification_status"] = "unverified"
        # else: no verification_status field (no etymology at all)

        # --- Classical-only phonetic validation via OC rhyme ---
        if (record.get("verification_status") == "classical-only" and
                record.get("shuowen")):
            sw_expl = record["shuowen"].get("explanation", "")
            if "聲" in sw_expl:
                char_rhymes = set()
                for p in record.get("historical_phonology", []):
                    rg = p.get("rhyme_group", "")
                    if rg:
                        char_rhymes.add(rg)
                phon_comp = record.get("formation_details", {}).get("phonetic_component_ytenx", "")
                if char_rhymes and phon_comp and phon_comp in ytenx_oc:
                    comp_rhymes = set()
                    for p in ytenx_oc[phon_comp]:
                        rg = p.get("rhyme_group", "")
                        if rg:
                            comp_rhymes.add(rg)
                    if comp_rhymes:
                        if char_rhymes & comp_rhymes:
                            record["shuowen_phonetic_validated"] = True
                        else:
                            record["shuowen_phonetic_validated"] = False

        # --- Confidence score ---
        record["confidence"] = compute_confidence(record)

        # Remove temporary field
        del record["_formation_claims"]

        merged[ch] = record

    print(f"  Inferred phonetic components from IDS+radical: {inferred_phonetic_count}")
    print(f"  Extracted phonetic components from Shuowen: {shuowen_phonetic_count}")
    local_glyph_count = sum(1 for r in merged.values() if r.get("local_glyphs"))
    print(f"  Characters with local glyph SVGs: {local_glyph_count}")

    # --- Post-merge: propagate etymology from variant characters ---
    propagated = 0
    for ch, record in merged.items():
        if record.get("etymology_notes"):
            continue  # already has etymology
        # Check traditional and semantic variants for etymology
        variants = record.get("variants", {})
        variant_strings = []
        for vtype in ("traditional", "semantic"):
            vs = variants.get(vtype, "")
            if vs:
                variant_strings.append(vs)
        if not variant_strings:
            continue
        # Parse variant references: can be "U+XXXX" or "U+XXXX<source" format or raw chars
        variant_chars = []
        for vs in variant_strings:
            for token in vs.split():
                if token.startswith("U+"):
                    try:
                        variant_chars.append(chr(int(token[2:].split("<")[0], 16)))
                    except ValueError:
                        pass
                elif len(token) == 1 and ord(token) >= 0x3400:
                    variant_chars.append(token)
        for trad_ch in variant_chars:
                trad_record = merged.get(trad_ch)
                if trad_record and trad_record.get("etymology_notes"):
                    # Propagate etymology notes, tagged as from traditional variant
                    for note in trad_record["etymology_notes"]:
                        record.setdefault("etymology_notes", []).append({
                            **note,
                            "via_traditional": trad_ch,
                        })
                    # Propagate formation type if missing
                    if not record.get("formation_type") and trad_record.get("formation_type"):
                        record["formation_type"] = trad_record["formation_type"]
                    if not record.get("formation_details") and trad_record.get("formation_details"):
                        record["formation_details"] = trad_record["formation_details"]
                    # Update verification status
                    etym_sources = set(n.get("source", "") for n in record.get("etymology_notes", []))
                    modern = etym_sources - {"shuowen_jiezi"}
                    if len(modern) >= 2:
                        record["verification_status"] = "cross-verified"
                    elif len(modern) == 1:
                        record["verification_status"] = "single-source"
                    propagated += 1
                    break

    print(f"  Propagated etymology from variant characters: {propagated}")

    # --- Helper: sort characters by frequency (most common first) ---
    def sort_by_freq(chars):
        """Sort characters by frequency rank (lower = more common), unknowns last."""
        def key(ch):
            r = merged.get(ch)
            if r:
                return r.get("frequency_rank") or 999999
            return 999999
        return sorted(chars, key=key)

    # --- Build phonetic/semantic series and siblings ---
    print("  Building phonetic & semantic series and siblings...")

    # Build reverse mapping: canonical radical → set of variant forms
    canonical_to_variants = defaultdict(set)
    for variant, canonical in radical_variants.items():
        canonical_to_variants[canonical].add(variant)

    # Collect all characters that use each phonetic/semantic component,
    # normalizing variant forms to canonical so 刂→刀, 氵→水, etc.
    phonetic_to_chars = defaultdict(set)
    semantic_to_chars = defaultdict(set)
    for ch, record in merged.items():
        fd = record.get("formation_details", {})
        phon = fd.get("phonetic")
        sem = fd.get("semantic")
        if phon:
            canon = radical_variants.get(phon, phon)
            phonetic_to_chars[canon].add(ch)
        if sem:
            canon = radical_variants.get(sem, sem)
            semantic_to_chars[canon].add(ch)

    def get_series(ch, comp_to_chars):
        """Get all derivatives for ch, including via its variant forms."""
        canon = radical_variants.get(ch, ch)
        derivs = set()
        # If this char is canonical, collect from itself + all variants
        if canon == ch:
            derivs |= comp_to_chars.get(ch, set())
            for var in canonical_to_variants.get(ch, set()):
                derivs |= comp_to_chars.get(var, set())
        else:
            # This char is a variant; collect from its canonical form
            derivs |= comp_to_chars.get(canon, set())
        return derivs

    def get_siblings(comp, comp_to_chars):
        """Get all siblings sharing the same component (normalized)."""
        canon = radical_variants.get(comp, comp)
        return comp_to_chars.get(canon, set())

    ps_count = ss_count = psib_count = ssib_count = 0
    for ch, record in merged.items():
        fd = record.get("formation_details", {})
        # Phonetic series: chars where THIS char (or its variants) is the phonetic
        derivs = get_series(ch, phonetic_to_chars)
        if derivs:
            total = len(derivs)
            record["phonetic_series"] = sort_by_freq(derivs)[:30]
            if total > 30:
                record["phonetic_series_total"] = total
            ps_count += 1
        # Semantic series: chars where THIS char (or its variants) is the semantic
        derivs = get_series(ch, semantic_to_chars)
        if derivs:
            total = len(derivs)
            record["semantic_series"] = sort_by_freq(derivs)[:30]
            if total > 30:
                record["semantic_series_total"] = total
            ss_count += 1
        # Phonetic siblings: other chars sharing my phonetic component
        phon = fd.get("phonetic")
        if phon:
            siblings = get_siblings(phon, phonetic_to_chars) - {ch}
            if siblings:
                total = len(siblings)
                record["phonetic_siblings"] = sort_by_freq(siblings)[:30]
                if total > 30:
                    record["phonetic_siblings_total"] = total
                psib_count += 1
        # Semantic siblings: other chars sharing my semantic component
        sem = fd.get("semantic")
        if sem:
            siblings = get_siblings(sem, semantic_to_chars) - {ch}
            if siblings:
                total = len(siblings)
                record["semantic_siblings"] = sort_by_freq(siblings)[:30]
                if total > 30:
                    record["semantic_siblings_total"] = total
                ssib_count += 1
    print(f"  Phonetic series: {ps_count}, Semantic series: {ss_count}")
    print(f"  Phonetic siblings: {psib_count}, Semantic siblings: {ssib_count}")

    return merged


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------
def write_jsonl(merged, path):
    """Write merged data as JSONL."""
    print(f"\nWriting JSONL to {path}...")
    with open(path, "w", encoding="utf-8") as f:
        for ch in sorted(merged.keys()):
            f.write(json.dumps(merged[ch], ensure_ascii=False) + "\n")
    print(f"  Written {len(merged)} records")


def write_sqlite(merged, path):
    """Write merged data to SQLite database."""
    print(f"Writing SQLite database to {path}...")
    if path.exists():
        path.unlink()

    conn = sqlite3.connect(str(path))
    c = conn.cursor()

    # Main characters table
    c.execute("""
        CREATE TABLE characters (
            character TEXT PRIMARY KEY,
            codepoint TEXT,
            pinyin TEXT,
            pinyin_numbered TEXT,
            definitions TEXT,
            formation_type TEXT,
            formation_type_conflict TEXT,
            confidence INTEGER,
            verification_status TEXT,
            frequency_rank INTEGER,
            decomposition_ids TEXT,
            ids TEXT,
            radical_stroke TEXT,
            total_strokes TEXT,
            source_count INTEGER,
            sources TEXT,
            data JSON
        )
    """)

    # Etymology notes table
    c.execute("""
        CREATE TABLE etymology_notes (
            character TEXT,
            source TEXT,
            note_text TEXT,
            caveat TEXT,
            FOREIGN KEY (character) REFERENCES characters(character)
        )
    """)

    # Historical phonology table
    c.execute("""
        CREATE TABLE historical_phonology (
            character TEXT,
            old_chinese TEXT,
            middle_chinese TEXT,
            gloss TEXT,
            gsr TEXT,
            FOREIGN KEY (character) REFERENCES characters(character)
        )
    """)

    # Shuowen table
    c.execute("""
        CREATE TABLE shuowen (
            character TEXT PRIMARY KEY,
            explanation TEXT,
            radical TEXT,
            pronunciation_fanqie TEXT,
            seal_character TEXT,
            duan_notes JSON,
            FOREIGN KEY (character) REFERENCES characters(character)
        )
    """)

    # Readings table
    c.execute("""
        CREATE TABLE readings (
            character TEXT,
            reading_type TEXT,
            reading_value TEXT,
            FOREIGN KEY (character) REFERENCES characters(character)
        )
    """)

    # Insert data
    for ch, record in merged.items():
        conflict = record.get("formation_type_conflict")
        mandarin = record.get("readings", {}).get("mandarin", "")
        mandarin_num = pinyin_to_numbered(mandarin)
        c.execute(
            "INSERT INTO characters VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                record.get("character", ""),
                record.get("codepoint", ""),
                mandarin,
                mandarin_num,
                record.get("definitions", ""),
                record.get("formation_type", ""),
                json.dumps(conflict, ensure_ascii=False) if conflict else None,
                record.get("confidence", 0),
                record.get("verification_status", ""),
                record.get("frequency_rank"),
                record.get("decomposition_ids", ""),
                record.get("ids", ""),
                record.get("radical_stroke", ""),
                record.get("total_strokes", ""),
                record.get("source_count", 0),
                ",".join(record.get("sources", [])),
                json.dumps(record, ensure_ascii=False),
            ),
        )

        for note in record.get("etymology_notes", []):
            c.execute(
                "INSERT INTO etymology_notes VALUES (?, ?, ?, ?)",
                (ch, note.get("source", ""), note.get("text", ""), note.get("caveat", "")),
            )

        for phon in record.get("historical_phonology", []):
            c.execute(
                "INSERT INTO historical_phonology VALUES (?, ?, ?, ?, ?)",
                (ch, phon.get("old_chinese", ""), phon.get("middle_chinese", ""),
                 phon.get("gloss", ""), phon.get("gsr", "")),
            )

        sw = record.get("shuowen")
        if sw:
            c.execute(
                "INSERT INTO shuowen VALUES (?, ?, ?, ?, ?, ?)",
                (ch, sw.get("explanation", ""), sw.get("radical", ""),
                 sw.get("pronunciation_fanqie", ""), sw.get("seal_character", ""),
                 json.dumps(sw.get("duan_notes", []), ensure_ascii=False)),
            )

        for rtype, rval in record.get("readings", {}).items():
            c.execute(
                "INSERT INTO readings VALUES (?, ?, ?)",
                (ch, rtype, rval),
            )

    # Create indexes
    c.execute("CREATE INDEX idx_etym_char ON etymology_notes(character)")
    c.execute("CREATE INDEX idx_etym_source ON etymology_notes(source)")
    c.execute("CREATE INDEX idx_phon_char ON historical_phonology(character)")
    c.execute("CREATE INDEX idx_read_char ON readings(character)")
    c.execute("CREATE INDEX idx_char_formation ON characters(formation_type)")
    c.execute("CREATE INDEX idx_char_sources ON characters(source_count)")
    c.execute("CREATE INDEX idx_char_confidence ON characters(confidence)")
    c.execute("CREATE INDEX idx_char_conflict ON characters(formation_type_conflict) WHERE formation_type_conflict IS NOT NULL")
    c.execute("CREATE INDEX idx_char_pinyin ON characters(pinyin_numbered)")
    c.execute("CREATE INDEX idx_char_verification ON characters(verification_status)")
    c.execute("CREATE INDEX idx_char_frequency ON characters(frequency_rank) WHERE frequency_rank IS NOT NULL")

    conn.commit()
    conn.close()
    print(f"  Written {len(merged)} character records to SQLite")


def compute_statistics(merged):
    """Compute and print database statistics."""
    total = len(merged)
    has_definitions = sum(1 for r in merged.values() if r.get("definitions"))
    has_etymology = sum(1 for r in merged.values() if r.get("etymology_notes"))
    has_formation = sum(1 for r in merged.values() if r.get("formation_type"))
    has_shuowen = sum(1 for r in merged.values() if r.get("shuowen"))
    has_phonology = sum(1 for r in merged.values() if r.get("historical_phonology"))
    has_ids = sum(1 for r in merged.values() if r.get("ids") or r.get("decomposition_ids"))
    has_phonetic = sum(1 for r in merged.values() if r.get("formation_details", {}).get("phonetic"))
    has_inferred = sum(1 for r in merged.values() if r.get("formation_details", {}).get("inferred"))
    has_phonetic_from_shuowen = sum(1 for r in merged.values() if r.get("formation_details", {}).get("phonetic_source") == "shuowen")
    has_phonetic_series = sum(1 for r in merged.values() if r.get("phonetic_series"))
    has_semantic_series = sum(1 for r in merged.values() if r.get("semantic_series"))
    has_local_glyphs = sum(1 for r in merged.values() if r.get("local_glyphs"))

    # Verification status
    verification_counts = defaultdict(int)
    for r in merged.values():
        vs = r.get("verification_status", "no-etymology")
        verification_counts[vs] += 1
    has_glyphs = sum(1 for r in merged.values() if r.get("historical_glyphs"))
    has_readings = sum(1 for r in merged.values() if r.get("readings"))

    formation_types = defaultdict(int)
    for r in merged.values():
        ft = r.get("formation_type", "")
        if ft:
            formation_types[ft] += 1

    source_counts = defaultdict(int)
    for r in merged.values():
        for s in r.get("sources", []):
            source_counts[s] += 1

    multi_source_etym = sum(
        1 for r in merged.values()
        if len(r.get("etymology_notes", [])) > 1
    )

    # Characters in common CJK Unified Ideographs block
    cjk_basic = sum(1 for ch in merged if 0x4E00 <= ord(ch) <= 0x9FFF)

    # Conflict analysis
    has_conflict = sum(1 for r in merged.values() if r.get("formation_type_conflict"))
    conflict_details = defaultdict(int)
    for r in merged.values():
        c = r.get("formation_type_conflict")
        if c:
            types_involved = tuple(sorted(set(c.values())))
            conflict_details[types_involved] += 1

    # Confidence distribution
    confidence_buckets = defaultdict(int)
    for r in merged.values():
        conf = r.get("confidence", 0)
        if conf >= 80:
            confidence_buckets["80-100 (high)"] += 1
        elif conf >= 50:
            confidence_buckets["50-79 (medium)"] += 1
        elif conf >= 20:
            confidence_buckets["20-49 (low)"] += 1
        else:
            confidence_buckets["0-19 (minimal)"] += 1

    # Average confidence for chars with any etymology
    etym_confidences = [r.get("confidence", 0) for r in merged.values() if r.get("etymology_notes")]
    avg_confidence = sum(etym_confidences) / len(etym_confidences) if etym_confidences else 0

    stats = {
        "total_characters": total,
        "cjk_unified_basic": cjk_basic,
        "has_definitions": has_definitions,
        "has_any_etymology": has_etymology,
        "has_formation_type": has_formation,
        "has_shuowen_entry": has_shuowen,
        "has_historical_phonology": has_phonology,
        "has_decomposition": has_ids,
        "has_historical_glyphs": has_glyphs,
        "has_readings": has_readings,
        "has_multi_source_etymology": multi_source_etym,
        "formation_type_breakdown": dict(formation_types),
        "characters_per_source": dict(source_counts),
        "formation_type_conflicts": has_conflict,
        "conflict_type_pairs": {str(k): v for k, v in conflict_details.items()},
        "confidence_distribution": dict(confidence_buckets),
        "avg_confidence_etymology_chars": round(avg_confidence, 1),
        "has_phonetic_component": has_phonetic,
        "has_phonetic_from_shuowen": has_phonetic_from_shuowen,
        "has_local_glyphs": has_local_glyphs,
    }

    print("\n" + "=" * 60)
    print("DATABASE STATISTICS")
    print("=" * 60)
    print(f"  Total unique characters:        {total:>8,}")
    print(f"  CJK Unified Basic (U+4E00-9FFF):{cjk_basic:>8,}")
    print(f"  With definitions:               {has_definitions:>8,}")
    print(f"  With any etymology note:        {has_etymology:>8,}")
    print(f"  With formation type:            {has_formation:>8,}")
    print(f"  With Shuowen entry:             {has_shuowen:>8,}")
    print(f"  With OC/MC phonology:           {has_phonology:>8,}")
    print(f"  With decomposition (IDS):       {has_ids:>8,}")
    print(f"  With historical glyph images:   {has_glyphs:>8,}")
    print(f"  With readings (any language):   {has_readings:>8,}")
    print(f"  With multi-source etymology:    {multi_source_etym:>8,}")
    print(f"  With phonetic component ID'd:   {has_phonetic:>8,}")
    print(f"    (of which inferred from IDS): {has_inferred:>8,}")
    print(f"    (of which from Shuowen):      {has_phonetic_from_shuowen:>8,}")
    print(f"  With phonetic series:           {has_phonetic_series:>8,}")
    print(f"  With semantic series:           {has_semantic_series:>8,}")
    print(f"  With local glyph SVGs:          {has_local_glyphs:>8,}")
    print()
    print("  Verification status:")
    for vs in ["cross-verified", "single-source", "classical-only", "unverified", "no-etymology"]:
        print(f"    {vs:30s} {verification_counts.get(vs, 0):>8,}")
    print()
    print("  Formation type breakdown:")
    for ft, count in sorted(formation_types.items(), key=lambda x: -x[1]):
        print(f"    {ft:30s} {count:>6,}")
    print()
    print("  RIGOR METRICS:")
    print(f"  Formation type conflicts:       {has_conflict:>8,}")
    if conflict_details:
        print("  Conflict type pairs:")
        for types, count in sorted(conflict_details.items(), key=lambda x: -x[1])[:10]:
            print(f"    {' vs '.join(types):40s} {count:>5,}")
    print(f"  Avg confidence (etym chars):    {avg_confidence:>8.1f}")
    print("  Confidence distribution:")
    for bucket in ["80-100 (high)", "50-79 (medium)", "20-49 (low)", "0-19 (minimal)"]:
        print(f"    {bucket:30s} {confidence_buckets.get(bucket, 0):>8,}")
    print()
    print("  Characters per source:")
    for src, count in sorted(source_counts.items(), key=lambda x: -x[1]):
        print(f"    {src:30s} {count:>8,}")
    print("=" * 60)

    return stats


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    print("=" * 60)
    print("Chinese Character Etymology Database Builder")
    print("=" * 60)
    print()

    # Parse all sources
    unihan = parse_unihan()
    mmah = parse_makemeahanzi()
    dong = parse_dong_chinese()
    cjkvi_ids = parse_cjkvi_ids()
    cjk_decomp = parse_cjk_decomp()
    shuowen = parse_shuowen()
    kangxi = parse_kangxi()
    baxter_sagart = parse_baxter_sagart()
    wiktionary = parse_wiktionary()
    cedict = parse_cedict()
    evobc = parse_evobc()
    guangyun = parse_guangyun()
    ytenx_oc = parse_ytenx_oc()
    frequency = parse_frequency()
    animcjk = parse_animcjk()
    st_cognates = parse_sino_tibetan_cognates()

    # Merge
    merged = merge_all(
        unihan, mmah, dong, cjkvi_ids, cjk_decomp, shuowen,
        kangxi, baxter_sagart, wiktionary, cedict, evobc,
        guangyun, ytenx_oc, frequency, animcjk, st_cognates,
    )

    # Output
    write_jsonl(merged, OUTPUT_DIR / "hanzi_etymology.jsonl")
    write_sqlite(merged, OUTPUT_DIR / "hanzi_etymology.db")

    # Statistics
    stats = compute_statistics(merged)
    with open(OUTPUT_DIR / "statistics.json", "w", encoding="utf-8") as f:
        json.dump(stats, ensure_ascii=False, indent=2, fp=f)

    # Write a sample record for verification
    sample_chars = ["一", "人", "水", "木", "馬", "好", "的", "我", "愛", "龍"]
    samples = {}
    for ch in sample_chars:
        if ch in merged:
            samples[ch] = merged[ch]
    with open(OUTPUT_DIR / "sample_records.json", "w", encoding="utf-8") as f:
        json.dump(samples, ensure_ascii=False, indent=2, fp=f)
    print(f"\nSample records written for: {', '.join(samples.keys())}")

    print("\nDone! Output files:")
    print(f"  {OUTPUT_DIR / 'hanzi_etymology.jsonl'}")
    print(f"  {OUTPUT_DIR / 'hanzi_etymology.db'}")
    print(f"  {OUTPUT_DIR / 'statistics.json'}")
    print(f"  {OUTPUT_DIR / 'sample_records.json'}")


if __name__ == "__main__":
    main()
