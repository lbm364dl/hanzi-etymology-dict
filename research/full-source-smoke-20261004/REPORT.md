# Bounded source-enrichment measurement

Run `runs/full-source-smoke-20261004`, tracked in GitHub #334. Fresh source enrichment from canonical approved entries, not generation from an empty dossier. Two workers, two model slots, every actual invocation gpt-6-luna / low. No continuation research imported. The 300-character batch remains paused.

## Actual outcomes

| Character | Elapsed to terminal state | Calls | Research | Outcome |
| --- | ---: | ---: | ---: | --- |
| 工 | 4m 48s | 6 | 3m 03s | Both editorial reviews passed on round 0; source verification held. |
| 妈 | 10m 20s | 2 | 10m timeout | No completed research result; no authored revision or approval. |
| 听 | 4m 02s | 6 | 3m 03s | Reviews requested corrections; planner transport rejected the schema before reasoning. |

The cohort finished in 10m 20s with 14 calls and zero publications. 听 started after 工 released its worker; its elapsed time excludes that queue wait. Durations include model tools/network and are not CPU or billing measurements. Stage sums can overlap. Existing approved entries remain the site fallback.

工's author edit took 26 seconds, factual/readability checks 13/8 seconds, source resolution 31 seconds and issue triage 12 seconds. The source reviewer held a historical description dependent on unresolved printed forms. The researcher also flagged correctly preserved unresolved glyph placeholders as OCR corrections; that classification needs fresh research rather than coordinator relabeling. Follow-up #335 retains the actual findings.

妈 rejected a false headword hit, then spent its remaining research time locating a supplemental entry in an image-only dictionary and hit the 600-second stage timeout. The logs contain investigation, not a completed schema-valid dossier. Follow-up #336 remains open. No automatic research retry was launched.

听's API error explicitly reported missing `glyph_action` in the strict planner schema's required keys. An unrelated Supabase token error in stderr did not establish the cause; the API response in stdout did. Source finding #337 separately records an unverified reading-order hypothesis on PDF page 96. The attempted attention continuation correctly refused to bypass that transcription finding.

## General fixes and verification

The planner's transport schema now requires every property, including `glyph_action`; older genuine retained plans remain valid under the internal contract. A regression checks both requirements. A separate genuine live Luna low planner call completed with `action=edit`, `glyph_action=retain`. It is retained under `planner-recovery/`, counts as one additional call, and is not a review approval or completed article repair.

Research instructions now distinguish preserved historical drawings from transcription mistakes, permit stroke descriptions without guessed Unicode names, request exact reordered spans for layout/OCR hypotheses, and prioritize verified indexes/page leads when a search hit proves to be another headword. Agents still have unrestricted tools and no arbitrary page cap. These prompt changes are not live-certified by the earlier cohort, and do not approve its candidates.

Focused suite: 181 tests pass. Actual candidates, reviews, source findings and metadata are retained alongside this report. The ten-minute network sampler remains in the run folder; live TCP counters include local traffic and miss closed/short-lived sockets, so they are not exact internet usage.

## Interpretation and remaining work

The ordinary 工 author/review path completed without a revision loop, but no character passed every publication gate. This experiment does not establish successful-entry throughput or justify another large batch. The next work is targeted source verification for 工/听 and better indexed access for 妈. All three still await an approved, source-cleared revised publication; changing prompts alone does not regenerate them.
