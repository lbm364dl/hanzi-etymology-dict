# Preserve the full issue hierarchy and avoid repeated metadata writes

上 publication spent substantial time synchronizing existing GitHub findings. Inspection found two general inefficiencies: parent subissues were read from only the default first response page, and labels/milestones were edited unconditionally even when they already matched. Later children could trigger unnecessary parent lookups and every known finding incurred a write.

The synchronization now uses the installed `gh api --paginate` behavior and parses its consecutive JSON list responses. It fetches labels/milestones with existing issue identity and writes only missing labels or a changed requested milestone. Human discussion, other labels, curated parents, stable deduplication markers, active finding reopening and no automatic closure remain unchanged. These are generic tracking improvements for the full cohort and future registered books.

All eight `pipeline.test_issues` tests pass, including a child on a second response page with already-correct labels/milestone requiring no mutation or parent lookup. Existing tests still cover new native subissue creation, curated hierarchy preservation and finding deduplication.
