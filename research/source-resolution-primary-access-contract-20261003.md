# Source resolution for primary-source access gaps (2026-10-03)

The 边 handoff had two retained findings describing a failed direct opening of a
1956 scheme page. They were recorded beside OCR findings, but their substance was
an access gap: the primary table and exact entry had not yet been inspected. The
old source-resolution dispositions could only leave a finding pending, release an
unused uncertain glyph identity, reject a proposed OCR replacement, or verify an
applied OCR repair. Mapping a newly inspected primary source to any of those other
outcomes would have misdescribed the evidence.

`source_enrichment.resolve_source_findings` now has a general
`verified_source_claim` disposition for a narrowly eligible retained primary-source
access gap. The caller must supply the exact research result and metadata plus the
evidence indices and scan pixel hashes. The harness verifies completed Luna-low
research metadata, exact result hash, source-image attachment file hashes, decoded
pixel hashes, and that the cited research evidence is explicitly a primary scan
inspection. The independent source-resolution call receives those source pages and
must return a matching per-finding observation. The saved gate rechecks the source
artifacts, scan pixels and exact evidence indices, then requires independent
support observation before releasing
the finding. Missing proof, changed hashes, a non-access finding, or a contradictory
observation leaves the gate pending. This disposition does not claim an OCR repair
or resolve other findings.

Tests cover absent scan proof, incorrect pixels, changed research hashes and the
saved gate's revalidation. The targeted suite is
`/tmp/hanzi-etymology-venv/bin/python -m unittest pipeline.test_source_enrichment`.

For 边, the retained primary scan research directly inspected the 1956 《汉字简化
第一表》 page and the unnumbered State Council resolution leaf. Its evidence says
the table note defines parenthesized characters as original traditional forms and
shows 边（邊）; the decree dates the first-table nationwide effective scope to
1956-02-01. A fresh independent source-resolution call must still decide whether
that exact primary evidence resolves the two retained failed-access findings; no
verdict is prewritten here.

The first fresh source-resolution attempt is preserved in
`runs/source-enrichment-ziyuan/bian-final-source-gates-20261003/ziyuan-2012/8FB9/source-resolution-2/`
(result hash `ab2df28f6f723a8906a8891c20b76222160ce18f233b8315ddcd9bd1b236789f`).
It made the requested 1956 source finding judgments from the original scans, but
it also assigned `unresolved_identity_not_used` to retained literal and applied
repair findings. The result was therefore not accepted as a clean gate. The prior
`source_resolution.json` metadata was copied unchanged into that stage folder;
the full stage result, prompt, image manifest, and source research artifacts remain
available for audit. A stricter gate now requires prior literal/repair evidence to
be repeated with its exact check, and requires unresolved identity dispositions to
name the actual article claim text and independently cited support. The attempt
was retained as a counterexample; it was not rewritten as an approval.

The same recovery exposed a second generic failure: the former gate accepted
`unresolved_identity_not_used` for findings that actually retained an OCR literal
or applied-repair receipt. The gate now preserves those prior check keys across
source-resolution result folders and refuses to let them pass through the identity
disposition; the matching literal/repair observations must be replayed and rechecked.
An identity release now binds the exact current article text path, cited evidence
IDs present in that field, and an independent-support explanation. Invalid later
resolutions also return the saved status to `needs_source_verification`. A negative
test ensures a historical applied-repair receipt cannot be downgraded into an
unused-identity outcome. These checks preserve older contradictory stage outputs
while keeping the current gate honest.

The next actual pass (`source-resolution-3`, Luna low, result retained with its
image manifest and prompt) repeated the 1956 findings and exact OCR checks. Its
identity adjudications cited source IDs and quoted the relevant claims, but used
labels such as `formation.text: “…”` where the gate requires machine-checkable
article paths. The independent result was retained and rejected by the new
path/evidence verifier; it did not update the source-resolution receipt or pass
the gate. The authoring contract now states exact path forms such as
`article.formation` and `article.components[5]`, and permits a verbatim excerpt
from that field while checking the field's real citations.

