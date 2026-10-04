# Source checks after the bounded review smoke

The full HSK1 batch remains paused. This follow-up completes source checks for the two smoke candidates; it does not restart the batch.

## 名

Fresh source coverage passed against the exact revised article and dossier. The ordinary source-enrichment publisher accepted the independent factual/readability receipts and source coverage and published article `008a470f291dcea381b58e2f073bb65dc7130943a7fc3c3999847a19e517164b`, dossier `09289ec178d205f1e0e3b57c541a2c1f32256bd0363030d31b41e2f6e813e3fa`. Actual job receipts are in `runs/source-gate-followup-20261004/ziyuan-2012/540D/`.

## 今: unresolved literal check

Three genuine scan verification attempts are retained in `runs/source-gate-followup-20261004/jin-ocr`, `jin-ocr-native`, and `jin-ocr-controls`. None establishes an OCR correction. The first reading contradicted its own location explanation; subsequent readings remained unresolved. The last claimed the target was clipped, although the retained complete paragraph crop contains the target well inside its bounds. These receipts must not authorize a producer overlay repair or publication.

The raw OCR at PDF page 476, offset 814–816 reads 此吋; proposed replacement 此时 remains unverified. No book OCR was changed.

This exposes a general visual-verification failure class: an agent can invent crop geometry or a control occurrence. Crop provenance alone cannot certify its interpretation. Future harness work should make target/control coordinates explicit and require observations tied to those regions; an unresolved result must remain pending rather than trigger repeated blind retries. This note records the finding; that coordinate contract is not yet implemented or tested.

## Timing interpretation

The successful 今 editorial smoke used nine calls and approximately 1 minute 56 seconds; 名 required sixteen calls and approximately 4 minutes 51 seconds including adjudication. These reused research and repaired candidates, and exclude this later source follow-up. They demonstrate reduced editorial loops, not end-to-end throughput for new characters. A small contrasting cohort at two model slots is needed before estimating batch duration.
