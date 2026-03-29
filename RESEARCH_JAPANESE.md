# Japanese Kanji Etymology: Source Research

This document catalogs all identified open-source and freely accessible data sources for Japanese kanji etymology, for use in the Japanese learning mode of this dictionary.

---

## Summary: Recommended Stack

### Tier 1 — Essential Foundation
| # | Source | Coverage | License | Format |
|---|--------|----------|---------|--------|
| 1 | **KANJIDIC2** | 13,108 kanji; on/kun readings, meanings, grade, JLPT, frequency | CC BY-SA 4.0 | XML |
| 2 | **KanjiVG** | ~6,500 kanji SVGs with stroke order + component annotations | CC BY-SA 3.0 | SVG+XML |
| 3 | **cjkvi-ids / ids-analysis.txt** | Semantic etymological decomposition from Shuowen | GPLv2 | Text |
| 4 | **KRADFILE / RADKFILE** | 13,108 kanji → visual component decomposition | EDRDG (CC BY-SA) | Text |
| 5 | **jmdict-simplified** | ~220K Japanese dictionary entries in JSON | CC BY-SA 3.0 | JSON |

### Tier 2 — High-Value Additions
| # | Source | Coverage | License | Format |
|---|--------|----------|---------|--------|
| 6 | **scriptin/kanji-frequency** | Aozora, Wikipedia, Wikinews kanji frequency | CC BY 4.0 | JSON |
| 7 | **BCCWJ frequency (NINJAL)** | 104M-word corpus; ~6,000+ kanji across genres | Free research | CSV |
| 8 | **nk2028/onyomi-gakken-kanwa** | Historical on'yomi stratification (Go-on/Kan-on) | Open | — |
| 9 | **nk2028 Middle Chinese** | OC/MC reconstructions → on'yomi mapping | CC0 | — |
| 10 | **dahlia/shinjitai-table** | 364 shinjitai↔kyūjitai pairs | Open | JSON |
| 11 | **melissaboiko/joyodb** | 2,136 Jōyō kanji, machine-readable | Open | JSON/TSV |
| 12 | **davidluzgouveia/kanji-data** | ~2,000 kanji with JLPT + WaniKani levels | MIT | JSON |

### Tier 3 — Supplementary
| # | Source | Coverage | License | Format |
|---|--------|----------|---------|--------|
| 13 | **KanjiAlive kanji-data-media** | 1,235 kanji + radical history SVGs | CC BY 4.0 | CSV+SVG |
| 14 | **Kuzushiji-Kanji (ROIS-CODH)** | 140K pre-modern glyph images, 3,832 chars | CC BY-SA 4.0 | Images |
| 15 | **GlyphWiki API** | 2M+ glyphs, variant/rare kanji, kokuji | Open | SVG API |
| 16 | **kanjiapi.dev** | 13,000+ kanji REST API | CC BY 3.0 FR | REST JSON |
| 17 | **Unihan kJapanese fields** | kJapaneseKun, kJapaneseOn, kJapanese (51K+) | Unicode ToS | Text |
| 18 | **mifunetoshiro/kanjium** | 6,400+ kanji with pitch accent, aggregated | CC BY-SA 4.0 | SQLite |

### Not Open / Use with Caution
- **Henshall's etymologies** — copyrighted, Tuttle Publishing; no open digital version
- **WaniKani mnemonics** — proprietary, Tofugu LLC; API requires subscription
- **Kanji Koohii mnemonics** — CC BY-NC-SA 3.0 (non-commercial only)
- **Heisig RTK keywords** — copyrighted, Heisig Estate
- **Lawrence Howell's EDHCC PDF** — author-permission only

---

## Overlapping Chinese Sources (Reusable for Japanese)

Most kanji derive from traditional Chinese characters, so many existing Chinese hanzi sources apply directly:

