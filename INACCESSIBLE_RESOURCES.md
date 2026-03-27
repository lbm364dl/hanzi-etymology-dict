# Resources Not Yet Integrated (But Valuable)

This documents data sources and references that could improve the database but are not currently integrated, either because they are paywalled, web-only, or require manual effort to digitize.

---

## A. Paywalled / Commercial (High Priority if Access Obtained)

### 1. Outlier Linguistics Dictionary of Chinese Characters
- **URL:** https://www.outlier-linguistics.com
- **Type:** Pleco add-on ($30 Essentials, $100 Expert)
- **Coverage:** ~1,500 characters + 300 semantic components (growing)
- **Why it matters:** The most rigorously researched modern etymology resource in English. Created by a team including a Chinese paleography PhD. Explicitly classifies components as semantic, phonetic, or empty. Distinguishes original meaning from modern meaning.
- **Status:** Proprietary. Cannot be integrated without license agreement.
- **What we could do:** Use as a cross-reference / validation source if purchased for personal research.

### 2. Wenlin Software
- **URL:** https://www.wenlin.com
- **Type:** Commercial software ($49-$99)
- **Coverage:** Includes Schuessler's EDOC data, character decomposition, stroke order
- **Why it matters:** Contains structured etymological data from Schuessler, one of the top Sino-Tibetan comparative linguists.
- **Status:** Commercial license required.

### 3. Pleco Professional Add-ons
- Various paid add-on dictionaries contain etymological information not available elsewhere in structured form.

---

## B. Web-Only (No Bulk Download / API Limitations)

### 4. Xiaoxuetang 小學堂 (Academia Sinica)
- **URL:** https://xiaoxue.iis.sinica.edu.tw
- **Coverage:** 22,000+ character forms across oracle bone, bronze, Warring States, seal, and regular scripts. 134,000+ phonological entries.
- **Why it matters:** The gold standard for digital Chinese paleography. Maintained by Taiwan's top research institution.
- **Status:** Web-only lookup. No bulk download. Registration may be required.
- **What we could do:** Manual extraction for high-priority characters; check if they offer academic data sharing agreements.

### 5. CUHK Multi-function Chinese Character Database 漢語多功能字庫
- **URL:** https://humanum.arts.cuhk.edu.hk/Lexis/lexi-mf/
- **Coverage:** Archaic script forms, component trees, form-meaning explanations, Shuowen index, dialect pronunciations
- **Why it matters:** Rated "world leading" academically. Integrates paleographic data with modern linguistic analysis.
- **Status:** Free web access, but no bulk download or API.

### 6. hanziyuan.net (Richard Sears / 汉字叔叔)
- **URL:** https://hanziyuan.net
- **Source code:** https://github.com/Dixin/Etymology
- **Coverage:** 96,000+ ancient character forms (31K oracle bone, 24K bronze, 49K seal, etc.)
- **Why it matters:** Largest single collection of historical glyph images. Visual evolution across script periods.
- **Status:** Website source code is on GitHub, but the glyph images themselves are not separately downloadable as a dataset. No explicit open data license.
- **What we could do:** Could potentially coordinate with Richard Sears for academic data sharing.

### 7. zdic.net 漢典
- **URL:** https://www.zdic.net
- **Coverage:** Integrates Kangxi, Shuowen, character evolution images, multiple references
- **Status:** Free web access. No bulk download.

### 8. HanziCraft Phonetic Sets
- **URL:** https://hanzicraft.com/lists/phonetic-sets
- **Coverage:** 422 exact-match + 225 tone-variant phonetic sets (~6,800 chars)
- **Why it matters:** Structured data on which characters share phonetic components
- **Status:** Web-only. Not available as downloadable structured data.

### 9. YinQiWenYuan 殷契文渊
- **URL:** https://jgw.aynu.edu.cn
- **Coverage:** Photos of original oracle bones, transcribed characters, research articles
- **Status:** Free web platform, registration required.

### 10. Academia Sinica Bronze Inscriptions Database
- **URL:** https://www.ihp.sinica.edu.tw/~bronze/
- **Coverage:** ~14,000 bronze vessel records with inscriptions
- **Status:** Web-based, registration required.

### 11. Open ACC (Ancient Chinese Characters Glyphs Database)
- **URL:** https://lingdata.org/acc/
- **Coverage:** Oracle bone, bronze, Chu bamboo slips, Qin bamboo slips, Dunhuang variants
- **Status:** Online collection; download/API access unclear.

---

## C. Books Not Yet Digitized as Structured Data (Highest Scholarly Value)

These are the most authoritative references that exist only as printed books or scanned PDFs (not structured data). Digitizing entries from these would dramatically improve our database quality.

### Priority 1: Essential

**12. 字源 Ziyuan (Li Xueqin 李學勤, chief editor)**
- Year: 2012, Tianjin Ancient Books Publishing
- Coverage: Comprehensive modern etymology for ~4,000+ common characters
- Status: Considered the most authoritative modern Chinese character etymology dictionary. Some MDX dictionary files exist on FreeMdict forums.
- **Impact if digitized:** Would provide the most reliable modern etymological analysis for thousands of characters.

**13. 說文新證 Shuowen Xinzheng (Ji Xusheng 季旭昇)**
- Year: 2002 (1st ed.), 2014 (2nd ed., expanded to 3 vols)
- Coverage: Modern corrections to every Shuowen entry using oracle bone/bronze evidence
- Status: Print only. No known digital structured data.
- **Impact if digitized:** Would flag exactly which Shuowen etymologies are incorrect and provide corrections.

