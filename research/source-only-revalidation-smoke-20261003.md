# Source-only revalidation smoke (2026-10-03)

## Scope and invariant

The source-resolution contract was exercised on the already-published 百 pair. The exact approved candidate and its source audit were retained; the Luna stage was limited to resolving the recorded source scan finding and could not edit authorship or reviews. The scan was the original 字源 PDF page 303 (printed page 291), with decoded-RGB SHA-256 `c506789d484cab6670b5a9c2202afeb5dc27f6779e63ea0fe5d807cd8c6cf217`.

## First smoke and correction

`runs/source-enrichment-ziyuan/bai-final-handoff-20261003/ziyuan-2012/767E/source-resolution-1/` is preserved. Its genuine Luna-low result assigned `unresolved_identity_not_used` to a marker stating that three printed glyph identities “are not established,” but the schema omitted `identity_observations`. The gate correctly left the source finding pending. Root cause was `_source_finding_class` matching singular `identity` but missing plural `identities`; this is a lexical classifier gap, not a character-specific exception or a reason to relax the gate.

The general classifier now matches `identit(?:y|ies)`, with regression coverage for the plural wording. This selects the existing exact-pair independent-observation contract. The change passed the focused suite: 42 tests across `test_source_enrichment`, `test_source_adoption`, and `test_source_progress`.

## Fresh bounded smoke result

A new Luna-low stage was run on the unchanged pair and same pixel-bound page: canonical JSON digest of `source-resolution-2/result.json` `8fac8a5d751832eb65c29865c43580986b7153fd8a0c24d6862b0de704a7565c`; canonical JSON digest of the final wrapper `source_resolution.json` `83099eed7707d00223601c6dd03d6b8b90d32461b6c6c0ebf6ee86d17a3c66eb`.

The result retains the finding as an unresolved printed-identity gap but supplies a complete-candidate observation bound to exact article SHA `31c38cce5e67d56eb0628d6f308558d07b337a4b45cfe34c8a1ab9a1b08d3aa0` and dossier SHA `9906574fdb8589d761d37c20a817f931cc316921259ae910e8142e453cbce545`. It inventories no dependent article or dossier claim and explains the remaining gap. `_source_findings_pending` is false; status is approved. The earlier invalid result and automatic-attempt record are preserved rather than rewritten.

The 百 case supplies the identity-only contrast to the mixed 边 smoke, which exercised identity gaps alongside verified literal repairs and primary-source access checks. The two successful bounded cases establish that the source-resolution gate handles distinct finding classes without changing article prose or review approvals.

## Parallel source-only scheduler and ownership

A 12-entry bounded actual Luna-low batch restored 百 through normal publication;
the other 11 retain fresh pending results with missing valid observations or remaining
source gaps. The scheduler reuses only unchanged canonical pairs and their exact
independent reviews/source audits. Prior source wrappers are archived. Verified retained
checks are replayed, and current original page attachments are derived from checkpoints
and corpus records. Invalid/noncanonical/duplicate candidates are skipped with reasons.

A root review found attempt-input and archive writes occurred before the job lock.
The scheduler now acquires the same global source-character claim as normal workers,
then the job lock, before attempt checks, archival, inputs or model work. It preserves
existing inherited lock descriptors, adds both ownership descriptors to model children,
rechecks canonical and job pairs, and publishes through the ordinary locked gate.
Contention tests prove no attempt artifact or model call occurs while owned elsewhere.
Root reran the 45-test focused suite successfully. These harness checks do not certify
the 11 source-held entries, which still require genuine evidence and fresh resolutions.
