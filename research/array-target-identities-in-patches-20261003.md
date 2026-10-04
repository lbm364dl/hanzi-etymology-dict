# Show current array identities beside patch indexes

The first real narrow author patch for 半 issue #162 put the half-sense prose
into the midpoint slot and midpoint prose into the partial slot. Both independent
reviews caught the mismatches; that pair was not approved or published. A later
actual author/review pass fixed the indexed records, rather than changing their
IDs to legitimize the misplaced content.

This is a general patch-context failure: a numeric path is syntactically valid
even when the author associates it with a neighboring sense. The patch contract
now supplies `array_item_targets`, generated from the exact current article's
IDs, glosses, component forms/scopes and learner component indexes. It shows
zero-based indexes and includes only items intersecting the editable paths;
generated meaning edges remain excluded. The map is recomputed for every
invocation, so a previous draft's order does not determine current targets.

These labels are guidance, not semantic approval or a substitute for factual
review. A regression test uses two distinct sense IDs, reorders them, and checks
that the scoped patch sees the current slot's identity while preserving the
other record and input article. That test and the existing generated-edge/source-
sense repair test pass (2 tests). No approved prose or review receipts were
changed by the harness update.
