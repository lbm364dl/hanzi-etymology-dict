# 爸 learner sound-cue clarification (2026-10-03)

Historical checkpoint before the subsequent book integration and publication; see `ba-7238-publication-20261003.md` for current state.

A bounded `editorial.refine` run repaired the actual readability finding from the terminal source job `runs/source-enrichment-ziyuan/hsk1-next-three-20261003/ziyuan-2012/7238`. It changed only `learner.components[1].text`, from a general mention of a similar Old Chinese reconstruction to the explicit pair 巴 *praː / 爸 *praːs in Zhengzhang Old Chinese and the statement that this supports the proposed sound cue, while preserving that 巴's original name and referent remain unsettled. It retained the existing evidence IDs and every other article field exactly. The cited evidence includes the reported Zhengzhang comparison and source-backed competing 巴 identity accounts.

Fresh independent factual and readability reviews both pass on the same exact candidate; no source names, new source claims, new citations, glyph changes, or dossier changes were added. The author/review stage is `runs/source-enrichment-ziyuan/hsk1-next-three-20261003/ziyuan-2012/7238/bounded-baba-soundcue-author-review-20261003/`.

- Candidate article SHA-256: `4a26bbed1265cb7ea4c2c78e1f3aafbbce2082ac6b4a604863bdfcd316380ef1`.
- Dossier SHA-256: `a0b97e6b9409172d04018798cdedf374a5f0402b098d79a8241e64a133e25983` (unchanged).
- Factual reviewer: `gpt-6-luna:low:factual:01a10016-a064-7930-839a-c9d8f9677ef2`, pass.
- Readability reviewer: `gpt-6-luna:low:readability:01a10016-ddca-7711-b16e-5e2663e58c20`, pass.

This is an editorially approved draft, not a publication or source-coverage approval. The retained source audit still has `verified: false` and no article-used 字源 citations. The new p. 1289–1290 巴 book record `X-37869a6afe8b21a152d8` remains in the dossier but was not added to the article; its use was not forced, and no source-coverage review was run for it. The three retained source findings are unchanged. In particular the p. 951 怕 finding says the scan confirms the comparison and no OCR correction is proposed; that is not an unresolved identity and was not reclassified. The p. 233 父 page and Sinica 巴 form-label findings remain separate open source-verification gaps.

An initial harness invocation failed before the editor ran because an allowed patch path was supplied with a leading slash; the failure is preserved at `bounded-baba-soundcue-20261003/`. The successful retry used the required path `learner/components/1/text`, `research_first=False`, `edit_first=True`, `max_revisions=0`, a held coordinator lock, and direct `editorial.refine`. No GitHub synchronization, canonical article/dossier write, producer change, or publication was performed.
