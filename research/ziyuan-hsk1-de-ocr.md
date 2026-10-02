# 字源 的 / 旳 source-scan OCR check

Checked 2026-10-02 against the original scan images for PDF pages 613 (printed page 600) and 614 (printed page 601), not just OCR or correction overlays. This note records literal transcription evidence for downstream source-bound correction. It is not a review approval for either full page.

## Evidence

Book repository: `/home/catalin/hanzi-etymology-books/research-ocr/ziyuan-full/`.

| PDF page | Source SHA-256 (the page manifest value) | OCR evidence SHA-256 | Source PNG SHA-256 |
|---|---|---|---|
| 613 | `2a1c71643780eac70dea94cf857ef09c9369f5ac1880ea084ea580af98c69e98` | `a8fe9ccff4fb0209b4dd2325531a90367f185c57e2f88c9de88b81186e0c3299` | `cc19dcb1032a0214167223f43fd2eef86162f950bcb184c345dd575dc08d28b0` |
| 614 | `e5c3740499352373582e7a99de9e1114ed3590dd728207f268e6ffe5cd3cbf88` | `2fe94497171991e9ca7779e89148e2e83c4e3af1e23a600fd9ae1616174265c1` | `5780bde47bb2fab153868ddf33db259f0d3ccd75d42ba65b80a26a4f23f15bdc` |

The p.613 printed headword is 旳, with 日 on the left and 勺 on the right, rather than 昀. This independently confirms the existing p.613 source-bound patch at raw OCR character range `[1625, 1629)` (`昀(的)` → `旳(的)`) and its `g021` description update (`《说文》小篆昀/的字` → `《说文》小篆旳/的字`). The range is zero-based Unicode code points with an exclusive end, as used by the correction layer.

## P.614 recheck: no confirmed `的` → `旳` corrections

I re-inspected each suspected occurrence against enlarged source-only crops and neighboring printed controls, after my first pass overread the contextual identity from p.613. The glyphs at raw OCR offsets 10, 59, 76, 86, 125, 156, 161, 185, 202, 222 and 232 visually match the page's ordinary printed `的` with 白 on the left; the OCR is not shown to be wrong at these spans. In particular, the offset-10 running-head sequence glyph is `的`, not evidence for `旳`. Keep these raw spans unchanged. Offsets are zero-based Unicode code points in the p.614 OCR text.

As controls, p.614 ordinary grammatical `的` is also visible at offsets 98 (俗字作的), 139 (所引的《易》), 168 (白额头的马), 198 (黑白相间的马), and 224 (the particle in `“的”的其他义项`). The first-pass 11 proposed edits are withdrawn. The p.614 entry's surrounding discussion refers to the p.613 headword, but that context alone does not show the printed form at any p.614 occurrence to be 旳.

## Unresolved printed glyph

At p.614 raw OCR offset 177, in `此字也通作“駒”。`, the printed glyph following `通作` is visibly not the ordinary 駒 form transcribed by OCR, but I cannot resolve its exact Unicode identity from this scan. Preserve that source occurrence as an occurrence-specific unidentified printed-character reference (or source-image reference); do not substitute a proposed identity such as 䯼 or 馰 without independent evidence. This remains a confirmed OCR mismatch with unresolved identity, not a Unicode correction.

## Pipeline lesson

This check exposed a review failure: a verified rare headword can bias a reviewer to normalize visually similar ordinary characters in a later passage. Search adjacent OCR to find suspects, then compare every occurrence's actual strokes with controls before proposing patches. Do not propagate a headword Unicode identity by context alone; retain unresolved glyphs as source-linked occurrences.
