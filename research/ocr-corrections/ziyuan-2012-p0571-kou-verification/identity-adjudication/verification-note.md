# 字源 p.571 headword identity adjudication

Date: 2026-10-02
Scope: only the headword immediately before `wéi 匣组、微部;云组、微韵、雨非切。` in PDF p.571 (printed p.558), raw OCR span `[741,742)`. The adjacent p.87 occurrence is a visual control only. No article prose or other p.571 text is in scope.

## Decision and limits

The intended Unicode identity at this occurrence is **囗 U+56D7**, read wéi, rather than **口 U+53E3**. This is a contextual source-identity decision, not a claim that the raster alone distinguishes the two. The original p.571 headword is an empty four-sided enclosure; it has **no interior horizontal stroke**. The p.87 口 kǒu control visibly has an interior stroke. Do not cite the earlier source-resolution receipt's claimed inner stroke as evidence: that claim is false, and its unmodified original is retained under `prior-receipts/`.

The whole p.571 entry places the target below `囗部`, gives the wéi reading, describes an enclosed area, and continues with 圜/團/圓 entries. Official Taiwan MOE records independently align these details: the Revised Mandarin Dictionary identifies 囗 as wéi under 囗部 with an enclosure/surround sense, while its separate 口 record gives kǒu under 口部 and the mouth sense. The MOE Dictionary of Chinese Character Variants has separate records B00478 囗 and A00480 口; the 囗 record gives the enclosure reading and 《說文》 囗部 wording, and the 口 record says the regular 口 form is smaller than 囗 and does not list 囗 as its variant. Unicode's Kangxi Radicals chart distinguishes U+2F1D MOUTH ≈ U+53E3 from U+2F1E ENCLOSURE ≈ U+56D7.

These sources strongly establish which character this entry intends. They do not establish that no publisher has ever used a 口-like outline as a graphic variant for 囗. The evidence does establish that the edition's raw OCR string `口` is a homographic/encoding ambiguity requiring contextual normalization to represent this entry's intended Unicode identity. The page's separate quotation `口，回也` and every other occurrence remain outside this correction.

## Independent review record

- `result.json` is an actual Luna low-reasoning whole-page context and source-identity research adjudication. It explicitly records no interior bar, the raster ambiguity, whole-entry context, inspected official dictionary/Unicode records, and the limits on the publisher-variant question.
- `scan-control-review/verified-occurrences.json` is a separate actual Luna low-reasoning scan-only review. It retained raw `口` because the p.571 outline appears to match the p.87 control. It was explicitly instructed not to use meaning-based identity inference and therefore does not adjudicate intended Unicode identity. Preserve its `correct_raw` finding and hash unchanged as a genuine contrary pixel-level opinion.
- `prior-receipts/contradictory-source-resolution-result.json` preserves the earlier receipt claiming an interior horizontal stroke. That rationale is contradicted by the exact pixels and superseded for identity adjudication; the receipt itself is not rewritten.
- `prior-receipts/original-source-research-result.json` preserves the original research finding.
- `../review/` and the adjacent crop files preserve the initial scan review and source pixels/controls.

## Source and producer/consumer verification

Source: 李學勤主編《字源》 (2012), PDF p.571 / printed p.558. Full scan decoded-RGB pixel SHA-256: `8d3fcdcb07517bdbc7c19216df84c8f5ebb83ba8a8be014da1fa6dcd1a606045`. Raw page evidence SHA-256: `966cca40a708b8ce4569edef696005351a9b5682ecb80abb0f381084a05c146f`. Exact raw span `[741,742)` is `口`; following anchor is `wéi 匣组、微部;云组、微韵、雨非切。`. The p.87 control page pixel SHA-256 is `8e03aa9818392e353942debcd274a96e32e4c10f785e0abde042d038191113e9`.

A page-local, source-pixel-bound correction overlay in the sibling book repository changes only that exact span from `口` to `囗`. Raw OCR was not altered. Producer `load_effective` and `source_repairs.verify` confirmed the exact source page, raw span, overlay, and effective evidence. Effective page evidence SHA-256: `b3709c72af9a58c1dff041d4bd08ce3ed454761900b89671aed286e2aba72dfd`. Overlay hash from `source_repairs.verify`: `2e8a2f9b047213f41e62d782215bec522ded54ae0d6ff91ef65950547fc52956`.

The consumer corpus was rebuilt from the effective source pages: 1,435 pages, prior corpus SHA-256 `83984a2447df89604338c85e851e37b1adfdd9bb5fe56346f726d516e7eabd7a`, rebuilt corpus SHA-256 `49e0fc2dde733747be4064dbe5cb35eb5bb71964ff360886dc441cd2be08c33b`. Its p.571 row now contains `囗` at offset 741. The correction scope remains exactly one occurrence; no page-wide transcription approval is implied.

## Authorities consulted

- Taiwan MOE Revised Mandarin Dictionary, 囗 (wéi): https://dict.revised.moe.edu.tw/dictView.jsp?ID=11395&la=0&powerMode=0
- Taiwan MOE Revised Mandarin Dictionary, 口 (kǒu): https://dict.revised.moe.edu.tw/dictView.jsp?ID=4501&la=0&powerMode=0
- Taiwan MOE Dictionary of Chinese Character Variants, B00478 囗: https://dict.variants.moe.edu.tw/dictView.jsp?ID=55668
- Taiwan MOE Dictionary of Chinese Character Variants, A00480 口: https://dict.variants.moe.edu.tw/dictView.jsp?ID=5366
- Unicode Standard 18.0, Kangxi Radicals chart: https://www.unicode.org/charts/PDF/U2F00.pdf

Tracking: existing repository issue #75 (subissue for this p.571 finding) and umbrella OCR issue #5. No duplicate issue was created.
