# Book source-corpus consumer review

Reviewed 2026-09-27 against `~/hanzi-etymology-books/source-corpus/README.md`, the actual `scripts/source_corpus.py` implementation and its five sample page records. The etymology pipeline can use this format for provisional source discovery, with direct scan checking of passages it actually cites. Whole-book clean PDF production is not a prerequisite.

## What already works

- Separate searchable text from layout reconstruction and publication approval.
- Return an original source scan, PDF page number, reading/manifest paths and hashes.
- Preserve unknown glyphs as explicit image references instead of silently inventing Unicode.
- Preserve uncertainty and null printed pages when unverified.
- Reject stale reading exports against source/evidence hashes during corpus construction.

Actual sample search: `世父` returns the 漢語大字典 sample at PDF page 274. `學` also returns that page, but as a quotation inside the 世 entry, not as the 學 headword. The five-page sample does not yet provide the 學 entry that was inspected separately in the 字源 scan.

## Priorities before whole-book expansion

1. **Compact default search results.** The 世父 hit currently serializes roughly 16,176 characters, including 32 page glyph assets and the entire review queue. Return book/edition ID, page/entry locator, short passage, review flags, source scan path and hash. Include only glyph references appearing in that passage. Put the full asset list and review queue behind a separate inspect command or `--details`. Keep bounded top-k results. This is the highest-priority token saving.
2. **Headwords and passage anchors.** Add entry/headword/variant metadata where detectable and preserve span or block IDs and bounding boxes. Distinguish an exact headword hit from a mention/citation elsewhere. Entries spanning pages need a continuation link. A search for 学/學 should rank that entry before every occurrence of 学者. Preserve original text when doing search normalization.
3. **Stable bibliography.** Add a book manifest with title, author/editor, edition, year, publisher, volume, ISBN, PDF hash and stable book ID. Current book IDs hash the filename and change on rename. Keep verified printed page separate from PDF page. Unverified printed pages should remain null.
4. **Explicit coverage.** Return processed pages/ranges and completeness status with searches. No hit in a five-page or partially processed corpus must not imply that the book lacks an account.
5. **Separate review dimensions.** Track transcription status separately from layout/spatial review and from historical-glyph identification. A pending clean layout should not block search; pending OCR remains a locator lead requiring scan inspection. Return these statuses and relevant uncertainty concisely.

A linear JSONL search is adequate for the pilot. A local text index can be added if measured whole-book search latency warrants it; embeddings or a vector service are not required for exact headword research.

## Expansion approach

Make the compact result contract and bibliography/coverage explicit, then process a representative small range including complex headwords, rare historical forms and a multi-page entry. Check retrieval and direct-source navigation before scheduling the whole book. Recognition-only page processing plus a provisional searchable corpus is the useful first whole-book output; expensive clean typography and full spatial reconstruction can remain separate. Record actual OCR cost and failures in that pilot before extrapolating the batch.

The dictionary consumer should retrieve a few passages, inspect the cited scans and preserve attribution. It must not import provisional OCR directly into published entries or demand full-page visual review for every irrelevant hit. No whole-book OCR has been launched from the dictionary project during this review.

## Producer response: version 2 accepted for provisional research

The producer's `source-corpus/HANDOFF-RESPONSE.md` and revised README were inspected later on 2026-09-27. Actual CLI checks covered 世父, 學, a no-hit query, the lightweight 唐 sample and `inspect` by returned page ID.

- The 世父 result now uses about 1,476 serialized characters instead of about 16,176. Its entire envelope is about 2,655 characters including five-book coverage.
- The no-hit envelope preserves incomplete processed-page coverage.
- Lightweight 唐 retrieval reports unreviewed transcription, layout not requested, and glyph references pointing to the page rather than fabricated crop coordinates.
- The search envelope is now schema version 2; `inspect` returns full details only on demand.
- PDF content hashes provide stable book IDs. Bibliographic nulls and unknown printed pages remain explicit.

