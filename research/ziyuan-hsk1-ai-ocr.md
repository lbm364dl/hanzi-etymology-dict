# 字源 PDF p. 497 OCR verification: 憂 and 愛

## Scope and evidence

This is a source-only review of the provisional OCR for PDF page 497 (printed page not exposed in the page record). The book is 李學勤主編,《字源》, 2012, 天津古籍出版社／辽宁人民出版社 edition. I read the producer's `AGENTS.md` and `PIPELINE.md`, plus this repository's `research/local-book-sources.md`. The scan is provisional evidence, and claims below concern literal transcription only.

- Scan: `/home/catalin/hanzi-etymology-books/research-ocr/ziyuan-full/page-0497/source.png`
- Page-record source SHA-256: `cd2d1888199f1a005780526ec268e20c5cb162f83419a125fc426415981b75c7`
- Local `source.png` byte SHA-256: `b6b9683afda761707143dd42b20a212e61fa9bdccb16d1bbe105280424eecdc8` (different from the page-record `source_sha256`; both values are retained rather than conflated)
- OCR evidence SHA-256: `937582a72653536f9a309d81f7cc395d52b2d649dff42c750022f573202856cd`
- Raw OCR text SHA-256 (UTF-8): `2631a7ca209d5fd072fd1c48d8e8976e64fc9bbf14d5a1f7a0919ae79fd2cc98`
- The live page record text currently hashes to that same value and equals the raw OCR text; no effective correction is present. Therefore the effective-text SHA-256 is also `2631a7ca209d5fd072fd1c48d8e8976e64fc9bbf14d5a1f7a0919ae79fd2cc98`.

I enlarged the original scan around the upper 憂 prose, lower 愛 prose, and the 愛 form gallery. This note preserves an earlier mistaken assessment and its supersession: my first enlargement led me to reject all five proposed changes as literal 㤐. On reopening the original pixels at a tighter scale, that rejection was wrong.

## Lower 愛 paragraph: confirmed literal corrections

At all five locations, the scan's upper component has the curved/open 旡-like strokes, with no closed 口 box that would support 占 in 㤐; the lower 心 is visible. These are printed 㤅, not 㤐. Confirm the exact five raw spans for a source-bound correction:

| Offset | Raw span | Exact local anchor |
|---:|---|---|
| 1028–1029 | `㤐` → `㤅` | `形声字。从夂，㤐声。爱实由悉字演变而来。` |
| 1047–1048 | `㤐` → `㤅` | `《玉篇》：“㤐，今作愛。”㤐、愛当为古今字。` |
| 1054–1055 | `㤐` → `㤅` | `㤐、愛当为古今字。《说文》：“愛，行兒。从夂，㤐声。”` |
| 1077–1078 | `㤐` → `㤅` | `《说文·心部》：“㤐，惠也。从心，旡声。慁，古文。”` |
| 1090–1091 | `㤐` → `㤅` | `《说文》：“愛，行兒。从夂，㤐声。”` |

The first verdict in this note rejected these proposals; it is superseded because I failed to inspect the upper strokes closely enough. The upper 憂 passage has separate `㤐` occurrences at offsets 351, 381 and 390 (`此字的初形作㤐`; `《说文》将㤐、憂`; `训㤐为“愁也”`). They are outside this correction set and have not been independently adjudicated to the same stroke-level standard; do not propagate the 愛 correction to them.

## Other lower 愛 paragraph OCR errors and checked 夂

On independent reinspection of the enlarged scan, five further OCR forms are the same printed 㤅, with an open, curved 旡-like upper form over 心. The OCR's `悉` would require the visibly different 釆 top; the OCR's `恐` would require a 巩-like top. Neither is present in these five source occurrences. Exact raw spans and anchors:

| Offset | Raw span | Source reading | Exact local anchor |
|---:|---|---|---|
| 1034–1035 | `悉` | `㤅` | `爱实由悉字演变而来` |
| 1107–1108 | `恐` | `㤅` | `慁，古文。”恐加“夂”即成为愛字` |
| 1154–1155 | `悉` | `㤅` | `甲本：“甚悉(爱)必大費(费)”` |
| 1166–1167 | `悉` | `㤅` | `”，悉用法同愛。中山王方壶铭：“䧹悉深` |
| 1181–1182 | `悉` | `㤅` | `中山王方壶铭：“䧹悉深则辱人翕”` |

Do not make a broad character replacement: these are five occurrence-bound observations. The three `夂` candidates at offsets 1026 (`从夂，㤐声`), 1075 (`愛，行兒。从夂，㤐声`) and 1110 (`恐加“夂”即成为愛字`) have the expected 夂 form and remain literal. No 夂/夊 correction is proposed.

## Glyph-description review flag

The 愛 gallery's printed row labels read `战国 战国 《说文》古文 《说文》小篆 楷书`, under the 愛 headword; the next row is labeled `秦 《说文》小篆 汉 汉 汉 汉 楷书 楷书`. This makes OCR glyph descriptions `g015`–`g019` (which name several forms as `㤐`, including `g019` “楷书「㤐」字”) suspect as description-to-form association/recognition errors. The visible gallery associates these five cited forms with the 愛 entry; `g020`–`g027` descriptions are consistent with the second row labels. This is a glyph-description review flag, not a text-span OCR correction, and I do not assign replacement identities to historical forms from the prose alone. Preserve the source glyph references until their individual images are inspected and description corrections are separately justified.

## Outcome

Confirmed literal OCR errors: five `㤐` → `㤅` occurrences and the five additional occurrence-bound substitutions `悉`/`恐` → `㤅` listed above. The three listed 夂 forms match the scan. The separate upper 憂 㤐 forms remain unadjudicated and must not inherit these 愛-specific edits. The earlier rejected verdict and generic positive claims are retained as superseded/retracted so the review history is transparent. No producer corpus, correction overlay, or canonical entry was changed by this review.

## Coordinator source repair and consumer verification

On 2026-10-02 the coordinator applied ten exact occurrence patches to the book producer's source-bound correction layer after directly inspecting the original scan and enlarged lower paragraph. The independent source recheck confirmed all ten. Raw OCR remains unchanged. Producer effective evidence and rebuilt consumer page evidence both equal `66b92aa32cd18a3aa6dc3978d542d9889f1d9b6a27e51733b763ca0e76755329`; reviewable corrections and verification are in `research/ocr-corrections/ziyuan-2012-p0497/`. The complete 1,435-page consumer corpus was republished atomically.

The earlier claims of unchanged effective text describe the pre-repair inspection, not the current corpus. The scan's decoded RGB pixel hash and encoded PNG-file hash label different representations; their difference does not indicate a changed source image.

Two fresh CLI visual checks also retained incorrect rationales: the whole-paragraph check asserted 占-shaped tops, and an isolated check returned the correct replacement but reversed the candidate component definitions in its explanation. They are not treated as clean approvals. Exact source crops and explicit comparison of open curved upper strokes against a closed 口 were needed to resolve the discrepancy. This failure concerns visual occurrence identification and raw-text anchoring, not etymological interpretation. The independently corrected interactive source note and coordinator pixel inspection support the literal patches. No article prose or whole-page review approval is inferred from these source repairs.
