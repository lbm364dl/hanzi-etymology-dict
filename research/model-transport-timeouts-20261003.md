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
