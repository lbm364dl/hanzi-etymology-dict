from concurrent.futures import ThreadPoolExecutor
import fcntl
from pathlib import Path
import tempfile
import threading
import time
import unittest

from pipeline.agent_slots import AgentSlots


class AgentSlotTests(unittest.TestCase):
    def test_two_managers_share_capacity_and_release_after_exception(self):
        with tempfile.TemporaryDirectory() as temp:
            slots = [AgentSlots(Path(temp), 3), AgentSlots(Path(temp), 3)]
            active = peak = 0
            guard = threading.Lock()
            def process(index):
                nonlocal active, peak
                with slots[index % 2].acquire() as fd:
                    with guard:
                        active += 1
                        peak = max(peak, active)
                    time.sleep(0.02)
                    with guard:
                        active -= 1
            with ThreadPoolExecutor(24) as pool:
                list(pool.map(process, range(48)))
            self.assertLessEqual(peak, 3)
            self.assertGreater(peak, 1)
            with self.assertRaises(RuntimeError):
                with slots[0].acquire():
                    raise RuntimeError('fixture')
            with slots[1].acquire() as fd:
                self.assertIsInstance(fd, int)

    def test_live_os_lease_blocks_new_manager_until_released(self):
        with tempfile.TemporaryDirectory() as temp:
            slots = AgentSlots(temp, 1)
            acquired = threading.Event()
            def waiter():
                with slots.acquire():
                    acquired.set()
            with (Path(temp) / '000.lock').open('a') as live:
                fcntl.flock(live, fcntl.LOCK_EX | fcntl.LOCK_NB)
                with ThreadPoolExecutor(1) as pool:
                    future = pool.submit(waiter)
                    self.assertFalse(acquired.wait(0.05))
                    fcntl.flock(live, fcntl.LOCK_UN)
                    future.result(2)
            self.assertTrue(acquired.is_set())


if __name__ == '__main__':
    unittest.main()
