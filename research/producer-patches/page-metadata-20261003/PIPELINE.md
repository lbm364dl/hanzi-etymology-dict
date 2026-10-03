# PDF-first scan digitisation pipeline

The primary output preserves each original page’s physical dimensions and layout. The original scan remains the visible background, with positioned searchable text and separately referenced source glyph assets. Reflowed HTML/PDF and Markdown are secondary reading exports; they do not define page geometry. Visible replacement typography remains a separately reviewed draft.

The existing `scripts/reconstruct_pilot.py` remains a one-page prose/layout experiment. Its manually chosen paragraph regions and reviewed overrides are not a general book pipeline. The reusable stages are now `scripts/page_pipeline.py` for mixed pages and `scripts/table_pipeline.py` for ruled tables containing historical drawings above printed captions. Neither reusable stage contains book names, selected-page coordinates, or transcription replacements.

## Reusable table stage

```bash
# Geometry and source assets only; no API calls
python3 scripts/table_pipeline.py --image scan.png --output result

# Read a PDF page with correct image polarity, then use Gemini for captions
python3 scripts/table_pipeline.py --pdf book.pdf --page 100 --output result --transcribe
```

The stage detects horizontal/vertical rules, checks their intersections, derives cells, and separates drawings from captions using whitespace and the width of the following ink band. It retains individual drawing crops, original caption crops, whole-cell source crops, and page coordinates. The same stage runs on every input without supplied cell counts or page-specific boxes.

Gemini transcribes labelled caption regions into text and uncertain image spans. Exact cell IDs, response completion, span kinds, and bounding boxes are validated before successful responses enter the content-addressed cache. Invalid cached responses are quarantined. Rare Unicode characters trigger a focused second recognition pass that requests preservation as source images. This heuristic catches some overconfident guesses, not every misreading; all cells still require independent review.

Outputs include `manifest.json`, `table.html`, `review.html`, `overlay.png`, source-image assets, raw cached responses, and structured captions. Geometry-only output displays original source captions instead of text placeholders. Rebuilding replaces generated assets and clears old manifests before work, while preserving cached responses and separate review records.

## Agent review stage

Use Codex subagents with **gpt-6-luna, low reasoning**, as requested. This is orchestrated by Codex's collaboration tools; the Python script does not call OpenAI or require a second API key.

1. Inspect `review.html`, the source image, and the manifest. Divide larger outputs into small cell batches. Each occupied cell needs checks for complete strokes, caption text excluded from drawing crops, every caption character/reference accounted for, correct reading order, and readable rendering. Review empty cells and grid structure too.
2. Review every generated caption, not just model-declared uncertainties. Give flagged rare forms or questionable boundaries another independent pass. If they cannot be resolved, retain source-image fallbacks and leave the output pending.
3. Correct general detector/prompt/validation behavior when a failure recurs. Add a regression case that captures the failure class. Page-specific reviewer coordinates may be recorded as evidence but must not become detector rules.
4. Record decisions against the exact manifest `evidence_sha256`. Review results belong in `review.json`, separate from cached recognition data. Include `decision: "pass"`, `grid_reviewed: true`, and `reviewed_cells` containing every cell ID only after those checks pass. Pipeline reruns recognize a pass only if the evidence hash and complete cell set match. Changed source/crops/captions invalidate the pass. Rendered PDF review is recorded separately because layout can change independently.

Until an exact review passes, `status` remains `needs_review` and cell states remain `pending`. HTML/PDF previews are review artifacts, not automatically approved publication outputs.

## Validation and current limits

```bash
python3 -m unittest discover -s tests -v
```

Tests cover grid detection across resolutions, two-line captions, gaps within drawings, blank cells/pages, unresolved splits, malformed model output, retained source fallbacks, and stale review rejection. Real samples include PDF pages 99, 100 and 101 of 說文新證; only page 100 has caption transcription and a rebuilt PDF so far. Geometry-only neighbour samples live in `pipeline-validation/`.

