# 邊 entry punctuation repaired in producer and consumer

Actual independent Luna-low OCR occurrence review `ba6c5a7d607b4847e2d221b6b0fb29fad73440ee313ac903aeba4c8142fa5291` and coordinator original-page inspection agree that the original PDF p145 / printed p133 clause uses a Chinese comma: `从辵，昪声`. Raw OCR has `从辵,昪声` at [1615,1620).

Applied one source-hash-bound producer overlay over the independently checked occurrence. Only the comma changes; all four characters are preserved. Raw OCR file hash remains `118a2219e88ae1668936af90056c5e09f7482cc90af71e825ba9adf08c5446b5`; source decoded-pixel hash remains `8bd6a81012882e00aafbf6f3ead6d12a88aec9c0de60f1bfa224588fdbc06529`. Producer load/export validation passed and the consumer corpus was rebuilt to 1435 records. All other 1434 rows are identical.

Snapshot overlay, exact actual reviewer files, raw before and consumer before/after records are in `research/producer-patches/bian-p145-comma-20261003`. The original occurrence review remains under the 边 source job. No guessed component replacement or page-wide approval is asserted. The old 从走 proposal and duplicate markers still require exact-pair source-resolution checks; this data repair does not by itself publish 边.

Failure class: duplicate research markers can describe one underlying OCR occurrence. Review and apply that occurrence once; preserve the separate findings for dependency checks rather than applying overlapping duplicate patches. Existing OCR duplicate/nonoverlap preflight already protects that contract and was used here.
