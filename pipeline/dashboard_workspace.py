"""Small, read-only repository and coordinator observations for the dashboard."""
import json
from pathlib import Path
import subprocess
import time


class Workspace:
    def __init__(self, root, interval=10):
        self.root = Path(root).resolve()
        self.interval = interval
        self.cached_at = 0
        self.cached = {}

    def snapshot(self):
        now = time.monotonic()
        if now - self.cached_at < self.interval:
            return self.cached
        result = {}
        try:
            def git(*args):
                return subprocess.run(['git', *args], cwd=self.root, text=True,
                    capture_output=True, timeout=5, check=True).stdout.strip()
            rows = git('status', '--porcelain').splitlines()
            result['repository'] = {'branch': git('branch', '--show-current'),
                'head': git('rev-parse', 'HEAD'), 'dirty_count': len(rows),
                'changes': [{'status': row[:2].strip(), 'path': row[3:]} for row in rows[:300]]}
        except (OSError, subprocess.SubprocessError):
            result['repository'] = {'status': 'unavailable'}
        path = self.root / 'runs/operations/coordination.json'
        if path.is_file():
            try:
                result['coordination'] = json.loads(path.read_text())
            except (OSError, ValueError):
                result['coordination'] = {'status': 'unavailable'}
        self.cached_at, self.cached = now, result
        return result