The detector currently handles relatively upright, dark, continuous ruled rectangular grids. It does not establish reliable support for borderless tables, merged cells, skewed/faint/broken rules, or arbitrary diagrams. Narrow captions and broad stacked drawings can also make separation ambiguous. Agent review remains mandatory; detecting a grid is not proof that all tables on a page were found.

Five cross-book mixed-page samples now live in `cross-book-pilot/`; see its `REPORT.md` and review gallery. Whole-book digitisation is not implemented or validated yet.

## Reading semantics and Unicode

Treat a rare printed character separately from a historical drawing. Verified character identities belong in a separate `character-identifications.json` registry, indexed by source-crop SHA256, with Unicode and evidence. An unverified model guess must not enter that registry. A verified printed character becomes Unicode in the accessible reading, while its exact source crop remains available. Historical drawings retain their visual form and source references; a modern headword does not replace their shape.

`python3 scripts/semantic_export.py reconstructed.html` traverses the linked manifests, exports ordered `reading.md` with image IDs and `reading.json` with context and source evidence, and creates `accessible.html` with meaningful image descriptions. Render this HTML with Playwright `tagged=True`. Then run the exporter with `--attach-to-pdf output.pdf` to embed the reading exports and original crops. This supports readers of PDF figure tags and attachments; plain text extractors may still omit images, so LLM ingestion should use the reading export and crop assets directly when those features are unsupported.

## Mixed-page stage and cross-book findings

```bash
python3 scripts/page_pipeline.py --pdf book.pdf --page 100 --output result
# After independently reviewing the exact evidence, ingest review.json without new API calls:
python3 scripts/page_pipeline.py --output result --consume-review
# Render accessible.html as a tagged PDF, then embed exports and source crops:
node scripts/render_pages.js result
python3 scripts/semantic_export.py result/rebuilt.html --attach-to-pdf result/rebuilt.pdf
```

The default command also runs spatial text recognition and renders `layout-preserved.pdf` and `layout-overlay-draft.pdf`. Use `--recognize-only` to stop after logical extraction.

The recognition command reads the existing private Gemini key from `~/.config/hanzi-etymology-books/gemini-api-key`. Rendering requires Playwright and Chrome; set `PLAYWRIGHT_MODULE` if using an existing installation outside this project. PDF page numbers are one-based. Existing PDF text is saved as reference, not silently trusted.

Layout recognition runs first, followed by per-region transcription and a separate context-based image-localization pass. Overlapping layout boxes trigger one layout retry. Horizontal column order is inferred from paragraph geometry, while traditional vertical catalogs use right-to-left column order. Mixed-direction cases remain review tasks. Historical image spans are never erased merely because another model proposes a Unicode equivalent.

For inverse rubbings, an independent connected-component inventory checks black panels against recognized specimen counts. Matching catalogs preserve complete original panels and polarity instead of cropping white strokes alone. Mismatched counts and uncovered dark graphics remain flagged. Other forms use contextual localization and connected-component crop refinement. Reference labels and diagram arrows remain selectable text.

These stages do not yet automatically dispatch detected ruled tables into the dedicated table stage; the modules are independently callable. The mixed-page reflow preserves span order but does not reproduce every two-dimensional diagram relationship. Retain the original scan for scholarly use.

Each page emits `review-bundle.json`, paired source/crop contact sheets, block crops, provenance hashes and a review queue. Delegate small bundles to **gpt-6-luna with low reasoning**, then use a separate source-based pass for disputed findings. Review every block and asset, including items Gemini did not flag. Judge ordinary printed characters separately from historical forms; a printed 丁 can become text after verification, while a two-stroke historical form stays an image even if its modern equivalent resembles 二. A reviewer's character correction is a hypothesis until checked against the scan: the dictionary sample demonstrated that a reviewer can wrongly suggest 行 for a valid 亓.

