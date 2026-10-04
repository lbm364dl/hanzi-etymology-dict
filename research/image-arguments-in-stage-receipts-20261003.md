# Retain image argument provenance in new stage receipts

The attached 学 research run had a genuine result and hash-bound source-scan prompt, but stdout did not include the executed image arguments. The fixed runner's deterministic insertion and its regression were sufficient evidence of attachment delivery; no retrospective extra approval gate was required. To make future coordination straightforward, new Codex image-bearing runs now retain `image_argument_manifest` in their ordinary stage metadata, listing the actual inserted image paths and encoded file hashes.

This records delivery configuration, not a model's claim to have read the pixels. It does not capture custom command credentials, certify factual accuracy, or change previous receipts. Old results are not rerun merely to populate an optional new metadata field. The existing transport regression now checks this persistent receipt against the image arguments and hashes; all three source-scan tests pass.
