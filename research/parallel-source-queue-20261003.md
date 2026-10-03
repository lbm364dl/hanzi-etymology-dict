# Source enrichment at cohort scale — 2026-10-03

The user's proposed workload is dozens of characters at once. Inspection found 16 CPU
threads, 30 GiB RAM (about 13 GiB available), and over 700 GiB free disk. A 24-worker
configuration is plausible; these measurements do not establish real model throughput or
memory at 24 workers. Existing unrelated Codex processes must remain undisturbed.

## Failure classes and general changes

The old source runner capped workers at three and selection at ten, submitted all selected
jobs eagerly, and collected results in cohort order. There was no source queue checkpoint;
a slow first job delayed recording fast results. Failed or source-blocked early characters
were selected repeatedly, starving later work. A durable queue now checkpoints claims and
completions, retains attempt histories, bounds active submissions, and holds terminal
attention states until explicit retries. Selection prioritizes less-attempted characters.
A saved running state permits recovery but never overrides an actual inherited OS lock.

Concurrent output folders could perform the same source/character work. A claim shared
across output folders now precedes the existing job lock, and both are inherited by actual
model subprocesses. One supervisor owns each durable queue. Queue and publication CLI paths
retain original exact provenance and require independent review, rather than inventing
receipts on recovery. Publication is locked per canonical character and rejects changed
canonical baselines. A test exposed a further distinction: source baseline hashes describe
the article extracted from the published entry, not its evidence/dossier/review envelope.
The publisher must validate the envelope and compare the extracted article.

GitHub markers, labels and subissue counts were read without a shared lock. Multiple workers
could create the same finding or exceed a parent's child capacity using stale counts.
Repository synchronization now locks before those reads. Model triage stays parallel, while
remote writes are serialized. Bounded remote commands and lock waits preserve pending work
instead of holding a character indefinitely.

Fixed temporary names allowed shared cache/checkpoint writers to collide. JSON writes now
use unique atomic temporaries. Corpus caches formerly used only mtime and size, allowing a
same-size/mtime atomic replacement to retain stale data. The reader now binds an opened inode
and checks its identity before/after reading, retrying a replaced edition.

The producer remains the owner of OCR originals and correction validation. Parallel research
returns source-bound findings; repairs require independent pixel verification and a serialized
producer transaction, followed by consumer verification. Literal accuracy does not establish
etymological truth. Material unresolved findings remain held, with actual GitHub tracking.

## Verification

- A 100-job fixture ran with 24 workers. More than 20 completions were durably recorded while
  the first fixture remained blocked. Active callbacks stayed within the configured limit.
- Separate tests cover attention fairness, explicit retry histories, interrupted claims,
  live supervisor/job/character locks, unique atomic writers and changed queue identities.
- Twenty-four real local fixture subprocesses produce distinct stage fingerprints/receipts;
  an unchanged-input cache replay succeeds after the fixture command file is removed.
  These are test fixtures, not research or editorial approvals.
- Publication tests cover same-character serialization, different-character concurrency,
  stale baselines and wrapped exact-candidate retry. GitHub tests use a local command fixture
  and verify concurrent finding deduplication and timeout propagation.
- Live smoke started on 差, 常 and 场 in `runs/source-enrichment-scale-20261003`, using the
  complete HSK1 cohort with 本/边/别/茶 temporarily excluded because of separate ongoing work.
  Actual model stages report `gpt-6-luna` / `low`. Completion and load are to be checked
  before expanding the live queue. The 24-worker fixture is not a 24-agent live benchmark.

These harness changes do not regenerate or certify any existing article. Every character
that lacks the current source/publication gates still needs its own genuine work.

## Capacity and live observation

The three-character smoke's descendants used approximately 1,883 MiB RSS during a measured
sample. Linear extrapolation to 24 simultaneous model processes would exceed the then
available 10 GiB. The harness therefore supports independent `--workers 24 --agents 12`:
24 character workers share 12 inherited model-process slots, recording slot wait times
separately from active stage time. OS leases survive orphaned child processes, preventing
a resumed supervisor from exceeding the same configured process capacity. These are
scheduling limits; active agents retain their authorized tool access.

The user also requested a live dashboard. `pipeline.dashboard` serves a local observer,
with a two-second filesystem/process feed and separate one-minute read-only GitHub polling.
Collection failures preserve the last state and identify the error. Exact receipt inspection
remains distinct from review approval and current-source verification. The frontend is
checked in a fresh Playwright session, including filtering, job details and snapshot refresh.

Publication of an already reviewed source candidate revealed another general contract
problem: an inspection note legitimately removed the original `no images inspected` rule,
but the publisher treated all context differences as concurrent baseline changes. An exact,
validated frozen source baseline now allows reviewed provenance/editorial-rule updates;
language, imported identity metadata and other context remain protected. Existing exact
review hashes still certify the incoming dossier. Changed canonical inputs remain rejected.

## Actual smoke outcomes and editorial implications

The live concurrency smoke completed 差, 常 and 场 independently. All three ended in
`needs_revision`; this is a real review outcome, not an infrastructure error or approval.
Current canonical entries were preserved. Findings concerned grouped current component
identity versus historical derivation, dictionary interpretations versus dated lexical
senses, alternative graph usage versus claimed spelling change, specialist sound contrasts,
and unsupported absence/borrowing assertions. These are general evidence/scope failures:
the source profile now explicitly addresses them for future research, authorship and review.
That prompt change does not repair the three held drafts or certify previously approved
entries. Their next authored revisions require fresh independent factual/readability reviews.
The queue retained their actual histories and moved them to attention instead of reselecting
them ahead of all pending characters.


## Dashboard verification and first expanded run

The expanded queue runs with 24 character workers and 12 model slots. Actual Linux
observations confirmed 12 concurrent Luna low model processes; queued model stages
remain separately visible. The queue retained the three smoke revision outcomes and
continued to new characters. Fresh failures include citation-contract rejection and
600-second model-stage timeouts; these are held for diagnosis and later retries, not
counted as published. Source/profile changes alone do not certify older entries.

A fresh Playwright session exercised the local dashboard against the actual repository:
live process and slot counts, changing snapshot timestamps, character search and
status/source/history controls, full hashes and JSON receipt links. Aborted API polling
kept the last worker count and labeled the snapshot stale; normal polling resumed after
restoring the route. Current coverage is explicitly the last verified source audit.
Real-data browser checks caught a queue adapter mismatch (string job paths versus nested
job objects), which could hide terminal/current entries and mislabel pending entries.
The adapter and current/history accounting must preserve every cohort row.

Review receipt hashes now compare with the actual current job files, using cached
canonical JSON digests. A prior status hash can describe an earlier revision; it cannot
certify the current draft. Missing current files use an explicitly labeled source baseline.
Standalone in-repository model processes with output paths can be shown without inventing
a character identity; OCR page provenance is retained when an occurrence packet exists.
Coordinator task records are explicit saved work descriptions, separate from live PIDs.


Final verification: 212 meaningful pipeline tests passed after the producer process-group
cleanup was complete. The final observer receipt/origin change passed 15 observer/server
tests. `node --check` passed. Fresh desktop (1440 px) and mobile (390 px) browser checks
showed no horizontal overflow; final navigation had no console warnings or errors.
The real board showed 300 current entries, 3 held revisions and 3 failed queue jobs at
that sample, with historical attention separate. Full review/finding/status JSON links
returned HTTP 200; snapshot timestamps advanced without a page reload.
Producer timeout and nonzero-exit tests prove helper descendants are stopped before rollback.
