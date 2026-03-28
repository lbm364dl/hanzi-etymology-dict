# Database Schema

Each character in the database is a JSON object with the following fields.
All fields are optional except `character` and `codepoint`.

## Core Identity

| Field | Type | Source | Description |
|-------|------|--------|-------------|
| `character` | string | all | The Chinese character (single Unicode character) |
| `codepoint` | string | all | Unicode codepoint, e.g., `"U+99AC"` |
| `definitions` | string | Unihan, MakeMe, CEDICT | English definition(s) |
| `readings` | object | Unihan | Pronunciation readings (see below) |
| `frequency_rank` | integer | hanziDB | Frequency rank (1 = most common, 的) |
| `hsk_level` | integer | hanziDB | HSK level (old standard, 1-6) |
| `hsk3_level` | integer | AnimCJK | HSK 3.0 level (2021 standard, 1-9) |
| `frequency_tier` | string | AnimCJK | One of: `"top_2500"`, `"3500_plus"`, `"common"` |

### `readings` Object

| Field | Type | Description |
|-------|------|-------------|
| `mandarin` | string | Standard Mandarin pinyin with tone marks |
| `cantonese` | string | Jyutping romanization |
| `japanese_on` | string | Japanese on'yomi (Sino-Japanese reading) |
| `japanese_kun` | string | Japanese kun'yomi (native reading) |
| `korean` | string | Korean reading (Yale romanization) |
| `vietnamese` | string | Vietnamese reading (Quoc ngu) |
| `tang` | string | Tang dynasty reading reconstruction |

## Structure & Decomposition

| Field | Type | Source | Description |
|-------|------|--------|-------------|
| `radical_stroke` | string | Unihan | Kangxi radical number + residual strokes, e.g., `"187.0"` |
| `total_strokes` | string | Unihan | Total stroke count |
| `ids` | string | CJKVI-IDS | Ideographic Description Sequence, e.g., `"⿰氵可"` |
| `decomposition_ids` | string | MakeMe/CJKVI | IDS decomposition (MakeMe preferred, CJKVI fallback) |
| `cjk_decomp` | string | CJK-Decomp | Alternative decomposition format, e.g., `"a(氵,可)"` |
| `variants` | object | Unihan, CEDICT | Traditional/simplified/semantic variant codepoints |

### `variants` Object

| Field | Type | Description |
|-------|------|-------------|
| `traditional` | string | Traditional variant(s), `"U+XXXX"` format |
| `simplified` | string | Simplified variant(s), `"U+XXXX"` format |
| `semantic` | string | Semantic variant(s) |

## Etymology & Formation

| Field | Type | Source | Description |
|-------|------|--------|-------------|
| `formation_type` | string | consensus | Character formation type (see values below) |
| `formation_type_inferred` | boolean | build | `true` if formation_type was inferred from IDS+radical |
| `formation_type_conflict` | object | build | Present when sources disagree. Maps source name to its claim. |
| `formation_details` | object | MakeMe, Dong, ytenx, Shuowen | Component identification (see below) |
| `etymology_notes` | array | multiple | Etymology explanations from each source (see below) |

### `formation_type` Values

| Value | Chinese | Description |
|-------|---------|-------------|
| `"phono-semantic"` | 形聲 | Semantic component + phonetic component |
| `"ideographic"` | 會意 | Compound of meaning-bearing components |
| `"pictographic"` | 象形 | Picture of the thing it represents |
| `"indicative"` | 指事 | Abstract symbol representing a concept |
| `"phonetic-loan"` | 假借 | Character borrowed for its sound |

### `formation_details` Object

| Field | Type | Source | Description |
|-------|------|--------|-------------|
| `semantic` | string | MakeMe, Dong | The semantic (meaning) component character |
| `phonetic` | string | MakeMe, Dong, IDS, Shuowen | The phonetic (sound) component character |
| `phonetic_source` | string | build | Where phonetic was identified: `"shuowen"` if from Shuowen extraction |
| `phonetic_component_ytenx` | string | ytenx | Phonetic component per Zhengzhang's system |
| `inferred` | boolean | build | `true` if semantic/phonetic were inferred from IDS + Kangxi radical |

### `etymology_notes` Array Items

| Field | Type | Description |
|-------|------|-------------|
| `source` | string | Source identifier: `"makemeahanzi"`, `"dong_chinese"`, `"shuowen_jiezi"`, `"wiktionary"` |
| `text` | string | The etymology explanation text |
| `caveat` | string | Warning about reliability (present on Shuowen entries) |
| `via_traditional` | string | If propagated from a traditional/semantic variant, the variant character |

## Historical Phonology

| Field | Type | Source | Description |
|-------|------|--------|-------------|
| `historical_phonology` | array | multiple | Old/Middle Chinese reconstructions (see below) |
| `guangyun` | array | NK2028 | Guangyun entries with phonological position + fanqie |
| `phonetic_class` | string | Unihan | Soothill/Fenn phonetic class number(s) |
| `phonetic_series` | array | Unihan | kPhonetic class numbers this character belongs to |
| `phonetic_family` | array | build | Sibling characters sharing the same phonetic series (max 30) |

### `historical_phonology` Array Items

Each item may have any combination of these fields:

