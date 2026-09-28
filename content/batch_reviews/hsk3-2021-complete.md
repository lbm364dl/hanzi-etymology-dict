# HSK 1 completion report

All 300 characters in `content/cohorts/hsk3-2021-level-1.json` have validated,
published structured entries. Their exact current articles and dossiers carry two
independent GPT-6 Luna low approval receipts. Production used separate per-character
research, writing and review jobs, bounded cohorts, external research and local sources,
with a shared ceiling of 20 character jobs. No production jobs remain active.

## Final evidence

- `output/hsk1-integrity-audit.json`: 300/300 pass. Checks current dossiers,
  review hashes and reviewer identities, external research records, meaning senses,
  source and site image hashes, built article equality, graph membership, exact
  relationship IDs, endpoints, citations and review hashes.
- `runs/hsk3-2021-level-1/glyph-coverage-final.json`: all 49 known missing-image
  cases with local source leads completed approved follow-ups. Later received-form
  rechecks and required factual/reader corrections are included.
- `runs/hsk3-2021-level-1/browser-final.json`: all 300 built articles pass the
  actual renderer's learner/expert structure and citation-ID checks. A separate mobile
  context also checked the final 教 entry: expert initially closed, historical image
  loaded, citation popup visible, no horizontal overflow.
- Final site and graph builds completed. The exported graph contains 303 structured
  entries including three outside this cohort, 1,961 nodes and 2,048 cited relationships.
- All 97 pipeline tests passed; `git diff --check` passed.

Every cohort entry includes meaning history. 190 have curated historical images;
110 have cited limitations rather than unverified illustrations. This does not claim
that no suitable image exists elsewhere. Source attribution, historical dates, redraw
labels and alternative analyses remain accessible through citations and image details.
The integrity audit verifies coverage and consistency, not scholarly consensus; factual,
readability and visual judgments are recorded in the independent production reviews.

## Pipeline improvements from the run

Learner and expert layers are separated. Component metadata distinguishes positional
forms, variants, earlier forms and simplifications; historical roles and graph edges
are scoped to the actual character form. Sound comparisons identify both readings and
their system, and loan accounts explain the proposed mechanism without inventing an
unknown object's name. Meaning history separates attestation, semantic change and loans.

Glyph work uses exact source filenames, a narrow official Commons metadata cache,
downloaded snapshots and mapped pixel attachments. Verified received-form redraws may
illustrate later forms without being presented as ancient artifacts or proof of origins.
Catalogue names alone cannot establish inscriptional character witnesses. Disputed graph
hypotheses retain explicit certainty rather than being treated as established facts.

Focused repairs preserve unaffected reviewed content. Contradictory review findings
request fresh actual review rather than being converted to pass. The repeatable cohort
audit catches stale site data, image assets and graph exports after publication.
The licensed Unihan extract and source-frequency snapshot are documented separately;
recurring dictionary usage does not grant permission to mirror their full contents.
