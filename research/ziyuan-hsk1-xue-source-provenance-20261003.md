# 學 (学), 《字源》 p.277 source-bound evidence update

This note records the narrow source refresh prepared on 2026-10-03 for the 学 HSK1 candidate. It is research and provenance, not publication approval. The current candidate dossier is `runs/source-enrichment-ziyuan/xue-p277-final-evidence-dossier-rev3-20261003/dossier.json`; its provenance metadata records the protected base hash, added research result hashes, retired records, and source hashes. The earlier dossier remains preserved as an intermediate.

## Source identity and boundaries

The consulted edition is 李學勤主編, 《字源》 (2012), PDF p.277 / printed p.265, ISBN 978-7-5528-0069-2. The decoded RGB hash of the original p.277 scan is `d71826450bb411b40d34cabacceaf5870e0eac285824128d9ab27b5d5dcd777f`. Current effective page text hash is `4885a69f96bbb5ba0d2bad5d606f9cc78b26fe39a416ce6c802a5426168a0694`; raw OCR evidence hash is `093d5eb7d675c2258bf40a15db7e121b78df58c672974819bbeaa5264b49696d`; decoded raw OCR text hash is `2f2bd69e9ca8ac3064350d8f140289731d0df49f694f4943e53925dfc9bd62ee`; the current 1,435-record corpus hash is `3dcf91d6df527e167861636e20cd005e68343072bc4270c36bbc84653b482de9`.

The 学/學 entry ends on p.277 with the 張標 credit. PDF p.278 continues the separate 斆 entry. The shared teaching/learning graph statement is in the 学 entry continuation on p.277, before its own credit. This page-bound evidence makes no use of p.278 as a 学 continuation.

## Current clean p.277 evidence additions

- `X-d76eda27ab40700bed32` — the source’s two-臼 analysis assigns sound to the following printed graphic unit after 冖. The exact Unicode identity is unresolved. It does not assign the sound role to either individual 臼 or to the whole 学 construction. This replaces no raw OCR and makes no claim that the unresolved printed glyph matches an OCR token.
- `X-b75386e2e25901f6af0a` — the source attributes to its 学 entry the proposal that two described construction patterns began combining in Shang forms and that Western Zhou forms added 子 to highlight the child as learner. This is presented as that entry’s proposal, not consensus.
- `X-860ceab763f4fe3410ca` — the source’s p.277 学 continuation says that teaching and learning were represented by one graph in antiquity and offers this as an explanation of their historical relation. The paraphrase does not claim the spoken words were identical and does not generalize the statement into a universal reciprocal rule.

These records were added to a copy of the protected dossier and validated by the project’s actual `enrich_dossier`, dossier, and external-evidence validators. First candidate dossier hash: `9cbcc75272e8c4e837bdfcd18ac2b2ad71706458a916d63df03d3919c4515748`; after adding the separately confirmed retirement of X-c3ce71fae96426de3c38, the current candidate canonical `pipeline.editorial.digest` hash is `a62067cc41a6d15fe0078ab42a69dec0f78113458ffe8f57f717f4a585e1e7db`. This candidate has not itself been reviewed or published.

## Prior evidence excluded from active citation

The candidate dossier marks the following retained records as retired; records and their receipts remain preserved for provenance:

- `X-88ac70e7a8e7d9f630d1`, `X-36ba2a68e28e14507d50`, `X-e26d0c65c0b70ea29fb3`, `X-b53128eb997f2914bb2e`, `X-69c66a2bd4be29d0effe`, and `X-5d7196761573adf42694`: these mixed page-boundary claims that incorrectly treated p.278 as continuation of 学/學, and some also overstate role/glyph relationships.
- `X-cf69d0b8705473133e06`: this record includes the unresolved parenthetical OCR and an unsupported individual-臼 sound assignment; it is not used for any partial claim.
- `X-c3ce71fae96426de3c38`: this mixed record confuses 交 with 廾/冖 and 臼 with 両/丩, and claims a Han huá loan; no part of this record is active support.
- `X-44ca4c8dfdad9682d84c`: this mixed book record has a false p.278 学 continuation and repeats the unresolved 升 pairings; do not cite it.
- `X-36908cb00585451acf81`: this mixed book record has a false p.278 continuation, unresolved 升 pairings, broad reciprocal-use claims, and a mixed original-meaning paraphrase; do not cite it.