Review JSON must contain `decision`, matching `evidence_sha256`, `page_coverage_reviewed: true`, and complete `reviewed_blocks` and `reviewed_assets` inventories. Use `findings` with block/asset IDs, failure class, severity and source evidence. A pass with unresolved `needs_changes`, `error`, or `critical` findings is rejected. Changed evidence invalidates approval. Consume reviews separately so approval does not itself trigger a new recognition/localization cycle. Prior source-bound findings may inform later localization; cached recognition responses remain separate from review decisions.

Recurring limitations discovered in these samples:

- A reference numeral can lie inside the overall rectangle of a historical form. Tightening the box alone cannot reliably remove it. The 字源 sample retains four such crops, explicitly flagged; future work needs source-grounded component segmentation and independent review, preserving the original crop and any mask provenance.
- An indented first line can make a model's paragraph box too narrow for subsequent lines, omitting characters at the left edge. Check paragraph coverage against the full page, not only the supplied region. The 字源 sample has an omitted 啻; no page-specific replacement was inserted.
- Confident OCR can still output Latin noise inside Chinese text (老dq instead of 老的 in the dictionary sample). Region and character-level proofreading remains necessary. No automatic publication follows a Gemini response.
- A crop/layout draft pass is not certification of rare names, citations, punctuation or character-level accuracy. Keep model uncertainties in the reading export even after draft review.

Reading JSON now carries source book/page, source dimensions and coordinate convention, evidence hash, review status/findings, recognition uncertainties, and ordered image references. Tagged PDF figures expose descriptions and the PDF embeds these exports plus crops. Ordinary plain-text PDF extraction may omit figures; feed LLMs `reading.md`, `reading.json`, and the referenced crops for explicit text/image semantics.

## Original-layout PDF output

```bash
# Add spatial recognition to an existing logical extraction:
python3 scripts/layout_pdf.py --output result --pdf book.pdf --page 100
# Rerender from spatial.json without new API requests:
python3 scripts/layout_pdf.py --output result --pdf book.pdf --page 100 --render-only
```

`spatial.json` stores individual physical text-run boxes in source pixels, including actual line/column breaks, independently of the logical paragraph/span representation. It has its own evidence hash and remains `needs_spatial_review`; a logical text or crop review does not approve typography or placement. Text differences between the two recognition stages, empty text regions, overlaps with source-image assets, extreme fitting, and mixed vertical orientations are flagged for source review.

`layout-preserved.pdf` is the primary faithful edition: original-size page, visible scan, positioned invisible/selectable Unicode text, and referenced original glyph crops. Its optional glyph-crop layer is off by default to avoid resampling the scan again. Turning that layer on shows source crops at their original positions. The scan alone already displays every historical form, rule, arrow, original font and illustration. This is a searchable facsimile, not a claim that every printed letter has been visibly replaced.

`layout-overlay-draft.pdf` adds visible replacement text and source glyph crops over the scan at their original coordinates. Its text layer also controls backing rectangles, so hiding that layer restores the scan. Unsafe text/image overlaps, extreme width fitting and mixed vertical runs retain the scan rather than receiving visible replacements. The renderer fits horizontal text to physical runs and places upright vertical Chinese characters individually; mixed rotated Latin/numeric runs and fine baseline/superscript typography still need a richer character-position contract and review. This output is a draft, not an approved clean edition.

Both outputs validate the source PNG against the manifest and the supplied original PDF page against that scan, retain physical page dimensions, provide separate scan/text/glyph PDF layers, and embed reading exports, spatial data, manifest, review and source crops. Positioned text is tagged as paragraphs. Historical glyph figures carry descriptions and explicit `[glyph:ID]` text alternatives; verified printed-image identities use their reviewed Unicode. A PDF reader's support for tags, optional content and attachments varies, so the explicit reading export remains useful for LLM ingestion.

Do not erase original text ink or switch to a clean visible edition before spatial review passes. Future ink masks must retain original source data and avoid deleting nearby ancient strokes, grid rules or annotations. Original-layout coverage and logical reading accuracy are separate acceptance checks.

## Clean layout, text selection, and copying forms

