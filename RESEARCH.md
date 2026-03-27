# Chinese Character Etymology: Source Research

## Tier 1: High-Priority Open Datasets (structured, licensed, ready to use)

### 1. Make Me a Hanzi
- **Repo:** https://github.com/skishore/makemeahanzi
- **Coverage:** 9,000+ simplified & traditional characters
- **Format:** Newline-delimited JSON (`dictionary.txt`, `graphics.txt`)
- **License:** `dictionary.txt` = LGPL v3+; `graphics.txt` = Arphic Public License
- **Key data:**
  - `decomposition` -- IDS-format (e.g., `⿰亻本`)
  - `etymology` -- object with `type`: "pictographic", "ideographic", or "pictophonetic"
  - For pictophonetic: `semantic`, `phonetic`, and `hint` subfields
  - `radical`, `pinyin`, `definition`
- **Quality:** High. Human-curated. The `etymology.type` field is the closest thing to a 六書 classification in any open dataset.
- **Caveat:** Not all 9000 characters have etymology data filled in.

### 2. Dong Chinese / chinese-lexicon
- **Repo:** https://github.com/peterolson/chinese-lexicon
- **Coverage:** ~1,000 common characters with detailed etymology
- **Format:** npm package (JS); wiki data at https://www.dong-chinese.com/wiki
- **License:** ISC (code), CC BY-SA 4.0 (wiki data)
- **Key data:**
  - Component function tags: `meaning` (semantic), `sound` (phonetic), `iconic` (pictographic/ideographic), `simplified`, `deleted`, `unknown`
  - Human-written etymology explanations
- **Quality:** Very high -- human-verified, monthly data releases
- **Blog post on methodology:** https://blog.dong-chinese.com/2019/07/07/character-origins.html

### 3. Unicode Unihan Database
- **Repo:** https://github.com/unicode-org/unihan-database
- **Coverage:** 97,000+ characters
- **Format:** Tab-delimited text; use https://github.com/cihai/unihan-etl for JSON/CSV/YAML export
- **License:** Unicode Terms of Use (permissive)
- **Key etymology-related fields:**
  - `kRSUnicode` -- Kangxi radical + residual strokes
  - `kPhonetic` -- phonetic class groupings (~1,500 classes)
  - `kDefinition` -- English definitions
  - `kMandarin`, `kCantonese` -- readings
  - `kSemanticVariant`, `kTraditionalVariant`, `kSimplifiedVariant`
- **Quality:** Authoritative baseline. Standard reference for all CJK metadata.

### 4. Wiktionary via Wiktextract (kaikki.org)
- **Repo:** https://github.com/tatuylonen/wiktextract
- **Data:** https://kaikki.org/dictionary/rawdata.html (Chinese JSONL)
- **Coverage:** All Chinese entries in English Wiktionary -- thousands of characters
- **Format:** JSONL, updated weekly
- **License:** CC BY-SA 3.0
- **Key data:** Etymology sections, glyph origin descriptions, definitions, readings
- **Quality:** Variable (community-edited), but extensive. Good for cross-referencing.

### 5. Sinetymology
- **Repo:** https://github.com/eugene-yh/Sinetymology
- **Details:** Dataset combining Old Chinese reconstructions with character formation data
- **Worth investigating for:** Phonetic series and historical phonology connections

---

## Tier 2: Structural Decomposition (components, not etymology narratives)

### 6. CHISE IDS Database
- **Repo:** https://gitlab.chise.org/CHISE/ids / GitHub mirror: https://github.com/chise/ids
- **Coverage:** 100,000+ characters (all CJK blocks including Extensions A-J)
- **Format:** Tab-separated: `<CODEPOINT>\t<CHARACTER>\t<IDS>`
- **License:** GPL v2+
- **Quality:** Gold standard for IDS decomposition. Academic project since 2002.

### 7. BabelStone IDS
- **URL:** https://www.babelstone.co.uk/CJK/IDS.HTML
- **Coverage:** 97,680 entries (Unicode 16.0)
- **Format:** Plain text IDS
- **License:** Not explicitly stated -- contact author
- **Quality:** Most up-to-date single IDS file. Maintained by Unicode expert Andrew West.
- **GitHub mirror:** https://github.com/qundao/mirror-babelstone-ids

### 8. CJK Decomposition Data
- **Repo:** https://github.com/amake/cjk-decomp
- **Coverage:** ~75,000 characters
- **Format:** Custom text: `的:a(白,勺)` (type + components)
- **License:** Choose from: Apache 2.0, LGPL 3.0, CC BY-SA 3.0, MIT, ODC-By v1.0, or EPL
- **Quality:** Comprehensive. Archived/unmaintained but very permissive license.

