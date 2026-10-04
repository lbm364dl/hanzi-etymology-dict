import json, time
from collections import defaultdict
from datetime import datetime
from pathlib import Path
r = Path(__file__).resolve().parent
queue = json.loads((r/'ziyuan-2012/queue.json').read_text())
seen = set(); calls=[]; chars={}; totals=defaultdict(lambda: {'calls':0,'seconds':0.0,'slot_wait_seconds':0.0})
for char, job in queue['jobs'].items():
    d=Path(job['job']); rows=[]
    for path in sorted(d.rglob('meta.json')):
        x=json.loads(path.read_text()); ids=x.get('agent_thread_ids') or []
        key=tuple(ids) if ids else (x.get('fingerprint'),x.get('started_at'),str(path))
        if key in seen: continue
        seen.add(key)
        seconds=max(0,x.get('finished_at',time.time())-x.get('started_at',time.time()))
        row={'character':char,'role':x.get('role'),'status':x.get('status'),'seconds':seconds,'slot_wait_seconds':x.get('slot_wait_seconds',0),'meta_path':str(path.relative_to(r)),'agent_thread_ids':ids,'model':x.get('model'),'reasoning':x.get('reasoning')}
        rows.append(row);calls.append(row)
        t=totals[row['role']];t['calls']+=1;t['seconds']+=seconds;t['slot_wait_seconds']+=row['slot_wait_seconds']
    start=datetime.fromisoformat(job['started_at']).timestamp()
    end=datetime.fromisoformat(job.get('finished_at',queue.get('updated_at'))).timestamp()
    chars[char]={'status':job['status'],'wall_seconds':end-start,'calls':len(rows),'model_seconds':sum(x['seconds'] for x in rows),'slot_wait_seconds':sum(x['slot_wait_seconds'] for x in rows),'stages':rows}
measurement=json.loads((r/'measurement.json').read_text())
network={'samples':0,'observed_worker_tcp_delta_bytes':{'bytes_sent':0,'bytes_received':0,'bytes_acked':0},'worker_process_identities':{},'limitations':['Interface totals include other programs.','TCP deltas include only observed live sockets and may miss short-lived connections.','TCP counters are not exact internet usage.']}
first=None;last=None
for line in (r/'network.jsonl').open():
    x=json.loads(line);network['samples']+=1;first=first or x;last=x
    owned={str(y['pid']):y for y in x['pid_identity_history'] if str(y.get('stage_output_path') or '').startswith(str(r))}
    for pid, identity in owned.items():
        network['worker_process_identities'][pid]=identity
        for field in network['observed_worker_tcp_delta_bytes']:
            network['observed_worker_tcp_delta_bytes'][field]+=x['tcp_pid_observed_delta_bytes'].get(pid,{}).get(field,0)
network['interface_delta_bytes']={}
if first and last:
    for name, final in last['interfaces'].items():
        initial=first['interfaces'].get(name)
        if initial:
            network['interface_delta_bytes'][name]={field:final[field]-initial[field] for field in ['rx_bytes','tx_bytes']}
summary={'measurement':measurement,'characters':chars,'unique_calls':len(calls),'by_role':dict(totals),'calls':calls,'network':network}
(r/'timing.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'measurement':measurement,'characters':{c:{k:v for k,v in x.items() if k!='stages'} for c,x in chars.items()},'by_role':dict(totals),'network_samples':network['samples']},ensure_ascii=False,indent=2))
