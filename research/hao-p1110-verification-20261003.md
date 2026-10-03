# 好: source check of 字源 p.1110 continuation (2026-10-03)

## Scope and outcome

This source-only check addresses the open 好 scan-verification finding for the continuation on printed p. 1095 / PDF p. 1110. It also viewed the relevant 好 passage on printed p. 1094 / PDF p. 1109 to establish the sentence boundary and confirm the already-applied correction. It does not certify either whole page, change the producer OCR layer, revise the canonical article/dossier, or close GitHub issue #161.

The independent Luna-low source-coverage result reports that the p. 1109 sentence ends `这种意义的` and p. 1110 opens with `“好”读为hào。(徐在国)`, completing `这种意义的“好”读为hào。` The next headword, 姝, begins on p. 1110, after that continuation. The scan visibly agrees with the supplied OCR for this line. No unidentified glyph or literal OCR error remains in the inspected p. 1110 continuation.

On p. 1109, the inspected bronze example has the already-applied corrected first graph `虘` at raw OCR span `[1438,1439)`. The initial source-coverage result incorrectly reported the neighbor as `鐘`; this is corrected by the separate exact-occurrence follow-up in [hao-p1109-neighbor-literal-followup-20261003.md](hao-p1109-neighbor-literal-followup-20261003.md), which preserves the prior source-coverage receipt unchanged and confirms printed `钟` at `[1439,1440)`. No new OCR patch is proposed.

The current article cites book evidence `X-c4efde7fafd2060af814` on the summary, formation, both component cards, history items 0 and 2, uncertainty items 1 and 3, `meaning_history.limitations[0]`, and learner overview. The source check found those book-attributed claims supported by the inspected p. 1109 passage, within the passage's stated limits. The p. 1110 pixels specifically support the continuation's hào reading, the book gloss 喜爱, and that the book cites the Analects; the scan does not verify the meaning of the underlying Analects passage itself.

The older record `X-16e99c246ced6cc50731` is not cited by the current article. It remains in the dossier unchanged and describes p. 1110 as an OCR-only locator because the scan was not attached in that earlier invocation. That historical record is not evidence of a remaining p. 1110 scan gap in this fresh check. No article/dossier update was authorized in this task.

The harness returned `verdict: pass` with a nonempty findings array. The separate follow-up below establishes that one p. 1109 observation is incorrect; retain the receipt as returned, but do not treat the overall result as a clean source-coverage pass. Its p. 1110 continuation observation remains independently scoped and valid; this is not factual/readability approval.

## Bound artifacts and receipts

- Current published article SHA-256: `9252ad7af88a64b429736b53cc68a1171c3c16cb6578521ddd708f24408a913b`.
- Current dossier SHA-256: `a72ad5ed50153e781d98ccd3e2a574d2fb290e70095f83a0da09b6ac4941cbc4`.
- Actual scan files: p. 1109 encoded-PNG SHA-256 `8c2cad410c397a9d1bbab4f627fc9c973b942739f4c0063ceb9021b4dd5ad155`; decoded RGB pixels `f57b420e60d20032f8df525c5dcae08228f9a01195720435613d53d0c14df040`. P. 1110 encoded-PNG SHA-256 `1388f3aeb87316fe069fd7f625ac3a9fc0ff475261dff07353363a4219f725a3`; decoded RGB pixels `c2ae9a72c1005fa601ae0517669674bfae203d976b146b19470c2dd1b42b14d0`.
- Source OCR locator hashes: p. 1109 OCR evidence SHA-256 `4ad1c5141bed8484c5d9088ce5888c2293aa5357267fc4ba04554e6f41620b56`; p. 1110 OCR evidence SHA-256 `1ba2256f2300a211e4ab2ef478f2351b5c76a31d2f258db85592f9b79356d367`.
- Durable crop provenance is in [hao-ziyuan-pages-20261003](source-crops/hao-ziyuan-pages-20261003/manifest.json). The p. 1109 crop is bounds `[1280,2350,2900,4050]` with decoded RGB hash `d603ceb8cf4c25ed772e6db8369543ba3879d28c3c51e4bfad95fd440017b85c`; the p. 1110 top-continuation crop is `[180,180,1450,850]` with decoded RGB hash `51274bde71576a4d8a4395789e7d5aa092796fdda256523de9c892d3778add9e`.
- Fresh source-coverage stage: `runs/source-enrichment-ziyuan/hao-p1110-verification-20261003/source-coverage/`. Runner role `source_coverage`, model `gpt-6-luna`, reasoning `low`; actual Codex thread ID `01a10000-4735-7ef2-bf82-12ceb9cc1835`. Exact result SHA-256 `d03eee071acd4abdbab0856bac52e8bd42726ca4872e612e2aca8b59608905d3`; the runner metadata also records the exact image-argument paths and file hashes.

## Source spans

The p. 1109 OCR string has `这种意义的` at raw span `[1560,1565)`. The p. 1110 OCR string has the continuation `“好”读为hào。(徐在国)` at raw span `[23,37)`. These offsets identify OCR locator strings only; the attached scan pixels directly confirm the visible continuation. No correction is proposed for either span.

## Issue #161 status for this scope

The applied p. 1109 虐→虘 correction is independently confirmed; p. 1110's boundary, continuation, and next-headword boundary are now source-checked; and the specified p. 1110 OCR passage has no remaining unresolved glyph or correction proposal. These checks satisfy the requested scan-verification work for the continuation. Any remaining task to reconcile the unused historical partial-evidence record or update issue tracking is outside this source-only authorization and remains for the coordinating agent.