The same renderer now also emits `layout-clean-draft.pdf`: a white page at the original physical size, native modern text fitted to original text-run locations, and historical raster glyphs at their exact source rectangles. Clean text uses natural font proportions rather than stretching letters. Small labels may use a readable minimum where width allows. Long source rules become vector lines. Source-reviewed ancillary illustrations in `asset-identifications.json` are traced as vector shapes; decorative marks are omitted. Verified ordinary-character image fallbacks become native Unicode instead of visible bitmap characters. Original crops are still retained as PDF attachments.

The clean page has no full-page scan underneath it. Modern text is rendered where geometry is safe; unresolved material text collisions use bounded source-backed fallbacks with searchable native text. The clean file stays a draft until geometry, text coverage and diagram graphics are reviewed. Mixed vertical rotations, reference-number contamination and unrecognized diagram connectors remain known limits. No missing text is silently certified as complete.

PDF text extraction and reference selection geometry are audited against the produced PDF, not inferred from successful drawing calls. Mouse selection and clipboard behavior require a separate viewer check. `selection-audit.json` records the output hashes, renderer hash and actual extracted-text checks for every recognized run. Exact native font ToUnicode maps protect against cmap aliases (for example a circled digit mapping to a visually similar dingbat). Full-run `ActualText` is omitted because it blocked Chrome selection in browser isolation tests. This is evidence of recognized-text extraction, not proof that all visible source text was recognized. The footnote regression arose because image insertion can prepend/reuse balancing content streams: indexing streams by count wrongly attached the first glyph’s semantics to the preceding footnote. Tag only new non-wrapper stream xrefs, and verify figure streams contain no text operators; vector illustrations do not require an image `Do` operator.

Historical forms are embedded image objects with figure descriptions/ID text alternatives and original PNG attachments. Plain text copy does not copy their pixels as Unicode. A reader may support copying/exporting images; `glyphs.html` also exposes each original PNG for browser copy/download. Some PDF readers ignore image text alternatives, so preserve the attached reading/source data for reliable multimodal ingestion.

Image copying now has an explicit PDF text path: each visible/source glyph has an invisible `[glyph:ID]` text object fitted to its image rectangle. Figure descriptions remain attached to the image; the reference text is a separate tagged span. This supplies real selection geometry rather than relying on an image-only `ActualText`, which some extractors position at the last text paragraph. Selecting/copying the form as text yields its ID, not a guessed Unicode character or its pixels. Source-reviewed illustrations use `[image:ID]`, and verified printed-character crops use their actual Unicode. The regression test checks the marker's selection rectangle matches the image rectangle and that the following footnote remains distinct.

## Inline composition and interactive review

Review pages embed actual PDFs and provide direct open/download links. Raster previews are inspection artifacts, not selectable document views. Extractor checks and browser interaction checks are separate: an extraction pass alone must never be reported as proof of successful mouse selection and clipboard copying.

`inline_layout.py` composes horizontal text around fixed source image atoms. Neighboring fragments share font size and baseline, and their adjoining edges are anchored to the image with proportional padding. A coarse spatial transcription crossing an image may be split only when the logical text-image-text spans supply matching surrounding anchors; any excluded unverified transcription is recorded. No book-specific coordinates or character replacements are used. Original spatial recognition remains unchanged; `rendering-plan.json` records composed runs, decisions and the compositor source hash.

Native text and image reference spans are emitted in spatial reading order within each logical block, so a copied historical-form reference can occur between its surrounding words. Tests cover evidence-bound splitting, absence of deletion without anchors, fixed image rectangles, order and multiple source scales. Review must still check unusual orientations and line associations; these rules do not approve pending extraction or spatial findings.


Browser isolation with minimal/native PDF controls showed that full-run `ActualText` prevented Chrome selection in these outputs. Removing only that property restored selection while retaining structure tags and PDF layers. The renderer now writes exact source-used Unicode into each native font's ToUnicode map, preserves figure descriptions and explicit native glyph-ID spans, and refuses ambiguous same-glyph/different-character encodings. Extraction audits reopen the saved PDF to avoid stale in-memory font maps. Chrome copy tests and independent Poppler footnote checks are required evidence for this path; full-run ActualText must not be reintroduced without passing browser selection tests.

