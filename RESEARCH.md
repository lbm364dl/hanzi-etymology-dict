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
- **License:** Unihan data files use Unicode License v3 unless a file identifies an exception. The checked-in project extract includes the upstream notice in `pipeline/data/LICENSE-UNICODE.txt`.
- **Key etymology-related fields:**
  - `kRSUnicode` -- Kangxi radical + residual strokes
  - `kPhonetic` -- phonetic class groupings (~1,500 classes)
  - `kDefinition` -- English definitions
  - `kMandarin`, `kCantonese` -- readings
  - `kSemanticVariant`, `kTraditionalVariant`, `kSimplifiedVariant`
- **Quality:** Authoritative baseline. Standard reference for all CJK metadata.
- **Editorial-pipeline use:** The local `sources/unihan/Unihan_Readings.txt` is a cross-check for current Mandarin readings. A compact 17.0.0 extract in `pipeline/data/unihan-kmandarin-hsk1.tsv` keeps this check available on a clean checkout; it covers the 300 HSK 1 characters and phonetic forms used in the published pilot. When a sound array needs a modern pair, inspect separate `kMandarin` rows for the component and host, then cite their official character-specific lookup pages, for example `https://www.unicode.org/cgi-bin/GetUnihanData.pl?codepoint=4E0D` for U+4E0D 不. The validator checks proposed Modern Mandarin values against the exact local rows when available. These readings describe current metadata only; they do not establish an ancient phonetic relationship.

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
- **Format:** The repository keeps a tab-separated character table at `sources/baxter-sagart/baxtersagart.tsv`. The official [2014 version 1.1 GSR-sorted table](https://sites.lsa.umich.edu/ocbaxtersagart/wp-content/uploads/sites/1415/2025/03/BaxterSagartOCbyGSR2014-09-20.pdf) is the citation target for row-level claims.
- **Quality:** State-of-the-art OC reconstruction. Essential for understanding phonetic loans and phonetic series.
- **Editorial use:** Compare exact local rows for both members of a proposed sound relationship. Keep this reconstruction system separate from Zhengzhang and other systems; the bracket notation in this table marks uncertainty, not optional material that can be silently dropped.

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
- **Coverage:** The guide reports more than 220,000 glyph records across oracle, bronze, Warring States, seal, and regular-script forms, plus historical readings.
- **Access:** Character lookup; selected downloads include independent historical phonology files and a seal font. The official [phonology download page](https://xiaoxue.iis.sinica.edu.tw/ccrdata/) marks the independent sound-data files with the Public Domain Mark (PDM).
- **Reuse:** The official [rights notice](https://xiaoxue.iis.sinica.edu.tw/License/License) applies CC0 1.0 to glyph images and glyph-attribute information obtained through its query interface. The sound-file PDM statement is separate and does not establish a blanket license for the full database, linked dictionaries, their text, or other Academia Sinica databases. The linked Shang phonology ZIP returned HTTP 401 in this review environment; no file was mirrored or access control bypassed. Store only specifically queried glyph images selected for entries, with record URLs and the rights notice.
- **Editorial-pipeline access:** Its [official usage guide](https://xiaoxue.iis.sinica.edu.tw/yanbian/Content/Files/yanbian-Get_Started.pdf) describes one-character searches. The form returns the glyph results after submission, so a plain GET or search-engine page may show only the interface. `pipeline/xiaoxuetang.py` performs this lookup only when glyph research finds no usable image or acquisition fails; it queries one locally recorded traditional counterpart when available, otherwise the entry form. A two-second minimum request interval and an hour-long pause after HTTP 401 limit repeated requests. The run keeps its query output, while only selected images and evidence are retained with the reviewed entry. It does not mirror the database.
- **Editorial-pipeline usage:** Cited in 96 of 155 validated published entries matching the current HSK 1 cohort (counted 2026-09-27).

### 30. CUHK Multi-function Chinese Character Database
- **URL:** https://humanum.arts.cuhk.edu.hk/Lexis/lexi-mf/
- **Content:** Etymology, ancient script forms, comprehensive per-character data
- **Access:** Web-based lookup only, no bulk download
- **Quality:** Rated "world leading" academically
- **Editorial-pipeline usage:** Cited from this domain in 120 of 155 validated published entries matching the current HSK 1 cohort (counted 2026-09-27).

### 31. zhongwen.com
- **URL:** https://zhongwen.com/
- **Content:** Character etymology tree (Rick Harbaugh's Chinese Characters: A Genealogy and Dictionary)
- **Access:** Web-based

### 32. Ministry of Education (Taiwan), Dictionary of Chinese Character Variants (教育部《異體字字典》)
- **URL:** https://dict.variants.moe.edu.tw/
- **Coverage and content:** 100,000+ character forms, variant links, readings, and source references ([MOE history](https://dict.variants.moe.edu.tw/page.jsp?ID=350&la=1)).
- **Access and reuse:** Searchable online. The [form-data policy](https://dict.variants.moe.edu.tw/page.jsp?ID=14) says some underlying reference material is not public, limits requests for that material to five main-character records per application, and requires users to observe copyright law. The MOE [public-license portal](https://language.moe.gov.tw/001/Upload/Files/site_content/M0001/respub/index.html) lists four other MOE dictionaries, not this dictionary; no bulk reuse grant for this dataset was identified. Do not mirror its contents without clearer permission.
- **Editorial-pipeline usage:** Cited from this domain in 110 of 155 validated published entries matching the current HSK 1 cohort (counted 2026-09-27). Keep character-specific links and concise attributed evidence in each dossier while treating it as a lookup source.

### 33. Unicode CJK Radicals Supplement
- **URL:** https://www.unicode.org/charts/PDF/U2E80.pdf
- **Content:** Official names and mappings for the CJK radical forms, including relationships between radical glyphs and their ideographs.
- **Editorial-pipeline use:** Consult the character-specific chart entry when a component's positional shape and its full form need to be distinguished from a historical ancestor. Cite the exact chart record in the entry; do not infer historical development from a Unicode mapping.

### Editorial-pipeline source frequency snapshot (2026-09-27)

Latest refreshed checkpoint: **300 validated HSK 1 entries**. Dossier URLs appear on Wikimedia Commons in 259 entries, CUHK Humanum in 223, the Taiwan variants dictionary in 217, Unicode in 216, Xiaoxuetang in 167, English Wiktionary in 152, and Academia Sinica's character database in 120. These are exact-host counts per entry, not independent corroboration or article-citation counts. The machine-readable file `output/hsk1-source-frequency.json` contains the refreshed totals. The paragraph below records the earlier 155-entry checkpoint.

The current HSK 1 cohort has 300 characters; 155 have validated published v2 entries with learner sections. Twelve additional published pilot entries fall outside the list. Counting distinct validated HSK entries with dossier evidence URLs on each exact hostname, CUHK Humanum and Wikimedia Commons each appear in 120/155, the Taiwan variants dictionary in 110/155, English Wiktionary in 105/155, and Xiaoxuetang in 96/155. Academia Sinica’s character database appears in 60/155, Unicode and Shuowen.org each in 58/155, Chinese Text Project in 55/155, `zdic.net` in 54/155 (with `www.zdic.net` counted separately in 21/155), and Chinese Wikisource in 45/155. The machine-readable checkpoint is `output/hsk1-source-frequency.json` (2026-09-27); it counts dossier URLs, including records that need not be cited in article prose. This counts linked evidence, not independent corroboration: source repetition and search-result-only records do not make a claim stronger. Wiktionary JSONL, Baxter–Sagart data, CJK decomposition, and other structured datasets are already in `sources/`; accepted glyph images are retained as reviewed, hash-checked per-entry snapshots. The recurring online dictionaries still lack a clearly identified blanket reuse grant for their full contents; continue linking to character-specific records instead of mirroring them. Xiaoxuetang's official CC0 notice covers queried glyph images and glyph attributes, not its entire database. Its separate sound-data downloads are marked PDM, but the selected linked file returned HTTP 401 during this review, so it was not cached. Unicode radical charts are directly useful for component-form relationships, but the chart is evidence for its code-point mappings, not historical character derivation. Unihan is the recurring exception where a compact local extract adds a concrete editorial cross-check and the upstream license permits redistribution; keep the extract scoped and retain per-character citations. Source frequency identifies what to investigate, while reuse terms and editorial need decide what to copy.

#### When to add a recurring source locally

Use the corpus frequency snapshot to spot sources worth reviewing, not as permission to copy them. Check the license and terms for the exact material, then ask whether a narrow, versioned extract would support a repeatable pipeline check or useful offline research. If both reuse permission and editorial value are clear, track its upstream version and URL, scope, license notice, checksum, and reproducible export path. Otherwise keep character-specific links and concise evidence paraphrases. A grant for selected glyphs or metadata does not extend to the source's full text or database. The currently approved addition is the project-scoped Unihan `kMandarin` extract documented in `pipeline/data/README.md`; the high-frequency MOE and other dictionary pages remain linked because a blanket reuse right for their contents has not been identified.

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

## Tier 7: Historical Phonology (Guangyun / Old Chinese)

### 31. NK2028 Guangyun Data (tshet-uinh-data)
- **Repo:** https://github.com/nk2028/tshet-uinh-data
- **Coverage:** 19,337 unique characters from the Guangyun (廣韻, ~1008 AD)
- **Format:** CSV with fields: 小韻號, 音韻地位, 反切, 字頭, 釋義
- **License:** CC0 1.0 (public domain)
- **Quality:** Definitive structured Middle Chinese data. The 音韻地位 field encodes full phonological classification (initial, division, rhyme, tone).
- **Integrated:** Yes

### 32. ytenx Old Chinese Reconstructions (BYVoid)
- **Repo:** https://github.com/BYVoid/ytenx
- **Coverage:** 13,118 unique characters with Zhengzhang Shangfang OC reconstructions
- **Format:** Space-separated text (DrienghTriang.txt) with 17 fields including IPA reconstruction, phonetic component (聲符), rhyme group
- **License:** Not explicitly stated
- **Quality:** Comprehensive OC reconstruction table with phonetic series built in. 1,412 unique phonetic components identified.
- **Integrated:** Yes

### 33. Sagart et al. Sino-Tibetan Database of Lexical Cognates
- **Repo:** https://github.com/lexibank/sagartst
- **Coverage:** 289 Old Chinese entries linked to cognate sets across 50 Sino-Tibetan languages
- **Format:** CLDF Wordlist (CSV files)
- **License:** CC-BY-4.0
- **Quality:** Expert-verified cognate judgments. Limited to ~250 basic concepts.
- **Integrated:** Not yet (concept-level, not character-level)

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
