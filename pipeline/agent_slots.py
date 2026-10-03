"""Fair model-process capacity shared by character workers and inherited by agents."""
from contextlib import contextmanager
import fcntl
from pathlib import Path
import threading


class AgentSlots:
    def __init__(self, directory, capacity):
        if capacity < 1:
            raise ValueError('Agent capacity must be positive')
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.capacity = capacity
        self.condition = threading.Condition()
        self.pending = []

    @contextmanager
    def acquire(self):
        ticket = object()
        lease = None
        with self.condition:
            self.pending.append(ticket)
            try:
                while lease is None:
                    if self.pending[0] is ticket:
                        for index in range(self.capacity):
                            candidate = (self.directory / f'{index:03d}.lock').open('a')
                            try:
                                fcntl.flock(candidate, fcntl.LOCK_EX | fcntl.LOCK_NB)
                            except BlockingIOError:
                                candidate.close()
                            else:
                                lease = candidate
                                break
                    if lease is None:
                        self.condition.wait(timeout=0.2)
                self.pending.pop(0)
                self.condition.notify_all()
            except BaseException:
                self.pending.remove(ticket)
                self.condition.notify_all()
                raise
        try:
            yield lease.fileno()
        finally:
            fcntl.flock(lease, fcntl.LOCK_UN)
            lease.close()
            with self.condition:
                self.condition.notify_all()
