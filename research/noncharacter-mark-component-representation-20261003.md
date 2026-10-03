# Representing visible marks without guessing their glyph identity

## Finding

The 本 continuation exposed a data-model gap: reviewers correctly rejected both a disputed
Han-character identity and the Unicode stroke symbol `㇐` as the component's asserted identity.
The scanned current form supports a separate short horizontal mark below 木, while the
transmitted explanations disagree about whether that mark should be read as 一 or 丅. The
representation previously required every component's `form` and graph-node ID to be a literal
Han character or radical. The writer therefore could either choose a disputed identity or omit
an evidenced visible element, even when the prose accurately distinguished the observed mark
from its historical interpretation.

The initial source crop was also found to come from the neighboring 樹 paragraph. A separate
provenance recheck identified the actual 本 paragraph on 字源 page 516 and retained its full-page
and corrected-crop images. The source-crop error is character-specific and remains archived;
the representation defect applies to any entry whose evidence identifies a visible noncharacter
mark while leaving its historical glyph identity unresolved.

## General contract

Ordinary glyph components retain the existing literal `form` and `origin_form` semantics and
literal relationship IDs. A positively identified visible noncharacter mark may instead use:

- `element_kind: "noncharacter_mark"`;
- empty `form` and `origin_form`;
- an opaque `element_id` scoped to its exact host, such as `本:mark:lower-1`;
- a concise `element_label` describing only the visible mark, such as “short horizontal mark.”

This record still requires cited evidence, a scoped component relationship, and independent
review. It cannot carry a phonetic role or a guessed reading. Reviewers must inspect the cited
claim and any attached scan; they must not match words like “mark” or “stroke” automatically or
force the label to match one competing historical reading. A label establishes neither the
mark's function nor its ancient identity. The identifier is local to one scoped graph and must
not be reused as a cross-entry glyph identity. Legacy records without the new fields continue to
mean literal glyph components. The alternative is not a workaround for an unidentified rare
character, an unread OCR graph, or a historical glyph specimen: retain occurrence-specific
provenance and an explicit identity gap for those cases.

## Verification receipts

The initial input to `runs/source-enrichment-ziyuan/ben-current-source-repair-20261003/final-continuation-v1`
was article `796c0e6fe919077246c6f843301d6cb3223be3bf221c3b62019016adf7455e20` and dossier
`5cd6d76140bb8a4fbb2506e3ee2e9895169390e8364cc0ff74f6d7a6804f8cc4`. Its first author patch
produced the exact reviewed candidate `36945d3ad0d6ead80adc45f7eeb75003e21165e457e433512282fd7e60212b8c`,
with `㇐` in the component and corresponding edge. The `round-0/factual/result.json` and
`round-0/factual-verification/verified-review.json` receipts both rejected that identity and
asked to retain the observed short horizontal mark separately from the competing 一/丅 readings.
The corresponding readability proposal and independent verification also revised the same
㇐ candidate; their specific finding about the component edge differed. These four round-0
review artifacts are not approvals. Later `reviews.json` binds article
`5790ebde6018f23dda8dd113cae4d49c719cbcec34369a3d420a575e4e4434c6` (the subsequent candidate
that restored `一`), not the initial input or the `㇐` candidate. The run ended failed on a
component-role/edge mismatch. The attached original
page 516 has SHA-256 `f732cc6b3e3988c9455fe2aa8c420cafa0adbc24c01aa76fb742a9f67a1df5b4`;
the corrected 本 paragraph crop has SHA-256
`659d8734e594e44132eba4096a31400f85405df57c9e10bb04c110daa107e26d`. Both stages remain
revision findings, not approvals. The ㇐ candidate also received an independent learner finding:
current evidence supports basis, not an unqualified current “source” meaning. This schema change
does not resolve that separate editorial finding.

## Scope

The new schema and review instructions preserve supported visible parts without assigning
unsupported historical component identities. They do not determine whether any particular
mark is actually present; source inspection and fresh independent reviews remain required.
No published entry was edited by this change.

## First integration continuation

The first fresh continuation under this contract,
`runs/source-enrichment-ziyuan/ben-current-source-repair-20261003/typed-mark-final-repair-v2`,
ended before independent review. Its genuine Luna-low author correctly emitted a typed visible
mark record, but placed `element_kind` and `element_label` on the relationship `subject` node as
well as on the component. The graph endpoint schema intentionally accepts only `{kind, id}`, so
the patch failed validation; the preserved patch-repair stages repeated that shape. This exposed
a prompt-location ambiguity, not a reason to loosen relationship node validation. The prompts
now state that the display metadata belongs only on the component record and that the endpoint
must remain `{kind: "component", id: element_id}`. This failed run produced no review approvals.

## Patch-path overlap finding

The first fresh author attempt using the typed component contract,
`runs/source-enrichment-ziyuan/ben-current-source-repair-20261003/typed-mark-final-repair-v3`,
used the right typed mark and the required exact `{kind, id}` relationship endpoint, but its patch combined whole-record replacements with descendant edits. It replaced `components/1` while also editing fields beneath that component, and replaced the `meaning_history/senses` array while editing individual sense descendants. The patch validator correctly rejected these overlapping paths and the bounded repair repeated the same structure. No independent review ran and the failed patches remain retained. This was a general authoring-protocol ambiguity: “distinct nonoverlapping paths” alone did not make the parent/descendant failure concrete. The article-patch prompt and its repair feedback now explicitly require choosing one level per edited object or array, with examples, and `test_overlapping_patch_paths_get_specific_repair_feedback` exercises the repair loop without changing the original candidate.

The next actual Luna-low attempt, `typed-mark-final-repair-v4`, avoided the overlap and completed two rounds of independent factual/readability review. It ended `needs_revision`; both final receipts bind article `b8486076739cac3822e4bde27e79f83bc568a172bad77f903175a2f211d12e00` and dossier `5cd6d76140bb8a4fbb2506e3ee2e9895169390e8364cc0ff74f6d7a6804f8cc4`. The visible mark component cites the active variant-dictionary evidence `X-fe8eabe47614373a6a2a`, and the generated indicator relationship uses the exact typed component endpoint. The final factual verifier still finds the root sense’s current status unsupported by its cited proposed-original/historical attestations; the final readability verifier instead treats current dictionary evidence as support for the current root period. This disagreement remains open for fresh adjudication. Both final review lines also document a need to align the component’s visible-mark evidence in its generated edge. Neither receipt is an approval. A new continuation is retained under `typed-mark-final-repair-v5`; no canonical entry was edited or published by this work.

## Legacy publication compatibility

The full site rebuild caught a scope gap that the HSK1-only integrity audit could not
cover: previously approved legacy entries outside that cohort use descriptive component
labels. Enforcing new typed literal-form rules on untyped records invalidated those old
reviewed articles. Validation now preserves absent element_kind records with their exact
legacy semantics; explicit typed records stay strict, and orphan element IDs/labels are
rejected. New writer schemas still require the typed fields. Regression tests load genuine
approved legacy records; no article or approval was edited. The targeted suite passed
124 tests. The rebuild now refreshes all 312 overlays, full graph exports 303 v2 entries
with 1942 nodes/2012 cited relationships, and the HSK1 snapshot integrity passes 300/300.
