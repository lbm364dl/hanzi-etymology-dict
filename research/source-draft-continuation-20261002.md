# Preserve unfinished drafts after source repairs

The 愛 recovery attempt ended without approval after fresh research and revisions. Its
new research correctly identified the unrelated 爰 headword on PDF355, while its draft
still needed author repairs. Starting every source refresh from the older published
article loses relevant research and revisions and repeats known failures.

The generic source harness now accepts a single exact terminal job as `--continue-from`.
It takes the previous job's OS lock before reading: a terminal status alone cannot
override a live orphaned agent. It checks character, registered book and unchanged
canonical baseline, validates the unsigned article/dossier, and freezes exact hashes in
the new job. Canonical source snapshots remain unchanged. Review receipts are not copied;
the new job always performs current-source research and fresh independent reviews.
Changed continuation inputs require another fresh job rather than overwriting provenance.

A contract test verifies draft reuse, preserved baseline, absence of copied approvals,
refusal after canonical changes and refusal while a prior lock is held.

The 二 smoke also exposed a review-contract gap: a verified `revise` finding said
“No change to this sense or its generated has_sense edge is required.” The existing
contract guard matched only shorter no-change phrases. It now recognizes scoped versions
and requests a genuine additional agent review. It never silently turns such a verdict
into pass. Both prior proposals and actual final review products remain retained.

87 editorial/source-enrichment/adoption/issue tests passed after these changes. Prompt
and guard changes do not certify any existing article; the pending drafts still require
fresh actual review approvals.
