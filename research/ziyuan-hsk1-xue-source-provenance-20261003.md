# 學 (学), 《字源》 p.277 source-bound evidence update

This append-only note records the narrow source refresh prepared on 2026-10-03 for the 学 HSK1 candidate. It is research and provenance, not publication approval. The dated sections before the final handoff are historical snapshots; consult the last section for the current exact candidate and its receipts.

## Source identity and boundaries

The consulted edition is 李學勤主編, 《字源》 (2012), PDF p.277 / printed p.265, ISBN 978-7-5528-0069-2. The decoded RGB hash of the original p.277 scan is `d71826450bb411b40d34cabacceaf5870e0eac285824128d9ab27b5d5dcd777f`. Current effective page text hash is `4885a69f96bbb5ba0d2bad5d606f9cc78b26fe39a416ce6c802a5426168a0694`; raw OCR evidence hash is `093d5eb7d675c2258bf40a15db7e121b78df58c672974819bbeaa5264b49696d`; decoded raw OCR text hash is `2f2bd69e9ca8ac3064350d8f140289731d0df49f694f4943e53925dfc9bd62ee`; the current 1,435-record corpus hash is `3dcf91d6df527e167861636e20cd005e68343072bc4270c36bbc84653b482de9`.

The 学/學 entry ends on p.277 with the 張標 credit. PDF p.278 continues the separate 斆 entry. The shared teaching/learning graph statement is in the 学 entry continuation on p.277, before its own credit. This page-bound evidence makes no use of p.278 as a 学 continuation.

## Evidence additions in an early snapshot (superseded where noted below)

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


## Final candidate verification (2026-10-03)

The final reviewed candidate is `runs/source-enrichment-ziyuan/xue-final-p277-author-reviews-rev8-20261003/article.json`, canonical article hash `e0bdb5ebf22474e087b19ac52b6f05ed6ed160dfdf3059b97336a9bc3b10eba2`. It cites the p.277 shared-graph proposal as a source-attributed explanation, and retains the attributed Western Zhou 子 proposal while leaving 子's present-day function unknown. The final dossier is `runs/source-enrichment-ziyuan/xue-final-p277-author-reviews-rev8-20261003/dossier.json`, canonical hash `3bde30ffea811112a6d2c8215555ec09ced8abf596b63612b91592fa3b403410`; it records the retained superseded evidence without activating the retired records listed above. The article and dossier are research-stage artifacts; this note does not claim publication.

Fresh factual and readability reviews both passed the exact final article/dossier pair. Their reviewer IDs are `01a0ffdc-bee0-71d0-b84d-a74771637a16` and `01a0ffdc-f0c8-7641-a4bd-bca486cb4b08`; each receipt binds article hash `e0bdb5ebf22474e087b19ac52b6f05ed6ed160dfdf3059b97336a9bc3b10eba2` and dossier hash `3bde30ffea811112a6d2c8215555ec09ced8abf596b63612b91592fa3b403410`. Rev5–rev7 remain preserved as earlier author/review cycles; rev8 is the current pair.

The first exact-pair source-coverage run returned revise with two findings that contradicted the current article: one called its already-stated two-臼/sound-role distinction incorrect; the other called its explicitly stated original-meaning proposal omitted. That result is preserved at `runs/source-enrichment-ziyuan/xue-final-source-coverage-rev8-20261003/source-coverage/result.json`, canonical result hash `ea0b5fc0f7ebb1bd5e9d93995febff80c2a168edf078a4e997acaf7a170d18a5`, reviewer thread `01a0ffdf-1e26-79c2-b970-8fa3a6c11003`. A separate exact-pair scan-bound coverage adjudication quoted those current fields and passed with no findings: `runs/source-enrichment-ziyuan/xue-final-source-coverage-adjudication-rev8-20261003/source-coverage/result.json`, canonical result hash `4d34b9dd0e19bdb1b62c0305814e6ed37cdf3507c766c38ee3c782671490780e`, reviewer thread `01a0ffe0-c83a-78b1-b535-28652b451355`. Both used the exact same final hashes and attached original p.277 and p.278 scans plus the verified p.277 formation crop. The passing result selected `X-326914a292c6b0a2bb70`, `X-b5d7e41af88c64f0a96d`, `X-ef7d9bef1ed86bea4365`, `X-1e8b893b3a53a1d38aab`, `X-b75386e2e25901f6af0a`, and `X-7cc520b57364176e06dc`; it did not select the article-used shared-graph record `X-860ceab763f4fe3410ca`, so the coordinating agent should check that point when assembling the source-adoption audit. The coverage check is not a publication gate by itself.

