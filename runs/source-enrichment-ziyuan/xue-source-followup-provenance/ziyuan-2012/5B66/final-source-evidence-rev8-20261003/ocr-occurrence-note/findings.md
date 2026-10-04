# 字源 p.277 学 OCR occurrence check

## Scope and source binding

This note records a scan-only check of the two-character parenthetical in the 学 formation paragraph and the adjacent sound-role graph. The source is 李学勤主编,《字源》, 2012 combined PDF, PDF page 277 (printed page 265). Original scan dimensions are 3000×4095 RGB. The decoded source-pixel SHA-256 is `d71826450bb411b40d34cabacceaf5870e0eac285824128d9ab27b5d5dcd777f`; raw OCR file hash is `093d5eb7d675c2258bf40a15db7e121b78df58c672974819bbeaa5264b49696d`; raw OCR text hash is `2f2bd69e9ca8ac3064350d8f140289731d0df49f694f4943e53925dfc9bd62ee`.

The existing p.277 correction at raw `[186,196)` (`也 heat有所体现` → `也有所体现`) is retained. No p.277 producer or consumer correction was applied during this check. The separate verified p.1259 OCR fix is not part of this finding; root rebuilt the consumer after that source-bound fix.

## Parenthetical `[1131,1133)`

Raw OCR is `毚片` in `或从两臼（毚片）从冖[glyph:g022]亦声`. The complete original-pixel crop is source box `[1265,3260,1410,3340]`, decoded crop-pixel SHA-256 `6ce006cbc87efd271170e50b78754740e6d3f3512916471afb1dab5d5de87329`.

Three preserved independent Luna-low results conflict:

- Whole two-character check, `runs/source-enrichment-ziyuan/xue-p277-occurrence-check-20261003/ocr-verification/verified-occurrences.json`, result SHA-256 `b5036a79f5bb62e2778907b096a3f5d1194a6ce75e74d9a269432e1ae07c1256`: `unresolved_identity` for the whole span. It described the crop as appearing to read `犹升`, but did not establish the full replacement.
- Split-character check, `runs/source-enrichment-ziyuan/xue-p277-parenthetical-char-check-20261003/ocr-verification/verified-occurrences.json`, result SHA-256 `1bb2f62bc1cf1b3c4f84f828b73236b020d4c8383b88937cd5b8172a5754abc7`: returned `correct_raw` for `毚` and `片`. Its rationale cited an earlier `毚` control that is not visible in the supplied images, and claimed the second character would require an enclosing outline to be 升. Those are unsupported control/geometry statements and this pass must not be treated as proof.
- Blind target-plus-control run, `runs/source-enrichment-ziyuan/xue-p277-blind-literal-20261003/blind-scan-result.json`, result SHA-256 `6a0eb32d562345aafe1d61ec3fece99f4d00d303976a6786aebaf4c449432e02`: with target sample A, no OCR text or proposed identity, it transcribed `犹井`. It matched target’s second character to sample B but called the shape 井-like.

Two additional blind comparisons used same-book body-text controls with separately retained coordinate mappings:

- `runs/source-enrichment-ziyuan/xue-compare-sealedforms-A-B-C-20261003/blind-scan-result.json`, result SHA-256 `9a53fd972c9f16f44aab7d53a3c47d9077edaed402a1c4a89d19f4ba7756ef92`: transcribed `犹升`; target’s second character matched both the p.1259 升 control and the p.213 control. The reviewer read the p.213 control as 升 even though its adjacent prose labels it 廾, showing that this control is itself visually confusable.
- `runs/source-enrichment-ziyuan/xue-compare-sealedforms-A-B-D-20261003/blind-scan-result.json`, result SHA-256 `5a3f7803897208c02ecfb0b5fa2ff27b72702e32ab835e64481304573b026256`: transcribed `犾井`; target’s second character matched a p.462 井 control and differed from the p.1259 升 control. It read the p.1259 anchor as 升 and the p.462 anchor as 井.

