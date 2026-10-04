import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from pipeline import network_sampling as sampling


SS_FIXTURE = '''ESTAB 0 0 192.0.2.10:43100 198.51.100.4:443 users:(("codex",pid=1201,fd=8))
\t cubic rtt:2.1/0.2 bytes_sent:100 bytes_acked:98 bytes_received:250
ESTAB 0 0 192.0.2.10:43102 198.51.100.5:443 users:(("codex",pid=1201,fd=9))
\t cubic rtt:3.1/0.2 bytes_sent:40 bytes_acked:39 bytes_received:50
ESTAB 0 0 192.0.2.10:43104 203.0.113.7:443 users:(("chrome",pid=2202,fd=11))
\t cubic bytes_sent:12 bytes_received:18
'''


class NetworkSamplingTests(unittest.TestCase):
    @staticmethod
    def write_fake_process(proc_root, pid, starttime, argv):
        directory = Path(proc_root) / str(pid)
        directory.mkdir(parents=True, exist_ok=True)
        # /proc/PID/stat fields after comm begin with state (field 3); starttime
        # is field 22, offset 19 in that remainder.
        (directory / 'stat').write_text(
            f'{pid} (python3) S ' + ' '.join(['0'] * 18) + f' {starttime}\n')
        (directory / 'comm').write_text('python3\n')
        (directory / 'cmdline').write_bytes(b'\0'.join(x.encode() for x in argv) + b'\0')
        for name in ('cwd', 'exe'):
            path = directory / name
            if path.exists() or path.is_symlink():
                path.unlink()
        (directory / 'cwd').symlink_to('/work/repo')
        (directory / 'exe').symlink_to('/usr/bin/python3')

    def test_process_identity_retains_only_safe_command_identity(self):
        with tempfile.TemporaryDirectory() as temporary:
            self.write_fake_process(temporary, 1201, 98765, [
                '/usr/bin/python3', '-m', 'pipeline.editorial', '--token',
                'secret-value', '--output', 'runs/stage/5927',
            ])
            identity = sampling.read_process_identity(1201, temporary)
        self.assertEqual(identity, {
            'pid': 1201,
            'starttime_ticks': 98765,
            'comm': 'python3',
            'executable_basename': 'python3',
            'cwd': '/work/repo',
            'stage_output_path': 'runs/stage/5927',
        })
        self.assertNotIn('secret-value', json.dumps(identity))

    def test_process_history_survives_exit_and_distinguishes_pid_reuse(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.write_fake_process(root, 1201, 100, [
                '/usr/bin/python3', '-o', 'runs/stage/old', '--secret', 'not-retained'])
            proc_file = root / 'dev'
            proc_file.write_text('lo: 100 0 0 0 0 0 0 0 200 0 0 0 0 0 0 0\n')
            runner = sampling.NetworkSampler(root/'samples.jsonl', proc_net_dev=proc_file,
                proc_root=root, ss_path='/fixture/ss', clock=iter([1.0, 2.0, 3.0]).__next__,
                wall_clock=iter(['manifest', 't1', 't2', 't3']).__next__)
            rows1 = SS_FIXTURE.replace('pid=2202', 'pid=1201')
            rows2 = ''
            rows3 = SS_FIXTURE.replace('pid=2202', 'pid=1201')
            results = [
                type('Version', (), {'returncode':0,'stdout':'ss test','stderr':''})(),
                type('Result', (), {'returncode':0,'stdout':rows1,'stderr':''})(),
                type('Result', (), {'returncode':0,'stdout':rows2,'stderr':''})(),
                type('Result', (), {'returncode':0,'stdout':rows3,'stderr':''})(),
            ]
            with patch.object(sampling.subprocess, 'run', side_effect=results):
                first = runner.sample()
                first_history = json.loads(json.dumps(first['pid_identity_history']))
                second = runner.sample()
                self.write_fake_process(root, 1201, 200, [
                    '/usr/bin/python3', '-o', 'runs/stage/new', '--secret', 'also-hidden'])
                third = runner.sample()
        old_identity = next(x for x in first_history
                            if x['starttime_ticks'] == 100)
        old_retained = next(x for x in second['pid_identity_history']
                            if x['starttime_ticks'] == 100)
        new_identity = next(x for x in third['pid_identity_history']
                            if x['starttime_ticks'] == 200)
        self.assertTrue(old_identity['currently_visible'])
        self.assertFalse(old_retained['currently_visible'])
        self.assertEqual(old_retained['stage_output_path'], 'runs/stage/old')
        self.assertTrue(new_identity['currently_visible'])
        self.assertEqual(new_identity['stage_output_path'], 'runs/stage/new')
        self.assertNotIn('also-hidden', json.dumps(third))

    def test_proc_net_dev_parser_and_interface_deltas(self):
        text = '''Inter-| Receive | Transmit
 face |bytes packets errs drop fifo frame compressed multicast|bytes packets errs drop fifo colls carrier compressed
    lo: 100 0 0 0 0 0 0 0 200 0 0 0 0 0 0 0
  wlan0: 300 0 0 0 0 0 0 0 400 0 0 0 0 0 0 0
'''
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'dev'
            path.write_text(text)
            first = sampling.read_interface_counters(path)
        self.assertEqual(first['lo'], {'rx_bytes':100, 'tx_bytes':200})
        self.assertEqual(first['wlan0'], {'rx_bytes':300, 'tx_bytes':400})
        current = {'lo': {'rx_bytes':115, 'tx_bytes':220},
                   'wlan0': {'rx_bytes':330, 'tx_bytes':450},
                   'new0': {'rx_bytes':5, 'tx_bytes':7}}
        self.assertEqual(sampling.interface_deltas(first, current), {
            'lo': {'rx_bytes':15, 'tx_bytes':20},
            'wlan0': {'rx_bytes':30, 'tx_bytes':50}})
        reset = {'lo': {'rx_bytes':1, 'tx_bytes':0}}
        self.assertEqual(sampling.interface_deltas(first, reset), {'lo': None})

    def test_ss_parser_groups_live_socket_bytes_by_pid(self):
        rows = sampling.parse_ss_tcp(SS_FIXTURE)
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0]['pid'], 1201)
        self.assertEqual(rows[0]['process'], 'codex')
        self.assertEqual(rows[0]['fd'], 8)
        grouped = sampling.group_tcp_by_pid(rows)
        self.assertEqual(grouped[1201], {
            'process':'codex','socket_count':2,'bytes_sent':140,
            'bytes_received':300,'bytes_acked':137,
            'counter_fields_available':['bytes_acked','bytes_received','bytes_sent']})
        self.assertEqual(grouped[2202]['socket_count'], 1)
        self.assertEqual(grouped[2202]['bytes_received'], 18)

    def test_missing_ss_byte_fields_are_not_misrepresented_as_observed_zero(self):
        rows = sampling.parse_ss_tcp(
            'ESTAB 0 0 192.0.2.1:1 198.51.100.2:443 users:(("codex",pid=3,fd=8))\n'
            '\t cubic rtt:2.1/0.2\n')
        grouped = sampling.group_tcp_by_pid(rows)
        self.assertEqual(grouped[3]['counter_fields_available'], [])
        self.assertEqual(grouped[3]['bytes_sent'], 0)

    def test_socket_counter_deltas_only_count_persistent_sockets(self):
        old = sampling.parse_ss_tcp(SS_FIXTURE)
        new = sampling.parse_ss_tcp(SS_FIXTURE.replace(
            'bytes_sent:100 bytes_acked:98 bytes_received:250',
            'bytes_sent:115 bytes_acked:110 bytes_received:270'))
        delta, resets = sampling.tcp_socket_deltas(old, new)
        self.assertEqual(delta[1201], {'bytes_sent':15,'bytes_received':20,'bytes_acked':12,
            'counter_fields_available':['bytes_acked','bytes_received','bytes_sent']})
        self.assertEqual(resets, [])
        reset = sampling.parse_ss_tcp(SS_FIXTURE.replace(
            'bytes_sent:100 bytes_acked:98 bytes_received:250',
            'bytes_sent:2 bytes_acked:1 bytes_received:4'))
        delta, resets = sampling.tcp_socket_deltas(old, reset)
        self.assertEqual(delta[1201]['bytes_sent'], 0)
        self.assertEqual(resets[0]['counter'], 'bytes_sent')

    def test_sampler_retains_time_series_and_explicit_scope_metadata(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output = root / 'samples.jsonl'
            proc_file = root / 'dev'
            proc_file.write_text('lo: 100 0 0 0 0 0 0 0 200 0 0 0 0 0 0 0\n')
            clock_values = iter([1.0, 2.0])
            runner = sampling.NetworkSampler(output, interval=1, proc_net_dev=proc_file,
                ss_path='/fixture/ss', clock=lambda: next(clock_values),
                wall_clock=lambda: '2026-10-04T10:00:00Z')
            completed = [type('Result', (), {'returncode':0,'stdout':SS_FIXTURE,'stderr':''})(),
                         type('Result', (), {'returncode':0,'stdout':SS_FIXTURE.replace(
                             'bytes_sent:100 bytes_acked:98 bytes_received:250',
                             'bytes_sent:115 bytes_acked:110 bytes_received:270'),
                             'stderr':''})()]
            with patch.object(sampling.subprocess, 'run',
                              side_effect=[type('Version', (), {'returncode':0,'stdout':'ss test','stderr':''})(),
                                            completed[0], completed[1]]):
                one = runner.sample()
                proc_file.write_text('lo: 125 0 0 0 0 0 0 0 240 0 0 0 0 0 0 0\n')
                two = runner.sample()
            self.assertEqual(one['tcp_socket_count'], 3)
            self.assertEqual(two['interface_delta_bytes']['lo'], {'rx_bytes':25,'tx_bytes':40})
            self.assertEqual(two['tcp_pid_observed_delta_bytes'][1201]['bytes_received'], 20)
            lines = output.read_text().splitlines()
            self.assertEqual(len(lines), 2)
            manifest = json.loads(Path(str(output)+'.meta.json').read_text())
            self.assertEqual(manifest['interface_scope'], 'current network namespace')
            self.assertIn('visible live TCP sockets', manifest['tcp_counter_scope'])

    def test_missing_ss_is_reported_as_unavailable_not_zero(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            proc_file = root / 'dev'
            proc_file.write_text('lo: 1 0 0 0 0 0 0 0 1 0 0 0 0 0 0 0\n')
            with patch.object(sampling.shutil, 'which', return_value=None):
                sampler = sampling.NetworkSampler(root/'samples.jsonl', proc_net_dev=proc_file)
                sample = sampler.sample()
            self.assertFalse(sample['tcp_ss_available'])
            self.assertIn('not found', sample['tcp_ss_error'])
            self.assertEqual(sample['tcp_pid_visible_socket_totals'], {})


if __name__ == '__main__':
    unittest.main()
