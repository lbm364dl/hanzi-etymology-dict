# 本 p516 print-versus-OCR resolution, 2026-10-03

## Finding

A retained source finding proposed changing the 字源 PDF p. 516 本 passage from raw OCR `木下日本` to scan text `木下曰本` (`ziyuan-2012:672C:06ce4e28242c`, proposed raw span `日` → `曰`, offset `[792,793)`). This proposal treated the wording expected from the Shuowen quotation as evidence about the glyph printed on the page.

## Pixel-bound verification

A fresh Luna-low `source_resolution` checked the exact occurrence and received the original p516 raster plus direct, unresampled crop controls. The target crop is `target_quote.png`, p516 bounds `[1050,2700,1450,2840]`, decoded RGB SHA-256 `c15692d157ad23bcb016a25fe44be1bdb99e1b7db22c046c946932b9a34fdf3c`. The same-page 曰 control is `same_page_yue_control.png`, p516 bounds `[180,830,1550,1070]`, decoded RGB SHA-256 `d2891a7e1ce496622ec517e7d8ff516af0bea98c70ed591ccebea5aae2c7417d`. The same-book 日 control is `same_book_ri_control.png`, p612 bounds `[1500,220,2810,1050]`, decoded RGB SHA-256 `9953273667c7802c2f2dfea069ea33a36382e998528b58b3596cabd4ea0bcdf8`; its full original page was also attached. The original p516 pixel hash is `76e89fb3390b16e589bbeacf1ff99ba36437a957df3969860a7df252c8f0de50`.

The independent resolver observed `日`, matching the current corpus literal and the same-book 日 control, and rejected the proposed replacement. It explains that the book’s quotation wording differs from the expected Shuowen wording, but that does not alter what the scan prints. The source finding is therefore not a 字源 OCR error; no producer overlay or consumer rebuild is authorized by this check. Whether the differing book quotation is an editorial or printing error remains unasserted here. A prior independent OCR receipt also returned `correct_raw` for this exact occurrence (result hash `2c35308b0b1fae12d2e0de328cbd54730215203a24dfbb59f233bcbdebb5ea67`); the fresh source resolver inspected the scans itself.

A second retained finding (`ziyuan-2012:672C:6449793cd842`) remains an occurrence-bound rare-glyph identity gap. The resolver found that the exact approved article describes the marks as unidentified and does not use a guessed Unicode identity; it therefore records `unresolved_identity_not_used` while retaining the limitation.

## Exact gates and state

Fresh resolution job: `runs/source-enrichment-ziyuan/ben-final-source-resolution-v6-20261003/ziyuan-2012/672C`.

- Article hash: `018cdebcb8ae440a035c8eea73bd6c734b6508a0b543b780113db8b59d365e67`.
- Dossier hash: `d7ad8fbea9919a43f8920f9979cd3e9dc5ded0bc2d8e766506336be4c3e41210`.
- Fresh source-resolution result hash: `96a52baf7528f9cfc7b399b556d3d59e52ebb670a3184e4fbe75b5452a572fc6`.
- Existing exact-pair source audit hash: `e6d5bd400dc0347aa48339d225ec5517f5fb6648c63b11270533332d7dd5ceb4`; standard source-adoption validation passes after preserving its genuine p516 coverage receipt.
- Source verification pending: false. No canonical content or producer corpus was edited.

## Publication

The first v6 publication was correctly rejected because its locator had been altered to include an extra review scan. The actual source candidates and pixels were unchanged. A clean v7 handoff froze the current baseline and kept review attachments separate from locator identity; genuine fresh coverage and independent adjudication passed. Published exact pair 018cdeb…/d7ad8f… from `ben-final-source-handoff-v7-20261003/ziyuan-2012/672C`, with source resolution retained and valid. Earlier failures remain unchanged in their own jobs.

Verification after publication: site refreshed 312 approved articles in 67417 records; graph contains 303 entries / 1942 nodes / 2011 relationships; all300 HSK1 entries pass snapshot integrity. Current book-source completion is35/300 after refreshing 日 for its repaired page label. Publication triage opened #180 for missing p516 printed-page metadata; original-scan metadata verification is in progress separately.