| Field | Type | Source | Description |
|-------|------|--------|-------------|
| `old_chinese` | string | Baxter-Sagart | OC reconstruction (Baxter-Sagart 2014), e.g., `"*mˤraʔ"` |
| `old_chinese_zhengzhang` | string | ytenx | OC reconstruction (Zhengzhang system), e.g., `"mraːʔ"` |
| `middle_chinese` | string | Baxter-Sagart | MC reconstruction (Baxter notation), e.g., `"maeX"` |
| `middle_chinese_guangyun` | string | NK2028 | MC phonological position from Guangyun, e.g., `"明二麻上"` |
| `fanqie` | string | NK2028 | Fanqie spelling from Guangyun, e.g., `"莫下"` |
| `rhyme_group` | string | ytenx | OC rhyme group classification |
| `gloss` | string | Baxter-Sagart | English meaning for this reading |
| `gsr` | string | Baxter-Sagart | Grammata Serica Recensa number |
| `source` | string | build | Source identifier: `"guangyun"`, `"zhengzhang"`, `"zhengzhang_wikt"`, `"baxter_sagart_wikt"` |

### `guangyun` Array Items

| Field | Type | Description |
|-------|------|-------------|
| `phonological_position` | string | Full MC classification: initial + open/closed + division + rhyme + tone |
| `fanqie` | string | Traditional fanqie pronunciation spelling |

## Classical Sources

### `shuowen` Object

| Field | Type | Description |
|-------|------|-------------|
| `explanation` | string | Xu Shen's original gloss (~100 AD) |
| `radical` | string | Shuowen radical classification |
| `pronunciation_fanqie` | string | Fanqie pronunciation |
| `seal_character` | string | Small seal script form |
| `components` | array | Structural components listed by Xu Shen |
| `xuan_note` | string | Xu Xuan's commentary |
| `kai_note` | string | Xu Kai's commentary |
| `duan_notes` | array | Duan Yucai's commentary entries |
| `variants` | array | Variant forms (重文) |
| `modern_correction` | object | Present when modern sources disagree with Shuowen (see below) |

### `shuowen.modern_correction` Object

| Field | Type | Description |
|-------|------|-------------|
| `shuowen_says` | string | Shuowen's formation type claim |
| `modern_says` | string | Modern consensus formation type |

### `kangxi` Object

| Field | Type | Description |
|-------|------|-------------|
| `explanation` | string | Kangxi Dictionary entry text |
| `radical` | string | Kangxi section/volume |

## Validation & Quality

| Field | Type | Source | Description |
|-------|------|--------|-------------|
| `confidence` | integer | build | Quality confidence score, 0-100 |
| `verification_status` | string | build | See values below |
| `shuowen_accuracy` | string | build | `"confirmed"` or `"corrected"` |
| `shuowen_phonetic_validated` | boolean | build | `true` if Shuowen's phonetic claim validated by OC rhyme |
| `source_count` | integer | build | Number of distinct sources contributing data |
| `sources` | array | build | List of source identifiers |

### `verification_status` Values

| Value | Meaning |
|-------|---------|
| `"cross-verified"` | 2+ modern sources provide etymology |
| `"single-source"` | Exactly 1 modern source provides etymology |
| `"classical-only"` | Only Shuowen Jiezi (no modern corroboration) |
| `"unverified"` | Has notes but no clear classification |
| *(absent)* | No etymology data at all |

## Historical Glyphs

| Field | Type | Source | Description |
|-------|------|--------|-------------|
| `historical_glyphs` | object | EVOBC | Glyph image availability from EVOBC dataset |
| `local_glyphs` | object | build | Local SVG files available (see below) |

### `historical_glyphs` Object

| Field | Type | Description |
|-------|------|-------------|
| `evobc_id` | string | EVOBC dataset character ID |
| `image_count` | integer | Total images available across all eras |
| `eras_available` | array | Script periods with images: `"oracle_bone"`, `"bronze_inscription"`, `"spring_autumn"`, `"warring_states"`, `"seal_script"`, `"clerical_script"` |

### `local_glyphs` Object

| Field | Type | Description |
|-------|------|-------------|
| `dong_chinese` | array | Script types available: `"oracle"`, `"bronze"`, `"seal"`, `"cursive"` |
| `wikimedia_seal` | array | Wikimedia Commons SVG filenames for seal script |

## Comparative Linguistics

| Field | Type | Source | Description |
|-------|------|--------|-------------|
| `sino_tibetan_cognates` | array | Sagart CLDF | Cognate links across Sino-Tibetan languages |

### `sino_tibetan_cognates` Array Items

| Field | Type | Description |
|-------|------|-------------|
| `concept` | string | Semantic concept (e.g., `"above"`, `"horse"`) |
| `cognacy_set` | string | Cognate set ID in the Sagart dataset |
| `cognate_count` | integer | Number of cognate forms across languages |
| `sample_cognates` | array | Up to 3 sample cognate forms: `[{"language": "OldTibetan", "form": "steŋ"}]` |

## CEDICT

| Field | Type | Source | Description |
|-------|------|--------|-------------|
| `cedict_definitions` | array | CC-CEDICT | List of definition strings from CC-CEDICT |
