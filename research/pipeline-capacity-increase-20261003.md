# Live model capacity increase — 2026-10-03

The previous 12-model setting was conservative. Measured available memory showed
room to increase concurrency without interrupting genuine in-flight research and reviews.

## Applied change

- Existing full HSK1 supervisor PID 3643036 continues: 24 character workers, 12 model slots.
- Additional supervisor PID 4173723 uses 24 workers and 24 shared model slots for the
  initially unclaimed final 96 characters recorded in
  `research/cohorts/hsk1-remaining-tail-20261003.json`.
- Both use the same indexed OS model leases and source/character locks.
- All model stages remain `gpt-6-luna` with low reasoning.
- Output: `runs/source-enrichment-capacity24-20261003/ziyuan-2012/queue.json`.

## Observed verification

Dashboard snapshot at 2026-10-03T12:51:03.560768+00:00 recorded:
24 actual live model processes, approximately 5.8 GiB aggregate direct model RSS,
13.9 GiB available machine memory, load averages 4.59 / 5.97 / 6.52 on 16 threads,
and no collector warnings. Both supervisor PIDs were alive.
48 configured character workers includes work waiting for the 24 model slots.
This is evidence of actual expanded concurrency, not a throughput claim; model calls
also spend time on remote services and tools.

## Remaining scheduling implication

The shard was disjoint from active/attempted work when selected. The original full
queue still contains those characters. Shared locks prevent concurrent duplicate work,
but its completion inventory was read at startup. Arrange a clean queue handoff before
it reaches the tail; do not claim that locks alone prevent later redundant research.
The full 300-character cohort remains the completion target. Queue record counts across
the two manifests are not a count of unique characters.
