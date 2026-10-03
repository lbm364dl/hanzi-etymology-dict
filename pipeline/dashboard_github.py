"""Periodic read-only GitHub snapshots, independent of the live filesystem feed."""
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import subprocess
import threading


def repositories(root):
    path = Path(root) / 'research/digitised-sources.json'
    if not path.exists():
        return []
    registry = json.loads(path.read_text())
    return sorted({s['github_repo'] for s in registry.get('sources', [])
                   if re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', s.get('github_repo', ''))})


class GitHubFeed:
    def __init__(self, repository_names, interval=60):
        self.repositories = repository_names
        self.interval = interval
        self.lock = threading.Lock()
        self.stopped = threading.Event()
        self.state = {'refresh_interval_seconds': interval, 'repositories': [], 'issues': [],
                      'status': 'starting' if repository_names else 'not_configured'}
        self.thread = threading.Thread(target=self._observe, daemon=True, name='dashboard-github')

    def start(self):
        if self.repositories:
            self.thread.start()

    def snapshot(self):
        with self.lock:
            return self.state

    def refresh(self):
        issues, errors, observed = [], [], []
        for repository in self.repositories:
            try:
                completed = subprocess.run(['gh', 'issue', 'list', '--repo', repository,
                    '--state', 'all', '--limit', '1000', '--json',
                    'number,title,state,url,updatedAt,labels,milestone'],
                    timeout=12, check=True, text=True, capture_output=True)
                records = json.loads(completed.stdout)
                if not isinstance(records, list):
                    raise ValueError('GitHub issue response is not an array')
                issues.extend({**record, 'repository': repository} for record in records)
                observed.append(repository)
            except (OSError, subprocess.SubprocessError, ValueError) as exc:
                errors.append({'repository': repository, 'error': type(exc).__name__})
        with self.lock:
            if errors and not observed:
                self.state = {**self.state, 'status': 'error', 'errors': errors,
                              'attempted_at': datetime.now(timezone.utc).isoformat()}
            else:
                self.state = {'status': 'partial' if errors else 'ready',
                              'updated_at': datetime.now(timezone.utc).isoformat(),
                              'refresh_interval_seconds': self.interval,
                              'repositories': observed, 'issues': issues, 'errors': errors}

    def _observe(self):
        while not self.stopped.is_set():
            self.refresh()
            self.stopped.wait(self.interval)

    def close(self):
        self.stopped.set()