## Physical-line collisions and source-bound repair

Spatial validation compares horizontal text runs with each other, including runs from neighboring blocks. Material overlap and near-duplicate text are review findings; similarity alone never authorizes deleting a line. `spatial_repair.py` groups affected text-only blocks, measures physical ink bands with `line_geometry.py`, and asks Gemini for one transcription per labelled source-line crop. Coordinates come from the scan bands, not another guessed paragraph box. Uncertain responses, unsupported font characters, clipped boundary rows, and regions containing glyph/diagram assets remain pending instead of being automatically committed.

Accepted repairs update the logical text, spatial runs and reading exports together; original evidence is archived, hashes change, and previous approvals are invalidated. `locate()` invokes the shared repair stage. Render-only operations make no recognition calls. Remaining material text collisions are rendered with bounded source-scan fallbacks and invisible native text, rather than overlapping modern text. `selection-audit.json` lists collision pairs and fallback rectangles. Consequently a clean draft can contain source-backed ordinary text pending repair; it must not be described as a completed all-native-text edition.

## First OCR edition for dictionary research

Use the lightweight `research_ocr.py` stage: one cached Gemini call per page, original scan, transcription, historical-form references/descriptions and uncertainties. It does not request coordinates, individual crop extraction, clean typography, or page-by-page agent approval. Mark it unreviewed and inspect source passages that research actually uses.

```bash
python3 scripts/research_ocr.py --pdf book.pdf --page 100 --output research-ocr/book-page-100
python3 scripts/source_corpus.py build --pages-root research-ocr --output source-corpus/research-pages.jsonl
python3 scripts/source_corpus.py search --corpus source-corpus/research-pages.jsonl --query 世父 --limit 3
```

The richer `page_pipeline.py --recognize-only` output also feeds the corpus when available. Search/indexing remains independent of spatial recognition and clean PDF rendering. The first edition is page-indexed JSON/Markdown alongside scans; no new PDF text layer is required for dictionary agents to use it.

The version-2 search contract returns a JSON envelope containing compact results and explicit coverage, even on no hit. Results carry original excerpts, scan paths/hashes, PDF page indices and independent review dimensions. Include only glyph references in the returned passage. Full metadata/assets are available through `inspect --page-id` or `search --details`. Book IDs derive from actual PDF content hashes, not filenames; verified bibliography is optional metadata, with unknown fields null. Printed page numbers remain unknown unless explicitly supplied.

Headword/variant ranking, entry continuation links and detailed manual metadata are deferred until retrieval needs them. A mention in a quote is not promoted to a verified headword. No clean-layout approval is required for provisional search, and no OCR passage is automatically published evidence. Follow the dictionary project's own citation contract when using inspected sources.

See `source-corpus/README.md` and `source-corpus/HANDOFF-RESPONSE.md`. Current corpora contain five earlier rich samples and a separate 12-page lightweight pilot, not full books. Paths point to workspace artifacts, not a portable copied archive. The dictionary repository remains unchanged.

### Reuse research OCR in the detailed edition

`page_pipeline.py --reuse-ocr OCR_DIRECTORY` takes the persisted first-pass OCR as its literal text source. The upgrade stage requests only layout/glyph geometry and assignment of supplied text/glyph IDs; schema validation rejects dropped/unknown IDs and text replacement. Preserve the original OCR cache key/evidence/usage separately from the new-stage request accounting. It does not request another full transcription. Physical alignment and targeted source corrections are still later work and may require new paid requests; local response caching only avoids repeating an identical request. Reuse reduces duplicated transcription, not all additional model cost.

### Bounded research-OCR smoke runs

