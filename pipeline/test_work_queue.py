import concurrent.futures
import copy
import sys
import fcntl
from pathlib import Path
import tempfile
import threading
import unittest

from pipeline import editorial, work_queue


class WorkQueueTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.path = self.root / 'queue.json'
        self.characters = [chr(0x4e00 + i) for i in range(100)]
        self.identity = {'characters': self.characters, 'source': 'fixture'}

    def queue(self):
        return work_queue.Queue(self.path, self.identity)

    def execute(self, queue, process, **kwargs):
        return queue.execute(self.characters, process, lambda char: self.root / f'{ord(char):04X}',
                             {}, kwargs.pop('workers', 24), kwargs.pop('limit', 100), **kwargs)

    def test_24_workers_100_jobs_checkpoint_fast_completions_before_slow_first(self):
        first_release, first_started, enough = threading.Event(), threading.Event(), threading.Event()
        active = peak = finished = 0
        lock = threading.Lock()
        def process(char):
            nonlocal active, peak, finished
            with lock:
                active += 1
                peak = max(peak, active)
            if char == self.characters[0]:
                first_started.set()
                if not first_release.wait(10):
                    raise RuntimeError('Test failed to release first job')
            else:
                first_started.wait(10)
                with lock:
                    finished += 1
                    if finished >= 80:
                        enough.set()
                # Keep peers in flight long enough to exercise the configured pool.
                enough.wait(0.01)
            with lock:
                active -= 1
            return {'character': char, 'status': 'approved'}
        with concurrent.futures.ThreadPoolExecutor(1) as outer:
            future = outer.submit(self.execute, self.queue(), process)
            try:
                self.assertTrue(enough.wait(10))
                saved = editorial.read(self.path)
                completed = [j for j in saved['jobs'].values() if j['status'] == 'approved']
                self.assertGreater(len(completed), 20)
                self.assertEqual(saved['jobs'][self.characters[0]]['status'], 'running')
            finally:
                first_release.set()
            rows = future.result(10)
        self.assertEqual(len(rows), 100)
        self.assertTrue(all(row['status'] == 'approved' for row in rows))
        self.assertLessEqual(peak, 24)
        self.assertGreater(peak, 3)
        self.assertEqual(editorial.read(self.path)['status'], 'idle')

    def test_attention_does_not_consume_next_selection_and_explicit_retry_preserves_history(self):
        calls = []
        def fail(char):
            calls.append(char)
            return {'character': char, 'status': 'needs_source_verification'}
        self.execute(self.queue(), fail, limit=2)
        self.execute(self.queue(), fail, limit=2)
        self.assertEqual(calls, self.characters[:4])
        rows = self.execute(self.queue(), fail, limit=100, retry_attention=True)
        self.assertEqual(len(calls), 104)
        saved = editorial.read(self.path)
        self.assertEqual(saved['jobs'][self.characters[0]]['attempts'], 2)
        self.assertEqual(len(saved['jobs'][self.characters[0]]['history']), 2)
        self.assertEqual(rows[0]['status'], 'needs_source_verification')

    def test_crash_recovery_reclaims_running_even_with_older_failed_result(self):
        queue = self.queue()
        char = self.characters[0]
        queue.state['jobs'][char] = {'status': 'running', 'attempts': 1, 'history': [],
                                    'result': {'character': char, 'status': 'failed'}}
        queue.checkpoint()
        # Other pending work is selected first; an abandoned claim is still recoverable.
        rows = self.execute(self.queue(), lambda char: {'character': char, 'status': 'approved'})
        self.assertEqual(rows[0]['status'], 'approved')
        self.assertEqual(editorial.read(self.path)['jobs'][char]['attempts'], 2)

    def test_returned_failure_held_even_if_stage_still_says_running(self):
        char = self.characters[0]
        editorial.write(self.root / f'{ord(char):04X}' / 'status.json', {'status': 'running'})
        def fail(char):
            raise RuntimeError('fixture stage timeout')
        self.execute(self.queue(), fail, limit=1)
        calls = []
        rows = self.execute(self.queue(), lambda char: calls.append(char) or
                            {'character': char, 'status': 'approved'}, limit=1)
        self.assertEqual(calls, [self.characters[1]])
        self.assertTrue(rows[0]['attention_required'])

    def test_running_lock_is_not_completion_or_attention_and_other_jobs_continue(self):
        char = self.characters[0]
        rows = self.execute(self.queue(), lambda char: {'character': char, 'status': 'already_running'}, limit=1)
        self.assertEqual(rows[0]['status'], 'already_running')
        calls = []
        self.execute(self.queue(), lambda char: calls.append(char) or
                     {'character': char, 'status': 'approved'}, limit=1)
        self.assertEqual(calls, [self.characters[1]])

    def test_queue_identity_change_and_second_live_supervisor_rejected(self):
        self.queue().checkpoint()
        with self.assertRaisesRegex(ValueError, 'inputs changed'):
            work_queue.Queue(self.path, {'source': 'changed'})
        lock_path = self.root / 'queue.lock'
        with work_queue.supervisor(lock_path):
            with self.assertRaisesRegex(RuntimeError, 'live supervisor'):
                with work_queue.supervisor(lock_path):
                    pass
        with work_queue.supervisor(lock_path):
            pass

    def test_parallel_stage_subprocesses_have_distinct_receipts_and_reuse_exact_cache(self):
        script = self.root / 'stage.py'
        script.write_text(
            'import json,pathlib,sys\n'
            'packet=json.JSONDecoder().raw_decode(sys.stdin.read().split("\\nINPUTS:\\n",1)[1])[0]\n'
            'pathlib.Path(sys.argv[1]).write_text(json.dumps({"character":packet["character"]}))\n')
        runner = editorial.Runner([sys.executable, str(script), '{output}'], model='fixture')
        schema = {'type': 'object', 'required': ['character'],
                  'properties': {'character': {'type': 'string'}}, 'additionalProperties': False}
        def process(char):
            local = copy.copy(runner)
            directory = self.root / f'{ord(char):04X}' / 'stage'
            result = local.run('prose_repair', {'character': char}, schema, directory)
            return {'character': result['character'], 'status': 'fixture_complete'}
        self.execute(self.queue(), process, limit=24)
        metas = {char: editorial.read(self.root / f'{ord(char):04X}' / 'stage/meta.json')
                 for char in self.characters[:24]}
        self.assertEqual(len({m['fingerprint'] for m in metas.values()}), 24)
        self.assertTrue(all(m['status'] == 'complete' for m in metas.values()))
        # Cached invocation succeeds even if launching the stage process would fail.
        script.unlink()
        with concurrent.futures.ThreadPoolExecutor(24) as pool:
            for row in pool.map(process, self.characters[:24]):
                self.assertEqual(row['status'], 'fixture_complete')
        for char, meta in metas.items():
            self.assertEqual(editorial.read(self.root / f'{ord(char):04X}' / 'stage/meta.json'), meta)

    def test_simultaneous_atomic_writers_never_share_temp_file_or_partial_json(self):
        path = self.root / 'shared.json'
        editorial.write(path, {'writer': -1, 'data': 'x' * 10000})
        start = threading.Barrier(25)
        def writer(i):
            start.wait()
            for _ in range(10):
                editorial.write(path, {'writer': i, 'data': str(i) * 10000})
                self.assertIn(editorial.read(path)['writer'], range(24))
        with concurrent.futures.ThreadPoolExecutor(24) as pool:
            futures = [pool.submit(writer, i) for i in range(24)]
            start.wait()
            for future in futures:
                future.result(10)
        self.assertFalse(list(self.root.glob('*.tmp')))


if __name__ == '__main__':
    unittest.main()
