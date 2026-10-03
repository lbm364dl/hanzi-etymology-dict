# GitHub hierarchy capacity

Actual issue #1 reached 100 direct children, confirmed through paginated API
inspection and GitHub 422 responses for 好/山 finding handoffs. Official limit:
https://docs.github.com/en/issues/tracking-your-work-with-issues/using-issues/adding-sub-issues

Created native subgroup #152 under #1 for subsequent character findings. Moved
only newly created automated #147 into #152 to free the one root slot required
for the subgroup; issue content, discussion and identity are unchanged. The
registry now routes new character findings to #152; OCR remains #5 and pipeline
remains #2. Existing curated parents are preserved by synchronization.

Issue workflow metadata is excluded from source identity: this does not invalidate
research or approvals. Failed handoffs must be retried against current registry
configuration, reusing their existing stable markers rather than creating duplicates.
The grouping does not shrink the objective or measure character completion.