### 9. CJKVI-IDS
- **Repo:** https://github.com/cjkvi/cjkvi-ids
- **Coverage:** All CJK Unified Ideographs (derived from CHISE)
- **License:** `ids.txt` = GPLv2 (from CHISE)
- **Also includes:** Stroke data, variant relationships (22 files in cjkvi-variants)

### 10. Wikimedia Commons Decomposition
- **URL:** https://commons.wikimedia.org/wiki/Commons:Chinese_characters_decomposition
- **Coverage:** 21,170 characters
- **Format:** TSV (11 columns), also on SourceForge
- **License:** CC-compatible
- **Quality:** 98% verified. Purely graphical (not etymological).

---

## Tier 3: Classical Texts (public domain, etymology narratives)

### 11. Shuowen Jiezi (說文解字) -- digitized
- **ctext.org:** https://ctext.org/shuo-wen-jie-zi (full text, API access)
- **GitHub:** https://github.com/shuowenjiezi/shuowen (Apache 2.0)
- **Coverage:** 9,353 characters in 540 radicals
- **Caveat:** Some etymologies are incorrect by modern scholarship (written ~100 AD). Must cross-reference with modern sources.
- **API:** CText API at https://ctext.org/tools/api (JSON, rate-limited)

### 12. Kangxi Dictionary (康熙字典) -- digitized
- **Repo:** https://github.com/samsonhoi/kangxi-dictionary
- **Coverage:** 48,710 records
- **Format:** XLSX
- **License:** MIT

### 13. Duan Yucai's Commentary (段注) on Shuowen
- Available through ctext.org but no standalone structured dataset.

### 14. Shuowen + 80K chars SQLite
- **Repo:** https://github.com/jsksxs360/Hanzi
- **Format:** SQLite database with 80,000+ character records from ctext.org
- **Useful for:** Bulk access to classical dictionary entries

---

## Tier 4: Historical Phonology & Reconstruction

### 15. Baxter-Sagart Old Chinese Reconstruction
- **URL:** https://sites.lsa.umich.edu/ocbaxtersagart/
- **Coverage:** ~5,000 Old Chinese reconstructions
- **Format:** XLSX, freely downloadable
- **Quality:** State-of-the-art OC reconstruction. Essential for understanding phonetic loans and phonetic series.

### 16. Schuessler EDOC (ABC Etymological Dictionary of Old Chinese)
- **Digital version:** https://edoc.uchicago.edu/edoc2013/digitaledoc_index.php (free, web-only)
- **Quality:** Major scholarly reference for Sino-Tibetan etymologies

### 17. ytenx (BYVoid) -- Historical Rhyme Books
- **Repo:** https://github.com/BYVoid/ytenx
- **Content:** Guangyun and other historical phonology data
- **Useful for:** Historical phonetic series, understanding sound changes

### 18. STEDT (Sino-Tibetan Etymological Dictionary and Thesaurus)
- **URL:** https://stedt.berkeley.edu/
- **Coverage:** 1,000,000 lexical records
- **Quality:** Major academic resource for comparative Sino-Tibetan

### 19. NK2028 Organization
- **Repo:** https://github.com/nk2028
- **Content:** Middle Chinese and Old Chinese phonology tools and data

---

## Tier 5: Historical Glyph Images

### 20. EVOBC (Evolution of Chinese Characters)
- **Repo:** https://github.com/RomanticGodVAN/character-Evolution-Dataset
- **Coverage:** 229,170 images across 13,714 characters, 6 historical periods
- **Periods:** Oracle Bone, Bronze, Spring & Autumn, Warring States, Seal Script, Clerical Script
- **Format:** JPG images + JSON metadata
- **Quality:** Largest open dataset of historical glyph images
- **Paper:** https://arxiv.org/abs/2401.12467

### 21. HUST-OBC (Oracle Bone Characters)
- **Repo:** https://github.com/Pengjie-W/HUST-OBC
- **Coverage:** 140,053 oracle bone images (1,588 deciphered + 9,411 undeciphered characters)
- **Quality:** Academic-grade (Nature Scientific Data publication)

### 22. Wikimedia Ancient Chinese Characters Project
- **URL:** https://commons.wikimedia.org/wiki/Commons:Ancient_Chinese_characters_project
- **Content:** SVG/PNG for oracle bone, bronze, seal script forms
- **License:** Public domain
- **Coverage:** 214 radicals completed across all forms, ongoing

### 23. hanziyuan.net (Richard Sears / 汉字叔叔)
- **URL:** https://hanziyuan.net/
- **Source code:** https://github.com/Dixin/Etymology (ASP.NET Core)
- **Coverage:** 96,000+ ancient character forms (oracle bone, bronze, seal, Shuowen, Liushutong)
- **Access:** Web-only. Glyph images NOT separately downloadable as dataset.
- **Caveat:** Great visual reference, but data is not openly licensed for reuse.

