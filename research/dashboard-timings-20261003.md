# Dashboard timing breakdown — 2026-10-03

The user asked whether the dashboard can explain slow progress. Active-stage ages alone
hide completed research, repeated reviews, failed calls and waits for model capacity.
The observer now exposes full retained stage timing history, including archived attempts,
and exact per-character queue start/finish/error fields. Failed durations freeze at finish;
unverified unfinished stale stages stay unknown instead of accumulating fictitious runtime.

The timing table and per-character drawer separate elapsed clock time, recorded model-stage
time and slot wait, group by stage role, retain repeated/failed calls, and link stage metadata
and results. Stage sums may overlap and include tools/network; they are not CPU or billing.
Current queue start/finish bounds exclude earlier/imported stage receipts. Nested job stages
roll up once; reused old jobs appear only with history enabled unless actually live.

A real browser sample at approximately 12:09 UTC showed 车 near 40 minutes of clock time,
18m25s of recorded model-stage time and 21m10s of slot waits. Readability/factual review and
repeated revision/planning calls were visible individually. With 24 workers sharing 12 model
slots, waiting explains a substantial part of clock time; increasing character workers alone
cannot remove that wait. Older 四 history showed 43 factual and 40 readability calls, evidence
that repeated repairs also deserve diagnosis; those older durations are not new run cost.

Verification: 19 observer/server/timing tests passed, including parallel-versus-wall duration,
slot wait, old receipt exclusion, failed archive freezing and stale unknown timing. Fresh
Playwright checks inspected actual current data, role bars, history/search filtering and a
stage metadata HTTP 200 link. Desktop and 390px mobile had no document overflow and no console
warnings/errors. The optional agent-browser CLI download timed out; available fresh Playwright
provided actual browser verification. No article approval is inferred from timing data.

Observer JSON/hash caches also bind inode and ctime, so an atomic same-size/mtime
receipt replacement cannot leave a stale timing or review hash in the dashboard.
