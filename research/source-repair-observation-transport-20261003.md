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
