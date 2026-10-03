"""Durable, bounded character scheduling; attention jobs never starve pending work."""
from __future__ import annotations
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from collections import Counter
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
from pathlib import Path
import uuid

from pipeline import editorial

ATTENTION = frozenset({'failed', 'needs_revision', 'needs_source_refresh',
    'needs_source_verification', 'needs_source_evidence', 'needs_source_research', 'stale'})


def now():
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def supervisor(path):
    """One scheduler per queue; child agents retain their own per-job locks."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError(f'Queue already has a live supervisor: {path}') from exc
        try:
            yield
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


class Queue:
    def __init__(self, path, identity):
        self.path = Path(path)
        self.identity = identity
        if self.path.exists():
            self.state = editorial.read(self.path)
            if self.state['identity'] != identity:
                raise ValueError('Queue inputs changed; use a fresh output directory')
        else:
            self.state = {'schema_version': 1, 'identity': identity, 'jobs': {}, 'created_at': now()}
        self.run_id = uuid.uuid4().hex

    def checkpoint(self):
        self.state['updated_at'] = now()
        self.state['summary'] = dict(Counter(j.get('status', 'queued') for j in self.state['jobs'].values()))
        editorial.write(self.path, self.state)

    def execute(self, characters, process, job_path, verified, workers, limit,
                retry_attention=False, publish=False, excluded=()):
        if workers < 1 or limit < 1:
            raise ValueError('Workers and selection limit must be positive')
        rows, eligible = {}, []
        jobs = self.state['jobs']
        for char in characters:
            path = Path(job_path(char))
            previous = jobs.get(char, {})
            saved = editorial.read(path / 'status.json') if (path / 'status.json').is_file() else {}
            result = previous.get('result', {})
            recovering = previous.get('status') == 'running'
            # A returned failure can differ from stage status; retain it until explicitly retried.
            value = None if recovering else result.get('underlying_status', result.get('status'))
            if not recovering and saved.get('status') in ATTENTION:
                value = saved['status']
            if char in excluded:
                rows[char] = {'character': char, 'status': 'excluded', 'job': str(path)}
            elif char in verified:
                rows[char] = {'character': char, 'status': 'published', 'job': str(verified[char])}
            elif value in ATTENTION and not retry_attention:
                rows[char] = {**result, 'character': char, 'status': value,
                              'job': str(path), 'attention_required': True}
            else:
                eligible.append(char)
                rows[char] = {'character': char, 'status': 'deferred', 'job': str(path)}
        for char, row in rows.items():
            record = jobs.setdefault(char, {'attempts': 0, 'history': []})
            if row['status'] != 'deferred':
                record.update(status=row['status'], result=row)
            elif record.get('status') != 'running':
                record['status'] = 'queued'
        # Least attempted first: live locks and transient failures cannot monopolize a small limit.
        eligible.sort(key=lambda char: jobs.get(char, {}).get('attempts', 0))
        selected = iter(eligible[:limit])
        self.state.update(run_id=self.run_id, workers=workers, selection_limit=limit,
                          status='running', started_at=now())
        self.checkpoint()

        def submit(pool, active):
            try:
                char = next(selected)
            except StopIteration:
                return False
            record = jobs.setdefault(char, {'attempts': 0, 'history': []})
            record.update(status='running', run_id=self.run_id, started_at=now(),
                          attempts=record['attempts'] + 1, job=str(job_path(char)))
            self.checkpoint()  # Record claim before starting any model work.
            active[pool.submit(process, char)] = char
            return True

        with ThreadPoolExecutor(max_workers=workers) as pool:
            active = {}
            for _ in range(workers):
                if not submit(pool, active):
                    break
            while active:
                completed, _ = wait(active, return_when=FIRST_COMPLETED)
                for future in completed:
                    char = active.pop(future)
                    try:
                        result = future.result()
                    except Exception as exc:
                        result = {'character': char, 'status': 'failed',
                                  'job': str(job_path(char)), 'error': str(exc)}
                    if result.get('underlying_status', result.get('status')) in ATTENTION:
                        result['attention_required'] = True
                    rows[char] = result
                    record = jobs[char]
                    receipt = {'run_id': self.run_id, 'attempt': record['attempts'],
                               'finished_at': now(), 'result': result}
                    record['history'].append(receipt)
                    record.update(status=result['status'], result=result, finished_at=receipt['finished_at'])
                    self.checkpoint()  # Fast completions survive even while another job hangs.
                    submit(pool, active)
        for char, row in rows.items():
            if char in verified:
                jobs.setdefault(char, {'attempts': 0, 'history': []}).update(status='published', result=row)
        self.state.update(status='idle', finished_at=now())
        self.checkpoint()
        return [rows[char] for char in characters]
