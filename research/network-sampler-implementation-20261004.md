# Network sampler implementation (2026-10-04)

## Sampling contract

`pipeline.network_sampling` is a standalone, read-only Linux sampler. It appends
one JSON record per interval and a sibling `.meta.json` manifest. Each sample
retains raw receive/transmit octets for every interface in `/proc/net/dev`,
interval deltas where the interface was present in both samples, and `ss -tinpH`
TCP socket counters grouped by visible owner PID. For sockets that survive across
two samples it records observed `bytes_sent`, `bytes_received`, and `bytes_acked`
deltas. Link counter resets and TCP counter resets are marked instead of reported
as negative traffic. For each visible socket owner, it also snapshots a safe
process identity from `/proc`: PID, process start-time ticks, `comm`, executable
basename, cwd, and only a stage output path extracted from recognized output
flags. It does not retain the full command line or environment. Identity history
is keyed by `(PID, starttime_ticks)` and remains in subsequent samples with
`currently_visible: false` after the process disappears, so PID reuse does not
overwrite an earlier stage mapping.

The interface counters cover the sampler's network namespace, not an individual
process. The `ss` counters describe visible live TCP sockets with an owner PID;
they do not include UDP or hidden/short-lived/closed sockets and are not equivalent
to per-process interface bytes or total internet use. Start sampling before the
smoke workload and retain both the JSONL and manifest. A bounded example is:

```bash
/tmp/hanzi-etymology-venv/bin/python -m pipeline.network_sampling \
  --output runs/operations/network-sampler-smoke.jsonl \
  --duration 300 --interval 1 --pid SUPERVISOR_PID --pid CODEX_PID
```

Omit `--pid` filters to inspect all visible TCP owners, or pass the exact process
IDs selected for the measured run. The sampler does not launch or alter the model
workload.

## Tool-startup evidence and follow-up

The Codex config contains four local Playwright MCP entries using
`/home/catalin/.local/bin/npx -y @playwright/mcp@0.0.79` (two persistent profiles,
an isolated context, and extension mode), plus remote Supabase, Composio, and
DataForSEO servers and a local Node REPL. The config makes repeated npm package
resolution a plausible startup overhead when separate Codex processes initialize
those entries, but config alone does not prove each process starts every server.

The inspected Oct. 4 app-server daemon log had one Supabase OAuth-refresh error and
one failed local HTTP session cleanup; it had no Playwright/npx startup messages.
Three retained OCR-stage stderr logs from separate Oct. 3 Codex invocations each
reported a timeout refreshing available models; two also reported a Supabase token
refresh error. These are repeated connection-initialization symptoms, not byte
measurements or proof that MCP startup caused the reported bandwidth load. The
current evidence does not show repeated Playwright startup in those specific logs.

For a low-overhead follow-up, measure a two-slot smoke with the sampler and keep all
configured tool capabilities available. Compare the existing `npx -y` startup with
a pinned, already-installed Playwright MCP executable (same package version,
arguments, profiles and extension mode) or a supported shared server process.
Do not remove tool definitions, restrict agent permissions, or change the review
workflow to reduce measured startup overhead. Recheck latency and throughput after
the change before adopting it.

## Verification

`/tmp/hanzi-etymology-venv/bin/python -m unittest pipeline.test_network_sampling -v`
passed eight tests for `/proc/net/dev` parsing/deltas, `ss` output parsing, PID
aggregation, persistent-socket deltas and reset detection, append-only sampling,
manifest scope, unavailable-`ss` reporting, safe process identity extraction,
and retained history across process exit and PID reuse. A direct `ss -tinpH`
parser sanity check succeeded against the host's current output (70 visible TCP
sockets with owner PID across 22 PIDs); this snapshot was not retained as workload
evidence.