| Chinese Source | Applicable to Japanese? | Notes |
|---|---|---|
| **Unihan Database** | Yes, extensively | kJapaneseKun (hiragana kun), kJapaneseOn (katakana on), kJapanese (new property, 51k+ characters) |
| **Baxter-Sagart Old/Middle Chinese** | Yes, indirectly | MC reconstructions map to on'yomi; phonetic series explain sound components |
| **Make Me a Hanzi** | Partially | Covers most kanji in traditional forms; etymology types applicable; PRC stroke order differs from Japanese in some cases |
| **CHISE IDS / cjkvi-ids** | Yes, directly | ids.txt and ids-analysis.txt cover all CJK including kanji; `waseikanji-ids.txt` and `hanyo-ids.txt` are Japan-specific |
| **Shuowen Jiezi data** | Yes, for non-kokuji | Shuowen is the etymological reference for all kanji derived from ancient Chinese |
| **nk2028 Middle Chinese / Guangyun** | Yes, directly | CC0; used by Kanjisense for phonetic component analysis |
| **EVOBC oracle bone** | Yes, for ancestral forms | Shows ancestral glyph development; Chinese-labeling but directly relevant |
| **Kaikki.org / Wiktionary** | Yes | Japanese extraction available at kaikki.org/jawiktionary; same infrastructure |
| **GlyphWiki** | Yes, directly | Includes Japanese-standard glyph variants, shinjitai/kyūjitai, kokuji |

---

## 1. Kanji Metadata & Frequency

### 1.1 KanjiDic2 (KANJIDIC2)
- **URL:** https://www.edrdg.org/kanjidic/kanjd2index_legacy.html
- **Download:** ftp://ftp.edrdg.org/pub/Nihongo/kanjidic2.xml.gz
- **Coverage:** 13,108 kanji (JIS X 0208 + 0212 + 0213). Data per kanji: on/kun readings (katakana/hiragana), English/French/Portuguese/Spanish meanings, stroke count, school grade (1–9), JLPT levels, Pinyin, Korean readings, frequency rank (1–2500), cross-references to Nelson, Halpern, Heisig, SKIP, Four Corner, De Roo, S&H codes.
- **License:** CC BY-SA 4.0
- **Format:** XML (UTF-8), well-documented DTD
- **Quality:** The definitive machine-readable kanji reference. Actively maintained by Jim Breen / EDRDG.

### 1.2 joyodb — Machine-Readable Jōyō Kanji Table
- **URL:** https://github.com/melissaboiko/joyodb
- **Coverage:** All 2,136 official Jōyō Kanji (2010 revision) with on/kun readings, example words, Unicode codepoints.
- **License:** Data from official government table (public domain); code open.
- **Format:** TSV, JSON, SQL, HTML
- **Quality:** Good automated extraction from the official PDF with test coverage.

### 1.3 Official Jōyō Kanji Table (Agency for Cultural Affairs)
- **URL:** https://www.bunka.go.jp/kokugo_nihongo/sisaku/joho/joho/kijun/naikaku/kanji/joyokanjisakuin/index.html
- **PDF:** https://www.bunka.go.jp/kokugo_nihongo/pdf/jouyoukanjihyou_h22.pdf
- **Coverage:** 2,136 kanji, November 2010 revision; approved readings and example compounds per character.
- **License:** Japanese government publication; PDF freely downloadable; machine processing requires parsing.

### 1.4 Jinmeiyō Kanji
- **Coverage:** 863 kanji (2017 revision) approved for personal names.
- **Best source:** In kanjium database (grade=9), KANJIDIC2, and x0213.org table
- **x0213.org URL:** https://x0213.org/jinmeiyou-kanji-code/index.en.html

### 1.5 JLPT Kanji Lists (Community-curated)
No official JLPT kanji list exists since the 2010 exam revision. Best community sources:
- **davidluzgouveia/kanji-data:** https://github.com/davidluzgouveia/kanji-data — JSON, MIT, ~2,000+ kanji with derived JLPT levels
- **AnchorI/jlpt-kanji-dictionary:** https://github.com/AnchorI/jlpt-kanji-dictionary — JSON per N-level
- **Tanos.co.uk:** https://www.tanos.co.uk/jlpt/ — Downloadable, based on pre-2010 official syllabi
- **Quality note:** All JLPT lists are approximations; treat as community consensus, not official data.

