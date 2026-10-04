# Editorial pipeline failure classes (2026-10)

Recent source-enrichment reviews exposed several reusable contract gaps. Source labels and workflow terms were rejected by final validation, but the targeted prose-repair stage used a narrower detector, so a repair pass could return no edits and leave the cycle stuck. The shared diagnostic now feeds the same findings to targeted repairs, including reader-facing `summary.text`, while preserving citations and source metadata.

Learner validation requires only components scoped to the current host, with historical cards optional in every language. The bounded length/coverage repair packet had retained an older Chinese rule that requested every component. It now derives required indices from the same `component_scope` contract for all languages; a regression confirms the repair packet asks only for the current component and freezes component metadata.

Independent review verification also needs to distinguish a positive priority claim from an uncertain date. `earliest_attested` requires evidence establishing priority, although lack of an exact date alone is not disqualifying and appropriately hedged support should remain acceptable. A displayed glyph redraw cannot inherit a cited specimen's identity or date without a verified image-to-specimen link. These checks now appear in verifier instructions.

Finally, text-focused source refreshes reuse reviewed Chinese glyph candidates and therefore skipped visual curation even when a review explicitly requested a caption/provenance correction. The refresh can now rerun the visual curator against existing candidates and image snapshots when `review_existing_glyphs` is set, without reacquiring a gallery. Routing tests cover both direct refresh and the `refine` research-first path.

Verification: `/tmp/hanzi-etymology-venv/bin/python -m unittest pipeline.test_editorial pipeline.test_japanese pipeline.test_structured` passed (111 tests) before the final end-to-end routing test; targeted rerun of the new routing, learner-scope and verifier-instruction tests passed (4 tests).
