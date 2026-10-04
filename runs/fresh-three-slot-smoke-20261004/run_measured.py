import json, subprocess, sys, time
from pathlib import Path
root = Path('/home/catalin/hanzi-etymology-dict')
out = root / 'runs/fresh-three-slot-smoke-20261004'
started = time.time()
netlog = (out / 'network-sampler.log').open('w')
sampler = subprocess.Popen([sys.executable, '-m', 'pipeline.network_sampling', '--output', str(out / 'network.jsonl'), '--interval', '5', '--duration', '7200'], cwd=root, stdout=netlog, stderr=subprocess.STDOUT)
cmd = [sys.executable, '-m', 'pipeline.source_enrichment', 'run', '--registry', 'research/digitised-sources.json', '--source', 'ziyuan-2012', '--cohort', str(out / 'cohort.json'), '--output', str(out), '--limit', '3', '--workers', '3', '--agents', '3', '--timeout', '600', '--publish-now', '--research-context', str(out / 'research-context.json'), '--tracking-issue-url', 'https://github.com/lbm364dl/hanzi-etymology-dict/issues/344']
proc = None
try:
    with (out / 'supervisor.log').open('w') as log:
        proc = subprocess.Popen(cmd, cwd=root, stdout=log, stderr=subprocess.STDOUT)
        (out / 'measurement.json').write_text(json.dumps({'started_at':started,'supervisor_pid':proc.pid,'sampler_pid':sampler.pid,'workers':3,'agents':3,'model':'gpt-6-luna','reasoning':'low','status':'running'},indent=2))
        rc = proc.wait()
finally:
    sampler.terminate()
    try: sampler.wait(timeout=10)
    except subprocess.TimeoutExpired:
        sampler.kill(); sampler.wait()
    netlog.close()
ended = time.time()
(out / 'measurement.json').write_text(json.dumps({'started_at':started,'ended_at':ended,'duration_seconds':ended-started,'supervisor_pid':proc.pid,'sampler_pid':sampler.pid,'workers':3,'agents':3,'model':'gpt-6-luna','reasoning':'low','exit_code':rc,'status':'complete'},indent=2))
print(json.dumps({'status':'complete','exit_code':rc,'elapsed_seconds':ended-started}))
