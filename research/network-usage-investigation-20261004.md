# Network usage investigation — 2026-10-04

User reported severe internet degradation that ceased after stopping agent workloads. Pipeline remains paused; investigation did not restart agents.

## Observed evidence

- Pre-stop process/socket snapshot attributed nine Codex processes to this repo: eight pipeline agents plus one interactive session; 71 established TCP sockets and one listening socket. Connection counts do not measure byte throughput.
- Stop manifest `runs/operations/user-stop-20261004.json` captured eight agent processes, twenty npm Playwright launchers and eighteen CUA processes. These are distinct process categories, not twenty proven downloads.
- Ten retained October 4 npm logs mention Playwright; twelve logged registry fetch attempts failed with ETIMEDOUT. Retained npm logs are incomplete and shared across projects; failures do not establish large downloads.
- Recent retry metadata contains 93 image attachment occurrences totalling 223.66 MiB of local encoded files (47/132.53 MiB smoke retry1; 19/27.31 MiB retry2; 14/40.45 MiB verified-raw; 13/23.37 MiB retry3). Repeated files count repeatedly. This measures configured attachments, not successful network upload bytes or server reuse.
- Host sysstat Wi-Fi samples ending 10:20, 10:30 and 10:40 local time show interval averages of roughly 3.29/2.30/2.40 MiB/s received and 0.48/0.51/0.41 MiB/s transmitted. Stop was at 10:37:29, so the 10:40 interval crosses the stop. These are whole-host measurements, including other projects.
- A three-second sample at 10:41:37–40 averaged 8.57 KiB/s received and 6.02 KiB/s transmitted. This short sample cannot establish long-term baseline.

## Interpretation and failure class

Large repeated image attachments and repeated per-stage tool-server startup are demonstrated overhead mechanisms. Whole-host traffic fell substantially following shutdown, consistent with the reported recovery. Historical per-process byte telemetry was absent, so this investigation cannot assign exact bandwidth shares or identify the dominant transfer source. npm timeouts demonstrate failed startup requests, not proof of repeated dependency downloads.

Concurrency planning considered model slots and memory but lacked network usage and latency measurements. Before a resumed scale run, add per-process/worker byte monitoring, retain time-series network measurements, inspect tool-server startup reuse and image delivery redundancy, and run a small measured smoke batch. Preserve agents’ unrestricted investigation capabilities and independent source/review gates. No pipeline change or resumed workload was performed during this paused investigation.
