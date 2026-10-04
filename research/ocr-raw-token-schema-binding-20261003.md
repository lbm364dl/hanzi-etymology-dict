# Bind OCR review transport to supplied tokens

The 杯 p534 full-page review remained unresolved. A fresh original-pixel crop review repeatedly returned raw_text 栢 although the supplied exact raw token is 楛. All three responses failed the existing local validator and remain preserved under `runs/source-enrichment-after-ocr/ocr-verification/ziyuan-2012-p0534-cup-headword-crop-check-20261003`; none supports an applied correction. Their descriptions of component geometry are also unreliable and do not establish the replacement.

General failure class: the scan reviewer substitutes its imagined OCR token for an immutable input anchor. The response schema now restricts occurrence IDs and raw_text to supplied values. For multiple targets, local validation still checks the exact ID-to-token mapping, unique complete coverage and verdict consistency. Printed identities and uncertainty remain reviewer outputs; the new schema does not force approval or settle pixels. A fresh independent check retains both the original full page and its unresampled headword crop.

Verification: the OCR unit suite passes, including a schema contract test rejecting an invented raw token and occurrence ID. Failed historical receipts are not edited. No previously published entry or OCR correction is certified by this prompt/schema change.
