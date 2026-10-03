import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from pipeline import dashboard, dashboard_github, dashboard_workspace
from unittest.mock import patch
import subprocess


class DashboardTests(unittest.TestCase):
    def test_git_observer_does_not_take_optional_index_locks_or_trim_porcelain(self):
        commands = []
        def invoke(command, **kwargs):
            commands.append(command)
            text = {'status': ' M pipeline/README.md\n', 'branch': 'test-branch\n',
                    'rev-parse': 'abc123\n'}[command[2]]
            return subprocess.CompletedProcess(command, 0, text, '')
        with tempfile.TemporaryDirectory() as temp, patch.object(dashboard_workspace.subprocess, 'run', invoke):
            snapshot = dashboard_workspace.Workspace(temp).snapshot()
        self.assertEqual(snapshot['repository']['changes'],
                         [{'status': 'M', 'path': 'pipeline/README.md'}])
        self.assertTrue(all(command[1] == '--no-optional-locks' for command in commands))

    def test_artifact_reader_rejects_traversal_absolute_paths_and_symlink_escape(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            root = base / 'repo'
            (root / 'runs').mkdir(parents=True)
            (root / 'runs/status.json').write_text('{}')
            (base / 'outside.json').write_text('{}')
            (root / 'runs/escape.json').symlink_to(base / 'outside.json')
            self.assertEqual(dashboard.artifact_path(root, 'runs/status.json'), root / 'runs/status.json')
            for path in ('../outside.json', str(base / 'outside.json'), 'runs/escape.json', 'AGENTS.md'):
                with self.assertRaises((ValueError, FileNotFoundError)):
                    dashboard.artifact_path(root, path)

    def test_live_feed_retains_last_snapshot_when_collector_fails(self):
        reached = threading.Event()
        class Collector:
            calls = 0
            def snapshot(self):
                self.calls += 1
                if self.calls == 1:
                    return {'generated_at': 'fixture-time', 'jobs': [{'character': '木', 'status': 'running'}]}
                reached.set()
                raise ValueError('fixture collector failure')
        feed = dashboard.Feed(Collector(), interval=0.05)
        feed.start()
        try:
            self.assertTrue(reached.wait(2))
            with feed.condition:
                feed.condition.wait_for(lambda: feed.snapshot.get('collector_status') == 'error', timeout=2)
            self.assertEqual(feed.snapshot['jobs'][0]['status'], 'running')
            self.assertIn('fixture collector failure', feed.snapshot['collector_error'])
        finally:
            feed.close()

    def test_github_timeout_retains_previous_remote_state_and_never_exposes_command_errors(self):
        feed = dashboard_github.GitHubFeed(['owner/repo'])
        response = subprocess.CompletedProcess([], 0, '[{"number":1,"state":"OPEN"}]', '')
        with patch('pipeline.dashboard_github.subprocess.run', return_value=response) as invoke:
            feed.refresh()
            self.assertEqual(invoke.call_args.kwargs['timeout'], 12)
        self.assertEqual(feed.snapshot()['issues'][0]['state'], 'OPEN')
        with patch('pipeline.dashboard_github.subprocess.run',
                   side_effect=subprocess.TimeoutExpired('fixture-command', 12)):
            feed.refresh()
        self.assertEqual(feed.snapshot()['status'], 'error')
        self.assertEqual(feed.snapshot()['issues'][0]['state'], 'OPEN')
        self.assertEqual(feed.snapshot()['errors'][0]['error'], 'TimeoutExpired')

    def test_http_state_etag_and_json_artifact_routes(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'runs').mkdir()
            (root / 'runs/meta.json').write_text('{"role":"research"}')
            feed = dashboard.Feed(None)
            server = dashboard.Server(('127.0.0.1', 0), root, feed)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = f'http://127.0.0.1:{server.server_port}'
            try:
                with urlopen(base + '/api/state') as response:
                    etag = response.headers['ETag']
                    self.assertEqual(json.load(response)['collector_status'], 'starting')
                with self.assertRaises(HTTPError) as error:
                    urlopen(Request(base + '/api/state', headers={'If-None-Match': etag}))
                self.assertEqual(error.exception.code, 304)
                with urlopen(base + '/api/artifact?path=runs/meta.json') as response:
                    self.assertEqual(json.load(response), {'role': 'research'})
                with self.assertRaises(HTTPError) as error:
                    urlopen(base + '/api/artifact?path=../../etc/passwd')
                self.assertEqual(error.exception.code, 400)
                with urlopen(base + '/health') as response:
                    self.assertEqual(json.load(response)['status'], 'starting')
            finally:
                feed.close()
                server.shutdown()
                server.server_close()
                thread.join(2)


if __name__ == '__main__':
    unittest.main()
