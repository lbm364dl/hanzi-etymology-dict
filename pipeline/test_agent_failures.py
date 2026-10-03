import subprocess
import tempfile
import unittest
from pathlib import Path

from pipeline.agent_failures import failure_metadata


class AgentFailureTests(unittest.TestCase):
    def test_timeout_requires_observed_transport_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            error = subprocess.TimeoutExpired(['codex'], 600)
            self.assertEqual(failure_metadata(error, directory)['failure_kind'], 'agent_timeout')
            Path(directory, 'stderr.log').write_text(
                'failed to connect to websocket: failed to lookup address information: Try again\n'
                'failed to refresh available models: request timed out\n')
            result = failure_metadata(error, directory)
            self.assertEqual(result['failure_kind'], 'transport_timeout')
            self.assertEqual(result['transport_diagnostics'], [
                'dns_lookup_failed', 'websocket_connect_failed', 'models_refresh_timeout'])

    def test_transport_diagnostic_does_not_reclassify_validation_as_timeout(self):
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, 'stderr.log').write_text('rate_limit_exceeded secret-token-not-to-copy')
            result = failure_metadata(ValueError('invalid component role'), directory)
            self.assertEqual(result['failure_kind'], 'failed_with_transport_diagnostics')
            self.assertNotIn('secret-token', str(result))

    def test_validation_without_transport_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            result = failure_metadata(ValueError('invalid schema'), directory)
            self.assertEqual(result['failure_kind'], 'agent_or_validation_failure')
            self.assertEqual(result['transport_diagnostics'], [])
