# Fresh three-slot source smoke — 2026-10-04

Fresh jobs from canonical approved baselines for 车、花、问; three workers and three shared model slots, all gpt-6-luna / low, unrestricted tools. These characters had older jobs; no prior draft was continued. Full HSK1 work remains paused. Issue #344 is linked as a follow-up subissue of #334 because #1 and #2 each already have GitHub’s 100 direct-child limit.

## Outcome

No new article was published. This run does not establish improved throughput. Its measured wall time was 12m50s, with 16 model calls. Slot waits totalled less than 0.1s: waiting for a free slot was not the bottleneck.

| Character | Full job wall time | Calls | Outcome |
|---|---|---|---|
| 车 | 12m 49s | 3 | failed |
| 花 | 10m 41s | 2 | failed |
| 问 | 5m 11s | 11 | needs_revision |

车 research finished in 89s, then its article_patch call emitted only thread/turn startup and hit the 600s limit. Flower research remained active (17 completed shell events and 15 completed web events) but returned no structured result within 600s. 问 research took 191s; after authorship and independent reviews, a feedback sequence requested explicit historical readings, then narrower qualification of what those readings establish. It reached the revision limit. Genuine model metadata and outputs are retained under this run; no approvals have been invented.

## General implications

- Long per-call service/tool latency remains a separate problem from review-loop cost. A quiet author call is not evidence of 600s of useful authorship. Its stderr contains an unrelated Supabase OAuth refresh error; this alone does not establish why it stalled. Do not disable tools or infer a service cause without checking.
- Research can still produce a contradictory scan marker: 问 states that its scan was directly checked with no unresolved feature while marking it SCAN VERIFICATION REQUIRED. Existing SOURCE_POLICY explicitly disallows this. It remains an unresolved gate in this job rather than being silently removed. A general structured distinction between verified scan provenance and genuinely unresolved occurrences merits a harness follow-up.
- Review instructions already require named historical comparisons and precise uncertainty. The 问 cycle shows that authors must report comparison values while qualifying only the inference they do not independently establish. Neither review certifies the final candidate jointly; it requires a fresh repair/review through the normal pipeline.
- 字源 may legitimately omit dedicated character accounts. Its appendix/table material must be evaluated against specific claims, not discarded with a missing headword. That SOURCE_POLICY correction was exercised in these fresh prompts. The earlier 妈 appendix discovery remains awaiting citation integration/reviews; its confirmed-looking OCR substitution remains awaiting independent producer repair.

The automated issue sync retained hypotheses #345 (花 sense status), #346 (车 cursive-date attribution) and #347 (车 rare printed forms). These are followups, not confirmed source corrections or completed repairs. 问’s precise review/source hold is tracked in the parent smoke issue and its durable job.

## Network and shutdown

Observed live TCP deltas attributed by saved stage output paths: 183.3 MB received, 20.7 MB sent. These are partial socket-level observations, not exact internet usage. Interface counters include other active projects; those cannot all be attributed here. This run still has meaningful bandwidth cost at three slots and does not justify increasing capacity.

The sampler and supervisor exited. worker-audit.json records zero live CLI workers for this run. Existing canonical entries and site articles remain in use. The 58 locator/source-enrichment contract tests passed for the non-headword policy change; there was no presentation change or publication requiring a fresh site build.
