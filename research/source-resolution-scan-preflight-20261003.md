# Original scan preflight for source resolution

A 本 continuation had copied a checkpoint without scan attachments. The worker noticed that a source-resolution invocation consequently received zero images and treated that attempt as insufficient rather than source verification.

Failure class: preserving an approved pair and its provenance does not establish that an independent scan reviewer receives the original pixels. Historical checkpoint copies can lack locator image records.

`resolve_source_findings` now rejects an empty scan packet and validates the supplied paths and decoded-pixel bindings through the existing attachment contract before invoking the reviewer. Metadata/transcription checks can still add their verified original scans, and explicit `source_context` remains supported. No source verdict or article is changed; failed receipts remain retained. Existing entries require their own exact source gates.

Verification: all 24 source-enrichment tests pass. The transport test demonstrates that absent scans fail before a review directory is created, then a supplied image reaches the actual reviewer transport contract.

The same failure class surfaced in a coordinating 不 handoff: the automatic locator found only OCR mentions and supplied no images. The custom coverage invocation accepted a review call without image attachments; the new resolution preflight correctly stopped the subsequent scan check. That handoff was not published. Its insufficient coverage receipt is retained, and a fresh handoff will attach the exact p1050/p1051 originals actually found by research.

The shared `source_adoption.check_coverage` entry point now also requires nonempty original scan attachments and validates their files/pixel bindings before any review call. This protects coordinating handoffs as well as normal adoption. Tests use actual temporary image fixtures and verify both empty and missing-file packets fail before invoking the reviewer or creating a job. All 29 combined source-adoption/enrichment tests pass.