**14. 文字學概要 Wenzixue Gaiyao / Chinese Writing (Qiu Xigui 裘錫圭)**
- Year: 1988 (Chinese); 2000 (English translation by Mattos & Norman)
- Coverage: Theoretical framework for Chinese character formation and evolution
- Status: English translation available on some academic platforms. PDF on Starling/Academia.edu.
- **Impact:** Provides the theoretical classification system for all character types.

### Priority 2: Highly Important

**15. 古文字詁林 Guwenzi Gulin (Li Pu 李圃, chief editor)**
- Year: 1999-2004, Shanghai Educational Publishing
- Coverage: 12 volumes. Collects ALL scholarly opinions on every character in the Shuowen from hundreds of scholars
- Status: Available on Archive.org as scanned images
- **Impact if digitized:** Would provide comprehensive scholarly consensus/disagreement for ~9,800 characters.

**16. 甲骨文字典 Jiaguwen Zidian (Xu Zhongshu 徐中舒)**
- Year: 1989 (1st ed.), 2006 (enlarged ed.)
- Coverage: 4,500+ oracle bone characters with detailed analysis
- Status: Some scanned versions available on Academia.edu
- **Impact if digitized:** Most authoritative reference for oracle bone script character analysis.

**17. 金文編 Jinwen Bian (Rong Geng 容庚)**
- Year: 1925 (1st ed.), 1985 (4th ed. expanded)
- Coverage: 18,000+ bronze inscription character forms
- Status: PDF available on FreeMdict forums
- **Impact if digitized:** Standard reference for bronze inscription character forms.

**18. 漢語大字典 Hanyu Da Zidian**
- Year: 1986-1990, Sichuan/Hubei Dictionaries Publishing
- Coverage: 56,000+ characters. The largest Chinese character dictionary.
- Status: Available on Archive.org as scanned PDF (9 volumes)
- **Impact if digitized:** Would provide definitions and historical citations for the broadest character coverage.

**19. 同源字典 Tongyuan Zidian (Wang Li 王力)**
- Year: 1982
- Coverage: Traces cognate relationships between Chinese characters sharing etymological roots
- Status: Print only
- **Impact if digitized:** Would add cognate/word family data to our database.

### Priority 3: Valuable Supplementary

**20. 漢字源流字典 Hanzi Yuanliu Zidian (Gu Yankui 谷衍奎)**
- Year: 2003, Huaxia Publishing
- Coverage: ~4,000 common characters with pictorial etymology explanations
- Status: Print only
- **Impact:** Accessible etymology explanations suitable for non-specialist audiences.

**21. 戰國古文字典 Zhanguo Guwenzi Dian (He Linyi 何琳儀)**
- Year: 1998
- Coverage: Warring States period character forms
- Status: Print only

**22. 古文字類編 Guwenzi Leibian (Gao Ming 高明)**
- Year: 1980 (1st ed.), 2008 (enlarged ed.)
- Coverage: Ancient character forms classified by structure
- Status: Print only

**23. Shirakawa Shizuka (白川静) Trilogy:**
- 字統 Jitō (1984): Origins and development of character forms
- 字通 Jitsū (1996): Comprehensive character analysis
- 常用字解 Jōyō Jikai (2003): Etymology of 2,136 common kanji
- Status: Japanese language, print only. Controversial among some Chinese scholars for some interpretations.

**24. Karlgren, Grammata Serica Recensa (1957)**
- Coverage: ~7,700 characters with reconstructed archaic and ancient Chinese pronunciation
- Status: PDF available on Starling database and Scribd. GSR numbers still widely used as reference.
- **Impact:** Would add GSR numbers and Karlgren's Middle Chinese reconstructions.

**25. Wieger, Chinese Characters (1915)**
- Coverage: ~2,500 characters with pictographic explanations and character trees
- Status: Full text on Archive.org and Google Books (public domain)
- **Impact:** Historical Western perspective. Some etymologies outdated but the character genealogy approach is useful.

---

## D. Datasets Partially Available (Could Be Expanded)

### 26. ctext.org Classical Texts via API
- **Status:** API exists (https://ctext.org/tools/api) but rate-limited. Full bulk download requires special arrangement.
- **What we could do:** Systematically query Shuowen entries, Erya glosses, Guangyun readings for characters not already covered. This is a manual/slow process due to rate limits.

### 27. STEDT (Sino-Tibetan Etymological Dictionary and Thesaurus)
- **URL:** https://stedt.berkeley.edu
- **Coverage:** 1,000,000 lexical records across Sino-Tibetan
- **Status:** Searchable online. Software on GitHub. Full bulk data on Dryad (https://datadryad.org/dataset/doi:10.6078/D1159Q)
- **What we could do:** Download the Dryad dataset and extract Chinese cognate data.

### 28. HUST-OBC Oracle Bone Images
- **URL:** https://github.com/Pengjie-W/HUST-OBC
- **Coverage:** 140,053 images, 1,588 deciphered + 9,411 undeciphered characters
- **Status:** Images available. Could extract the character-to-image mapping.

### 29. Wikimedia Ancient Chinese Characters Project
- **URL:** https://commons.wikimedia.org/wiki/Commons:Ancient_Chinese_characters_project
- **Status:** SVG/PNG files for oracle bone, bronze, seal script. 214 radicals completed. Ongoing.
- **What we could do:** Download completed character evolution SVGs and integrate.

---

## E. Action Items for Future Integration

1. **Highest impact, lowest effort:** Download STEDT data from Dryad; download Wikimedia SVGs; query ctext.org API for Guangyun readings
2. **High impact, moderate effort:** Obtain FreeMdict/MDX versions of 字源, 金文編; OCR and structure key entries
3. **High impact, high effort:** Contact Xiaoxuetang / CUHK for academic data sharing; digitize 說文新證 corrections
4. **Community effort:** Set up contribution pipeline for scholars to add/verify entries from print references
