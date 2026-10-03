# Additional source scans without changing locator identity

本 is a text mention in the automatic locator despite having a directly inspected relevant paragraph. A prior handoff injected the p516 review scan into the locator, which made the otherwise unchanged locator fail its publication identity check. The subsequent valid handoff kept the scan separate.

`source_adoption.adopt` now accepts optional `source_context` scan records, validates them through the existing original-image attachment validator, saves them separately, and supplies them to actual independent source coverage. The frozen locator and its hash remain exactly the locator output. Missing scans still fail, and the article/dossier/review gates remain intact. This permits agents to use additionally discovered pages from any registered book without falsifying locator provenance or requiring bespoke handoff scripts.

A contract test covers a mention-only locator with a supplied original scan, unchanged published content and locator, retained context, and rejection when scans are absent. The 本 metadata refresh is the real-source smoke case.
