# Bound OCR repair observations to actual repairs

好's genuine source-resolution-1 correctly distinguished the applied PDF1109
first-character repair from the separate PDF1110 continuation identity gap,
but also emitted a repair observation for the non-repaired continuation. The
existing exact-key validator rejected that extra record and kept publication
blocked. The real output is preserved; it was not edited into an approval.

The transport schema now exposes the same contract enforced by validation:
repair observations have exactly the requested repair count and only requested
repair keys; literal-proposal observations likewise use their exact counts/keys.
A regression accepts the requested record and rejects both an unrelated identity
key and an extra record. Source-enrichment and repair tests pass (24 tests).
A fresh real Luna low scan-resolution process runs under this updated schema.
This is a transport-contract repair, not OCR approval or whole-page verification.

The next real scan check returned the full vessel phrase rather than the single
changed character. Exact literal validation kept it blocked, and the actual
result remains preserved. The repair-observation schema now bounds literal
length to requested spans and permits null for an unreadable span (which cannot
release an applied-repair gate). Instructions require only raw_start/raw_end,
never neighboring text or script normalization. The regression rejects a full
phrase for a single-character repair and accepts null as an unresolved report;
24 tests still pass. A fresh check with a source-bound continuation crop is
running; prior contradictory results remain audit evidence.
