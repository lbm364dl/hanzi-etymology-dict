# Generated meaning edges and targeted revisions

Water's genuine `water-status-repair/ziyuan-2012/6C34/round-0/revision/result.json`
changed `relationships/0/object/id`, `id` and `text`, while leaving the authored
sense ID unchanged. Later rounds likewise targeted generated edge text/citations.
Assembly reconstructs those edges from `meaning_history`, silently discarding
those edits. This explains a recurring ineffective revision class, not an OCR
error or evidence that agent receipts were fabricated.

The targeted-patch schema now excludes direct paths into generated meaning edges.
An array replacement may omit them or preserve them unchanged; mutated or new
generated edges are rejected with bounded repair feedback. Agents must edit the
source sense/development fields, including development endpoints on a sense rename.
Graphic relationship indices are preserved; there is no filtered-array index shift.

A regression exercises the array-replacement bypass, actual repair feedback, an
authored sense-certainty edit and its regenerated edge, preserving input immutability.
It and the indexed citation-alias and unaffected-field patch tests pass (3 tests).
This contract does not rewrite or recertify published articles. 水's distinct
certainty mismatch remains tracked in #147 pending genuine authorship and reviews.

## Follow-up: authored arrays and replacement types

The 日 current-sense repair correctly returned an empty authored `relationships`
array after replacing its meaning history. The pre-assembly article schema rejected
that array as empty, even though assembly supplies the required meaning links.
Targeted patches now validate the assembled shape while retaining the direct
mutated-generated-edge rejection. A regression verifies this empty-array case,
actual regenerated edges, input immutability and a single successful patch call.

The 四 repair separately exhausted bounded retries by placing bare prose in the
object-valued `summary` and `formation` fields. The patch contract now exposes
each allowed path's value kind and explicitly requires complete object values,
or an allowed text child for prose-only edits. Invalid values remain rejected;
the coordinator does not wrap prose or invent missing citations.

Four focused patch tests pass, including generated-edge mutation rejection and
semantic-validation repair. Both interrupted jobs retain every real response and
resume from their actual reviewed drafts in `patch-contract-recovery`, using
fresh Luna low authorship and independent reviews. This does not certify either
entry or any previous publication. The distinct 水 certainty repair was since
published with fresh approvals; #147 is closed, as recorded in
`research/shan-shui-publication-20261003.md`.