Use `research_batch.py --pages COMMA_SEPARATED_PDF_PAGES --workers 3` to sample across a book plus adjacent pages for boundary behavior. The runner records individual failures, cache hits, token usage and latency without printing credentials. Persist successes even if another page fails; reruns reuse the existing page caches. Build the corpus from a single chosen edition root to avoid duplicate identities. Record estimated cost separately from billed charges and distinguish new requests from reused usage. Use representative source-based agent review; model-declared uncertainties alone do not establish text coverage or character accuracy. Page-end fragments must remain literal and uncertain rather than being completed from model knowledge.

Representative smoke review revealed that ordinary printed component names inside explanatory prose can be wrongly emitted as historical-form references, even when surrounding OCR is strong. The research prompt explicitly separates printed Unicode from pictured script forms and asks for distinct IDs per occurrence. It also emphasizes tone marks and visually similar characters. Do not fix these by book-specific substitutions. Keep raw OCR intact, store source/evidence-bound `research-review.json` findings, and expose `needs_correction` in the corpus when reviewed errors remain. An inspected subset does not certify the entire page or sample. A prompt revision changes the request cache key; existing responses remain durable evidence and must not be described as outputs of the revised prompt.

### Source-verified correction layer

Printed page labels use a separate `page-metadata.json` overlay. It binds the original
source pixels, raw OCR evidence, PDF page identity and label to a completed independent
Luna-low source-resolution observation and its exact result/metadata/binding paths and
hash. The shared loader validates those receipts and observed label, exposes
`printed_page` and `metadata_provenance`, and preserves raw OCR/text evidence. Corpus
indexing consumes this effective metadata rather than hardcoding unknown page labels.
Roman labels and integer page numbers are supported; this never infers a fixed
PDF-to-print offset or approves a whole page. Existing unknown labels stay unknown.


Fix verified OCR errors before handing text to downstream consumers. Preserve raw `ocr.json` and API cache evidence, but use a shared effective-text loader in corpus indexing and the detailed-edition upgrade. Page-local `ocr-corrections.json` stores exact source-bound character-range edits, before/after text, verification reasons and parent/source hashes. The loader rejects stale evidence, mismatched anchors, overlapping edits and unbound glyph references. Export corrected JSON/Markdown separately. Keep genuine historical IDs stable; remove a misclassified printed-character ID only after every occurrence has been replaced by source-verified Unicode. Store resolved review findings alongside correction provenance without promoting partially reviewed pages to full approval. Reviewer corrections are hypotheses until independently checked against the scan; enlarge ambiguous source regions and compare similar printed marks before changing them. Do not rewrite literal book text to conventional spellings or pronunciations without source support.
Dictionary-consumer discoveries feed this same layer: record the exact page and suspect span, inspect its original scan, apply only verified page-local edits, then regenerate the effective exports and consumer JSONL corpus. A fluent OCR passage can still substitute a component name or invent a familiar Unicode identity; inspect each occurrence in context, and use an occurrence-specific `unidentified_printed_character` reference when the printed identity remains unresolved. Keep the raw response intact and the page unreviewed unless a full-page review separately approves it.

### Rare printed identity and model comparisons

The consumer found repeated rare-headword substitutions that persisted even after the shared prompt revision. Headword/component identities must come from visible strokes, not familiar lookalikes or inferred pronunciation. Research glyph metadata now supports `historical_form` and `unidentified_printed_character`; legacy missing kinds default to historical forms. When the exact Unicode of printed text remains unresolved, preserve occurrence-specific references and explicit uncertainty rather than a confident false name. Correction overlays can add printed-character references and repair source-bound glyph descriptions; preserve the distinction through corpus search and detailed-edition reuse.

Use `research_batch.py --model MODEL_ID` for matched comparisons with identical source pages, render width, prompt/schema and thinking. Model selection is a per-request argument, not mutation of a process global, and request caches include model identity. Keep experimental outputs separate from the consumer corpus. Count rejected response token usage in cost measurements; schema-valid completion does not establish accuracy. Compare source-grounded identity, omitted text, citations and glyph handling, including unseen contrasting pages. A few spot checks cannot establish whole-book character-error rates. The six-page Flash3.8/Flash-Lite3.5/Flash-Lite3.1 comparison is measured evidence, not a whole-book approval or an automatic default-model switch.

