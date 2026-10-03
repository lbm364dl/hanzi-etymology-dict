"""Small atomic file helpers for shared pipeline caches."""
from __future__ import annotations

from contextlib import contextmanager
import fcntl
import json
import os
from pathlib import Path
import tempfile


def atomic_write_bytes(path, data: bytes) -> None:
    """Write bytes through a unique sibling temporary file and atomically replace."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=target.name + ".", suffix=".tmp", dir=target.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def atomic_write_text(path, text: str, encoding="utf-8") -> None:
    atomic_write_bytes(path, text.encode(encoding))


def atomic_write_json(path, value, *, indent=2, sort_keys=False) -> None:
    text = json.dumps(value, ensure_ascii=False, indent=indent, sort_keys=sort_keys) + "\n"
    atomic_write_text(path, text)


@contextmanager
def file_lock(path):
    """Hold an exclusive cross-process lock associated with a cache key."""
    lock_path = Path(path)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a") as stream:
        fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
