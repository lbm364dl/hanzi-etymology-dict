# Historical Chinese Character Glyph Data Sources

Research conducted 2026-03-27. Documents coverage, format, license, and integration steps
for historical Chinese character glyph data that can supplement the EVOBC dataset.

---

## 1. Wikimedia Commons Ancient Chinese Characters Project

**URL:** https://commons.wikimedia.org/wiki/Commons:Ancient_Chinese_characters_project

### Coverage

Files are organized by script type into categories accessible via the Wikimedia API:

| Category (API name) | File Count | Format |
|---|---|---|
| Shuowen_seal_script_characters_(SVG) | **3,097** | SVG |
| Kaishu_script_characters_(SVG) | **718** | SVG |
| Songti_script_characters_(SVG) | **417** | SVG |
| Oracle_bone_script_characters | **117** | Mixed (SVG/PNG/JPG) |
| Shuowen_seal_script_characters | **107** | Mixed |
| Shuowen_ancient_script_characters | **41** | Mixed |
| Bronze_script_characters | **16** | Mixed |
| Shang_oracle_script_characters | **6** | Mixed |
| Western_Zhou_bronze_script_characters | **6** | Mixed |
| Warring_States_bronze_script_characters | **5** | Mixed |
| Clerical_script_characters | **2** | Mixed |

**Key finding:** The Shuowen seal script SVG collection (3,097 files) is the most
valuable subset. Files use naming convention `ACC-sXXXXX.svg` (Ancient Chinese Characters
project, seal, sequential ID). Oracle bone files use inconsistent naming (mix of
`Character_Name_Oracle.svg`, `甲骨XX.svg`, `X-oracle.svg`).

### License

**Public domain.** All work in the Ancient Chinese Characters project is stated as public
domain. Attribution to Wikimedia Commons recommended but not required.

### Bulk Download Method

Use the Wikimedia Commons API with `categorymembers` queries:
```
https://commons.wikimedia.org/w/api.php?action=query&list=categorymembers
  &cmtype=file&cmtitle=Category:Shuowen_seal_script_characters_(SVG)
  &cmlimit=500&format=json
```

Pagination via `cmcontinue` parameter is required (500 files per page).

**Download tools:**
- `CommonsDownloader` (Python, pip): `pip install CommonsDownloader`
- `commons-downloader` (shell script): https://sr.ht/~nytpu/commons-downloader/
- `wikimedia-downloader` (async Python): https://github.com/ryanrudes/wikimedia-downloader

### Integration Steps

1. Use Wikimedia API to enumerate all files in `Shuowen_seal_script_characters_(SVG)`
2. Download SVGs via CommonsDownloader to `sources/wikimedia-seal/`
3. The ACC-sXXXXX naming needs a mapping table to Unicode characters (may require
   scraping file description pages for the character each SVG represents)
4. Priority: the 3,097 seal script SVGs provide excellent coverage beyond EVOBC

---

## 2. GlyphWiki Data

**URL:** https://en.glyphwiki.org

### Coverage

- **2,000,000+ glyph entries** covering CJK Unified Ideographs and extensions
- Primarily covers standard CJK character forms (modern variants, regional variants)
- Glyph naming uses Unicode codepoints: `u4e00` for U+4E00, `u2xxxx` for Extension B+
- Also includes `koseki-XXXXXX` (Japanese registry) and `toki-XXXXXXXX` variants
- **No explicit historical script type classification** (oracle bone, seal, bronze are not
  systematically categorized in the dump)

### Data Format

- **KAGE notation**: Skeletal stroke data describing glyph shapes stroke-by-stroke
- Dump file: `dump_newest_only.txt` (plain text, pipe-delimited)
- Each entry: glyph name | related Unicode reference | KAGE stroke data
- KAGE data uses colon-separated stroke descriptors with coordinates

### Download