The next genuine call (`source-resolution-4`) supplied the required exact article
paths and independent evidence references, and repeated the prior OCR checks. It
was retained but rejected because one source-claim observation misstated the
resolution-leaf pixel hash. The observation schema no longer asks a reviewer to
retype evidence indices or pixel hashes. The finding key joins its independent
support observation to the exact scan-bound research check recorded in the gate;
the prose reason still reports what the pixels show.


The next attempted independent pass (`source-resolution-6`) actually ran on the unchanged
candidate and returned all findings, but the gate correctly rejected incomplete identity
inventories: some findings had `affected_paths` without matching claim excerpts, and several
explicitly unused identity findings had empty path inventories. Its real output remains at
`runs/source-enrichment-ziyuan/bian-final-source-gates-20261003/ziyuan-2012/8FB9/source-resolution-6/`;
it did not write a current resolution receipt or approve status. This identified that the
old schema had no explicit way to distinguish a complete no-dependency judgment from an
omitted analysis.

The no-dependency path is now explicit and exact-pair bound. For an identity-only finding,
an independent reviewer may return an empty affected-claim inventory only after checking the
whole article and dossier and echoing their exact hashes, with an explicit reason that no
article or dossier claim depends on or uses the identity. Nonempty inventories still require
exact current article paths, verbatim claim text and independently cited dossier IDs. The
wrapper binds these judgments to the exact candidate hashes and retained finding key. This
route cannot release findings with literal, repair, metadata or transcription checks. A new
regression covers absent/mismatched binding and contradictory affected paths.

`source-resolution-7` and `source-resolution-8` are retained failed calls with no review result.
Their saved stdout identifies the concrete failure: Codex structured-output validation
requires every object property to be listed in `required`; the added no-dependency identity
properties were initially omitted. The source-resolution harness now validates its completed
wire schema locally before launching a model, and a nested array-item regression catches this
failure class. The source-resolution-7 stderr also contains a model-catalogue refresh timeout,
but the stdout's invalid schema error is the definitive terminal cause. No verdict from either
failed call was used.

The current fresh attempt is `source-resolution-9/` (Luna low, shared capacity 24). It also
includes the general exact-observation/reason consistency prompt for literal checks: findings
must say what the pixels show and agree with current, proposed, and observed literals. The
attempt remains pending until it returns and the exact retained checks plus all finding keys
pass the gate.


After the schema fix, `source-resolution-9` completed as a real Luna-low review, but its
result was still not accepted. It named IDs absent from the quoted article field for some
identity claims, returned no explicit identity observations for two findings whose wording
used “printed special component identity is unresolved,” and used identity dispositions for
those findings. These were concrete contract/input issues, not source evidence failures. The
result and meta remain unchanged in `source-resolution-9/`; no wrapper or approval was written.
The identity classifier now recognizes an unresolved `identity` phrase regardless of whether
it is preceded by “printed”, “special component”, or “Unicode”. The reviewer instruction now
requires `affected_paths` to exactly match the cited paths and says to copy evidence IDs only
from the exact path's own `evidence_ids` array. Article-path parsing also rejects any unconsumed
or malformed suffix rather than silently ignoring it.

A separate failure-class audit found that the prior historical-check collector trusted raw
`result.json` dispositions, even when the result had no matching wrapper or verified check.
Historical check classes now come only from completed Luna-low wrapper/result/meta tuples bound
to the current findings, article and dossier hashes, with exact matching observations and fresh
validation of the underlying corpus/source repair. For example, this job still reports one
verified historical literal finding and three applied repair findings from its preserved
`source-resolution-prior-result-20261003` wrapper; stray raw dispositions alone add no
obligation. A regression verifies that behavior. The strict Codex schema validator is also
covered by a nested required-fields regression.

`source-resolution-10` is the next actual attempt under this corrected contract, still bound
to the same exact candidate pair and primary scans. It remains pending while queued/running.
