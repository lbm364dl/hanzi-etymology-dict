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

Do not make a broad character replacement: these are five occurrence-bound observations. The three questioned forms at offsets 1026 (`从夂，㤐声`), 1075 (`愛，行兒。从夂，㤐声`) and 1110 (`恐加“夂”即成为愛字`) have not been assessed for a stroke-level 夂/夊 distinction. No 夂/夊 correction is proposed and no identity claim is made here.

## 愛 gallery metadata proposals

I inspected the original gallery in numbered reading order. The first row is directly below the 愛 (爱) headword and its reading. Its five form images are followed/aligned by the labels `战国`, `战国`, `《说文》古文`, `《说文》小篆`, and `楷书`. The ordered association is clear from the image positions; Unicode identities for the first three historical shapes are not established by these labels. Replace the current over-specific metadata descriptions with page-bound descriptions that preserve the source label without naming a guessed Unicode character:

| ID | Current raw description | Proposed safe description |
|---|---|---|
| g015 | `战国文字「㤐/愛」字形` | `《字源》愛条字形1；图下注“战国”` |
| g016 | `战国文字「㤐/愛」字形` | `《字源》愛条字形2；图下注“战国”` |
| g017 | `《说文》古文「㤐/愛」字形` | `《字源》愛条字形3；图下注“《说文》古文”` |
| g018 | `《说文》小篆「㤐」字` | `《字源》愛条字形4；图下注“《说文》小篆”` |
| g019 | `楷书「㤐」字` | `《字源》愛条字形5；图下注“楷书”` |

These are metadata wording proposals only. They describe the figures' page location, sequence, and printed captions; they make no independent Unicode reading claim. Bounds below are source-image pixel coordinates (x0,y0,x1,y1); hashes are SHA-256 of the cropped RGB pixel bytes before enlargement. The page-record `source_sha256` is the decoded RGB-pixel hash `cd2d1888199f1a005780526ec268e20c5cb162f83419a125fc426415981b75c7`; the encoded PNG file-byte hash is `b6b9683afda761707143dd42b20a212e61fa9bdccb16d1bbe105280424eecdc8`.

| ID | Crop bounds | Crop pixel SHA-256 |
|---|---|---|
| g015 | `(160,2460,320,2640)` | `017e0550790e52c541e0e8e0dabdfd8edd487872697c6dc9df80b1c00f3f14ee` |
| g016 | `(360,2460,525,2640)` | `69f6de8916612f665c51e580eaa84dc90050938033d188abfb858124216320b2` |
| g017 | `(540,2460,705,2640)` | `300e3b5d237279665930d2867d8652c94f8945cf84bc694f37616631136414dd` |
| g018 | `(720,2460,890,2640)` | `958c4a4eaa78a3beb3d51f8ca3adb1c756abf8017466536644c28653b12141b9` |
| g019 | `(910,2460,1110,2640)` | `8547a7347e5340955b05853370528c41b8675de36078639d70a414dc48562254` |

The complete inspected gallery crop `(180,2260,1410,2860)` has RGB-pixel SHA-256 `259ee3565c1e470aad1968764a9ab22227df3c513c7f74fc75996a51a7f9a5ef`. `g020`–`g027` are in the following row, which the source labels `秦 《说文》小篆 汉 汉 汉 汉 楷书 楷书`; this review makes no change proposal for that row.

## Offset 1101 glyph after the 㤅 definition

The raw-code-point offset 1100 is a full stop; the following glyph at offset 1101 is OCR `慁` in `从心，旡声。慁，古文。` (the character is not at offset 1100). Its source crop `(1280,3395,1380,3460)` has RGB-pixel SHA-256 `ef9e61bf093951336a6e38d31ae5f310bd2c038cd69bdc12721613b7d9205b6b`. The scan shows a compact, almost enclosed upper block with several interior strokes over a lower set with a dot, side marks, and a curved base. Those strokes do not make its exact Unicode identity certain to me. Do not normalize it to 㤅 or retain `慁` as a source-verified identity on my authority; preserve this occurrence as an unresolved printed-character reference pending a specialist glyph comparison. No before/after OCR correction is proposed for this span.

