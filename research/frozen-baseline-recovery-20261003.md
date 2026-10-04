# Verified recovery of old frozen inputs

The approved 大 job still had the pre-fix editorial input collision. The actual
published baseline matched both original hashes in its unchanged `source.json`.
A general recovery helper now archives collided inputs and restores only that
exact baseline. It rejects changed canonical inputs and any live coordinator or
agent lock, and records that it creates no authorship or approval.

The publication gate now validates frozen snapshots through `prepare_job`,
before any canonical writes. Tests cover rejected changed baseline, rejected
live lock, preserved collision evidence, unchanged source metadata, successful
exact recovery and publication rejection after an approved job's inputs are
overwritten. This repairs orchestration provenance without hand-editing prose.
