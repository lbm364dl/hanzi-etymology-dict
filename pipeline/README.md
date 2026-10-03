# Editorial pipeline

Entries are researched beyond the repository, written as neutral explanations, then independently reviewed for factual support and readability. The published article explains formation, meaningful component roles and graphic changes, followed by history and uncertainties. Source names belong in references; every explanatory section cites evidence.

## Enriching approved entries with digitised books

`pipeline.source_enrichment` processes existing approved entries for a newly available source;
ordinary `pipeline.batch` readiness is not proof that an entry has consulted that source.
Register digitised books in `research/digitised-sources.json`. Each registry record identifies
the exact edition, book hash and consumer corpus; adding later books does not require changing
character prompts or adding character-specific rules. Only 字源 is currently registered.

`status`, `prepare` and `run` reuse verified completions across `runs/`,
`content/source_coverage/` and the requested output folder. A fresh batch folder
does not restart entries already completed elsewhere. Reuse requires the current
exact source, locator, audit, article, dossier and review/publication gates; stale
jobs, legacy approvals and another book do not count. Returned published rows
identify the actual verified job folder. The limit applies to remaining work.

```bash
python3 -m pipeline.source_enrichment status --registry research/digitised-sources.json --source ziyuan-2012 --cohort content/cohorts/hsk3-2021-level-1.json
python3 -m pipeline.source_enrichment run --registry research/digitised-sources.json --source ziyuan-2012 --cohort content/cohorts/hsk3-2021-level-1.json --limit 3
```

