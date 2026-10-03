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
