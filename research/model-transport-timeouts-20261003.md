# Model transport timeouts

Inspection of the two live source-enrichment outputs found 15 failed stage receipts
with 600-second process timeouts. The accompanying audit retains exact artifact paths
and observed diagnostic classes. DNS lookup failures, websocket connection failures
and model-list refresh timeouts occur in retained stderr. These are transport symptoms,
not evidence that character research is impossible or that model output was approved.
A later root DNS check resolved chatgpt.com in 0.005 seconds and github.com in 6.653
seconds; that snapshot does not prove all earlier failures have permanently cleared.

Failure metadata now records predefined diagnostic names and an exact stderr artifact
path. An unaccompanied timeout stays agent_timeout; a validation failure with transport
symptoms is not relabeled as a transport timeout. No old receipt is rewritten, no live
call is restarted, and no review gate is relaxed. Three focused tests verify these
distinctions and that arbitrary stderr text/secrets do not enter added metadata.
Explicit attention retries can reuse completed upstream stages once the cause is fixed.

## Live dashboard verification

Failed stages now expose observed diagnostic names in their Time breakdown details.
Old receipts are read without modification; newer model calls retain diagnostic fields
directly. The dashboard labels the observations as connection-log symptoms.
Twenty dashboard tests passed, including a regression proving a retained failed-stage
receipt and its 600-second duration remain unchanged while DNS diagnostics are surfaced.
The read-only observer was restarted as PID1222611 on the same localhost8765 address.
Fresh Playwright opened the actual failed 右 queue job and observed DNS lookup, websocket
connection and model-list refresh timeout diagnostics in its stage details, with no
horizontal overflow and no console errors. No model worker was restarted by this change.

The exact original supervisor has now exited. The handoff watcher launched replacement
PID1197547 with24 workers/agents, current pipeline code and disjoint tail exclusions.
The replacement was verified live by /proc/ps; the tail supervisor4173723 remains live.