The same-page/body-text control map, original boxes, pixel hashes, source page hashes and anchors are retained at `blind-crop-coordinate-mapping.json` and `named-control-coordinate-mapping.json`. The target is sample A. The p.1259 control comes from the visible body-text phrase `斗和升都是量器` (PDF page source-pixel hash `96dcee517496798f7e960efeea99bda45f262e0be11f955cf734221c0ed1a957`). The p.213 control comes from the body-text statement that a component is usually transcribed as 廾 (source PDF page 213; printed page 201; source-pixel hash `36616934a91575dee4933b10c2d9b9b8958929c2ac1027604909b68bffad29f1`). The p.462 control comes from the body-text description of 井 (source-pixel hash `d1e1fa3cf2e459e61eaf49cd317f7fbdcca456adb5fb25dedcd0f37bd97fa12b`).

**Current result:** the parenthetical is unresolved at the exact two-character level because fresh blind readings and control matches conflict. Root’s direct pixel inspection reads the first glyph as 犹 (犭 left, 尤 right); the blind runs returned 犹 and 犾 respectively. The second glyph remains unresolved because blind passes matched it to different independently labeled controls (升 versus 井) and one control labeled 廾 was itself read as 升. Do not normalize, infer from the parenthetical meaning, or patch either raw character on these receipts alone.

## Sound-role graph after 冖

The separate exact-occurrence scan comparison is `runs/source-enrichment-ziyuan/xue-p277-role-glyph-check-20261003/source-occurrence-review.json`, result SHA-256 `f4e6bc0ed161580a026fe473d044c982de891958aaba662ef69ee93b8e029cea`. Its comparison crop is source box `[0,3180,1580,3500]`, pixel SHA-256 `49432fe269e195620e4b6060a232aa2f5c2c70361d810764b27135cd81607f9a`.

That check reports that the embedded graph after 冖 differs visibly from both the preceding jù graph and ordinary printed 臼. The source wording assigns 声 to the embedded graph after 冖 in `或从两臼（毚片）从冖[glyph:g022]亦声`; it does not say that an individual 臼 supplies sound. The graph’s Unicode identity remains unresolved. This is an occurrence-level reading only, not a page-wide OCR or etymology approval.

## Failure class

The earlier per-character pass produced false confidence by citing an unavailable `毚` comparator and explaining away an observed mismatch with an invented expected outline. Target/control crops also needed precise source-coordinate mappings, and a visually similar same-book control can itself be misidentified without its complete printed anchor. New checks therefore kept the OCR candidate hidden for the blind pass, used original-pixel crops with source-page hashes, and retained each control’s box and adjacent printed anchor separately. The checks still disagree, so the remaining gap is genuine visual identification uncertainty rather than permission to infer from the gloss.

This finding is tracked under existing issue #3. Raw OCR is preserved; no source patch or corpus change for p.277 is authorized by these conflicting results.

## Focused first-character check after improved crop handoff

A subsequent standard `pipeline.ocr_verification.verify` pass checked only raw `[1131,1132)` `毚` → candidate `犹`, using the project-recorded complete formation crop and same-page continuation crop. The crop RGB hashes match `research/source-crops/ziyuan-p0277-xue-crop-provenance.json`; the raw occurrence, source scan and crop extents are recorded in the stage input. Result: `runs/source-enrichment-ziyuan/xue-p277-firstchar-target-verification-20261003/ocr-verification/verified-occurrences.json`, Luna-low result SHA-256 `758d0207eabde02a9b9fdd20a2eb47b78b02e4874c0c641f41f957b6b1673540`.

It returned `correct_raw` for 毚 and described dense/enclosing strokes. Its reason did not compare the target’s right subcomponent to the supplied 尤 control; it compared the whole target outline to the control. Root’s and coordinator’s direct views of the complete crop read the printed first character as 犹. This new receipt conflicts with the unprompted blind transcriptions `犹`/`犾` and does not resolve the literal. Preserve it as another failed/contradictory scan judgment; it is not an authorization to retain or replace raw OCR. No source mutation was made.