Audit the entire cohort across all source batches and source-coverage jobs with
the project environment (including the registered producer's verification dependencies):

```bash
python3 -m pipeline.source_progress --registry research/digitised-sources.json --source ziyuan-2012 --cohort content/cohorts/hsk3-2021-level-1.json --output research/hsk1-source-completion.json
```

The default roots are `runs/` and `content/source_coverage/`; repeat `--job-root`
to audit other locations. The report uses the current exact source/publication
gate for every candidate and counts each cohort character once. Legacy approvals,
saved `published` labels, jobs for another book and archived input copies do not
establish source completion. A later registered book gets its own audit by changing
`--source`, with no character-specific rule changes.

All agents introduced for this workflow, including findings triage, use `gpt-6-luna` with
low reasoning. Jobs retain source and published-input snapshots, bounded locator leads,
scan attachments, research, authored revisions and exact independent reviews. Header-like
OCR lines, parenthetical counterparts and continuation pages are locator hypotheses, not
verified headwords. Missing source access remains an explicit gap; external authoritative
references can still improve an entry. Agents use reasoning to flag suspicious OCR, then
verify replacements against scans. Corrections feed the book repository's source-bound
layer and its rebuilt consumer corpus; raw OCR is preserved.

`pipeline.ocr_verification.verify` checks proposed literal replacements through a separate
Luna low scan reviewer. Each proposal carries a stable occurrence ID, exact raw-text offsets,
an anchor and surrounding context. Incomplete coverage, duplicate IDs, wrong raw text and
contradictory verdicts are rejected. Unresolved identities retain no guessed Unicode replacement.
The output is an occurrence check, not approval of a whole page; the coordinator still validates
source-bound producer patches and their rebuilt consumer records.

`pipeline.source_enrichment.resolve_source_findings(job, runner)` offers a separate scan-backed
review of an exact already-approved candidate. It may release a retained unresolved identity
only when that identity is not used to establish any article claim. The findings remain recorded,
and the resolution is bound to exact article, dossier and finding hashes. A separate scan
check can also reject a false replacement proposal when the current corpus already matches
the pixels; its exact completed Luna low result and metadata are required. Targeted original
pixel crops may accompany the source scans. Confirmed OCR errors
and material unresolved claims remain blocked for source repair or new research; this check
does not replace factual/readability reviews.

Applied literal OCR repairs can be checked through `resolve_source_findings(...,
repair_checks=[...])`. Each check identifies the retained finding, producer page directory,
raw start/end offsets, and original before/after literals. The actual producer correction
validator and the current consumer page must agree. A separate original-scan review then
observes the repaired literal; changed overlay or consumer evidence invalidates resolution.
This preserves a real corrected finding rather than reclassifying it as a false proposal.
Registered producers using this adapter provide `scripts/research_corrections.py` and its
source-bound `load_effective` contract; other corpus formats need a corresponding adapter.

Source jobs acquire an OS coordinator lock before writing their stage files; agent subprocesses
inherit that lock so an orphaned live agent still prevents duplicate writes after a coordinator
exits. A second harness reports `already_running` without replacing the first job's status.
For sustained runs, use a persistent process with captured logs. Inspect its actual process ID
and child processes before resuming: a saved `running` status does not prove liveness, and a
terminated command wrapper can leave its agent child alive. Retain previous stage artifacts
when recovering interrupted work.

If completed research returns page-specific book records that an otherwise approved
article does not cite, the harness runs one bounded editing pass over that current
dossier in `citation-integration/`. The editor chooses supported claims and attaches
their evidence IDs; fresh independent factual and readability reviews follow.
The previous exact pair and receipts remain in `before-citation-integration/`.
This avoids restarting research merely to adopt a newly generated evidence ID.
It neither inserts citations automatically nor releases OCR/source blocks.

After a source repair, `run --continue-from /path/to/previous/character/job` can start a
fresh single-character job from the previous unfinished draft. The previous coordinator
and agents must have released their OS lock, and its canonical article/dossier baseline
must still match. The harness validates and saves the draft with exact provenance hashes;
it never copies review approvals. Current-source research and fresh independent reviews
remain required. Keep the previous job directory as the record of earlier failures.
An approved source job whose locator inputs changed is held as `needs_source_refresh`;
its previous status is preserved in `source-refresh-required.json`. Such a job can
also supply a continuation draft, requiring fresh research and reviews. Unchanged
approved jobs cannot be continued through this route.
For old jobs affected by the editorial input collision, use
`pipeline.source_enrichment.recover_frozen_inputs(job)` only after their
coordinator and agent locks are released. It archives the collided files and
restores the canonical baseline only when both original hashes still match;
it never changes source identity, authored drafts or approvals. Publication
also verifies the frozen snapshots and rejects a collision before writing.

Use `--research-context path/to/context.json` to hand new source leads and findings to
the actual research agent. The JSON object is frozen in the job and passed as research
tasks; it does not create verified dossier evidence or approvals. The researcher must
consult those sources directly, check identity/scope and cite useful claims before
authorship. Repeating a lead in a coordinating chat does not put it in a CLI research
packet. Changed context requires a fresh source job. For an example, see
`research/source-followups/ai-current-structure.json`.

`pipeline.source_adoption.adopt` can register book research already used by an approved
article. It preserves the article, dossier and original factual/readability receipts, then
requires a separate Luna low check against the original scans. Merely having book evidence
in a dossier is insufficient: the article must actually cite page-specific book evidence.
The saved coverage result is bound to the exact article and dossier hashes and rechecked
when calculating source completion. This avoids unnecessary rewriting while retaining a
reviewable source check; entries without used book evidence still require enrichment.

## GitHub findings

Track material errors, mistakes, improvements and clarifications in GitHub issues. The current
work is [HSK1 book enrichment](https://github.com/lbm364dl/hanzi-etymology-dict/issues/1);
`research/source-enrichment-issues.json` retains issue identities. An issue identifies the
affected character or source page, actual evidence, and the check needed to verify a fix.
Keep suspected OCR or scholarly disagreements explicitly uncertain. Rejected reviewer
proposals are not established errors. Link repeated manifestations to the existing issue.

`pipeline.issues.triage_job` invokes a separate Luna low agent over saved verified findings,
research gaps and validation failures; it saves proposed issue records without inventing
approvals. `pipeline.issues` synchronizes findings using stable markers, so reruns reuse
existing issues and preserve human discussion. It never closes issues automatically.
Registered sources can set `issue_parent_number`, `issue_milestone` and `issue_labels`;
new findings become native subissues with kind labels and the configured milestone.
Current job findings reopen a matching closed issue: a newly failed check must remain
visible as active work. Historical manifest synchronization preserves closure. Neither
path closes issues automatically or treats a new finding as proof that prior approvals
were fabricated or invalid.
GitHub workflow settings are kept separate from book identity, so relabeling work does not
invalidate completed research. Edition or corpus identity changes still require new jobs.

```bash
python3 -m pipeline.issues research/source-enrichment-findings.json --repo lbm364dl/hanzi-etymology-dict --receipts research/source-enrichment-issues.json
```

Close an issue only after its required checks are demonstrated and the fixing artifacts are
reviewable. Local repairs should be recorded as local progress until their published code or
content is linked. Source OCR corrections and character publication have separate verification
requirements even when tracked by the same issue.

Install the harness dependencies with `python3 -m pip install -r pipeline/requirements.txt` (or use your existing project environment). Run commands from the repository root.

## Checked-in pilot

The pilot entries are written and independently reviewed by interactive agents using the same publication gate. To verify their saved reviews and rebuild the website:

```bash
python3 -m pipeline.pilot check
python3 -m pipeline.pilot publish
python3 build_site.py
python3 -m http.server 8000 --directory docs
```

When the upstream `sources/` files and full `output/hanzi_etymology.jsonl` are absent but
`docs/data.json.gz` already contains the complete compiled legacy records, refresh only the
approved Chinese article overlays with `python3 build_site.py --refresh-articles`. This
validates each published article and dossier, preserves the legacy fields and all existing
character records, and refuses missing or stale article records. Then regenerate the
editorial graph and run the cohort audit:

```bash
python3 -m pipeline.graph --entries content/entries --output output/editorial-graph.json
python3 -m pipeline.audit_cohort
```

Open `http://localhost:8000` to browse the pilot. `publish` writes local artifacts; it does not deploy the site. See `content/README.md` for the evidence limitations and source attribution.

After publishing and rebuilding, run `python3 -m pipeline.audit_cohort` to check every HSK 1 entry against its current dossier and site article. The report at `output/hsk1-integrity-audit.json` checks independent Luna low review receipts, external research records, meaning senses, original and site glyph hashes, and graph relationships, citations and review hashes. It exits nonzero for missing or stale content. This is an integrity snapshot; it does not replace factual, reader or visual review, and running jobs can make the built site stale again.

## Preparing dossiers

The dossier builder lives in `pipeline/dossiers.py`. A dossier identifies one character and includes `evidence` records with `id`, `source`, `field`, `text`, `record_character`, and `kind`, plus `context`. The provenance belongs to the source record even when a traditional counterpart or related character supplies the evidence. Rebuilding base dossiers preserves previously recorded external evidence and its research audit.

Snapshot a dossier as a resumable job:

```bash
python3 -m pipeline.editorial prepare content/dossiers/6728.json runs/editorial/6728
```

## Running agents

By default, `run` invokes separate Codex agents using `gpt-6-luna` with low reasoning, live search, and a read-only sandbox. After `prepare`, the complete single-character run is:

```bash
python3 -m pipeline.editorial run runs/editorial/6728
```

Use `--model` and `--reasoning` to override those settings explicitly. Every stage records both settings. The harness also accepts a custom JSON command argument array, without a shell. It sends a prompt on stdin and expects the command to write schema-conforming JSON to `{output}`. `{schema}`, `{model}`, `{reasoning}`, and `{role}` are also available. This permits existing agent tools or a custom wrapper without an SDK dependency. The defaults are `gpt-6-luna` with `low` reasoning for every separate stage invocation.

For example, the Codex CLI invocation used by the sibling graded-readers harness can be supplied as:

```bash
python3 -m pipeline.editorial run runs/editorial/6728 \
  --model gpt-6-luna --reasoning low \
  --command '["codex","--search","exec","--json","--ephemeral","--ignore-user-config","-s","read-only","-m","{model}","-c","model_reasoning_effort=\"{reasoning}\"","--output-schema","{schema}","-o","{output}","-"]' \
  --timeout 600 --max-revisions 2
```

The external command determines its own execution permissions; the example requests a read-only agent sandbox and enables live web search. Your chosen runner must expose a browser/search tool to the research agent. Each stage is a separate invocation. Factual and readability reviewers see the dossier and candidate article, without the other reviewer's verdict. A revision sees both reviews, and both reviewers assess the revised article again. Reviewers must produce `pass` with no findings or `revise` with actionable findings. There is no automatic conversion of a failed verdict to approval.

The harness validates character identity, formation and component fields, and all citation IDs mechanically. A phonosemantic formation must identify semantic and phonetic component roles. An indivisible pictograph uses its whole form as the pictorial component. Pictorial components depict physical objects or forms in the original scene; semantic components contribute a lexical meaning or category. These roles are not interchangeable, and a compound classified as semantic may contain pictorial components. Corruption is distinct from a regular variant, stylization, simplification or deliberate replacement. Reviewers assess whether the cited evidence actually supports the prose. Dossier limitations must not be inflated into claims that scholarship does not know the answer.

Prompts, schemas, results, subprocess logs and job status persist on disk. The cache key includes complete inputs, prompt, schema, model, reasoning and command. Cached output must match its recorded digest. Changed or failed attempts are archived under the stage's `attempts/` directory; reruns reuse successful unchanged stages. Invalid reader prose in curated glyph captions or limitations is sent back to the visual curator, since the article writer cannot alter those fields. Corrected glyph prose updates the dossier hash and requires fresh reviews. Timeout, process failure and invalid JSON/schema mark the job failed. Exhausted revision rounds produce `needs_revision`, exit code 2, and no publication. Inspect findings and rerun. To change the input dossier, repeat `prepare` before `run`; preparation updates the original snapshot and invalidates affected caches.

```bash
python3 -m pipeline.editorial status runs/editorial/6728
python3 -m pipeline.editorial publish runs/editorial/6728
```

Publication requires both review roles, distinct reviewer identities, and approval of the exact article and dossier hashes. It writes `content/entries/6728.json` and the exact reviewed enriched dossier to `content/dossiers/6728.json`. Publication also requires the external research audit, validates URL/title/access-date metadata on external evidence, and permits no new external findings only when the audit records unresolved gaps. The website builder also validates published artifacts against the current dossier, so editing prose or evidence requires new reviews. Digests establish artifact consistency; they are not digital signatures or a substitute for genuine independent review.

## External research and resumability

The stages are research → historical glyph candidate research → snapshot and visual curation → evidence analysis → writer → copy editor → independent factual/readability reviews → targeted revision when required. Research is mandatory, including for characters with apparently sufficient local data. It investigates historical component roles, shape changes, conflicting explanations and missing information using external references. A missing repository account must not become an unsupported claim that an etymology is unknown.

The research stage returns:

```json
{
  "evidence": [{
    "source": "Reference name", "field": "historical_components",
    "text": "A concise paraphrase of the inspected source's relevant finding.",
    "record_character": "木", "kind": "external_research",
    "url": "https://example.org/entry", "title": "Entry title",
    "accessed_at": "2026-09-26"
  }],
  "search_audit": [{
    "query": "Actual search query", "urls": ["https://example.org/entry"],
    "outcome": "What was inspected and established, including any access problems."
  }],
  "gaps": []
}
```

The example URL is a placeholder for this documentation, not evidence. Agents must inspect real pages and record actual queries and access dates. Failed external access is recorded explicitly. No reliable additions is a valid research outcome only with a nonempty audit and explicit gaps; fabrication is never required to fill a quota. A runner without browsing must fail this stage rather than fabricate activity.

`prepare` stores `source_dossier.json`; each run researches that original snapshot, then saves the merged `dossier.json`. External evidence gets deterministic `X-` IDs derived from its content and provenance, excluding the access date. Repeating a merge preserves IDs and does not append duplicates. The audit is saved under `dossier.external_research`. Cached research can be reused with identical inputs; changing the original dossier, research prompt, schema, model or command invalidates it.

## Importing work from interactive agents

Interactive research/writing/review agents can use the same publication gate. Merge their research results with `enrich_dossier(base_dossier, research)` before writing and review, or store equivalent external evidence and `external_research` audit fields directly. Save the actual reviews and retain agent/run provenance in the reviewer identifier. Never construct a passing receipt unless that reviewer actually passed these exact inputs.

```python
from pipeline.editorial import make_review, publish

reviews = [
    make_review("factual", factual_result["verdict"], factual_result["findings"],
                article, dossier, reviewer="factual-agent:<run-id>"),
    make_review("readability", readability_result["verdict"], readability_result["findings"],
                article, dossier, reviewer="readability-agent:<run-id>"),
]
publish(article, dossier, reviews)
```

Article structure:

```json
{
  "character": "木",
  "summary": {"text": "A concise explanation.", "evidence_ids": ["source:record:field"]},
  "formation": {"type": "pictographic", "text": "A stylized drawing of a tree.", "evidence_ids": ["source:record:field"]},
  "components": [{
    "form": "木", "origin_form": "", "roles": ["pictorial"], "form_status": "stylized",
    "text": "The whole graph depicts a tree.", "evidence_ids": ["source:record:field"]
  }],
  "history": [{"text": "A fuller account.", "evidence_ids": ["source:record:field"]}],
  "uncertainties": []
}
```

Keep `history` or `uncertainties` empty when there is no supported material for those sections. Do not fill them with speculative connective stories.

## Validation

Every component tagged `phonetic` must include a nonempty `sound` array. Each comparison records `component_form`, `component_reading`, `character_reading`, `system`, explanatory `text`, and `evidence_ids`. The site displays both pronunciations inside the component card. Modern readings should be given alongside a historical comparison when sound change obscures the relationship; reconstructed pairs must use one identified system. A historical component's pronunciation must not be assigned to a later lookalike, and Japanese on'yomi must not be conflated with kun'yomi.

```bash
python3 -m unittest pipeline.test_editorial pipeline.test_dossiers pipeline.test_glyph_assets -v
```

Tests cover component citations and roles, external research audit requirements, repeat-safe enrichment, preservation of research during base rebuilds, missing/unknown citations, character mismatch, stale or failed reviews, independent review identities, published artifact tampering, cache invalidation and retention, command timeout and bounded revision without implicit approval. They use local fake commands and never invoke a model.

## Version 2: independent character jobs

New `run` jobs require version 2. Existing approved version 1 entries remain readable and keep
valid exact-input review receipts; there is no automatic migration or bulk regeneration. Keep
experiments within the existing 20-character pilot, using 木, 來, 我 and 清 for the richer smoke workflow.
Each character has its own job directory, research, selected images, article and reviews.

Version 2 retains the base article fields and adds:

- `schema_version: 2`.
- `meaning_history`: `senses` (stable character-scoped `id`, `gloss`, `period`, attestation/use
  `status`, claim `certainty`, cited explanation), `developments` (`from_sense`, `to_sense`, type, certainty and cited
  explanation), and cited `limitations`. An attested gloss is not automatically an original sense.
  Graphic borrowing for another word differs from semantic extension; uncertain transitions can
  remain unconnected.
- `historical_glyphs`: at most six curated `items` and cited `limitations`. Each item has `id`,
  `image_url`, `source_url`, `source_title`, `period`, `tradition`, `caption`, `alt`, `selection_reason`,
  `rights`, `rights_url`, and `evidence_ids`. No items is valid only with a cited limitation.
- `relationships`: cited, explained edges with `id`, `subject` and `object` nodes (`kind`, `id`),
  `predicate`, `context_character`, and `certainty` (`established`, `probable`, `disputed`).
  Every internal component role and sense must be represented. Whole-graph pictographs retain their pictorial analysis as character metadata rather than requiring a component-of-self edge. Character/component identities
  use canonical forms; sense identities use character-scoped IDs such as `木:tree`. Narrative
  labels and ambiguous combined alternatives cannot become graph nodes. Alternative hypotheses
  remain separate, explicitly disputed claims.

The authoritative schemas are `ARTICLE_V2_SCHEMA` in `editorial.py` and the component schemas
in `structured.py`. `history` now describes graphic history; `meaning_history` describes meanings.
Neither requires a fabricated continuous chronology.

Local glyph hints can include an exact-title official Commons imageinfo metadata lead from `pipeline/data/commons-imageinfo-hsk1.json`. The cache documents its queries and check time; it does not establish glyph identity, historical dating, or publication approval. See `pipeline/data/README.md` for its scope.

The `glyph_research` agent inspects source pages and identifies eligible image candidates. It
returns the research schema plus proposed `historical_glyphs`. The harness downloads the actual
images, then `glyph_visual` receives attached raster views of those exact snapshots and returns
the final subset. Visual curation may correct captions, alt text and selection reasons; it cannot
change image identity or provenance. Updated captions may cite other existing dossier evidence, and every citation is validated. Images should demonstrate an explanatory point, not exhaust a
source collection. Record script tradition separately from dating, distinguish scholarly redrawings
from artifact photographs, and establish reuse rights. Unresolved identity or rights means omit the
image and record the limitation. Do not generate or invent historical glyph images.

If glyph research finds no usable image or a selected image cannot be acquired, the harness can
query Xiaoxuetang's official single-character form. It prefers one locally recorded traditional
counterpart, or the entry form when no counterpart is available. The site's form returns glyphs
through a POST request, so a plain search or GET often shows only the empty query interface.
Returned labels and direct rendered-image URLs are stored per character under
`<job>/xiaoxuetang-query/` and supplied to a targeted research pass. The lookup uses a two-second
minimum interval and pauses for an hour after an authorization response. It is not a database
mirror: the researcher selects only useful forms, and the visual curator still checks their exact
snapshots. Xiaoxuetang's CC0 notice applies to glyph images and attributes obtained through its
query interface; any selected asset keeps its source link and rights notice.

Glyph evidence is merged with deterministic evidence IDs. The exact selected glyph set, audit and
gaps live in `dossier.glyph_research`; article selection must match that reviewed input. Glyph candidates can cite new
evidence as `new:1`, `new:2`, etc., referring to the returned evidence array using one-based indices.
The harness resolves these aliases to deterministic evidence IDs before visual curation. Prefer
existing evidence IDs when they already support the claim.
Both reviewers must assess image identity, captions, visual/prose coherence, provenance, meaning
changes and graph consistency. No image or graph data bypasses the exact-article review hash.

The harness checks reference integrity, component-role agreement, graph endpoint types, sense
coverage, curated selection identity and HTTP(S) provenance URLs. Factual reviewers establish
whether the citations, image identifications, rights assertions and semantic links are true; valid
JSON alone cannot establish those facts. Selected images are snapshotted before analysis and writing; reviewers inspect the exact local
files. Site publication uses the verified snapshots, preserving source-page links for attribution.

### Image snapshots and repair rounds

`dossier.glyph_assets` binds each selected glyph ID and image URL to a repository-relative
`content/glyph-assets/<sha256>.<ext>` path, SHA-256, byte count and detected MIME type. Downloads
have a timeout and 8 MiB limit, verify PNG/JPEG/GIF/WebP signatures or an SVG XML root, and reject
HTML and active/external SVG content. Valid cached snapshots are reused without downloading.
Publication and site loading verify exact byte hashes locally; missing or modified files block
publication. Reviewers must view these snapshot files, not merely read their source descriptions.
The asset manifest is part of the reviewed dossier hash.

A mechanically invalid article is saved with validation findings and enters the same bounded
revision budget; it never receives invented reviewer approval. An overlong learner layer first
gets up to two focused Luna learner edits, preserving all expert fields. The complete result
still passes normal validation and fresh factual/readability review. A factual/readability rejection
also triggers targeted follow-up research and glyph selection, allowing correction of upstream
image choices, captions or evidence. The revised dossier and snapshots are then passed to the
revision writer and both independent reviewers. Exhausted rounds retain their findings for the
next deliberate run and cannot publish.

Reader-facing paragraphs that narrate the dossier or contain inline citation labels receive
a focused `prose_repair` invocation. Its schema permits only the flagged text fields; evidence
IDs, component metadata, readings and graph endpoints remain frozen. Curated glyph prose stays
with the glyph curator. The resulting article still requires normal validation and both reviews.

SVG originals retain their reviewed byte hashes. CairoSVG creates raster previews under
`content/glyph-previews/` for model image attachments, with a renderer/version and output-hash
receipt. Modified or invalid preview caches are regenerated from verified originals. Candidate,
visual-curation and reviewer invocations remain separate agent calls; caption/source text alone
does not count as visual inspection.

### Running the smoke subset

Each character can be prepared, resumed, checked and published independently. Keep the new run
small while changing the pipeline:

```bash
python3 -m pipeline.editorial prepare content/dossiers/6728.json runs/v2-smoke/6728
python3 -m pipeline.editorial run runs/v2-smoke/6728
python3 -m pipeline.editorial status runs/v2-smoke/6728
python3 -m pipeline.editorial publish runs/v2-smoke/6728
```

The default allows three revisions after the initial attempt. Increase `--max-revisions` explicitly
when an inspected failure needs more work. Research, candidate selection, visual curation,
analysis, writing, factual review and readability review all use Luna low by default. The Codex
adapter attaches rendered image files to visual curation and both reviewers. Custom adapters
must support the `attached_images` manifest supplied in the prompt.

A verified review that says “revise” while claiming no correction is needed triggers
one further model review of that contract. The harness never converts it into a pass;
a repeated contradictory verdict fails the stage and keeps the job unpublished.

Full schemas stay in `schema.json`; `agent-schema.json` omits the API-unsupported `uniqueItems`
keyword. Returned JSON is still validated with the full schema. Codex research calls must record
actual web searches or source-page inspections; direct inspection of a supplied source URL
counts as research, while a generated claim of having researched is insufficient. Reviewer
receipts record model, reasoning setting, role and the actual agent thread ID when available.

Research also receives exact local Unihan/Baxter–Sagart rows for named entry, component and
host graphs, plus bounded leads from existing local seal files when available. Neither packet
is automatically citable external evidence or establishes graphic roles. Glyph leads still need
source-page, image, rights and relevance checks. `refine --research-first` supplements evidence
before editing and binds new reviews to the augmented dossier hash.

Export the reviewed graph with `python3 -m pipeline.graph`. It includes cited relationships,
certainty, character context, approving hashes and the authored sound comparisons for phonetic
edges. It reports version-one entries separately instead of inferring relationships for them.

The writer's transport schema omits `historical_glyphs`. The harness assembles that field from
the visual curator's final product, then reviewers assess the complete entry. This avoids asking
the writer to reproduce an immutable selection and lets its output focus on prose, meanings and
relationships. A visual change goes through glyph curation and subsequent review.

Analysis, writing and visual-curation calls receive short citation aliases (for example, `ref001`). The adapter
maps their returned citation lists back to the original evidence IDs without guessing or fuzzy
matching. The alias map, raw agent result, and restored result are saved separately, and the
mapping participates in the cache fingerprint. Unknown citations still fail validation. Relationship
schemas constrain endpoint kinds by predicate; sense development connects sense nodes, while
component claims connect components to their host character. Explicitly disputed role hypotheses
may accompany a component whose role remains unresolved; they cannot be promoted to established
claims by the exporter.

Meaning ownership and development edges are assembled directly from the authored sense records
and developments, preserving their exact text, citations and certainty. The writer emits only
additional component and graphic relationships. Both reviewers see and approve the complete
assembled article; reviewer instructions explicitly distinguish it from the intermediate writer
schema. Character nodes in the graph export retain the reviewed formation and component records.

The visual agent likewise returns only selected IDs and caption/alt/selection-reason/citation
fields. The harness attaches the candidate's unchanged image identity, source, date, tradition
and rights metadata. Repeated identical citation IDs are removed during normalization; unknown
IDs remain errors. No source identity or claim is guessed during normalization.

## Refining an existing researched entry

To improve an existing version-2 entry without repeating initial research, analysis and writing:

```bash
python3 -m pipeline.editorial refine content/entries/6728.json runs/refine/6728
python3 -m pipeline.editorial status runs/refine/6728
python3 -m pipeline.editorial publish runs/refine/6728
```

`refine` has the same model, reasoning, command, timeout and revision-budget options as `run`
(default `gpt-6-luna`, low reasoning, three revisions). It snapshots the source article and dossier,
checks schema, character identity, evidence references and local image integrity, then starts with
the copy editor. New prose rules are checked after editing so older wording can actually be repaired.
The same independent factual and readability reviews, targeted research on rejection, bounded
revisions and exact-input publication gates apply. Existing approval receipts are not reused.
Refinement writes a job result; publication remains a separate explicit command.

To continue from a reviewed job checkpoint, pass its `article.json`; the adjacent `dossier.json`
is used automatically. Supply saved review findings to the first editor with `--feedback`:

```bash
python3 -m pipeline.editorial refine runs/v2-smoke/4F86/article.json runs/refine/4F86 \
  --feedback runs/v2-smoke/4F86/reviews.json
```

The original feedback is snapshotted as `source_feedback.json`; it informs editing but never
substitutes for fresh independent review.

If a saved candidate already includes the verified corrections, use `refine ... --review-current`
to send its exact article and adjacent dossier directly to fresh independent factual and
readability review. This skips only the initial copy edit; validation, review, bounded repairs
and publication gates still apply. For Chinese entries, a research follow-up preserves existing
curated glyphs unless a finding concerns glyphs, captions, image rights or another visual issue.
Do not combine `--review-current` with `--research-first`, since newly added evidence may require
editing the candidate first.

For a small correction to a candidate that already has genuine pass receipts, add
`--approved-base-job <approved-job>` to `--review-current`. The harness verifies both base
receipts and an identical dossier hash, computes every changed article path, and asks fresh
factual and readability reviewers to assess those changes and their effects on the complete
entry. The new receipts still bind the exact complete candidate and dossier. If research changes
the dossier, later rounds revert to full review scope.

Use `--research-first` when new source evidence is required before editing. For a small
scan-backed follow-up, feedback may include `source_scan_images`: up to three objects with an
absolute `path`, integer `pdf_page`, and an optional verified `printed_page`. The Codex research
stage receives the exact source images as attachments and their SHA-256 values in its input.
The images make a prior OCR passage inspectable; they do not certify the OCR or replace the
researcher's page-specific source check. The research agent must distinguish its own scan
inspection from a prior agent's note. A changed image changes the stage fingerprint.
When the scan reveals an OCR error, record its exact page and span and correct the book
repository's source-bound OCR layer, then rebuild its effective consumer corpus. A dossier
note alone does not repair the source text later entries will search.
For a Chinese text-focused refinement whose existing glyph selection and snapshots remain valid,
set `reuse_existing_glyph_candidates: true` in feedback. The pipeline verifies and retains those
assets while researching the new text evidence; omit the flag if the finding concerns image choice.

## Brief learner layer

New writer, revision and copy-editor outputs must include `learner`, independently cited and
reviewed against the detailed account. Its `overview` is a cited paragraph of at most 40 words;
`components` contains one cited explanation (at most 25 words) per current-form detailed component, linked by
zero-based `component_index`; `takeaway` is a cited paragraph of at most 35 words or `null` when
no essential present-meaning or borrowing caveat is needed. Existing component roles, forms and
sound comparisons remain canonical; the learner layer does not duplicate pronunciation data.

The short layer must preserve essential uncertainty and avoid invented mnemonics. Detailed
formation, component accounts, historical forms and meaning history remain available for deeper
reading. Both reviewers assess consistency between the short and detailed explanations. Coverage,
citations, reader-facing prose rules and word limits are mechanically checked.

`learner` is optional when loading previously approved v2 entries, preserving their existing
article hashes. Once present, every learner field participates in the article hash and requires
fresh review after edits. Refinement extracts optional article fields too, so it cannot silently
discard an approved learner explanation.

## Adding only the learner layer

```bash
python3 -m pipeline.editorial add-learner content/entries/6728.json runs/learner/6728
python3 -m pipeline.editorial publish runs/learner/6728
```

Use `add-learner` when the detailed entry is already approved and should be preserved exactly.
The source must pass publication integrity checks. A dedicated learner agent returns only the
learner object; the harness freezes every other article field, the dossier and image assets.
Both independent reviewers assess the added layer and its consistency with the unchanged approved
entry. New receipts bind the complete resulting article and dossier; no prior pass is inherited.
Failed learner validation/reviews return as feedback within the revision budget. Wording revisions
do not trigger mandatory new research; unsupported learner claims must be omitted. Publication
remains separate. Model/reasoning/timeout/command/revision options match `run` and `refine`.

## Sound borrowing smoke cases

The expanded smoke run adds 我 and 清 to 木 and 來. These contrast reuse of a whole graph for another word with a sound component inside a compound. Research must investigate the proposed source word and target word separately. A reconstruction of the target word alone cannot establish the name or pronunciation of a pictured implement. Entries must explain the borrowing mechanism in plain language, show supported comparisons, and preserve uncertainty where the proposed match cannot be verified. The learner overview or takeaway must explain this connection rather than merely label it a phonetic loan.

Learner length targets are 40 words for the overview, 25 per component, and 35 for the optional takeaway. Mechanical limits allow five extra words; reviewers judge clarity and focus rather than rejecting an otherwise concise explanation for a one-word overrun.

### Verifying proposed review corrections

A reviewer verdict of `revise` triggers a separate invocation of that review role before any
revision or follow-up research. The verification agent checks the alleged problem against the
exact article fields and cited evidence, retaining real required corrections and discarding
false or duplicate requests. It may itself return either `pass` or `revise`; the harness never
converts a failed review to approval. Both responses are archived under the role and
`<role>-verification` directories, and the final receipt names the actual deciding invocation.
This check applies to full-entry and learner-only review, preserving the latter's scope.

## Authored component-form relations

Component `origin_relation` explicitly classifies the relationship of `origin_form` to the visible
`form`: `full_form` for a positional/component shape's full form, `earlier_form` for a supported
historical ancestor or replaced form, `variant_form` for a nonchronological alternative,
`simplified_form` when the source explicitly identifies a standardized simplified counterpart, and
`uncertain` when the cited evidence does not establish the relationship. Use `none` exactly when
there is no distinct `origin_form`. Component roles or shape differences never establish chronology
by themselves. New writer/editor/revision outputs require this field; existing published v1/v2
entries may omit it without changing their approved hashes.

To add only these classifications to an approved entry:

```bash
python3 -m pipeline.editorial annotate-forms content/entries/6E05.json runs/forms/6E05
python3 -m pipeline.editorial publish runs/forms/6E05
```

The annotation agent returns `components: [{component_index, origin_relation, evidence_ids}]`.
Coverage must be exact and each annotation's citations must be a subset of that component's
existing citations. Only `origin_relation` is added to the article; all prose, other fields,
evidence, and assets remain frozen. Fresh independent factual and readability reviews assess the
classification and bind the complete resulting article/dossier. Unresolved evidence calls for
`uncertain`, not invented ancestry. Bounded repairs affect only annotations, and publication is
separate. Defaults remain Luna with low reasoning.

## Explicit cohorts and bounded batches

`pipeline.batch` takes a JSON cohort manifest with a unique `characters` array and keeps its
order. It never expands the selected batch automatically. Use small batches, inspect their
results, and improve the pipeline before starting the next batch:

```bash
python3 -m pipeline.batch status content/cohorts/hsk3-2021-level-1.json
python3 -m pipeline.batch prepare content/cohorts/hsk3-2021-level-1.json --limit 10
python3 -m pipeline.batch run content/cohorts/hsk3-2021-level-1.json --limit 10 --workers 10 --publish
```

`--limit` defaults to 10 and counts characters needing work, skipping valid published v2 entries with a learner
layer and classified distinct component origins. A component with no distinct origin need not
be regenerated just to add `none`. Legacy entries remain candidates for upgrading. Default
concurrency is ten independent character jobs, capped at ten; default output is
`runs/hsk3-2021-level-1`. Status reports the entire manifest, not just the last batch.

Each character has its own dossier snapshot, resumable stage caches and status. Existing canonical
dossiers are not rebuilt during preparation. A failed character does not stop other selected
characters, but produces a recorded failure and nonzero batch exit. Already approved jobs reuse
their reviewed outputs without invoking agents again. Publication is optional (`--publish` on
run, or the explicit `publish` action); there is no automatic deployment.

Publication revalidates both real receipts and current source compatibility, archives previous
canonical artifacts under `content/review_history/batch/`, syncs drafts/reviews/research/analysis
products, and retains exact JSON/text job artifacts under `content/editorial_runs/`. The per-entry
provenance record identifies that retained run and the deciding reviewers. No batch operation
constructs model approval or weakens the individual entry's publication gates.

Batch progress is durable before the first character starts and after each completion. The latest
`batch-status.json` records the exact selection, remaining characters and results. Each invocation
also keeps immutable numbered snapshots under `batch-history/<timestamp-id>/`, so a later batch
cannot erase an earlier checkpoint. Completion with failures and interrupted runs remain explicit.
Canonical `content/research/<character>.json` contains the complete reviewed external evidence,
search audit and unresolved gaps, including glyph research and targeted follow-ups; retained run
artifacts separately preserve the original unmodified stage outputs.

## Japanese N5 adaptation pilot

`python3 -m pipeline.japanese prepare` builds six inspectable Japanese packets. `python3 -m pipeline.japanese run --concurrency 6` researches, writes and independently reviews 日・学・国・気・生・聞 using GPT-6 Luna with low reasoning. Each character has its own job directory and bounded revision rounds. Failed or unapproved work is retained and never substituted for approved content.

Japanese publications live in `content/ja/entries` and `content/ja/dossiers`; Chinese entries remain independent. The site's Japanese view loads only Japanese approvals and otherwise shows its existing Japanese legacy content. The N5 list is an explicitly approximate community list, with a tracked source and checksum, not an official JLPT specification.

For an exact graph with an approved Chinese entry, preparation verifies the existing article and dossier receipts, records both hashes, and reuses cited research plus reviewed glyph candidates. A Japanese researcher still consults external references and a visual curator re-evaluates images and captions for the Japanese explanation. Different graphs never inherit an article or image set silently. The actual Japanese character meanings and relevant readings require inspected Japanese sources and fresh independent factual/readability approvals. Chinese component sound history does not establish Japanese native readings.

`japanese_usage` holds cited character-level context and selected reading notes. New writers cannot emit vocabulary example fields; archived reviewed records remain valid but their reading/example cards are not displayed. Japanese meanings belong in the learner overview and meaning history, and sound comparisons in component analysis. Compact on/kun metadata remains in the header. Character-level historical roles and Japanese readings remain separate. Research packets retain `source_reuse` provenance and source record owners, so later improvements can detect which Japanese entries reused a changed Chinese research dossier.

Export Japanese graph metadata separately with `python3 -m pipeline.graph --entries content/ja/entries --output output/japanese-editorial-graph.json`. Keep the language-specific sense graphs separate until a deliberate cross-language mapping is authored; matching character or sense IDs alone does not establish identical meanings.

Source roles and access limits are listed in `research/japanese-pipeline-sources.md`.

Japanese learner cards cover the current Japanese graph only; historical scoped components
remain in expert detail. Length and coverage repairs use a bounded learner-only agent edit,
preserving the expert article before the same independent review gates. Source records found
to contain an incorrect paraphrase can be retained for audit in `retired_evidence_ids`, but
cannot support a published passage. Model-facing citation aliases include those retirement
records and feedback references. Later review packets retain Chinese reuse hashes and evidence
but omit the duplicate complete Chinese draft to avoid confusing it with the Japanese article.

Resume a rejected pilot with `python3 -m pipeline.japanese repair --characters 学国気聞`.
The repair command selects the latest descendant job and keeps inspected research and assets;
additional research is requested by an agent only for a concrete remaining evidence gap.

Japanese copy edits and revisions of an existing draft return targeted JSON-path patches,
not a complete rewritten article. The harness rejects overlapping paths, restores citation
aliases, preserves untouched fields, and assembles the result through the existing full
validation and independent review gates. Initial writing still returns a complete draft.
Curated historical glyphs cannot be patched by a prose editor. The retained agent result is
the actual patch, alongside the resulting article and its hash-bound reviews.

Focused repair feedback can specify `allowed_edit_paths` to constrain the actual model
output schema. Invalid patch values receive up to two correction attempts, with all visible
schema errors reported together. String fields accept verbatim model prose as well as JSON
string values; arrays and structured values require valid JSON. Every patched complete
article still passes the full schema before assembly and factual review.

## Component refresh lessons and targeted corrections

Read `AGENTS.md` and `research/local-book-sources.md` for the current editorial rules and bounded scan access. A scan citation must distinguish the original page actually inspected from unread references mentioned on it.

Default Codex editor/revision calls now use the shared `apply_article_patch` mechanism for both Chinese and Japanese. Custom external commands retain their full-article contract. Patch candidates receive immediate schema, citation, component-role/edge, origin-relation and scope validation before independent review; sense edges are rebuilt from the candidate's meaning history. When a repair needs another attempt, that attempt receives the current candidate and preserves prior edits, rather than silently restarting from the original article. Independently approved artifacts remain the only publishable output.
