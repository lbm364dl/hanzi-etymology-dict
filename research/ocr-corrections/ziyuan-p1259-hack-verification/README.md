# Confirmed p1259 insertion repaired

While finding same-book font controls for the 学 OCR investigation, the consumer
text exposed `发生hack在` on PDF p1259 / printed p1244. The original crop shows
`发生在`. A separate genuine gpt-6-luna low occurrence review confirmed that
the four Latin letters were absent from the print. The coordinator also inspected
the actual target crop; no other transcription on this page is certified.

- Raw offsets: `[1294,1301)`, `发生hack在` → `发生在`.
- Actual reviewer thread: `01a0ff87-516c-7a60-9630-f1c90a8045eb`.
- Result hash: `525fb49b8d24ba712d95574c67ff5f3a60d8acca1a333c4d473f1c548a1bacb0`.
- Original OCR remains unchanged; its raw span and original evidence are retained.
- The actual producer `ocr-corrections.json` validates through `load_effective`;
  `producer-overlay.json` here is an exact reviewable copy.
- The coordinator rebuilt all 1435 processed consumer pages and checked the p1259
  record against the producer's effective text and evidence hash. See
  `consumer-validation.json`; it supersedes the earlier producer-only report's
  `consumer_corpus_rebuilt:false` observation without rewriting that observation.

The broader insertion class was already known from p277's earlier `heat` repair.
This is another independently verified occurrence, not a book-wide substitution
or whole-page approval. The correction is tracked under existing OCR umbrella #5;
no separate routine issue was created for this completed literal fix.

The changed p1259 effective evidence invalidated 半's old locator receipt. Its
fresh source check found an actual omitted semantic proposal, now being repaired
under #162. The cohort audit currently counts 17/300, rather than retaining a stale
18/300 completion claim. 学 remains unpublished during its separate repair.
