# Repeatable whole-cohort source audit

The temporary full-cohort audit initially missed earlier job locations, omitting
valid 一/半 publications. It was corrected to inspect those locations before
the 9/300 report was accepted. The reusable `pipeline.source_progress` command
now searches all source snapshots under configured roots (default runs and
source coverage), selects the requested registered book and exact character-job
directories, and invokes the actual current `_published_matches` gate.

It includes every cohort character, reports verification failures, de-duplicates
jobs and counts each verified character once. Saved status labels never certify
completion. Tests exercise duplicate roots/jobs, another source, archived copies,
unstarted characters, false publication labels and failed verification. Combined
source-progress/source-enrichment tests: 23 pass.

The actual current HSK1 report was regenerated with the prepared producer-aware
Python environment; missing verification dependencies cannot establish a repaired
source's integrity. This is source-completion tracking, not a substitute for
individual claim certainty, factual review or the remaining 291 entries.
