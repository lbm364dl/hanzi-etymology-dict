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