- **URL:** https://glyphwiki.org/dump.tar.gz
- **Size:** ~109 MB compressed
- **Contents:** `dump_newest_only.txt`, `dump_all_versions.txt`, `README_en.txt`, `LICENSE.txt`
- Updated periodically (current dump dated 2026-03-27)

### License

Data contributed to GlyphWiki transfers intellectual rights to GlyphWiki. All data is
stated as "free to use" with no warranty. Contributors agree not to exercise moral rights.
Fonts generated from the data are also free. Exact license classification unclear (not a
standard CC or OSS license).

### Rendering KAGE to SVG

Two KAGE engine implementations can convert KAGE data to SVG:
- **Python:** https://github.com/HowardZorn/kage-engine (renders Bezier curves)
- **JavaScript:** https://www.npmjs.com/package/@kurgm/kage-engine

**Font generation:** https://github.com/kawabata/glyphwiki-afdko converts KAGE to
OpenType fonts via SVG intermediate step.

### Integration Steps

1. Download `dump.tar.gz` to `sources/glyphwiki/`
2. Extract and parse `dump_newest_only.txt`
3. Use the Python KAGE engine to render glyphs matching our character set to SVG
4. **Limitation:** GlyphWiki mainly provides modern glyph variants, not historical script
   forms (oracle bone, seal, etc.). Useful for variant coverage, not historical evolution.
5. Potential: Search for seal script variants by naming patterns (if any exist)

---

## 3. AnimCJK Project

**URL:** https://github.com/parsimonhi/animCJK
**Local clone:** `/home/catalin/hanzi-etymology-dict/sources/animcjk/` (shallow, 193 MB)

### Coverage

| Folder | Characters | Description |
|---|---|---|
| svgsZhHans | **7,726** | Simplified Chinese (HSK + common + components) |
| svgsJa | **5,753** | Japanese kanji (joyo + jinmeyo + hyogai) |
| svgsZhHant | **1,014** | Traditional Chinese (HSK v3 levels 1-3) |
| svgsKo | **535** | Korean hanja (levels 4-8) |
| svgsJaKana | **177** | Hiragana + katakana |

### Decomposition Data (beyond Make Me a Hanzi)

AnimCJK provides **two decomposition systems** per character:

1. **IDS decomposition** (`decomposition` field): Standard Ideographic Description
   Sequences, same as Make Me a Hanzi (e.g., `⿰亻尔` for 你)

2. **ACJK decomposition** (`acjk` field): AnimCJK's proprietary system that adds
   **stroke-group numbering**. Each component gets a number indicating how many strokes
   it contains, and `.N` marks the "main" component with its stroke count.
   - Example: 你 = `你⿰亻.2尔5` (亻 is the main part with 2 strokes, 尔 has 5 strokes)
   - Example: 国 = `国⿴囗.:2玉5囗.:1` (nested structure with stroke counts)

3. **Additional fields vs Make Me a Hanzi:**
   - `set`: HSK level + frequency classification (18 categories including `hsk31`-`hsk39`,
     `frequent2500`, `lessFrequent1000`, `commonNotFrequent`, etc.)
   - AnimCJK lacks Make Me a Hanzi's `matches` field (component-to-stroke mapping)

4. **Dictionary files:**
   - `dictionaryZhHans.txt`: 7,726 entries (JSON lines)
   - `dictionaryJa.txt`: 5,753 entries
   - `dictionaryZhHant.txt`: 953 entries
   - `dictionaryKo.txt`: 535 entries

5. **Key differences from MMAH:**
   - Different stroke orders for many Japanese/Korean characters
   - Different glyphs for characters that share Unicode but differ by locale
   - Stroke-level component grouping (ACJK system) enables coloring components
   - Frequency/HSK classification metadata

### SVG Format

Each SVG is named by decimal Unicode (e.g., `19968.svg` for 一/U+4E00). SVGs are
1024x1024 coordinate system with CSS animation for stroke-by-stroke display. Derived
from Arphic fonts via Make Me a Hanzi.

### License

