# OCR morphology and mixed-script verification

The 好 passage at 字源 PDF 1109 / printed 1094 exposes two general failures:
plausible names biased repeated scan checks, and a multi-character replacement
normalized a correctly printed adjacent simplified character. The raw span is
虐钟; the target first graph has a closed lower component, matching the same
book's 虘 headword rather than the open-right lower part of its 虐 headword.
The adjacent scan graph is 钟, not 鐘. A proposed 虘鐘 replacement was therefore
only partly supported.

Named checks incorrectly reported raw 虐 even while describing geometry that
contradicts its source-raster control. Those receipts are preserved. A genuine
Luna low higher-resolution blind comparison, with target and randomized source
controls and no character names or OCR verdicts, matched the closed-lower target
to the 虘 control. The coordinator independently inspected the original target
and controls. The exact attachments, image hashes and blind review result are
retained in the 好 source job's `ocr-morphology-blind-comparison-highres/` stage.

The generic occurrence-verification instruction now requires discriminating
pixel geometry before character identification, checks each character of a span,
preserves mixed scripts, and calls for a genuine retained blind comparison when
named identities bias conflicting reviews. This is not a universal rule about
ancient graph etymology. It does not automatically certify images or modify OCR.
Actual producer overlays and rebuilt consumer verification remain required;
this note records the finding, not completion of the producer repair.

## Applied producer and consumer verification

The producer now repairs only raw offsets [1438,1439), 虐 → 虘. Its actual
`research_corrections.load_effective(page-1109)` validator passes. Effective
producer text at [1438,1440) is 虘钟, and the current consumer record ending
`:001109` matches that complete effective text exactly. Raw OCR is preserved.

- Decoded source scan: `f57b420e60d20032f8df525c5dcae08228f9a01195720435613d53d0c14df040`.
- Original OCR evidence: `4ad1c5141bed8484c5d9088ce5888c2293aa5357267fc4ba04554e6f41620b56`.
- Effective evidence: `83da0aaef5c5f850afd23793440be39bf5847b19a5f1d4cdec8fb68e8d6a6022`.

The actual blind result is at `ocr-morphology-blind-comparison-highres/result.json`
(directly in the stage, not a `review/` subdirectory). It explicitly identifies
the target's closed right-side geometry and matches `right_control`. The
producer's initial receipt path typo was reported for correction. Fresh source
continuation and article reviews remain required; this verification does not
claim the 好 article is published or the entire OCR page reviewed.