## Outcome

Confirmed literal OCR errors: five `㤐` → `㤅` occurrences and the five additional occurrence-bound substitutions `悉`/`恐` → `㤅` listed above. The three possible 夂/夊 occurrences and separate upper 憂 㤐 forms remain unadjudicated. The earlier rejected verdict and generic positive claims are retained as superseded/retracted so the review history is transparent. No producer corpus, correction overlay, or canonical entry was changed by this review.

## Coordinator source repair and consumer verification

On 2026-10-02 the coordinator applied ten exact occurrence patches to the book producer's source-bound correction layer after directly inspecting the original scan and enlarged lower paragraph. The independent source recheck confirmed all ten. Raw OCR remains unchanged. Producer effective evidence and rebuilt consumer page evidence both equal `66b92aa32cd18a3aa6dc3978d542d9889f1d9b6a27e51733b763ca0e76755329`; reviewable corrections and verification are in `research/ocr-corrections/ziyuan-2012-p0497/`. The complete 1,435-page consumer corpus was republished atomically.

The earlier claims of unchanged effective text describe the pre-repair inspection, not the current corpus. The scan's decoded RGB pixel hash and encoded PNG-file hash label different representations; their difference does not indicate a changed source image.

Two fresh CLI visual checks also retained incorrect rationales: the whole-paragraph check asserted 占-shaped tops, and an isolated check returned the correct replacement but reversed the candidate component definitions in its explanation. They are not treated as clean approvals. Exact source crops and explicit comparison of open curved upper strokes against a closed 口 were needed to resolve the discrepancy. This failure concerns visual occurrence identification and raw-text anchoring, not etymological interpretation. The independently corrected interactive source note and coordinator pixel inspection support the literal patches. No article prose or whole-page review approval is inferred from these source repairs.


## Later source-bound repair and corpus receipt (2026-10-02)

A later exact-pixel pass added one more confirmed literal correction to this page: at original raw code-point offset 1072, `兒` → `皃` (U+7683) in `《说文》：“愛，行皃。从夂，㤅声。”`. The corrected original crop is `(1230,3270,1490,3410)`, RGB-pixel SHA-256 `642367b36a73862011a0852377f869184e837979002fa8c30db11a79446951c0`. It visibly contains `行皃，从夂`. A previously suggested crop `(940,3270,1260,3400)` does not contain this glyph and is not used as its evidence. Raw OCR text is unchanged (UTF-8 SHA-256 `2631a7ca209d5fd072fd1c48d8e8976e64fc9bbf14d5a1f7a0919ae79fd2cc98`).

The five page-bound gallery descriptions g015–g019 were also applied to the producer correction layer as listed above. Their revised descriptions preserve sequence and printed captions without assigning unsupported Unicode identities. The ten lower-paragraph `㤅` corrections remain, for eleven source-verified literal text spans total. Upper 憂 forms, the unresolved offset 1101 glyph, and possible 夂/夊 occurrences remain outside this correction set.

The latest p.497 effective evidence and consumer record hash is `8f54971c427d8a3611ebeb5597b50dac290b632ab1d41486e1466861d1bc14bd`; effective UTF-8 text SHA-256 is `d5381bb26ea1a38f30360d6572087db96f1fb71639e91a23359ccc7e3d38dbdd`. The correction overlay digest is `6aaf5be393140138d8b10b5c9382fd76fcb0a07e18533ce5b9debfb3d750cc1e`. The final 1,435-page consumer corpus SHA-256 is `83984a2447df89604338c85e851e37b1adfdd9bb5fe56346f726d516e7eabd7a`. The earlier `66b92…` and `033e2…` receipts refer to previous, valid intermediate overlays; they are superseded for the current p.497 record. Reviewable current artifacts are in `research/ocr-corrections/ziyuan-2012-p0497/`. This remains a page-local correction, not a full-page transcription approval.
