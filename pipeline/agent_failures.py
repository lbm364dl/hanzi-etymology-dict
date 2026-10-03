"""Classify failed calls from retained transport diagnostics, without inferring reviews."""
import re
import subprocess
from pathlib import Path


def failure_metadata(error, directory):
    path = Path(directory) / 'stderr.log'
    try:
        # Bound the read; only predefined diagnostic names enter metadata.
        with path.open('rb') as stream:
            stream.seek(0, 2)
            stream.seek(max(0, stream.tell() - 65536))
            stderr = stream.read().decode('utf-8', errors='replace')
    except OSError:
        stderr = ''
    patterns = {
        'dns_lookup_failed': r'failed to lookup address information|temporary failure in name resolution',
        'websocket_connect_failed': r'failed to connect to websocket',
        'models_refresh_timeout': r'failed to refresh available models: request timed out',
        'rate_limit': r'\b429\b|rate limit exceeded|rate_limit_exceeded',
    }
    diagnostics = [name for name, pattern in patterns.items()
                   if re.search(pattern, stderr, re.I)]
    if isinstance(error, subprocess.TimeoutExpired):
        kind = 'transport_timeout' if diagnostics else 'agent_timeout'
    elif diagnostics:
        # Transport symptoms can accompany a distinct validation failure. Do not
        # claim that the model did no work or that retrying must resolve it.
        kind = 'failed_with_transport_diagnostics'
    else:
        kind = 'agent_or_validation_failure'
    return {'failure_kind': kind, 'transport_diagnostics': diagnostics,
            'stderr_artifact': str(path)}
