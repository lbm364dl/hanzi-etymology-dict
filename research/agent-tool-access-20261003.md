# Agent tool access

The owner requested that pipeline agents use tools freely. Previous runs often overrode a read-only default manually, while prompts imposed a three-page investigation cap and discouraged additional inspection. A source-resolution worker also stopped at a claimed inadequate crop instead of preparing its own from the available original. These restrictions hindered investigation without establishing factual reliability.

The default Codex command now selects `danger-full-access` and `approval_policy="never"`, retains live web search, and loads user configuration so configured tools/integrations remain available. Model and reasoning remain explicitly `gpt-6-luna` / `low`. This configuration follows the documented [full-access settings](https://learn.chatgpt.com/docs/sandboxing). A custom runner still determines its own capabilities.

Shared instructions now permit tools, additional pages, scripts, rendering and self-prepared crops as needed. The local book guide and AGENTS.md preserve this preference. Supplied scan lists are no longer rejected or silently truncated after three attachments in research feedback and source resolution. The automatic locator still chooses a small initial set of leads; it is not a limit on further investigation.

Shared-file ownership, independent research/authorship/review roles, source-pixel verification and exact publication receipts remain necessary for coherent concurrent work. Tools can produce or inspect evidence; they do not replace those checks. Active coordinating agents were informed; already-running CLI invocations retain their original launch configuration and are not restarted merely to change a prompt.

Verification: 124 editorial, agent-schema, source-enrichment and source-adoption tests pass. The transport test now proves four source images reach the Codex argument list and retained attachment manifest; the feedback test proves additional pages survive packet construction. Model/search settings, full-access flags and user-configuration availability are asserted.
