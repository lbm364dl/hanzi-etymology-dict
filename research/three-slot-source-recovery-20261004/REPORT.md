# Three-slot source recovery and harness consolidation

## Published results

| Character | Outcome | Book adoption |
|---|---|---|
| 工 | Fresh research/reviews and source verification; producer OCR repair applied | Yes |
| 听 | Current-form evidence added; current hearing-sense record repaired through the new completion command | Yes |
| 妈 | Current semantic/phonetic decomposition and direct meaning explanation; fresh dictionary reviews | No: retained book passage supports no article claim |

Exact final article/dossier hashes, real reviewer identities and job paths are in `publications.json` and canonical `content/provenance/`.

## General changes

- Consistent single/grouped OCR receipt shapes and literal-anchor preflight.
- Frozen OCR JSON parsing tolerates the appended shared instruction contract while preserving exact provenance.
- Authors reconsider earlier findings against newer active evidence.
- Unchanged citation integration preserves genuine reviews and source holds; it skips two redundant reviews.
- Attention recovery can complete citation/source/issue/publication gates, or finish existing reviewed jobs without reauthoring.
- Published source repairs and dictionary-only repairs freeze fresh canonical baselines and receive fresh independent authorship/reviews.
- Dictionary-only recovery requires genuine rejection of irrelevant book records, preserves the book hold, and never counts source adoption.
- Approved-pair issue proposals receive a separate independent confirmation. Confirmed editorial defects hold publication; rejected proposals retain receipts without adding issues.

The live 听 finding-validation check rejected a stale rewrite request and created no article or review approval. Its receipt is in `finding-validation/`.

## OCR repair

A confirmed mismatch at 字源 PDF423, raw offset1855, replaced the guessed scalar 毚 with source-bound unidentified glyph `[glyph:p001]`. Unicode remains unresolved. Original raw OCR is preserved. Producer transaction `ocr-repair-20261004T102612Z-acf3c94e0229` rebuilt all 1435 corpus pages; 1434 unrelated pages were verified unchanged. `gong-source-repair-result.json` and `ocr-occurrence-proof/` retain the actual transaction/review bindings. Full scans and large corpus snapshots remain local.

## Verification and cost

- 253 focused tests pass, including holds, unchanged review preservation, stale baselines, independent proposal confirmation and concurrent-candidate mutation.
- 300/300 HSK1 entries pass final snapshot integrity.
- A separate Playwright context checked 工、妈、听 learner sections, opened their history sections and citation dialogs, and found no broken historical images or page errors.
- Current full-cohort source audit: 44/300, up from 42. 妈 is explicitly excluded from book completion.

`timing-final.json` includes 148 unique pipeline calls across failed and repeated recovery attempts, deduplicated by actual thread IDs. Its 62m54s wall span includes coordinator pauses and harness engineering; total model-stage time was 45m58s, with overlapping stages. Code-writing collaboration agents are outside this scan. This is a recovery cost report, not a benchmark proving the new harness is fast. The 6 research calls total 16m12s; repeated authorship and review cycles are also a major cost. A fresh contrasting smoke is required before a throughput claim or broader expansion.

## Remaining work

The unidentified printed quotation, producer printed-page metadata and disputed isolated mare gloss remain research/metadata followups. The full 300-character goal stays paused. No broad batch was restarted; active model capacity stayed at three. Recovery commands are explicit and reusable, rather than an unattended planner for every scholarly gap.

## GitHub tracking and shutdown

Closed verified-complete tasks #335, #336, #337, #340 and #342. Closed #343 as not planned after the independent exact-pair finding check rejected the rewrite request. Unresolved quotation identity (#338), producer page metadata (#339) and historical evidence for the reported mare gloss (#341) remain open, with their current scope documented. They are not fabricated completions.

`worker-audit-final.json` records zero live project Luna exec workers after verification. The temporary verification server was stopped. The older 300-character goal remains paused. Other entries retain their earlier approvals; they were not regenerated or certified against these new prompt instructions.