The source-bound OCR status remains unresolved and raw text remains unchanged. The raw p.277 spans `[944,945)` (`升`) and `[1131,1133)` (`毚片`) have conflicting independent visual readings and are not used to assign rare-glyph Unicode identities. The new scan-bound source clarification `runs/source-enrichment-ziyuan/xue-p277-parenthetical-source-clarification-20261003/research/result.json` (hash `614f4d8a3221d4a78e12185608b17dada188f324ae516cd9dc22030ac4583704`) supports a grouped two-臼 construction and assigns the sound role to the printed graph after 冖; it does not identify that graph's Unicode scalar. The separate abbreviated-looking graph's identity is also unresolved. Neither is silently treated as corrected OCR or as a whole-page approval.


A first bounded author invocation saved a genuine Luna-low patch but failed before review because the crop pixel hashes in its scan manifest were placeholders; its outputs are preserved and not treated as approvals. The subsequent rev2 and rev3 author/review stages are terminal and retained. Rev3 is `runs/source-enrichment-ziyuan/xue-final-p277-author-reviews-rev3-20261003`: article `3709be8cf7270375e29f2b650be7085a73a06407590bfa842af0247072ef9846`, dossier `be902485ff28938c28bdc50ca59f83ea1984b61c980f0cddbd30ddd21189a65e`, factual pass and readability revise. This pair is not approved for publication.

The factual invocation attached the full p.277 image and these original-RGB crop hashes: formation crop `f32052d09a178499b555bd59b995e97ac0972efc1e44d6cab096e10bb62c9dad`, upper-right continuation crop `5f09615b76f71e7ddd2769d3fa9e1e019d96bb8d3c8364fa09f3e20bf57a19d5`. The coordinator independently checked that both crop pixel arrays exactly match their recorded parent-page rectangles; see `research/source-crops/ziyuan-p0277-xue-crop-provenance.json`. This is crop provenance, not an agent inspection receipt.

The earlier author-cycle and source-clarification paragraphs above are historical snapshots. The source clarification and final review states are superseded by the exact results in the final verification and handoff sections.

## Frozen-parent handoff and source-resolution receipt

The current final pair and exact successful reviews have been handed to `runs/source-enrichment-ziyuan/xue-source-followup-provenance/ziyuan-2012/5B66/`. The original prepared snapshots were preserved byte-for-byte: `source.json` SHA-256 `11083b72b154a970150e8a244928ac3d480a9f6ca7ab88d1c04640440870c829`, `source_article.json` `259b39577d012e6e9d3a8d5cec7f21d61407812304241c78a0690f1b85f729e5`, `source_dossier.json` `e68bbdd719fb241ba588afdcbe7bd84fbf2cb677ebb61af0b08af24ae7125318`, and `source_checkpoint.json` `bcb008840a93cd74c206903aeb45ccee471b3972cc5beea695a8cdf1fbbaafb8`. The previous mutable candidate and status artifacts were copied into `before-final-handoff-rev8-20261003/`. The parent job's current page locator hash remains `02c9e2e3eb682d6fb176f82e660c15414a86fc23d8bafdc987b5d82c8c16c76c`; no p.277 producer or consumer correction was applied.

The parent now carries the rev8 article/dossier/reviews and the exact passing source-coverage receipt. Its source audit is `mode: existing_approved_research`, verified against the same article/dossier hashes and coverage result; audit digest is `c0a204c0c33a1220804461f1093578b2b1b8f1ce3c1994c1feebd0ec6d388d51`. The passing coverage result selected six active source IDs listed above; not selecting X-860 does not erase its genuine active citation in the article or its separate factual/readability review. The older revise result remains preserved and was contradicted by its own quoted current-text observations.

The parent `source_findings.json` retains three unresolved items with source-linked provenance: (1) exact Unicode identities for the graph after 冖 and the abbreviated-looking graph remain unknown; (2) the p.277 raw parenthetical occurrence reference `[1131,1133)` (`毚片`) remains unresolved; and (3) the p.277 body-relative occurrence reference `[944,945)` (`升`) remains unresolved. These coordinates and competing checks are documented in `research/ocr-corrections/ziyuan-2012-p0277-xue-source-check-20261003/findings.md`; they are occurrence references from that research record, not a whole-page approval. An initial resolver receipt was preserved but its rationale referred to retired records as support. A corrected exact-pair scan-bound recheck supersedes that rationale without removing or replacing the original receipt: `source-resolution-1/result.json`, result hash `e634bb28be0c0042df5d5d64d9f0c5b2ce5256ecd6a07bf603929fe59f58ebbc`, Luna-low thread `01a0ffea-ba9f-7dc0-9a3e-dfb1e633917f`. It marks all three `unresolved_identity_not_used`, cites only active current evidence, records no literal checks or applied repairs, and leaves all raw OCR unchanged. The parent `source_findings` gate is mechanically clear for this exact pair; final issue synchronization and publication remain with the coordinator.

In the current dossier, `X-d76eda27ab40700bed32` and `X-1ae32afc41b2d518a267` are retired along with the IDs listed above; the scoped, scan-bound `X-7cc520b57364176e06dc` is the active clarification. Earlier text in this note describing X-d76 as an active addition or rev3/rev4 as current is historical only. Current rev8 identities and receipt hashes are stated in “Final candidate verification” above.