This is sufficient for the dictionary's provisional source-discovery workflow. Headword classification and cross-page entry links may remain deferred for the first OCR edition, provided results remain explicitly `text_mention` / `entry_metadata: not_extracted`. They are later retrieval improvements, not prerequisites for recognizing useful text. First-pass OCR reuse in the clean edition is a producer feature; this consumer review did not run or benchmark the upgrade or verify its billing.

Use compact top-k search first, inspect only relevant results, and verify the cited scan passage before authoring. No-hit results mean no match in processed OCR text, never no scholarly explanation. Neither this review nor a complete OCR corpus is a publication approval. No whole-book OCR was launched by this project.

## First-book recommendation

Start with 李學勤主編《字源》 (2012): the lightweight OCR sample already uses its PDF page 101, its character-entry structure suits independent etymology jobs, and direct inspection of its 學 entry supplied useful attributed evidence. Put 季旭昇《說文新證》 next as an independent complementary account. This is an OCR rollout recommendation, distinct from the earlier acquisition priority ranking. Neither recommendation launches a batch from the dictionary project.

## Expanded 12-page consumer check

Checked the producer handoff, corpus, batch summary and live CLI on 2026-09-27. Search queries 唐, 臼, 性, 女 and a no-hit query returned bounded version-2 envelopes with correct 12-page incomplete coverage. `inspect` returned the full corrected page and correction provenance. All 12 scan paths exist. Effective page 220 text contains both verified 臼 corrections; original evidence remains separately identified. Producer measurements report 11 new requests plus one cache hit in 59.28 seconds; this consumer did not independently run or benchmark OCR.

The format is suitable for provisional research, but additional visual spot checks of PDF pages 820 and 1100 expose an important recognition failure: page 820 repeatedly substitutes 魃 for the printed 鬾 headword, and page 1100 repeatedly substitutes 芈 for a different uncommon printed headword. These substitutions alter searchable character identity and can misassign phonetic roles. Page 820 also still substitutes 一日 for printed 一曰. These are source-image observations, not etymological disputes. Verify exact uncommon Unicode or use explicit page-bound unresolved-glyph references; never invent an identity.

Search still returns the first page occurrence, often a running header: 唐 returns page 101's header without its entry; 女 returns page 1100's header rather than its useful explanatory passage. Full-page `inspect` makes the evidence accessible, so headword ranking remains a deferred enhancement rather than an expansion gate. Agents must inspect the cited passage and check continuation boundaries.

Recommendation: retain this lightweight workflow, correct the new verified recognition errors through the existing provenance layer, and run a fresh small smoke using the revised prompt before scheduling whole-book OCR. The producer README explicitly says its latest prompt has not yet received a live smoke run. Include the two problem pages and a few unseen pages; keep separate review dimensions and report any unresolved headword identities. No need to add clean layout or full-page approval as a prerequisite. This project launched no OCR or whole-book job.

An independent `gpt-6-luna` low consumer agent also inspected these two scans and confirmed the identity errors and 曰/日 substitution. It found the page 1100 脊/束 phonetic discussion useful and substantially preserved. Its recommendation likewise accepts small provisional batches after source-bound corrections and a fresh contrasting prompt smoke. Exact identity of the unusual page 1100 headword remains unresolved in this consumer check; do not replace it with an unverified Unicode guess.

## Live full-edition handoff

The producer has started the authorised 字源 run. On this consumer check, `ziyuan-pages.jsonl` contained 55 unique pages out of 1,435 and the producer status reported running. CLI coverage agreed with the indexed count. Search for 鬾 retrieved the corrected page 820; page 1100 preserved unresolved printed-character references rather than false 芈 substitutions. Both retained correction provenance. Search for 學 returned no hit under explicitly incomplete coverage; its previously inspected PDF page 277 was not yet indexed. Counts are a snapshot, not a live promise.

The dictionary's local-source instructions now prefer `ziyuan-pages.jsonl` for 字源, retain other-book samples and the pilot fallback, and prohibit treating overlapping pilot/live records as independent evidence. No producer job was started, resumed or modified by this consumer check.
