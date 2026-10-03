# Original scan preflight for source resolution

A 本 continuation had copied a checkpoint without scan attachments. The worker noticed that a source-resolution invocation consequently received zero images and treated that attempt as insufficient rather than source verification.

Failure class: preserving an approved pair and its provenance does not establish that an independent scan reviewer receives the original pixels. Historical checkpoint copies can lack locator image records.

`resolve_source_findings` now rejects an empty scan packet and validates the supplied paths and decoded-pixel bindings through the existing attachment contract before invoking the reviewer. Metadata/transcription checks can still add their verified original scans, and explicit `source_context` remains supported. No source verdict or article is changed; failed receipts remain retained. Existing entries require their own exact source gates.

Verification: all 24 source-enrichment tests pass. The transport test demonstrates that absent scans fail before a review directory is created, then a supplied image reaches the actual reviewer transport contract.
