# Hanzi Etymology Dictionary

A comprehensive open-source database of Chinese character (汉字) etymologies, compiled from 11 authoritative sources.

## Database Statistics

| Metric | Count |
|--------|-------|
| Total unique characters | 103,207 |
| CJK Unified Basic block | 20,992 |
| With definitions | 28,073 |
| With etymology notes | 16,480 |
| With formation type classified | 62,556 |
| With Shuowen Jiezi entry | 9,815 |
| With Old/Middle Chinese reconstruction | 13,309 |
| With Guangyun MC phonology | 19,337 |
| With IDS decomposition | 88,942 |
| With historical glyph images | 13,714 |
| With readings (any language) | 50,896 |
| With multi-source etymology | 8,710 |
| With phonetic component identified | 59,575 |
| With phonetic series (kPhonetic) | 22,456 |
| Cross-verified etymology | 5,427 |
| Historical glyph SVGs (Dong Chinese) | 578 chars |
| Historical glyph SVGs (Wikimedia seals) | 3,638 available |

### Formation Type Breakdown (cross-source consensus + inference)

| Type | Count |
|------|-------|
| Ideographic (會意) | 40,353 |
| Phono-semantic (形聲) | 21,694 |
| Pictographic (象形) | 486 |
| Indicative (指事) | 20 |
| Phonetic loan (假借) | 3 |

### Verification Status

| Status | Count | Meaning |
|--------|-------|---------|
| Cross-verified | 5,427 | 2+ modern sources agree on etymology |
| Single-source | 6,350 | 1 modern source provides etymology |
| Classical-only | 4,367 | Only Shuowen Jiezi (needs modern corroboration) |
| Unverified | 336 | Has notes but unclear classification |

### Rigor Metrics

| Metric | Value |
|--------|-------|
| Formation type conflicts (sources disagree) | 1,636 |
| High confidence characters (80-100) | 5,728 |
| Medium confidence (50-79) | 9,871 |
| Average confidence (chars with etymology) | 70.0 |
| CJK basic: ideographic vs phono-semantic conflicts | 1,037 |

## Output Files

- **`output/hanzi_etymology.jsonl`** (50 MB) -- One JSON record per line, per character
- **`output/hanzi_etymology.db`** (89 MB) -- SQLite database with indexed tables
- **`output/sample_records.json`** -- Example records for 一人水木馬好的我愛龍
- **`output/statistics.json`** -- Machine-readable statistics

## Schema

Each character record contains:

```json
{
  "character": "馬",
  "codepoint": "U+99AC",
  "definitions": "horse; surname; Kangxi radical 187",
  "readings": {
    "mandarin": "mǎ",
    "cantonese": "maa5",
    "japanese_on": "BA ME MA",
    "korean": "MA",
    "vietnamese": "mã"
  },
  "formation_type": "pictographic",
  "formation_details": { "semantic": "...", "phonetic": "..." },
  "decomposition_ids": "⿹？灬",
  "ids": "⿹⑥灬",
  "radical_stroke": "187.0",
  "total_strokes": "10",
  "phonetic_class": "863",
  "variants": { "simplified": "U+9A6C" },
  "etymology_notes": [
    { "source": "makemeahanzi", "text": "A horse galloping to the left" },
    { "source": "dong_chinese", "text": "Pictograph of a horse." },
    { "source": "shuowen_jiezi", "text": "怒也。武也。象馬頭髦尾四足之形。",
      "caveat": "Classical source (~100 AD)..." },
    { "source": "wiktionary", "text": "Pictogram (象形) – a horse..." }
  ],
  "shuowen": {
    "explanation": "...",
    "pronunciation_fanqie": "莫下切",
    "seal_character": "...",
    "duan_notes": [...]
  },
  "historical_phonology": [
    { "old_chinese": "*mˤraʔ", "middle_chinese": "maeX", "gloss": "horse", "gsr": "0040a" }
  ],
  "historical_glyphs": {
    "evobc_id": "10159",
    "image_count": 488,
    "eras_available": ["oracle_bone", "bronze_inscription", "seal_script", ...]
  },
  "formation_type_conflict": {
    "makemeahanzi": "ideographic",
    "shuowen_jiezi": "phono-semantic",
    "wiktionary": "phono-semantic"
  },
  "confidence": 93,
  "verification_status": "cross-verified",
  "frequency_rank": 7059,
  "hsk_level": null,
  "phonetic_series": ["863"],
  "phonetic_family": ["驱", "驻", "骂", ...],
  "sources": ["unihan", "makemeahanzi", "dong_chinese", ...],
  "source_count": 11
}
```

