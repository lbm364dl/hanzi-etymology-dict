"""Low-overhead Linux network counter sampler for measured pipeline runs.

Interface byte counters are namespace-wide cumulative counters from /proc/net/dev.
Per-PID TCP byte counters are sums of socket-lifetime values exposed by `ss -tinp`;
they cover visible live TCP sockets only and are not exact per-process interface bytes.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import sys
import time


_TCP_COUNTERS = ("bytes_sent", "bytes_received", "bytes_acked")
_PID_RE = re.compile(r"pid=(\d+)")
_FD_RE = re.compile(r"\bfd=(\d+)")
_METRIC_RE = re.compile(r"\b(bytes_sent|bytes_received|bytes_acked):(\d+)")
_PROCESS_RE = re.compile(r'users:\(\(\"([^\"]+)\",pid=\d+')


def _stage_output_path(argv):
    """Extract only a known result/output path; never retain arbitrary argv values."""
    for index, token in enumerate(argv[:-1]):
        if token in ("-o", "--output", "--output-file"):
            return argv[index + 1]
    for token in argv:
        for prefix in ("--output=", "--output-file="):
            if token.startswith(prefix):
                return token.split("=", 1)[1]
    return None


def read_process_identity(pid, proc_root="/proc"):
    """Read safe process identity fields, excluding the original command line."""
    directory = Path(proc_root) / str(pid)
    stat_line = (directory / "stat").read_text(encoding="ascii")
    closing = stat_line.rfind(")")
    if closing < 0:
        raise ValueError(f"Malformed proc stat for PID {pid}")
    fields_after_comm = stat_line[closing + 1:].split()
    if len(fields_after_comm) <= 19:
        raise ValueError(f"Proc stat lacks starttime for PID {pid}")
    starttime_ticks = int(fields_after_comm[19])
    command = (directory / "cmdline").read_bytes().split(b"\0")
    argv = [item.decode("utf-8", errors="replace") for item in command if item]
    try:
        executable = Path(os.readlink(directory / "exe")).name
    except OSError:
        executable = None
    try:
        cwd = os.readlink(directory / "cwd")
    except OSError:
        cwd = None
    try:
        comm = (directory / "comm").read_text(encoding="utf-8").strip()
    except OSError:
        comm = None
    return {
        "pid": int(pid),
        "starttime_ticks": starttime_ticks,
        "comm": comm,
        "executable_basename": executable,
        "cwd": cwd,
        "stage_output_path": _stage_output_path(argv),
    }


def read_interface_counters(path="/proc/net/dev"):
    """Return raw per-interface rx/tx octet totals from Linux procfs."""
    result = {}
    with open(path, encoding="ascii") as stream:
        for line in stream:
            if ":" not in line:
                continue
            name, counters = line.split(":", 1)
            values = counters.split()
            if len(values) < 9:
                continue
            result[name.strip()] = {
                "rx_bytes": int(values[0]),
                "tx_bytes": int(values[8]),
            }
    return result


def interface_deltas(previous, current):
    """Return nonnegative byte deltas for interfaces present in both samples."""
    deltas = {}
    for name, counters in current.items():
        old = previous.get(name)
        if old is None:
            continue
        values = {key: counters[key] - old[key] for key in ("rx_bytes", "tx_bytes")}
        # Counters can reset on link/device recreation. Keep the raw values and
        # mark this interval unknown instead of reporting a misleading negative.
        deltas[name] = (values if all(value >= 0 for value in values.values()) else None)
    return deltas


def parse_ss_tcp(output):
    """Parse `ss -tinpH` records into socket rows with process and TCP_INFO bytes."""
    records = []
    current = None

    def flush():
        nonlocal current
        if current is None:
            return
        text = " ".join(current["parts"])
        pids = sorted({int(value) for value in _PID_RE.findall(text)})
        if len(pids) == 1:
            metrics = {name: int(value) for name, value in _METRIC_RE.findall(text)}
            records.append({
                "pid": pids[0],
                "process": next(iter(_PROCESS_RE.findall(text)), None),
                "fd": int(((_FD_RE.findall(text)) or [0])[0]),
                "state": current["state"],
                "local": current["local"],
                "peer": current["peer"],
                **metrics,
            })
        current = None

    for raw_line in output.splitlines():
        if not raw_line.strip():
            continue
        if raw_line[:1].isspace():
            if current is not None:
                current["parts"].append(raw_line.strip())
            continue
        flush()
        fields = raw_line.split()
        # ss -H -t output: state, recv-q, send-q, local endpoint, peer endpoint.
        if len(fields) < 5:
            current = None
            continue
        current = {"state": fields[0], "local": fields[3], "peer": fields[4],
                   "parts": [raw_line.strip()]}
    flush()
    return records


def group_tcp_by_pid(records):
    """Aggregate current visible TCP socket counters by owning PID."""
    result = {}
    for row in records:
        pid = row["pid"]
        aggregate = result.setdefault(pid, {
            "process": row.get("process"), "socket_count": 0,
            **{counter: 0 for counter in _TCP_COUNTERS},
            "counter_fields_available": set(),
        })
        aggregate["socket_count"] += 1
        for counter in _TCP_COUNTERS:
            if counter in row:
                aggregate[counter] += row[counter]
                aggregate['counter_fields_available'].add(counter)
    for aggregate in result.values():
        aggregate['counter_fields_available'] = sorted(aggregate['counter_fields_available'])
    return result


def tcp_socket_deltas(previous, current):
    """Compute observed per-PID deltas for sockets present in consecutive samples."""
    def index(rows):
        return {(row["pid"], row.get("pid_starttime_ticks"), row.get("fd", 0),
                 row["local"], row["peer"]): row
                for row in rows}

    old_rows, new_rows = index(previous), index(current)
    by_pid = {}
    resets = []
    for key, row in new_rows.items():
        old = old_rows.get(key)
        if old is None:
            continue
        pid = row["pid"]
        delta = by_pid.setdefault(pid, {**{counter: 0 for counter in _TCP_COUNTERS},
                                        "counter_fields_available": set()})
        for counter in _TCP_COUNTERS:
            if counter not in row or counter not in old:
                continue
            delta['counter_fields_available'].add(counter)
            difference = row[counter] - old[counter]
            if difference < 0:
                resets.append({"pid": pid, "fd": row.get("fd"), "counter": counter})
            else:
                delta[counter] += difference
    for delta in by_pid.values():
        delta['counter_fields_available'] = sorted(delta['counter_fields_available'])
    return by_pid, resets


class NetworkSampler:
    """Append timestamped interface and visible TCP socket counters as JSONL."""

    def __init__(self, output, interval=1.0, pids=None, proc_net_dev="/proc/net/dev",
                 ss_path=None, clock=time.monotonic, wall_clock=None,
                 proc_root="/proc"):
        if interval <= 0:
            raise ValueError("Sampling interval must be positive")
        self.output = Path(output)
        self.interval = float(interval)
        self.pids = set(pids or [])
        self.proc_net_dev = proc_net_dev
        self.ss_path = ss_path or shutil.which("ss")
        self.clock = clock
        self.wall_clock = wall_clock or (lambda: datetime.now(timezone.utc).isoformat())
        self.proc_root = Path(proc_root)
        self.previous_interfaces = None
        self.previous_tcp = []
        self.previous_monotonic = None
        self.pid_identity_history = {}
        self.manifest_path = Path(str(self.output) + ".meta.json")
        self._manifest_written = False

    def _ensure_manifest(self):
        if self._manifest_written:
            return
        if self.manifest_path.exists():
            raise FileExistsError(f"Sampler manifest already exists: {self.manifest_path}")
        version = None
        version_error = None
        if self.ss_path:
            try:
                result = subprocess.run([self.ss_path, "-V"], capture_output=True,
                                        text=True, timeout=2, check=False)
                version = (result.stdout or result.stderr).strip() or None
                if result.returncode:
                    version_error = f"ss -V exited {result.returncode}"
            except (OSError, subprocess.TimeoutExpired) as exc:
                version_error = str(exc)
        manifest = {
            "schema_version": 1,
            "started_at": self.wall_clock(),
            "sampler_pid": os.getpid(),
            "hostname": socket.gethostname(),
            "python_executable": sys.executable,
            "python_version": sys.version.split()[0],
            "interface_counter_source": str(self.proc_net_dev),
            "interface_scope": "current network namespace",
            "ss_path": self.ss_path,
            "ss_version": version,
            "ss_version_error": version_error,
            "ss_filter_pids": sorted(self.pids),
            "process_identity_source": str(self.proc_root),
            "process_identity_fields": ["PID", "starttime_ticks", "comm",
                                        "executable_basename", "cwd", "stage_output_path"],
            "tcp_counter_scope": "visible live TCP sockets with owner PID and ss byte fields",
            "interval_seconds": self.interval,
            "sample_file": str(self.output),
        }
        self.output.parent.mkdir(parents=True, exist_ok=True)
        with self.manifest_path.open("x", encoding="utf-8") as stream:
            json.dump(manifest, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        self._manifest_written = True

    def _read_tcp(self):
        if not self.ss_path:
            return {"available": False, "error": "ss executable not found", "sockets": []}
        try:
            completed = subprocess.run([self.ss_path, "-tinpH"], check=False,
                                       capture_output=True, text=True, timeout=5)
        except (OSError, subprocess.TimeoutExpired) as exc:
            return {"available": False, "error": str(exc), "sockets": []}
        if completed.returncode:
            return {"available": False,
                    "error": f"ss exited {completed.returncode}: {completed.stderr.strip()}",
                    "sockets": []}
        records = parse_ss_tcp(completed.stdout)
        if self.pids:
            records = [row for row in records if row["pid"] in self.pids]
        return {"available": True, "error": None, "sockets": records}

    def _record_process_identities(self, rows, timestamp):
        """Retain first/last visibility and safe identity for observed socket owners."""
        for item in self.pid_identity_history.values():
            item["currently_visible"] = False
        current = {}
        errors = []
        for pid in sorted({row["pid"] for row in rows}):
            try:
                identity = read_process_identity(pid, self.proc_root)
            except (OSError, ValueError) as exc:
                errors.append({"pid": pid, "error": str(exc)})
                continue
            key = (identity["pid"], identity["starttime_ticks"])
            retained = self.pid_identity_history.get(key)
            if retained is None:
                retained = {**identity, "first_seen_at": timestamp,
                            "last_seen_at": timestamp, "currently_visible": True}
                self.pid_identity_history[key] = retained
            else:
                retained["last_seen_at"] = timestamp
                retained["currently_visible"] = True
            current[pid] = identity
        for row in rows:
            identity = current.get(row["pid"])
            if identity:
                row["pid_starttime_ticks"] = identity["starttime_ticks"]
        history = sorted(self.pid_identity_history.values(),
                         key=lambda item: (item["pid"], item["starttime_ticks"]))
        return history, errors

    def sample(self):
        self._ensure_manifest()
        now_mono = self.clock()
        interfaces = read_interface_counters(self.proc_net_dev)
        tcp = self._read_tcp()
        rows = tcp["sockets"]
        timestamp = self.wall_clock()
        identity_history, identity_errors = self._record_process_identities(rows, timestamp)
        tcp_delta, resets = tcp_socket_deltas(self.previous_tcp, rows)
        interface_delta = (interface_deltas(self.previous_interfaces, interfaces)
                           if self.previous_interfaces is not None else {})
        elapsed = (now_mono - self.previous_monotonic
                   if self.previous_monotonic is not None else None)
        record = {
            "timestamp": timestamp,
            "monotonic_seconds": now_mono,
            "elapsed_seconds": elapsed,
            "interfaces": interfaces,
            "interface_delta_bytes": interface_delta,
            "tcp_ss_available": tcp["available"],
            "tcp_ss_error": tcp["error"],
            "tcp_pid_visible_socket_totals": group_tcp_by_pid(rows),
            "tcp_pid_observed_delta_bytes": tcp_delta,
            "tcp_counter_resets": resets,
            "tcp_socket_count": len(rows),
            "pid_identity_history": identity_history,
            "pid_identity_errors": identity_errors,
            "limitations": [
                "Interface counters cover the sampler's network namespace, not a single PID.",
                "TCP totals include only currently visible sockets with ss byte fields and owner PID.",
                "Per-PID deltas cover sockets observed in consecutive samples; short-lived or closed sockets can be missed.",
                "TCP byte counters are socket-level and are not equivalent to interface bytes or total internet use.",
            ],
        }
        self.output.parent.mkdir(parents=True, exist_ok=True)
        with self.output.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(record, ensure_ascii=False) + "\n")
        self.previous_interfaces = interfaces
        self.previous_tcp = rows
        self.previous_monotonic = now_mono
        return record

    def run(self, duration):
        if duration <= 0:
            raise ValueError("Sampling duration must be positive")
        start = self.clock()
        end = start + duration
        samples = 0
        while self.clock() < end:
            before = self.clock()
            self.sample()
            samples += 1
            remaining = end - self.clock()
            if remaining <= 0:
                break
            time.sleep(min(self.interval, remaining))
        return samples


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="Append-only JSONL time series")
    parser.add_argument("--interval", type=float, default=1.0)
    parser.add_argument("--duration", type=float, required=True, help="Sample duration in seconds")
    parser.add_argument("--pid", type=int, action="append", default=[],
                        help="Optional PID filter; may be repeated")
    args = parser.parse_args()
    sampler = NetworkSampler(args.output, interval=args.interval, pids=args.pid)
    print(json.dumps({"output": str(args.output), "sampler_pid": os.getpid(),
                      "python": sys.executable, "interval": args.interval,
                      "duration": args.duration, "ss_path": sampler.ss_path,
                      "scope": "network namespace interfaces; visible live TCP sockets only"},
                     ensure_ascii=False))
    print(json.dumps({"samples_written": sampler.run(args.duration)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