### 1.6 scriptin/kanji-frequency
- **URL:** https://github.com/scriptin/kanji-frequency
- **Coverage:** Frequency from Aozora Bunko (~8k kanji), Japanese Wikipedia (~20k kanji), Wikinews; interactive explorer at https://scriptin.github.io/kanji-frequency/
- **License:** CC BY 4.0
- **Format:** JSON files per corpus

### 1.7 BCCWJ Kanji Frequency (NINJAL)
- **URL:** https://clrd.ninjal.ac.jp/bccwj/en/freq-list.html
- **Coverage:** 104.3M-word corpus; NDC genre-specific kanji frequency lists; ~6,000+ kanji.
- **License:** Free for research/educational use
- **Format:** CSV/Excel

### 1.8 mifunetoshiro/kanjium
- **URL:** https://github.com/mifunetoshiro/kanjium
- **Coverage:** 6,400+ kanji; 124,137 words with pitch accent; on/kun/jukujikun readings; Chinese trad/simp forms; Korean equivalents; Pinyin; composition; JLPT levels; frequency from 5,000+ novels; Tatoeba example sentences.
- **License:** CC BY-SA 4.0
- **Format:** SQLite database

### 1.9 davidluzgouveia/kanji-data
- **URL:** https://github.com/davidluzgouveia/kanji-data
- **Coverage:** ~2,000+ kanji in single `kanji.json` with JLPT levels, WaniKani levels, stroke counts, grade, frequency, meanings, on/kun readings.
- **License:** MIT
- **Format:** JSON

### 1.10 kanjiapi.dev
- **URL:** https://kanjiapi.dev/ — GitHub: https://github.com/onlyskin/kanjiapi.dev
- **Coverage:** 13,000+ kanji via REST API; on/kun readings, meanings, stroke count, grade, JLPT, words.
- **License:** CC BY 3.0 FR
- **Format:** REST JSON API

### 1.11 kanjidatabase.com (Psycholinguistic Research)
- **URL:** https://www.kanjidatabase.com/
- **Coverage:** ~2,500 kanji with frequency (Asahi 1985–1998), stroke count, concreteness, familiarity, imageability, age of acquisition, visual complexity.
- **License:** Academic use
- **Format:** CSV download

---

## 2. Kanji Decomposition / Structure

### 2.1 KanjiVG
- **URL:** https://kanjivg.tagaini.net/ — GitHub: https://github.com/KanjiVG/kanjivg
- **Coverage:** ~6,500+ kanji SVG files with stroke-order data, element/component annotations (radical, element type, position), stroke shape/direction metadata. Variants archive included. Focused on Jōyō, Jinmeiyō, commonly used kanji.
- **License:** CC BY-SA 3.0
- **Format:** SVG with embedded XML attributes (kvg: namespace); programmatically parseable.
- **Quality:** The definitive Japanese stroke-order SVG dataset. Used by Jisho.org, Tagaini Jisho, many apps. Actively maintained.
- **Note:** Japanese stroke conventions differ from Chinese (PRC/Taiwan) in some characters.

### 2.2 KRADFILE / RADKFILE
- **URL:** https://www.edrdg.org/krad/kradinf.html
- **Download:** ftp://ftp.edrdg.org/pub/Nihongo/kradfile.gz and radkfile.gz
- **Coverage:** KRADFILE: 6,355 JIS X 0208 kanji → visual elements. RADKFILE: element → kanji list. KRADFILE2: 5,801 JIS X 0212 kanji. KRADFILE-U: 13,108 kanji unified.
- **License:** EDRDG licence (CC BY-SA); KRADFILE2 under CC BY-SA 3.0
- **Format:** Plain text (UTF-8 version available)
- **Note:** Elements are visual search components for JIS standard, not classical 214 Kangxi radicals.