- **SVGs and graphics files (kanji/hanzi):** Arphic Public License (permissive, allows
  redistribution and modification)
- **Other files (kana, strokes, scripts):** LGPL v3+
- Full license at `sources/animcjk/licenses/COPYING.txt`

### Integration Steps

1. Already cloned to `sources/animcjk/`
2. Parse `dictionaryZhHans.txt` for ACJK decomposition and frequency data
3. SVGs provide modern character stroke animations (not historical forms)
4. The ACJK decomposition system could supplement our structural analysis
5. HSK/frequency classification useful for prioritizing character coverage

---

## 4. Open-Source Seal Script / Ancient Script Fonts

### Available Resources

| Resource | Type | Coverage | License | Notes |
|---|---|---|---|---|
| **BabelStone Han** | OTF font | 60,000+ Han chars | Free for personal/commercial use | Includes rare/archaic chars for Early Chinese text transcription; does NOT contain actual historical script forms |
| **HUST-OBC Dataset** | Image dataset | 1,588 deciphered + 9,411 undeciphered oracle bone chars (140,053 images) | Not specified | Research dataset for ML; images are rubbing scans and handwritten copies; https://github.com/Pengjie-W/HUST-OBC |
| **JiaGuWen** | JSON/SQLite database | Unknown count (1.6 MB repo) | MIT License | Oracle bone to modern character mapping with images; https://github.com/Chinese-Traditional-Culture/JiaGuWen |
| **OracleBone.org** | SVG | ~40 pages of characters | CC BY-NC 4.0 | Individual SVGs crafted in Inkscape; non-commercial only |
| **Splend1d/Zhuan** | Referenced data | ~2,000 chars | Unknown | References Academia Sinica seal script database; images not self-contained |
| **Jingyuan Platform** | Font + database | 52,288+ oracle bone glyphs | Unknown (research) | Launched 2024; high-resolution oracle bone font |
| **Fangzheng Xiaozhuan** | TTF font | Common seal script chars | Commercial/free download | Seal script font; not open source |

### Key Finding

**There is no single comprehensive open-source font** that contains all historical Chinese
script forms (oracle bone, bronze, seal) in a standard font format. The landscape is
fragmented:

- Research datasets (HUST-OBC, EVOBC) have the best oracle bone coverage but as raster images
- Wikimedia Commons has the best seal script SVG coverage (3,097 Shuowen seal SVGs)
- No free oracle bone script font with broad character coverage exists
- The JiaGuWen database (MIT licensed) is the most accessible oracle bone mapping resource

### Integration Steps

1. Clone JiaGuWen to `sources/jiaguwen/` for oracle bone to modern char mappings
2. OracleBone.org SVGs are CC BY-NC 4.0 (non-commercial restriction may be limiting)
3. HUST-OBC is valuable but license unclear -- contact authors before integration
4. BabelStone Han useful as a fallback display font for rare characters

---

## 5. Dong Chinese Inline SVGs

**File:** `/home/catalin/hanzi-etymology-dict/sources/chinese-lexicon/etymology/etymologyImages.js`

### Coverage

| Script Type | Characters | SVG Type |
|---|---|---|
| Oracle bone (甲骨文) | **113** | Real path-based SVGs (historical glyph images) |
| Bronze inscription (金文) | **136** | Real path-based SVGs (historical glyph images) |
| Seal script (篆文) | **148** | Real path-based SVGs (historical glyph images) |
| Cursive (草书) | **18** | Real path-based SVGs (historical glyph images) |
| Traditional (繁体) | **23** | Text-based SVGs (createSVG placeholders, just renders the char in a font) |

**Total unique characters with real historical glyph SVGs: 209**
(70 characters have all three main types: oracle + bronze + seal)

**Total SVG elements in the file: 1,074** (across all script types and characters)

### Format

