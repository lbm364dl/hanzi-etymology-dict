# Reconcile findings against actual resolution and prior issues

The next HSK1 batch exposed two recurring tracking gaps. Research strings survived
in archived outputs after current source checks resolved their article-level concern,
and recently created issue identities were absent from the older curated manifest.

Issue triage now receives the actual source-resolution result, exact binding and
current gate status. It distinguishes verified citation provenance from an unapplied
corpus metadata repair; no resolution implies that raw OCR or consumer metadata was
changed. A focused packet regression checks that distinction.

Triage also recovers stable keys from prior local `issue_findings.json` records only
when the paired receipt names the same GitHub repository, contains an issue number,
and binds the exact finding hash. Unsynced proposals, changed findings and other
repositories are excluded. Existing character/source scoping remains in force.
Three focused issue tests passed, including this recovery and the prior scoping gate.

`source_enrichment.run` synchronizes registered GitHub findings even with
`publish_now=False`. For an isolated task that forbids external writes, use direct
`editorial.refine`, or a source copy without GitHub workflow fields. Those fields are
excluded from research identity; the coordinating publisher still performs the real
configured issue sync before publication. The 吧 recovery exposed the unexpected
automatic issue #168; its receipt is preserved and the subsequent isolated edit
uses direct editorial refinement. This is orchestration guidance, not a claim that
any issue or unpublished candidate was automatically resolved.