## Sources Integrated

| # | Source | Characters | License | Data Type |
|---|--------|-----------|---------|-----------|
| 1 | [Unicode Unihan](https://unicode.org/reports/tr38/) | 102,998 | Unicode ToS | Readings, definitions, radical-stroke, variants |
| 2 | [CJKVI-IDS](https://github.com/cjkvi/cjkvi-ids) | 88,937 | GPLv2 | Ideographic Description Sequences |
| 3 | [CJK Decomposition](https://github.com/amake/cjk-decomp) | 74,751 | MIT/Apache/CC | Structural decomposition |
| 4 | [Kangxi Dictionary](https://github.com/samsonhoi/kangxi-dictionary) | 46,815 | MIT | Definitions, radicals |
| 5 | [Wiktionary](https://kaikki.org) via wiktextract | 30,387 | CC BY-SA 3.0 | Etymology narratives |
| 6 | [CC-CEDICT](https://cc-cedict.org) | 14,417 | CC BY-SA 4.0 | Definitions |
| 7 | [EVOBC](https://github.com/RomanticGodVAN/character-Evolution-Dataset) | 13,714 | Academic | Historical glyph metadata (6 eras) |
| 8 | [Shuowen Jiezi](https://github.com/shuowenjiezi/shuowen) | 9,815 | Apache 2.0 | Classical etymology, seal script, Duan Yucai notes |
| 9 | [Make Me a Hanzi](https://github.com/skishore/makemeahanzi) | 9,574 | LGPL v3 | Formation type, decomposition, etymology hints |
| 10 | [Dong Chinese](https://github.com/peterolson/chinese-lexicon) | 5,067 | CC BY-SA 4.0 | Component function tags, etymology explanations |
| 11 | [Baxter-Sagart](https://sites.lsa.umich.edu/ocbaxtersagart/) | 4,056 | Free academic | Old Chinese & Middle Chinese reconstructions |
| 12 | [NK2028 Guangyun](https://github.com/nk2028/tshet-uinh-data) | 19,337 | CC0 | Middle Chinese phonology (音韻地位, fanqie) |
| 13 | [ytenx Old Chinese](https://github.com/BYVoid/ytenx) | 13,118 | Unlicensed | Zhengzhang OC reconstruction, phonetic components |

## SQLite Database

The SQLite database (`output/hanzi_etymology.db`) contains these tables:

- **`characters`** -- Main table (character, codepoint, definitions, formation_type, decomposition, full JSON `data` column)
- **`etymology_notes`** -- All etymology notes with source attribution
- **`historical_phonology`** -- Baxter-Sagart Old/Middle Chinese reconstructions
- **`shuowen`** -- Shuowen Jiezi entries with Duan Yucai commentary
- **`readings`** -- Character readings (Mandarin, Cantonese, Japanese, Korean, Vietnamese, etc.)

Example queries:

```sql
-- Find all pictographic characters with Shuowen entries
SELECT c.character, c.definitions, s.explanation
FROM characters c JOIN shuowen s ON c.character = s.character
WHERE c.formation_type = 'pictographic';

-- Characters with etymology from 3+ sources
SELECT character, definitions, source_count
FROM characters WHERE source_count >= 3
ORDER BY source_count DESC;

-- Search etymology notes
SELECT character, source, note_text
FROM etymology_notes WHERE note_text LIKE '%pictograph%' LIMIT 20;
```

## Building

```bash
# 1. Clone sources (or use the pre-built output/)
# 2. Extract Dong Chinese data
node extract_dong_chinese.mjs

# 3. Build database (requires Python 3, openpyxl)
pip install openpyxl
python3 build_database.py
```

## Project Files

```
├── README.md                  # This file
├── RESEARCH.md                # Detailed source research & evaluation
├── BOOKS.md                   # Bibliography of 73 authoritative references
├── INACCESSIBLE_RESOURCES.md  # Resources we couldn't integrate (yet)
├── build_database.py          # ETL pipeline (16 parsers, cross-validation)
├── extract_dong_chinese.mjs   # Dong Chinese etymology extraction
├── extract_dong_svgs.mjs      # Historical glyph SVG extraction
├── download_wikimedia_seals.py # Wikimedia seal script SVG downloader
├── analyze_quality.py         # Cross-source quality analysis
├── output/
│   ├── hanzi_etymology.jsonl  # Full database (JSONL)
│   ├── hanzi_etymology.db     # Full database (SQLite)
│   ├── sample_records.json    # Example records
│   ├── statistics.json        # Build statistics
│   ├── priority_gaps.json     # High-frequency chars needing work
│   └── glyphs/                # Historical character form SVGs
│       ├── dong_chinese/      # 578 chars (oracle, bronze, seal, cursive)
│       └── wikimedia_seal/    # 3,638 Shuowen seal script SVGs
└── sources/                   # Raw source data (not committed)
```

## Cross-Source Validation

The database extracts formation types from 4 independent sources and detects disagreements:

1. **Make Me a Hanzi** -- explicit `etymology.type` field
2. **Dong Chinese** -- inferred from component function tags (meaning/sound/iconic)
3. **Wiktionary** -- extracted via regex from etymology text (e.g., "Phono-semantic compound (形聲)")
4. **Shuowen Jiezi** -- extracted from classical explanation patterns (e.g., `从X, Y聲` = phono-semantic)

**Consensus algorithm:**
- Each source's claim is weighted by reliability (Dong Chinese > Wiktionary > Make Me a Hanzi > Shuowen)
- "other" / uncertain classifications don't participate in conflict detection
- Indicative (指事) and ideographic (會意) are collapsed for conflict purposes (subtle distinction)
- When sources disagree, all claims are preserved in `formation_type_conflict`

**Confidence score** (0-100) based on:
- Number of etymology sources (max 30 pts)
- Source agreement on formation type (max 25 pts)
- Shuowen entry exists (10 pts)
- Baxter-Sagart phonology exists (10 pts)
- Historical glyph images available (up to 10 pts)
- Has decomposition (5 pts), definitions (5 pts), readings (5 pts)

**Known conflict patterns:**
- **Ideographic vs phono-semantic** (1,037 cases): The biggest scholarly debate. Some characters have components that *could* be phonetic but also carry meaning. Example: 冬 -- is 仌 (ice) purely phonetic, or also semantic?
- **Pictographic vs ideographic** (227 cases): The subtle line between "picture of a thing" and "abstract representation of a concept." E.g., is 上 a picture or a symbol?
- **Shuowen vs modern** (~613 cases): Shuowen was written before oracle bone discovery, so many of its analyses are corrected by modern paleography.

## Caveats & Methodology

- **Shuowen Jiezi** (~100 AD): Written before oracle bone and bronze inscriptions were discovered. Many etymologies are incorrect by modern paleographic standards. All Shuowen entries are flagged with a caveat.
- **Wiktionary**: Community-edited, quality varies. Useful for cross-referencing but should not be sole authority.
- **Formation types**: The "pictophonetic" vs "ideographic" vs "pictographic" classification primarily comes from Make Me a Hanzi and Dong Chinese. Some classifications are debatable among scholars.
- **Multi-source etymology**: When sources disagree, all interpretations are preserved with attribution rather than choosing one.

## Documentation

- **[RESEARCH.md](RESEARCH.md)** -- Detailed evaluation of all 30+ sources considered
- **[BOOKS.md](BOOKS.md)** -- Comprehensive bibliography of 73 books, papers, and digital resources
- **[INACCESSIBLE_RESOURCES.md](INACCESSIBLE_RESOURCES.md)** -- Resources that could improve the database but aren't currently available as open data

## License

The combined database inherits licenses from its sources. Key constraints:
- CJKVI-IDS data is **GPLv2** (derived from CHISE)
- Make Me a Hanzi dictionary is **LGPL v3**
- Wiktionary and Dong Chinese wiki data are **CC BY-SA**
- Shuowen, CJK-Decomp, Kangxi are permissively licensed (Apache/MIT)
- Unihan is under Unicode Terms of Use

The build scripts in this repository are released under **MIT License**.