Separate research attempts that returned a wrong p.278 boundary or these unsupported role/identity claims are retained but not used. The earlier f348 teaching record is also excluded because it bundled unrelated 教 examples and inaccurately called the source’s 同字 clause “graph/word.” A later narrowly bounded record is used instead.

## Unresolved OCR

The raw p.277 tokens at `[944,945)` (`升`) and `[1131,1133)` (`毚片`) remain unchanged and unresolved. Independent same-book-font comparisons returned conflicting readings for each occurrence; this is a verifier disagreement, not proof that the printed source is illegible or internally ambiguous. No guessed Unicode replacement is used to establish an article claim. The p.277 producer and consumer source text remain unchanged. This note and dossier are not whole-page OCR approval.

## Research receipt status

The three active additions came from separate `gpt-6-luna` low source-research runs with p.277 attached, search audits, schema-valid result records, and current source hash context:

- Sound-role unit: `runs/source-enrichment-ziyuan/xue-p277-clean-unit-20261003/research/result.json`, canonical result hash `b6894e749f748d4133418b2fe1b9ba5e8a6bb21a89dad1e3c2c2b701a15a5fab`.
- Chronology: `runs/source-enrichment-ziyuan/xue-p277-clean-chronology-linked-20261003/research/result.json`, canonical result hash `90ac7940f79c7d57754d54f9c28fc292f887ad760daee9530eef09b782b75d19`.
- Shared graph statement: `runs/source-enrichment-ziyuan/xue-p277-clean-shared-graph-retry-20261003/research/result.json`, canonical result hash `1ae4576af6a018cfa53b6a45d152b35c7c4b10d0e69d075c7ec9961aa9eece92`.

The earlier shared-graph attempt under `xue-p277-clean-shared-graph-20261003` failed its runner receipt (wrong command event mode/model selection); do not use it as research. The separate f348 teaching record is retained as superseded research, not cited.


A first bounded author invocation saved a genuine Luna-low patch but failed before review because the crop pixel hashes in its scan manifest were placeholders; its outputs are preserved and not treated as approvals. The subsequent rev2 and rev3 author/review stages are terminal and retained. Rev3 is `runs/source-enrichment-ziyuan/xue-final-p277-author-reviews-rev3-20261003`: article `3709be8cf7270375e29f2b650be7085a73a06407590bfa842af0247072ef9846`, dossier `be902485ff28938c28bdc50ca59f83ea1984b61c980f0cddbd30ddd21189a65e`, factual pass and readability revise. This pair is not approved for publication.

The factual invocation attached the full p.277 image and these original-RGB crop hashes: formation crop `f32052d09a178499b555bd59b995e97ac0972efc1e44d6cab096e10bb62c9dad`, upper-right continuation crop `5f09615b76f71e7ddd2769d3fa9e1e019d96bb8d3c8364fa09f3e20bf57a19d5`. The coordinator independently checked that both crop pixel arrays exactly match their recorded parent-page rectangles; see `research/source-crops/ziyuan-p0277-xue-crop-provenance.json`. This is crop provenance, not an agent inspection receipt.

Before another author repair, a separate source clarification is checking the post-冖 sound-unit referent and the graph named in the parenthetical reduction note. Its actual research stage is `runs/source-enrichment-ziyuan/xue-p277-parenthetical-source-clarification-20261003/research`. No result or approval from that stage is asserted here. Reviewer agreement or repetition of the word “combined” does not independently settle the printed referent.
