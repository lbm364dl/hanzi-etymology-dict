# Local scholarly book sources

On this workstation, acquired books are in `/home/catalin/hanzi-etymology-books` (normally `~/hanzi-etymology-books`). This collection is optional; missing local access must not prevent external research or become a claim that scholarship has no answer.

Read its `PIPELINE.md` before using exports. Available references include 季旭昇《說文新證》2014 second edition, 李學勤主編《字源》2012, 劉釗《古文字構形學》2011 revised edition and 裘錫圭《文字學概要》2013 revised edition. Enumerate filenames to verify the edition actually present. 黃德寬《古文字譜系疏證》2007 was not present at this inspection.

Original PDF scans are inspectable source material. The collection's `cross-book-pilot`, `reconstruction-pilot` and other digitisation outputs cover selected pages and are not a complete searchable edition. Distinguish verified page exports, pending OCR and directly inspected source images. Do not treat a clean-looking draft export as independent source verification.

For relevant entries, locate the book's index/headword, inspect the actual page and record printed page plus PDF page, exact edition and what was directly inspected. Preserve rare or historical shapes with source provenance; do not silently normalize them into convenient Unicode characters. Record unavailable pages explicitly. Summarize claims in your own words and retain competing scholarly interpretations where material.

Local file paths are access metadata, not public citation destinations. Cite bibliographic details and pages, with a stable publisher/catalogue URL when available, while describing direct scan inspection accurately in the research record. Having a scan does not grant rights to republish its glyph images; curated image publication has its own provenance and rights gate.

## Resource budget for scans

The owner is still digitising this collection. Prefer existing reviewed exports, embedded searchable text and indexes. Limit an entry's initial local scan investigation to a brief locator check and at most three targeted relevant pages once a reliable locator is found. Do not run whole-book OCR, rendering or visual search, and do not invoke digitisation APIs as part of entry research. If the headword cannot be located efficiently, record that access gap and continue with accessible scholarly references. Additional scan work requires a concrete expected benefit and the owner's direction.

## Provisional searchable corpus

If available, query `~/hanzi-etymology-books/source-corpus/ziyuan-pages.jsonl` first for 字源 using that repository's `scripts/source_corpus.py search`. This is the live, incrementally published provisional edition; read returned coverage rather than assuming completion. The detailed `pages.jsonl` covers earlier samples from other books; `research-pages.jsonl` is the 12-page 字源 pilot fallback when the live edition is unavailable. Do not combine the 字源 pilot and live edition as independent corroborating sources or duplicate their page records. Hits locate provisional passages and original scans; they are not reviewed source transcriptions. A character mentioned in a quotation is not necessarily the page headword. Avoid feeding full-page glyph and review metadata to an agent: keep compact excerpts and only referenced glyph assets. Follow the consumer requirements in `research/book-source-corpus-handoff.md` as the producer expands the corpus.

The accepted version-2 CLI returns a single JSON envelope with `coverage` and compact `results`; use `--limit 3`. Full page details are available with `inspect --corpus PATH --page-id ID`. Read `match_type` and `entry_metadata`: current hits are text mentions, not verified headword matches. Preserve the separate transcription/layout/glyph statuses and do not interpret null printed pages as a inferred page number. Fast OCR glyph references can point to a full page scan without individual crop geometry. Search the traditional, simplified and relevant independent component spellings explicitly rather than guessing substitutions.

The expanded 12-page 字源 pilot demonstrates that repeated rare-headword substitutions can survive apparently fluent OCR (PDF page 820 uses 魃 for a different printed headword; page 1100 uses 芈 for a different printed headword). Confirm the identity of any cited headword or component against the scan before adopting its role, reading or relationships. If Unicode identity is unresolved, retain a page-bound glyph reference and an explicit identity gap rather than guessing a familiar character. Running headers can be the first search occurrence and hide the substantive passage; use full-page `inspect` for a relevant hit and check adjacent pages when the account continues. These are general research requirements, not character-specific corrections.

### Live 字源 access

```bash
python3 /home/catalin/hanzi-etymology-books/scripts/source_corpus.py search --corpus /home/catalin/hanzi-etymology-books/source-corpus/ziyuan-pages.jsonl --query 學 --limit 3
```

Progress is in `~/hanzi-etymology-books/research-ocr/ziyuan-full/run-status.json`; the corpus is published atomically after each batch. Pages already indexed can be used immediately with the same bounded scan verification. Search simplified and traditional spellings separately. Completion means provisional OCR coverage, not factual review. Verified fixes to pages 820 and 1100 are included in the live corpus; the latter's unresolved printed identities use explicit glyph references. Do not invoke or resume the producer's OCR job from entry research.