### 24. Open-Oracle Hub
- **Repo:** https://github.com/Yuliang-Liu/Open-Oracle
- **Content:** Aggregates HUST-OBC, EVOBC, and other datasets with research code

---

## Tier 6: Additional Useful Resources

### 25. CC-CEDICT
- **URL:** https://www.mdbg.net/chinese/dictionary?page=cedict
- **Coverage:** 124,079 entries
- **License:** CC BY-SA 3.0
- **Useful for:** Definitions, readings (not etymology per se)

### 26. GlyphWiki
- **URL:** https://en.glyphwiki.org/wiki/GlyphWiki:MainPage
- **Coverage:** 2,000,000+ glyph entries
- **Content:** User-editable glyph database with historical forms

### 27. CCDB Chinese Character Web API
- **URL:** http://ccdb.hemiola.com/
- **Coverage:** ~21,000 characters
- **Format:** REST API (JSON/XML)
- **Content:** Radicals, strokes, definitions. Based on Unihan.

### 28. HanziCraft Phonetic Sets
- **URL:** https://hanzicraft.com/lists/phonetic-sets
- **Content:** 422 exact-match + 225 tone-variant phonetic sets (~6,800 chars)
- **Access:** Web-only (not bulk downloadable)

### 29. Xiaoxuetang (小學堂) -- Academia Sinica
- **URL:** https://xiaoxue.iis.sinica.edu.tw/
- **Coverage:** 22,000+ characters with glyph evolution
- **Access:** Web-based, registration may be required

### 30. CUHK Multi-function Chinese Character Database
- **URL:** http://humanum.arts.cuhk.edu.hk/Lexis/lexi-mf/
- **Content:** Etymology, ancient script forms, comprehensive per-character data
- **Access:** Web-based lookup only, no bulk download
- **Quality:** Rated "world leading" academically

### 31. zhongwen.com
- **URL:** https://zhongwen.com/
- **Content:** Character etymology tree (Rick Harbaugh's Chinese Characters: A Genealogy and Dictionary)
- **Access:** Web-based

---

## Source Reliability Assessment

| Source | Reliability | Notes |
|--------|------------|-------|
| Shuowen Jiezi | Mixed | Classical authority but many false etymologies by modern standards |
| Outlier Dictionary | Very High | Best modern analysis, but proprietary/paywalled |
| Dong Chinese | High | Careful curation, cites multiple sources |
| Make Me a Hanzi | Medium-High | Good for common characters, some entries less rigorous |
| Wiktionary | Variable | Community-edited, ranges from excellent to unreliable |
| Baxter-Sagart | Very High | Gold standard for Old Chinese phonology |
| CUHK Database | Very High | Academic quality, but not open |
| Richard Sears (hanziyuan) | Medium | Great glyph collection, but etymological explanations are basic |
| Unihan | High | Authoritative for metadata, minimal etymology |

---

## License Compatibility Summary

For an open-source project, the safest combination:

| License | Compatible Sources |
|---------|-------------------|
| **CC BY-SA 4.0** (recommended for data) | Dong Chinese wiki, Wiktionary, CC-CEDICT, CJK-Decomp (CC BY-SA option) |
| **MIT/Apache 2.0** (for code) | Unihan (Unicode ToS), CJK-Decomp (MIT option), Kangxi dict, Shuowen repo |
| **LGPL v3** (copyleft) | Make Me a Hanzi dictionary.txt |
| **GPL v2** (strong copyleft) | CHISE IDS, CJKVI-IDS -- use carefully, may require derived dataset to be GPL |
| **Public Domain** | Classical texts (Shuowen, Kangxi original), Wikimedia ancient chars |

---

## Recommended Integration Strategy

### Phase 1: Foundation
1. Start with **Unihan** as the character universe (97K+ chars)
2. Layer on **Make Me a Hanzi** for etymology types + IDS decomposition (9K chars)
3. Add **Dong Chinese** component function tags for common characters (~1K)
4. Add **CJK Decomposition Data** (MIT) for broad structural decomposition (~75K)

### Phase 2: Classical & Scholarly
5. Integrate digitized **Shuowen Jiezi** entries (9,353 chars) -- flag as "classical, may be incorrect"
6. Add **Kangxi Dictionary** data (48K records)
7. Integrate **Baxter-Sagart** Old Chinese reconstructions (~5K)
8. Pull **Wiktionary** etymology sections via kaikki.org JSONL

### Phase 3: Cross-referencing & Enrichment
9. Cross-reference sources to flag disagreements
10. Use **EVOBC** glyph evolution images for visual documentation
11. Add phonetic series data from Unihan `kPhonetic` + HanziCraft
12. Scrape/integrate additional scholarly sources as available

### Phase 4: Expansion & Verification
13. Use LLM-assisted extraction from academic texts (with human review)
14. Community contribution system
15. Expert review pipeline
