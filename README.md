# Hanzi / Kanji Etymology Dictionary

An open-source etymology dictionary for Chinese characters (汉字) and Japanese kanji (漢字), compiled from 20 parsers across 17+ authoritative sources. Features cross-source validation, confidence scoring, historical phonology, glyph images, and a live web dictionary.

**Live site:** [lbm364dl.github.io/hanzi-etymology-dict](https://lbm364dl.github.io/hanzi-etymology-dict/)

---

## Features

- **103,207 Chinese characters** with etymology, phonology, glyph images, and definitions
- **13,108 Japanese kanji** with on/kun'yomi, JLPT levels, school grade, frequency, and full etymology reuse from the Chinese database
- **Dual-mode web dictionary** — toggle between Chinese (汉字) and Japanese (漢字) views; searches by character, pinyin, romaji, kana, or English
- Cross-source formation type validation with conflict detection and confidence scores
- Old Chinese and Middle Chinese phonological reconstructions (Baxter-Sagart, Zhengzhang)
- Historical glyph images: oracle bone, bronze inscription, seal script (578 chars via Dong Chinese; 3,638 via Wikimedia)
- Kokuji (国字) identification — Japanese-invented characters not in Chinese national standards

---

## Chinese Character Database Statistics

| Metric | Count |
|--------|-------|
| Total unique characters | 103,207 |
| CJK Unified Basic block | 20,992 |
| With definitions | 28,073 |
| With etymology notes | 18,778 |
| With formation type classified | 63,585 |
| With Shuowen Jiezi entry | 9,815 |
| With Old/Middle Chinese reconstruction | 20,047 |
| With Guangyun MC phonology | 19,337 |
| With IDS decomposition | 88,942 |
| With historical glyph images | 13,714 |
| With readings (any language) | 50,896 |
| With multi-source etymology | 8,710 |
| With phonetic component identified | 61,966 |
| Cross-verified etymology | 7,000+ |
| Sino-Tibetan cognate links | 369 |
| Historical glyph SVGs (Dong Chinese) | 578 chars |
| Historical glyph SVGs (Wikimedia seals) | 3,638 available |

### Formation Type Breakdown

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
| Cross-verified | 6,976 | 2+ modern sources agree |
| Single-source | 5,707 | 1 modern source |
| Classical-only | 4,367 | Shuowen only, no modern corroboration |
| Unverified | 336 | Has notes but unclear classification |

---

## Japanese Kanji Database Statistics

| Metric | Count |
|--------|-------|
| Total kanji (KANJIDIC2) | 13,108 |
| With JLPT level | 2,230 |
| Jōyō kanji (grades 1–8) | 2,138 |
| With etymology notes | 10,442 |
| With formation type | 12,323 |
| With historical phonology (reused) | 10,165 |
| With Shuowen Jiezi entry (reused) | 6,426 |
| Kokuji identified (国字) | 839 |

---

## Sources Integrated

### Chinese sources (16)

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
| 12 | [NK2028 Guangyun](https://github.com/nk2028/tshet-uinh-data) | 19,337 | CC0 | Middle Chinese phonology (fanqie) |
| 13 | [ytenx Old Chinese](https://github.com/BYVoid/ytenx) | 13,118 | Unlicensed | Zhengzhang OC reconstruction, phonetic components |
| 14 | [hanziDB](https://github.com/ruddfawcett/hanziDB.csv) | 9,900 | MIT | Frequency ranking, HSK levels |
| 15 | [AnimCJK](https://github.com/parsimonhi/animCJK) | 7,000 | Arphic/LGPL | HSK 3.0 levels, frequency tiers |
| 16 | [Sagart Sino-Tibetan](https://github.com/lexibank/sagartst) | 369 | CC BY 4.0 | Cognate links across 50 Sino-Tibetan languages |

### Japanese sources (4)

| # | Source | Characters | License | Data Type |
|---|--------|-----------|---------|-----------|
| 17 | [KANJIDIC2](https://www.edrdg.org/wiki/index.php/KANJIDIC_Project) (EDRDG) | 13,108 | CC BY-SA 4.0 | On/kun readings, meanings, grade, stroke count, JLPT |
| 18 | [davidluzgouveia/kanji-data](https://github.com/davidluzgouveia/kanji-data) | ~2,200 | MIT | JLPT levels (new scale), WaniKani levels |
| 19 | [scriptin/kanji-frequency](https://github.com/scriptin/kanji-frequency) | ~3,500 | CC BY 4.0 | Frequency from Aozora Bunko, Wikipedia, news |
| 20 | [cjkvi-ids/ids-analysis.txt](https://github.com/cjkvi/cjkvi-ids) | 13,000+ | GPLv2 | Shuowen-based etymological decomposition |

---

## Building

### Chinese database

```bash
# Install dependencies
pip install openpyxl

# Extract Dong Chinese glyph data (requires Node.js)
node extract_dong_chinese.mjs
node extract_dong_svgs.mjs

# Build the full database (~10 min)
python3 build_database.py

# Build the GitHub Pages site data
python3 build_site.py
```

### Japanese kanji database

```bash
# Download sources (KANJIDIC2, kanji-data, kanji-frequency)
python3 download_kanji_sources.py

# Build kanji database (requires Chinese DB to already exist for etymology reuse)
python3 build_kanji.py

# Rebuild site data (includes both Chinese and kanji)
python3 build_site.py
```

The Chinese database (`build_database.py`) must be built first — the kanji pipeline reuses its etymology notes, historical phonology, glyph data, and formation details for characters shared between the two writing systems.

---

## Output Files

| File | Size | Description |
|------|------|-------------|
| `output/hanzi_etymology.jsonl` | ~50 MB | Chinese characters, one JSON record per line |
| `output/hanzi_etymology.db` | ~89 MB | SQLite with indexed tables |
| `output/kanji_etymology.jsonl` | ~15 MB | Japanese kanji, one JSON record per line |
| `output/sample_records.json` | small | Example records for 一人水木馬好的我愛龍 |
| `output/statistics.json` | small | Machine-readable statistics |
| `docs/data.json.gz` | ~6.6 MB | Compressed Chinese site data |
| `docs/kanji_data.json.gz` | ~3 MB | Compressed Japanese site data |

---

## Schema

Each Chinese character record contains:

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
  "ids": "⿹⑥灬",
  "radical_stroke": "187.0",
  "total_strokes": "10",
  "variants": { "simplified": "U+9A6C" },
  "etymology_notes": [
    { "source": "makemeahanzi", "text": "A horse galloping to the left" },
    { "source": "dong_chinese", "text": "Pictograph of a horse." },
    { "source": "wiktionary", "text": "Pictogram (象形) – a horse..." }
  ],
  "shuowen": { "explanation": "...", "pronunciation_fanqie": "莫下切" },
  "historical_phonology": [
    { "old_chinese": "*mˤraʔ", "middle_chinese": "maeX", "gloss": "horse" }
  ],
  "confidence": 93,
  "verification_status": "cross-verified",
  "frequency_rank": 7059,
  "phonetic_family": ["驱", "驻", "骂", "..."],
  "sources": ["unihan", "makemeahanzi", "dong_chinese", "..."],
  "source_count": 11
}
```

See [SCHEMA.md](SCHEMA.md) for the complete field-by-field reference.

---

## SQLite Database

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

Tables: `characters`, `etymology_notes`, `historical_phonology`, `shuowen`, `readings`.

---

## Project Files

```
docs/                            # GitHub Pages static site
  index.html                     # Web dictionary (loads data.json.gz / kanji_data.json.gz)
  data.json.gz                   # Chinese site data (103K chars, ~6.6 MB gzipped)
  kanji_data.json.gz             # Japanese site data (13K kanji, ~3 MB gzipped)
  glyphs/dong_chinese/           # Historical glyph SVGs (oracle, bronze, seal)
  glyphs/wikimedia_seal/         # Seal script SVGs from Wikimedia

build_database.py                # Chinese ETL pipeline (16 sources, cross-validation)
build_kanji.py                   # Japanese kanji ETL pipeline
build_site.py                    # Build GitHub Pages data files
download_kanji_sources.py        # Download Japanese source files
extract_dong_chinese.mjs         # Dong Chinese etymology data extraction
extract_dong_svgs.mjs            # Historical glyph SVG extraction
download_wikimedia_seals.py      # Wikimedia seal script SVG downloader
search.py                        # Command-line search interface
export_anki.py                   # Anki flashcard deck exporter
export_review.py                 # Export review CSVs for expert adjudication
analyze_quality.py               # Cross-source quality analysis
analyze_phonetic_series.py       # Phonetic series reliability testing
validate_reconstructions.py      # OC cross-validation & Shuowen error detection

output/                          # Generated (not committed to repo)
  hanzi_etymology.jsonl
  hanzi_etymology.db
  kanji_etymology.jsonl
  glyphs/

sources/                         # Raw downloaded source data (not committed)
```

---

## Validation Results

| Test | What it measures | Result |
|------|-----------------|--------|
| Shuowen vs modern sources | Classical accuracy | 94.4% confirmed |
| Phonetic series (Mandarin) | Do families sound alike? | 91.4% rhyme match |
| Phonetic series (Old Chinese) | Ancient rhyme consistency | 82.8% (Zhengzhang) |
| Baxter-Sagart vs Zhengzhang | Two OC systems agree? | 81.4% tone, 72.7% vowel |
| Inferred formation type | IDS+radical inference quality | 98.1% vs Shuowen |
| Top 1000 chars | Missing etymology | 0 |
| Top 3000 chars | Missing etymology | 0 |
| Top 5000 chars | Missing etymology | 5 |
| Top 3000 chars | Average confidence | 80.3 |

---

## Cross-Source Validation

Formation types are extracted from 4 independent sources and disagreements are flagged:

1. **Make Me a Hanzi** — explicit `etymology.type` field
2. **Dong Chinese** — inferred from component function tags
3. **Wiktionary** — extracted via regex from etymology text
4. **Shuowen Jiezi** — extracted from classical explanation patterns

When sources disagree, all claims are preserved in `formation_type_conflict`. The **confidence score** (0–100) is based on number of agreeing sources, existence of Shuowen/Baxter-Sagart entries, historical glyphs, and decomposition coverage.

See [RESEARCH.md](RESEARCH.md) for a detailed evaluation of all 30+ sources considered, and [BOOKS.md](BOOKS.md) for the full bibliography.

---

## Caveats

- **Shuowen Jiezi** (~100 AD): Written before oracle bone discovery. Many analyses are incorrect by modern paleographic standards. All Shuowen entries are flagged with a caveat.
- **Formation types**: Some classifications are debatable. When sources disagree, all interpretations are preserved with attribution.
- **Japanese sources**: KANJIDIC2 is the authoritative reference for Japanese readings. JLPT levels use the post-2010 five-level scale.

---

## Contributing

Contributions are welcome. The most impactful areas:

**Expert etymology review** — Run `python3 export_review.py` to generate CSV files:
- `formation_conflicts.csv` (1,636 entries) — sources disagree on formation type; top-frequency characters first
- `shuowen_corrections.csv` (551 entries) — Shuowen entries disputed by modern scholarship
- `classical_only.csv` (4,367 entries) — characters with only Shuowen etymology, no modern corroboration; adding analysis for high-frequency entries here is the biggest open task

**New sources** — Additional open-licensed sources for etymology, phonology, or glyph data are welcome. See [RESEARCH.md](RESEARCH.md) for what has already been evaluated and [INACCESSIBLE_RESOURCES.md](INACCESSIBLE_RESOURCES.md) for known gaps.

**Japanese kanji** — The Japanese pipeline currently reuses Chinese etymology data. Dedicated Japanese-specific etymology sources (e.g. KanjiVG stroke order, JMdict definitions, on'yomi stratification by layer) would improve the kanji mode significantly.

**Bug reports and corrections** — Open an issue on [GitHub](https://github.com/lbm364dl/hanzi-etymology-dict). For single-character corrections, include the character, the field, the current value, and a source for the correction.

---

## License

The combined database inherits licenses from its component sources. Key constraints:

- CJKVI-IDS data is **GPLv2**
- Make Me a Hanzi is **LGPL v3**
- Wiktionary and Dong Chinese are **CC BY-SA**
- KANJIDIC2 is **CC BY-SA 4.0** (EDRDG)
- Shuowen, CJK-Decomp, Kangxi, kanji-data are permissively licensed (Apache/MIT)
- Unihan is under the Unicode Terms of Use

The build scripts and web interface in this repository are released under the **MIT License**.

---

## Documentation

- [RESEARCH.md](RESEARCH.md) — Evaluation of 30+ Chinese data sources considered
- [RESEARCH_JAPANESE.md](RESEARCH_JAPANESE.md) — Evaluation of Japanese kanji sources
- [BOOKS.md](BOOKS.md) — Bibliography of 73 books, papers, and digital resources
- [SCHEMA.md](SCHEMA.md) — Complete field-by-field database schema
- [GLYPH_DATA_SOURCES.md](GLYPH_DATA_SOURCES.md) — Historical glyph sources and integration
- [INACCESSIBLE_RESOURCES.md](INACCESSIBLE_RESOURCES.md) — Known gaps (paywalled, un-digitized sources)
- [LICENSE](LICENSE) — Per-source license breakdown
