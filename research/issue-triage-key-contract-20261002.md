# Issue triage key contract (2026-10-02)

大 source enrichment reached a terminal needs-revision state, but issue tracking failed when the triage agent invented an existing finding key. The semantic key check ran after the repair loop and therefore could not trigger a fresh corrected agent attempt.

The agent schema now enumerates the supplied existing keys plus null for new findings. The semantic guard also runs inside the repair loop. Unknown keys require another genuine Luna low triage attempt; they are never silently mapped to an unrelated issue. A regression verifies the retry and the supplied-key schema.