Each SVG is an inline data URI containing path-based vector graphics. Example structure:
```javascript
oracle: {
    "女": svg(`<svg ... viewBox="0 0 65 115" ...><g ...><path d="M344 979 c-5 ..."/></g></svg>`),
    ...
}
```

The `svg()` function wraps each SVG as a data URI: `url("data:image/svg+xml;charset=utf8,...")`

The `createSVG()` function (used only in `traditional` section) generates simple text SVGs
that just render the character in the default font -- these are NOT historical glyph images.

### Characters Covered

All 209 unique characters with historical SVG images:
```
女止白勺我戈不人土才口舌言文又月門韋古來京高尤至刀兒兄兌日十廿卅木王今目魚山火犬石足糸能
九明天馬大小巴卩邑衣宀豕家旡真去矢首此隹合頁黃光多夕戠羊見黑以米食良對上下尸玉矦出再㝵
史吏使事𡈼直耳丁斤雨而豆壴歹䧹鳥垂自學戶禾工發生网買子爾士在行有也要八力手金心五六七囧
𢆶貝朋友乍亥匕冉聿會回世幺為象可免冒巾寺尚堂反得德需丰豐封亡走襄弓髮𣎆了肉竹个韦疒骨
冎別水艸棗虫熊几戍沒艮本愛音做气夬寸候廴頭過車東難漢僅興當長關寫歲場樂無擇
```

### License

Part of Dong Chinese (sources/chinese-lexicon). The SVG images appear to be traced from
Richard Sears' Chinese Etymology data (chineseetymology.org), which is used with
permission in various projects. Exact redistribution terms need verification.

### Integration Steps

1. Parse `etymologyImages.js` to extract SVGs per character per script type
2. Decode the URL-encoded SVG data URIs back to raw SVG
3. Normalize SVG viewBox dimensions (currently vary: 65x115, 45x79, etc.)
4. Store as individual SVG files: `{char}-oracle.svg`, `{char}-bronze.svg`, `{char}-seal.svg`
5. These 209 characters provide high-quality, curated historical glyph images
6. Priority targets: the 70 characters with all three historical types

---

## Comparison with Existing EVOBC Data

Our existing EVOBC dataset (`sources/evobc/`) contains:
- **13,714 characters** with **229,170 images** across 6 historical periods
- Eras: Oracle Bone (OBC), Bronze Inscriptions (BI), Seal Script (SS),
  Spring & Autumn (SAC), Warring States (WSC), Clerical Script (CS)
- Images are JPG/PNG raster files (stored externally on Google Drive)
- This is by far the most comprehensive source

### Coverage Gaps EVOBC Can Fill vs. What Others Add

| Source | Unique Value | Characters | Historical Types |
|---|---|---|---|
| **EVOBC** | Most comprehensive; 6 historical periods | 13,714 | OBC, BI, SS, SAC, WSC, CS |
| **Wikimedia Shuowen Seal SVGs** | High-quality vector seal script | ~3,097 | Seal only |
| **Dong Chinese SVGs** | Curated, ready-to-use vector images | 209 | Oracle, Bronze, Seal, Cursive |
| **AnimCJK** | Modern stroke animation + ACJK decomposition | 7,726 | Modern only |
| **GlyphWiki** | 2M+ variant forms, KAGE notation | 2,000,000+ | Modern variants only |
| **JiaGuWen** | Oracle bone to modern char mapping (MIT) | TBD | Oracle only |

### Recommended Integration Priority

1. **Dong Chinese SVGs** (immediate, 209 chars) -- already in repo, extract and normalize
2. **Wikimedia Shuowen Seal SVGs** (high value, 3,097 chars) -- public domain, vector format
3. **AnimCJK decomposition data** (already cloned) -- ACJK decomposition + frequency metadata
4. **JiaGuWen database** (quick clone, MIT) -- oracle bone character mappings
5. **GlyphWiki dump** (large, complex) -- useful for variant coverage, requires KAGE rendering
6. **EVOBC full images** (external download needed) -- 229K images on Google Drive
