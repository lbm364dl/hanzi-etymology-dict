# Scan hash failure diagnostics

During the 学 source repair, two crop attachments carried placeholder strings
in `source_pixel_sha256`. The existing decoded-RGB validation correctly rejected
them before any factual review ran. This was a coordinator provenance error,
not an OCR verdict or a failed factual review. The genuine preceding author
output remains retained; it does not acquire approval from the failed invocation.

The validator now reports the failing path, PDF page, expected hash and actual
decoded RGB hash. This applies to every book and character and makes failures
with multiple attachments directly actionable. It does not relax verification,
infer crop coverage, or establish that an agent inspected the image. Crop hashes
describe the crop's pixels; parent-page hashes belong in separate provenance.

The existing pixel-hash test now verifies these diagnostics while preserving
its checks that re-encoding a PNG leaves the RGB hash unchanged and that changing
a pixel is rejected. That focused test passed. No article facts, prose or
publication receipts changed, and 学 still awaits a valid authored candidate and
fresh independent reviews.
