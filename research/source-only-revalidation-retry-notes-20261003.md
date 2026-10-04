# Source-only revalidation retry notes (2026-10-03)

## Scope and exact-pair preservation

This pass retries only current canonical article/dossier pairs whose source gate remains
pending. It does not revise article, dossier or review content. Prior source-resolution
results remain in their original job paths. New calls bind the exact current article and
dossier hashes, review receipts, source findings and current source-scan pixels.

The retained findings identify distinct checks that must not be collapsed into a generic
“unused” outcome:

- **爸**: PDF p. 951 / printed p. 936 has a previously scan-checked literal occurrence;
  preserve/replay its transcription check. PDF p. 233 / 父 is a separate uninspected
  source lead. The article's 父 account cites other evidence; the source agent must verify
  whether that page is actually unused. The Academia Sinica 巴 lookup remains a distinct
  identity/source observation, not evidence from 字源.
- **帮**: PDF p. 708 / printed p. 695 has three glyph specimens not individually
  identified. The question is whether any exact article claim depends on assigning their
  identities; do not infer scalar identities from surrounding prose.
- **病**: PDF p. 684 / printed p. 671 has an exact retained transcription check for the
  形声字 clause and a separate 方 identity/scope question. A matching clause reading does
  not itself resolve what 方 labels.
- **不**: PDF p. 1050 / printed p. 1035 has a retained source-bound OCR correction
  finding about running-header text. It cannot be cleared as an unused identity/access
  gap; any real printed-text mismatch remains subject to the producer repair gate.
- **菜**: PDF p. 61 / printed p. 49 has four unidentified historical specimens. The
  entry prose may support the article's component claim independently, but the specimen
  identities remain unresolved unless separately established.
- **茶**: the PDF p. 71 / printed p. 59 headword/body and running-header occurrences have
  retained transcription findings; preserve their exact scan checks and do not downgrade
  them. Separate uninspected leads concern PDFs pp. 59, 60, 72 and 74; any finding about
  an unused locator can only be released after checking exact candidate dependence.
  External reading-dataset omissions remain independent gaps.
- **人**: PDF p. 711 / printed p. 698 contains small glyph specimens not individually
  identified; keep article evidence and these scalar-identity questions separate.
- **四**: PDFs pp. 1279–1280 have distinct gaps for numbered glyph drawings and the
  continuation-page specimens. The read 泗 passage does not identify unrelated drawings.
- **学**: PDF p. 277 / printed p. 265 retains unresolved identities after 冖 and in the
  parenthetical reduction, plus literal uncertainties at raw spans [944,945) and
  [1131,1133). Do not select Unicode identities or downgrade these checks without pixel
  evidence.
- **一**: PDF p. 13 has visually similar rare numeral forms; preserve the difference
  between a supported doubled-looking comparison and an unverified scalar identity.

## General gate improvement

The current source-resolution contract had a typed, exact-pair no-dependency disposition
for printed identity gaps, but no equivalent for a primary-source access finding that is
only an unrelated locator lead. Adding a narrowly scoped `source_gap_not_used` outcome
allows a fresh independent reviewer to report that no exact article/dossier claim relies
on an uninspected page. It requires complete-candidate review, both current hashes, an
exact affected-claim inventory, and cited independent evidence IDs for every reported
claim. OCR, literal, repair and identity findings cannot use this path; validated prior
literal/repair/transcription receipts mechanically bar downgrade. Source-gap resolution
does not create or replace the registered-book adoption audit.

## Contrasting smoke evidence

For **你**, the fresh source-resolution result at
`runs/source-enrichment-ziyuan/ni-hao-ma-smoke/ziyuan-2012/4F60/source-resolution-3/result.json`
inspected the original PDF p. 1100 scan (printed p. 1085). It reports 女/姓 material,
not a 你 entry, and independently finds no article/dossier claim depends on either
duplicate locator hit. The result is bound to article
`b484af4bf0aab34f84173ead13d9765a2cc6ba07e919a22f3d4864ee7e68bba2` and dossier
`fdf46757b49478949cc6e830a397d08db6c9cf35cd30f220d464346ceb00ae21`; the ordinary
publication path completed. This does not attest that the missing locator pages establish
anything about 你. Automated negative tests keep a gap pending when a candidate claim
depends on missing evidence or cites evidence that does not support the quoted claim.

## Retry outcomes

The exact-pair source-only retries produced the following completed results:

- **人** (`retry-2`): result `d7786c8dbd6da4445b17ed415ff7c106414803d7c99feb55aaff31005338dfad`, wrapper
  `a98bf8212a3f1f3c91235e8b14354fa7efd081974c04608b942499fb5d38ece8`. The exact
  approved pair passed source resolution and the normal publication gate.
- **一** (`retry-2`): result `1c4fe49d55b550e2c935e1609940281fd9df8c8110a19f42118f31afcc907e37`, wrapper
  `5b4615dfccfde7143c865ddb643fea298f11e9ab6ad478824526923ca6241cab`. The exact
  approved pair passed source resolution and the normal publication gate.
- **四** (`attempt-03`): at
  `runs/source-enrichment-ziyuan/si-immutable-source-and-components/ziyuan-2012/56DB/source-only-revalidation/c0633b37f0b9-16692d99b822/attempt-03/summary.json`,
  result `3d5cc8e22a17d7719ada3cf9eab7744e650244cc0dae53a6180c3a1828ed0651`, wrapper
  `b877a2604b9ba238a2db0bcb7e00b04e9a7ed483abc349378267ccb0cee619d0`. The two
  historical drawing identities were explicitly found unused; normal publication passed.
- **茶**: source resolution 6 at
  `runs/source-enrichment-ziyuan/tea-handoff-final-20261003/ziyuan-2012/8336/source-resolution-6/result.json`,
  result `2ded0001b9f95c9b722dc8dca28cf77fed915dbd16db40299a9df8a30f2a48db`, wrapper
  `33c41d5d6bfc81269edcceb59d2bb3ae1a994cb502794126bb177eb77f4569f3`. Independent
  scan observation matched both retained p. 71 literals to corpus (body 荼 and running
  header 茶). Six separate unavailable/uninspected source leads were found unused in the
  exact pair. The result explicitly does not establish what those missing pages or
  datasets contain. Normal publication passed.
- **你** smoke remains the contrasting locator example above; it also passed the normal
  gate with its original exact pair.

**学** remains held: raw spans `[944,945)` (`升`) and `[1131,1133)` (`毚片`) have no
verified correction or identity decision, so its exact-pair source gate remains pending.
The source-only scheduler also reported **爸、帮、病、不、菜** already running under
the full-queue coordinator claims; it performed no writes or model calls for those
characters. Recheck only after those claims are released.

## Coordinator verification and candidate coverage receipt gates

Root reviewed the source-gap and retry changes and reran51 focused source tests.
The same source audit validation now checks both existing approved research and
new source_coverage_candidate modes against the completed exact-pair Luna-low
coverage receipt; stale or missing candidate receipts cannot pass publication.
This preserves the actual candidate audit mode rather than relabeling it.

The full current-source audit checkpoint now verifies38/300, with no scan errors.
Nine changed canonical entries (三、六、南、回、女、帮、米、面、高) each occur in that
verified set; all retain actual authored/reviewed publication artifacts. The source-
only rechecks retain their unchanged article/dossier facts and fresh exact source
wrappers. Both cohort supervisors ended idle; attention recovery requires explicit
new work, not inference that terminal queues finished the full objective.
