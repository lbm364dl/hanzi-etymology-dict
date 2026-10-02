# 字源 PDF p.571 headword check

Scope: only the raw headword occurrence at offsets `[741,742)` before `wéi 匣组、微部;云组、微韵、雨非切。` in the page-0571 producer OCR. The producer `load_effective` validator returned the unchanged raw text `口 wéi 匣组、微部;云组、微韵、雨非切。`; no page overlay exists.

- Book: 李學勤主編《字源》, 2012, ISBN 9787552800692.
- PDF page 571; printed page 558.
- Raw/effective evidence SHA-256: `966cca40a708b8ce4569edef696005351a9b5682ecb80abb0f381084a05c146f`.
- Original scan decoded RGB pixel SHA-256: `8d3fcdcb07517bdbc7c19216df84c8f5ebb83ba8a8be014da1fa6dcd1a606045`.
- Targeted crop: `headword-crop.png`, from original pixels `[150,2960,1500,3230]`; encoded-file SHA-256 `628806f24649d0ca8634228947ca0610e5010c65b9d43bb4e990697cf4088f43`, decoded RGB pixel SHA-256 `2e062fe66ffac2bb1a1ae010f13b6d40a2382693af9eb884800a3f92962504c0`.
- Occurrence identity/offsets, anchor and original-scan review are preserved in `occurrences.json`, `verified-occurrences.json`, and `review/`.

The separate actual Luna low OCR verifier returned `correct_raw`, printed text `口`, with result SHA-256 `8c1640ce6024f3f30e8699a803ce77a59110b6dedc5952d53f03c953d2926c36`. The review assessed this one occurrence only; it did not review the full page. A p.87 scan shows the book's separate `口 kǒu` entry. The p.571 box and the p.87 headword are visually similar; the pixels do not provide a clear reason to replace the literal with `囗`. The p.571 prose also refers to `口` as a component. These contextual clues do not override the exact occurrence review or prove a Unicode identity from shape alone.

Disposition for source repair: **no `口`→`囗` patch applied**. The proposed replacement remains unverified; this receipt rejects it for the checked occurrence. Preserve raw OCR and the page evidence unchanged. This is not a page-wide transcription approval.
