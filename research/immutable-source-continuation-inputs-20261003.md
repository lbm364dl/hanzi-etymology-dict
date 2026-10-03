# Preserve outer source snapshots during editorial refinement

The resumed 口 smoke exposed a genuine snapshot collision. `prepare_job` saved
the published baseline in `source_article.json` and `source_dossier.json`, with
hashes in `source.json`. Editorial refinement of a continuation draft then
overwrote those same files. A later resume correctly rejected their hash mismatch.

Where an outer `source.json` snapshot exists, refinement now stores its actual
draft inputs as `refine_input_article.json` and `refine_input_dossier.json`.
Standalone editorial jobs retain the previous filenames. This changes no
research, prose, citations or review approvals. A contract test checks that a
failed refinement leaves the outer snapshot byte-equivalent as JSON and that
preparation can validate it again.

Already overwritten job snapshots remain preserved as evidence of the failure.
Recovery uses a fresh job from the intact earlier baseline, not rewritten hashes.
Live workers running earlier imported code are allowed to finish; their jobs
must be checked for this collision before any resume or publication.