### 2.3 cjkvi/cjkvi-ids (with Japan-specific files)
- **URL:** https://github.com/cjkvi/cjkvi-ids
- **Coverage:** Full CJK range + extensions. Japanese-specific: `hanyo-ids.txt` (general-use Japanese), `waseikanji-ids.txt` (Japanese-made kanji, GlyphWiki-linked). `ids-analysis.txt` provides Shuowen Jiezi-based etymological decomposition.
- **License:** GPLv2
- **Format:** Tab-separated text (IDS sequences using Unicode IDC characters)
- **Quality:** Authoritative. The `ids-analysis.txt` is the primary open-source kanji etymology decomposition dataset. Used by Kanjisense, Kanjijump.

### 2.4 Kanji Database Project ids-analysis.txt
- **URL:** https://kanji-database.sourceforge.net/ — also in cjkvi-ids above
- The key etymological data file: semantically-based decompositions from Shuowen Jiezi (Duan Yu edition), distinguishing semantic from phonetic components.
- **License:** GPLv2
- **Used by:** Kanjisense (https://kanjisense.com), Kanjijump (https://kanjijump.com)

### 2.5 IDSJoyoPlus (fasiha)
- **URL:** https://github.com/fasiha/IDSJoyoPlus
- **Coverage:** IDS decompositions for ~3,028 essential kanji (2,136 Jōyō + ~900 additional)
- **License:** Derived from cjkvi-ids (GPLv2)
- **Format:** Text — convenient pre-filtered subset for Japanese use

---

## 3. Etymology Specific to Kanji

### 3.1 cjkvi ids-analysis.txt (Best Open Etymology Source)
See §2.3/§2.4 above. This is the **best freely available structured kanji etymology** — traces character formation to Shuowen Jiezi, distinguishes semantic/phonetic components. Machine-usable, GPLv2.

### 3.2 Wiktionary / kaikki.org Japanese Data
- **URL:** https://kaikki.org/jawiktionary/ — Raw downloads: https://kaikki.org/dictionary/rawdata.html
- **Coverage:** All Japanese Wiktionary entries; includes etymology_text and etymology_templates for many kanji. Individual kanji glyph etymology varies widely in quality.
- **License:** CC BY-SA (same as Wiktionary)
- **Format:** JSONL
- **Quality:** Variable. Better for word-level etymology than individual kanji glyph origin. Same infrastructure as Chinese hanzi data — directly reusable with Japanese filtering.

### 3.3 Henshall's "A Guide to Remembering Japanese Characters"
- **Status:** NOT open data. Copyrighted by Tuttle Publishing. No official open digital version.
- **Coverage:** ~1,945 kanji (old Jōyō list) with etymological notes tracing glyph history from seal script.
- **Assessment:** Would be ideal if open; currently legally unavailable. Cannot use.

### 3.4 Lawrence Howell's EDHCC PDF
- **URL (parser):** https://github.com/acoomans/kanjinetworks — PDF: https://bradwarden.com/kanji/etymology/kanjietymology.pdf
- **Coverage:** ~6,000+ characters with etymologies; glyph-to-meaning connections in Old Chinese.
- **License:** Author-permission only for PDF; parser MIT-licensed. Not freely redistributable.
- **Quality:** Rich etymological content but not truly open.

### 3.5 Heisig RTK Index (Community Data)
- **cyphar/heisig-rtk-index:** https://github.com/cyphar/heisig-rtk-index — INDEX_VOL1.csv with Heisig numbers, Unicode, stroke counts, primitive flags.
- **sdcr/heisig-kanjis:** https://github.com/sdcr/heisig-kanjis — Heisig keywords, readings, component names.
- **Coverage:** ~2,200 kanji (Vol. 1) + ~1,000 (Vol. 3)
- **License:** Gray area — Heisig's keyword list is copyrighted. Legal redistribution is constrained.

### 3.6 Kanji Koohii Mnemonics
- **URL:** https://kanji.koohii.com/ — GitHub: https://github.com/fabd/kanji-koohii
- **Coverage:** 2,200 kanji; community-contributed mnemonic stories.
- **License:** CC BY-NC-SA 3.0 (non-commercial only); RTK data restricted.
- **Format:** Not a clean exportable dataset.

---

## 4. Japanese Readings & Phonology

### 4.1 JMdict / jmdict-simplified
- **JMdict URL:** https://www.edrdg.org/jmdict/j_jmdict.html
- **jmdict-simplified:** https://github.com/scriptin/jmdict-simplified (updated every Monday, CC BY-SA 3.0)
- **Coverage:** ~220,000+ Japanese-English entries; kanji forms + kana readings + POS tags + meanings. Pre-built JSON releases.
- **License:** CC BY-SA 3.0
- **Format:** JSON (via jmdict-simplified), XML (original)
- **Quality:** The definitive Japanese dictionary. Actively maintained.

### 4.2 Historical On'yomi (Go-on / Kan-on) Data
- **nk2028/onyomi-gakken-kanwa:** https://github.com/nk2028/onyomi-gakken-kanwa — On'yomi materials from Gakken Comprehensive Sino-Japanese Dictionary. Best open structured dataset for historical on'yomi stratification.
- **KANJIDIC2:** Has on'yomi but does not systematically label Go-on vs. Kan-on.
- **Unihan kSBGY:** Guangyun field for Middle Chinese → on'yomi correspondence (covers 19,583 characters).

### 4.3 Middle Chinese → Japanese On'yomi Mapping
- **nk2028/ToMiddleChinese:** https://github.com/nk2028/ToMiddleChinese — Python library for MC reconstructions.
- **nk2028 tshet-uinh-data:** https://github.com/nk2028/tshet-uinh-data — CC0, 19,337 Guangyun characters. Already used in Chinese hanzi mode; directly applicable.
- **Baxter-Sagart:** Already integrated in Chinese mode; OC/MC reconstructions map to on'yomi for phonetic components.
- **Kanjijump Middle Chinese reference:** https://www.kanjijump.com/middle-chinese — Tabular MC rime → Japanese on'yomi (Go/Kan) correspondences (Karlgren, Li Rong, Baxter transcriptions).

---

## 5. Visual / Historical Glyph Data

### 5.1 Chinese Historical Glyphs (Applicable to Japanese)
Oracle bone, bronze, and seal script data from Chinese sources apply directly to most kanji (all non-kokuji):
- **Oracle bone (甲骨文):** EVOBC dataset (already in project), Hanziyuan
- **Bronze inscriptions (金文):** Same
- **Seal script (小篆 / Shuowen):** Directly applicable; already integrated
- **Make Me a Hanzi:** Traditional forms covering most kanji; etymology types applicable

### 5.2 GlyphWiki
- **URL:** https://en.glyphwiki.org/ — API: https://glyphwiki.org/
- **Coverage:** 2M+ named glyphs; Japanese-standard variant forms (Jōyō standard, shinjitai/kyūjitai, kokuji, JIS standard forms).
- **License:** Data freely usable
- **Format:** SVG API, KAGE engine format
- **Quality:** Most comprehensive for rare/variant/kokuji forms.

### 5.3 Kuzushiji-Kanji (Pre-modern Japanese Script)
- **URL:** https://github.com/rois-codh/kmnist
- **Coverage:** 140,424 images of 3,832 historical kanji from pre-Meiji texts.
- **License:** CC BY-SA 4.0
- **Format:** Image dataset (ML-oriented)
- **Quality:** Shows pre-modern Japanese glyph forms; not an etymology database.

### 5.4 KanjiAlive Radical History SVGs
- **URL:** https://github.com/kanjialive/kanji-data-media
- **Coverage:** 247 radicals with historical derivation SVG animations; 1,235 kanji data.
- **License:** CC BY 4.0
- **Format:** CSV + SVG + MP3

---

## 6. Shinjitai / Kyūjitai Mappings

### 6.1 dahlia/shinjitai-table
- **URL:** https://github.com/dahlia/shinjitai-table
- **Coverage:** ~364 shinjitai↔kyūjitai pairs from official Jōyō Kanji Table. `shinjitai.json` (modern→traditional), `kyujitai.json` (traditional→modern).
- **License:** Open

### 6.2 new-village/joyo-kanji
- **URL:** https://github.com/new-village/joyo-kanji
- **Coverage:** Python library for shinjitai↔kyūjitai conversion; `kanji.json` + `variants.json`.
- **License:** Open

### 6.3 cjkvi/cjkvi-variants
- **URL:** https://github.com/cjkvi/cjkvi-variants
- **Coverage:** Broader CJK variant relationships database.
- **License:** Open

---

## 7. Reference Implementations (Open-Source Apps Using This Data)

### 7.1 Kanjisense
- **URL:** https://kanjisense.com/about
- Stack (all open): CHISE IDS ids-analysis.txt (GPLv2, etymology), KANJIDIC2 (readings), nk2028 Middle Chinese (phonology, CC0), scriptin/kanji-frequency (CC BY 4.0), GlyphWiki/Hanazono font, Unihan.
- Most closely comparable to what we want to build.

### 7.2 Kanjijump
- **URL:** https://www.kanjijump.com/
- Uses Kanji Database Project ids.txt and ids-analysis.txt (GPLv2). Explicitly addresses MC → on'yomi correspondences for phonetic components.

### 7.3 scriptin/topokanji
- **URL:** https://github.com/scriptin/topokanji
- **Coverage:** Topological learning order for ~2,200 kanji by component dependency + frequency.
- **License:** CC
- **Useful for:** Determining display order, component dependency graph.

### 7.4 Tagaini Jisho
- **URL:** https://github.com/Gnurou/tagainijisho
- Open-source (GPL) desktop app; uses KanjiVG, JMdict, KANJIDIC2. Well-maintained reference implementation.

---

## 8. Japanese-Specific Character Set Notes

- **Joyo kanji:** 2,136 (official list; most important for learners)
- **Jinmeiyo kanji:** ~863 (for personal names)
- **Common hyogai:** ~2,000–3,000 additional frequently encountered
- **Kokuji (国字):** ~400+ Japanese-invented kanji not in Chinese; ~9 in Jōyō (e.g. 働 hataraku = work). Documented in Wikipedia kokuji list, kanjium, `waseikanji-ids.txt`.
- **Shinjitai/Kyūjitai pairs:** ~364 where forms differ between modern and traditional.

---

## 9. Academic Resources

### 9.1 NINJAL
- **URL:** https://www.ninjal.ac.jp/english/ — Corpus: https://clrd.ninjal.ac.jp/en/
- Key datasets: BCCWJ frequency (§1.7), Corpus of Spontaneous Japanese, Oxford-NINJAL Corpus of Old Japanese (https://oncoj.ninjal.ac.jp/)

### 9.2 ROIS-DS CODH
- **URL:** https://codh.rois.ac.jp/
- Key: Kuzushiji-Kanji images (§5.3), pre-modern Japanese text dataset.

### 9.3 kanjidatabase.com
See §1.11. Psycholinguistic properties of ~2,500 kanji.

---

## Integration Priority for This Project

### Phase 1: Core Kanji Mode
1. **KANJIDIC2** — primary metadata (readings, meanings, JLPT, grade, frequency rank)
2. **cjkvi-ids/ids-analysis.txt** — etymological decomposition (already partially used for Chinese)
3. **jmdict-simplified** — word readings for search/cross-reference
4. **davidluzgouveia/kanji-data** — JLPT levels + WaniKani level metadata (MIT, easy JSON)
5. **scriptin/kanji-frequency** — frequency rankings
6. **melissaboiko/joyodb** — Jōyō classification + official readings

### Phase 2: Visual & Historical
7. **KanjiVG** — stroke order SVGs with component annotations (different from Make Me a Hanzi)
8. **dahlia/shinjitai-table** — shinjitai↔kyūjitai mapping for variant display
9. Chinese historical glyph data (already present) — reuse for non-kokuji kanji

### Phase 3: Advanced Phonology
10. **nk2028 Middle Chinese** — already present; expose Japanese on'yomi connections
11. **nk2028/onyomi-gakken-kanwa** — Go-on / Kan-on stratification
12. **kaikki.org Japanese Wiktionary** — supplementary etymology text

### Phase 4: Learning Features
13. **scriptin/topokanji** — component learning order
14. **kanjidatabase.com** psycholinguistic data (concreteness, familiarity, AoA)
15. **kanjium** pitch accent data
