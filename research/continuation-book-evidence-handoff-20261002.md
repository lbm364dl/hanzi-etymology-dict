# Consulted book evidence in fresh continuations

Failure class: a source job can complete genuine research yet leave its exact book records unused in the article. The subsequent fresh continuation preserved the draft and revise findings, but its automatic uncited-record feedback inspected only the new job audit. A new directory has no prior audit, so the exact consulted records were not automatically handed onward. This contributed to repeated citation omissions for 上、小、大.

The continuation now writes `continuation_book_leads.json` with the previous audit hash and only records whose IDs and source/field/text exactly match retained dossier evidence. Missing IDs and mismatched claims are removed. The records are explicitly research leads requiring current-source verification. They do not create a new source audit, reuse approvals, or satisfy source completion. Writer feedback directs agents to cite supported claims in metadata after fresh verification; independent factual/readability reviews and article-used book checks remain required.

Verification: all 15 `pipeline.test_source_enrichment` tests pass. The continuation contract test covers retained versus missing IDs, altered claim text, preservation of real draft provenance, and absence of inherited reviews/source certification. Live workers started before this change retain their original inputs; later continuations receive the new handoff.

## Bounded current-research citation integration

A fresh continuation can create a new page-evidence ID while the article retains a valid earlier ID. Repeatedly restarting research just to cite the newest ID can repeat this omission indefinitely. The source harness now permits one genuine authoring/refinement pass over the current researched dossier when an otherwise approved candidate has uncited page-specific book records. It preserves the prior exact pair/reviews/status in `before-citation-integration/<article-hash>/`, passes current exact records to the editor, and obtains new factual/readability reviews in `citation-integration/`. It does not attach citations itself or fabricate approvals. The resulting pair still must pass article-used book auditing and any source/OCR resolution gate. An unresolved support gap stays unresolved.

All 16 source-enrichment tests pass. The new fixture test checks that editing uses existing current research without rerunning initial research, prior receipts are archived, and a failed review remains a failed review rather than triggering repeated automatic passes. The real 爱 smoke run uses separate Luna low editing and review stages; it is not certified by this fixture test.

## Focused citation author

The 学 smoke showed that the general editor could return no edits despite seeing a correct superseding record, leaving an inaccurate older record cited. A dedicated `book_citation` authorship worker now receives candidate claims, retained evidence and exact current book records, and returns explicit edits only to existing `evidence_ids` arrays. It may identify unsupported records rather than invent support. An explicit `superseded_book_evidence_ids` task can request removal/replacement on supported claims; it does not delete the append-only dossier record.

The harness applies the actual agent's returned metadata edits, rejects unknown paths/IDs and duplicate paths, and runs fresh factual/readability reviews without another initial general edit. No coordinator chooses citations or hand-edits authored prose. The previous exact pair and actual receipts remain archived. All 17 source-enrichment tests pass, including refusal of prose paths and unknown IDs; real current smoke workers must still verify effectiveness.