### Direct Luna VLM comparison

A direct-agent OCR comparison must be blind to prior OCR, corrections and review conclusions. Give agents only source scans and the same extraction prompt/schema; allow source zoom/crops and record that extra interaction. Keep transcriber and evaluator roles separate and bind evaluation to exact source/response hashes. This compares an interactive Codex agent workflow with single-call Gemini OCR, not identical inference budgets. Do not infer API dollars from Codex collaboration or label its usage free when billing/token information is unavailable.

`import_agent_ocr.py` validates the transcription and original-PDF pixels, then saves corpus-compatible OCR/reading evidence without an API call. Imported agent text can use the same correction layer and later geometry upgrade, but experimental direct-agent outputs are not automatically substituted into the consumer corpus. Record unavailable usage explicitly instead of fabricating tokens/cost or counting it as Gemini consumption. Preserve raw blind output for comparison even when source review finds errors.

The direct-agent experiment found omitted source entries and inserted material from another page when one transcriber handled several pages. A fresh, blind single-page control recovered the missing entry and avoided those unrelated entries, but still made literal transcription errors. Prefer fresh page-isolated contexts for direct OCR comparisons and keep any grouped run as a distinct protocol. Validate source coverage and article/page association independently of JSON/glyph-reference validity; passing a schema does not show that the page was read completely or that all emitted text belongs to it. One isolation control cannot establish a general accuracy rate.

### Resumable full-book first edition

`research_book.py` runs bounded `research_batch` chunks, skips source/evidence-validated completed pages, preserves imported smoke corrections, and atomically publishes a separate incremental JSONL corpus through `fast_record`. Its exclusive edition lock prevents concurrent jobs; identity checks reject changed source PDFs/models. Seed scans are checked against rerendered original PDF pixels. Preserved older prompt generations are reused as durable OCR evidence, not claimed to be current-prompt responses.

Use `run-status.json` for full-book success/coverage; a batch summary's completion only means its tasks returned. Persist missing pages and failures, stop on authentication errors or pervasive quota errors, check free disk space and an estimated-usage ceiling between chunks, and cap failed-page retries. Preserve rejected responses before retry and include returned invalid-response usage in estimates. Budget estimates are not billed charges and can miss interrupted requests. Publish all verified corrections through the shared effective loader; retain unreviewed status for everything without full-page source approval. Blank/no-readable-text failures are explicit coverage gaps pending source verification, never fabricated text or automatic approvals.
After a blank response, `classify_blank_research_page.py` may accept an empty scan only when the saved Gemini response has no text or glyphs, the saved image exactly matches the original PDF pixels, and the source is nearly white. It binds the classification to the original response and source hashes, retains both, and gives the page an explicit `source_verified_blank_scan` status in the corpus.
A response with an extra `glyph:` prefix on one or more glyph object IDs can be recovered by `recover_prefixed_glyph_ids.py` only if stripping those prefixes makes the unique IDs match every text reference. The original rejected response and exact source pixels remain hash-bound evidence. Other glyph-reference mismatches require review rather than guessed repair.

### Quota-aware full-book resume

A wave of HTTP 429 responses is a service quota condition, not a failed transcription for each selected page. The whole-book runner now preserves completed pages, excludes 429s from the per-page attempt cap, and enters `quota_wait`. It waits with bounded exponential backoff, probes only one page with one worker, and resumes ordinary bounded batches after a successful probe. This avoids exhausting the retry budget or sending another 24-page request wave into a still-blocked quota. Numeric HTTP status and safe quota reason/ID fields are recorded without response bodies or credentials. Authentication/client 400/401/403/404 errors still stop the run. The status file distinguishes quota waiting from completed-with-failures; blank-page and invalid-schema failures remain separate review work.
When resuming a saved quota wait, the runner subtracts time already elapsed since the last checkpoint, so an expired wait can probe immediately.
