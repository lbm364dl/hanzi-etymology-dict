# Local scholarly book sources

The digitised sources supplied to cohort enrichment are explicitly registered in
`research/digitised-sources.json`; currently this includes only 字源. Other acquired scans
remain possible scholarly references, rather than fully digitised consumer corpora. New books
can be registered later with exact edition and source identity. Consult additional authoritative
sources when the supplied book leaves a gap or a material disagreement.

Track errors, mistakes, improvements and clarifications in repository GitHub issues, linking
page-bound evidence and the required verification. The current cohort work is issue #1.
Use reasoning to identify suspicious OCR, but verify literal replacements against original
scan pixels; a plausible correction is a hypothesis until checked. Newly discovered verified
errors must reach both the source correction layer and the searchable corpus.

On this workstation, acquired books are in `/home/catalin/hanzi-etymology-books` (normally `~/hanzi-etymology-books`). This collection is optional; missing local access must not prevent external research or become a claim that scholarship has no answer.

Read its `PIPELINE.md` before using exports. Available references include 季旭昇《說文新證》2014 second edition, 李學勤主編《字源》2012, 劉釗《古文字構形學》2011 revised edition and 裘錫圭《文字學概要》2013 revised edition. Enumerate filenames to verify the edition actually present. 黃德寬《古文字譜系疏證》2007 was not present at this inspection.

Original PDF scans are inspectable source material. The 《字源》 first-pass OCR corpus now covers its full PDF; the collection's `cross-book-pilot`, `reconstruction-pilot` and other digitisation outputs still cover selected pages. Distinguish verified page exports, provisional OCR and directly inspected source images. Do not treat a clean-looking draft export as independent source verification.

For relevant entries, locate the book's index/headword, inspect the actual page and record printed page plus PDF page, exact edition and what was directly inspected. Preserve rare or historical shapes with source provenance; do not silently normalize them into convenient Unicode characters. Record unavailable pages explicitly. Summarize claims in your own words and retain competing scholarly interpretations where material.

Local file paths are access metadata, not public citation destinations. Cite bibliographic details and pages, with a stable publisher/catalogue URL when available, while describing direct scan inspection accurately in the research record. Having a scan does not grant rights to republish its glyph images; curated image publication has its own provenance and rights gate.

## Resource budget for scans

The owner explicitly authorizes agents to use available tools freely. Prefer existing reviewed exports, searchable text and indexes for efficiency; start with relevant pages and expand as needed. There is no three-page research cap or requirement to ask permission for additional scan work. Agents may use shell scripts, image tools, rendering, browser/search and other available capabilities, and should create or repair their own crops from original scans when supplied crops are inadequate. Coordinate shared corpus and correction-overlay writes with the job owner to avoid collisions, preserve raw OCR, and retain actual source and review receipts. All introduced agents remain gpt-6-luna with low reasoning.

## Provisional searchable corpus

Query `~/hanzi-etymology-books/source-corpus/ziyuan-pages.jsonl` first for 字源 using that repository's `scripts/source_corpus.py search` or direct JSONL reading if the CLI environment lacks PyMuPDF. This is a complete-coverage provisional OCR edition. The detailed `pages.jsonl` covers earlier samples from other books; `research-pages.jsonl` is the 12-page 字源 pilot fallback when the full edition is unavailable. Do not combine the 字源 pilot and full edition as independent corroborating sources or duplicate their page records. Hits locate provisional passages and original scans; they are not reviewed source transcriptions. A character mentioned in a quotation or running header is not necessarily the page headword, and an index pointer is not evidence until its target entry is found. Verify the actual headword, relevant prose, rare characters and glyph references against the scan before using a claim; check whether the entry continues onto another page. When this check discovers an OCR error, return the exact page and suspect span to the book repository, verify it against the original scan, add a source-hash-bound `ocr-corrections.json` record there, and rebuild the effective exports and consumer corpus. Do not leave a known error only in an entry research note or silently substitute text in a citation. An unresolved printed identity needs an occurrence-specific reference, not a guessed Unicode character. Avoid feeding full-page glyph and review metadata to an agent: keep compact excerpts and only referenced glyph assets. Follow the consumer requirements in `research/book-source-corpus-handoff.md` as the producer expands the corpus.

For an entry update that depends on a new book claim, attach the relevant source scans to the research stage and independent factual review when feasible. Compare the exact component or graph named in the article against the pixels, not merely against a prior agent's summary; adjacent entries can contaminate synthesis even when the OCR itself is correct. The 学/教 smoke check in `research/ziyuan-hsk1-xue-jiao.md` records both an actual OCR substitution and a separate cross-entry research error.

The accepted version-2 CLI returns a single JSON envelope with `coverage` and compact `results`; use `--limit 3`. Full page details are available with `inspect --corpus PATH --page-id ID`. Read `match_type` and `entry_metadata`: current hits are text mentions, not verified headword matches. Preserve the separate transcription/layout/glyph statuses and do not interpret null printed pages as a inferred page number. Fast OCR glyph references can point to a full page scan without individual crop geometry. Search the traditional, simplified and relevant independent component spellings explicitly rather than guessing substitutions.

The expanded 12-page 字源 pilot demonstrates that repeated rare-headword substitutions can survive apparently fluent OCR (PDF page 820 uses 魃 for a different printed headword; page 1100 uses 芈 for a different printed headword). Confirm the identity of any cited headword or component against the scan before adopting its role, reading or relationships. If Unicode identity is unresolved, retain a page-bound glyph reference and an explicit identity gap rather than guessing a familiar character. Running headers can be the first search occurrence and hide the substantive passage; use full-page `inspect` for a relevant hit and check adjacent pages when the account continues. These are general research requirements, not character-specific corrections.

### Live 字源 access

```bash
python3 /home/catalin/hanzi-etymology-books/scripts/source_corpus.py search --corpus /home/catalin/hanzi-etymology-books/source-corpus/ziyuan-pages.jsonl --query 學 --limit 3
```

Progress is in `~/hanzi-etymology-books/research-ocr/ziyuan-full/run-status.json`; the corpus is published atomically after each batch. Pages already indexed can be used immediately with the same bounded scan verification. Search simplified and traditional spellings separately. Completion means provisional OCR coverage, not factual review. Verified fixes to pages 276, 277, 718, 820 and 1100 are included in the live corpus; unresolved printed identities use explicit glyph references. Do not invoke or resume the producer's OCR job from entry research.

As checked on 2026-09-30, the 字源 first-pass run reports complete coverage: 1,435/1,435 PDF pages, with 1,427 provisional OCR pages and eight source-verified blank scans. `source-corpus/ziyuan-pages.jsonl` has 1,435 records. This supersedes the earlier incomplete-coverage snapshot in `research/book-source-corpus-handoff.md`; it does not upgrade unreviewed OCR to verified transcription. On this workstation the corpus JSONL was readable, but `scripts/source_corpus.py` could not start in the current shell because `fitz` (PyMuPDF) was missing. Research agents can inspect the records directly or use the CLI in an environment with that dependency, and must still check source scans for cited passages.
