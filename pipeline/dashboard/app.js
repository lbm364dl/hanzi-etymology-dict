(() => {
  'use strict';
  const POLL_MS = 2000;
  const $ = (selector, root = document) => root.querySelector(selector);
  const el = (id) => document.getElementById(id);
  const state = { snapshot: null, jobs: [], selected: null, query: '', status: 'all', source: 'all', lastSuccess: 0, timer: 0, toastTimer: 0, loadSamples: [], showHistory: false };
  const escapeHtml = (value) => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const val = (obj, ...keys) => { for (const k of keys) if (obj && obj[k] !== undefined && obj[k] !== null) return obj[k]; return ''; };
  const asArray = v => Array.isArray(v) ? v : [];
  const numeric = v => v === null || v === undefined || v === '' || typeof v === 'boolean' ? null : Number.isFinite(Number(v)) ? Number(v) : null;
  const statusText = s => String(s || 'unknown').replace(/[_-]+/g,' ').replace(/\b\w/g, c => c.toUpperCase());
  const slug = s => String(s || 'unknown').toLowerCase().replace(/[^a-z0-9_-]+/g,'_');
  const iso = v => { if (v === null || v === undefined || v === '') return null; if (typeof v === 'number' || (typeof v === 'string' && /^\d+(?:\.\d+)?$/.test(v.trim()))) { let n=Number(v); if(!Number.isFinite(n)) return null; if(n < 1e12) n*=1000; const d=new Date(n); return Number.isNaN(d.getTime())?null:d; } const d=new Date(v); return Number.isNaN(d.getTime()) ? null : d; };
  const absoluteTime = v => { const d = iso(v); return d ? d.toLocaleString([], {month:'short',day:'numeric',hour:'2-digit',minute:'2-digit',second:'2-digit'}) : 'Time unavailable'; };
  function age(v) {
    const d = iso(v); if (!d) return 'time unknown';
    const seconds = Math.max(0, Math.floor((Date.now()-d.getTime())/1000));
    if (seconds < 60) return `${seconds}s ago`;
    if (seconds < 3600) return `${Math.floor(seconds/60)}m ago`;
    if (seconds < 86400) return `${Math.floor(seconds/3600)}h ago`;
    return `${Math.floor(seconds/86400)}d ago`;
  }
  function bytes(n) {
    const x = numeric(n); if (x === null) return '—';
    if (x < 1024) return `${Math.round(x)} B`;
    const units=['KiB','MiB','GiB','TiB']; let v=x/1024, i=0; while(v>=1024 && i<units.length-1){v/=1024;i++;}
    return `${v>=100?Math.round(v):v.toFixed(1)} ${units[i]}`;
  }
  function fullHash(s) { return s ? String(s) : 'not recorded'; }
  function safeGitHubUrl(raw) {
    try { const u = new URL(raw, location.origin); return u.protocol === 'https:' && (u.hostname === 'github.com' || u.hostname.endsWith('.github.com')) ? u.href : ''; } catch { return ''; }
  }
  function artifactUrl(path) {
    if (!path || typeof path !== 'string') return '';
    return `/api/artifact?path=${encodeURIComponent(path.replace(/^\/+/,''))}`;
  }
  function statusBucket(s) {
    const x=String(s||'').toLowerCase();
    if (/fail|block|needs_revision|needs_source|attention|error|reject/.test(x)) return 'attention';
    if (/complete|approved|published|passed|done|success/.test(x)) return 'complete';
    if (/running|active|research|review|queued|in_progress|working|waiting_for_agent_slot/.test(x)) return 'active';
    return 'other';
  }
  function jobPath(j) {
    const nested=j?.job && typeof j.job==='object' ? j.job : {};
    return val(j,'actual_path','job_path') || val(nested,'actual_path','job_path','path') || (val(j,'path') && !j.queue_path ? j.path : '') || '';
  }
  function characterOf(j) {
    const nested=j?.job && typeof j.job==='object' ? j.job : {};
    return val(j,'character','hanzi','glyph','key') || val(nested,'character','hanzi','glyph','key') || '?';
  }
  function normalizedRecord(raw, queue=null) {
    const nested=raw?.job && typeof raw.job==='object' ? raw.job : {};
    const row={...nested,...raw};
    delete row.job;
    const path=(typeof raw?.job==='string'?raw.job:'') || jobPath(raw) || jobPath(nested);
    const source=val(raw,'source_id','queue_source_id') || val(nested,'source_id') || val(queue,'source_id') || 'unassigned';
    const qpath=val(raw,'queue_path') || val(queue,'path') || '';
    const character=characterOf(raw);
    const queuedWithoutPath=Boolean(queue && !path);
    const id=val(nested,'id','job_id') || val(raw,'id','job_id') || '';
    const key=path?`${source}::${path}`:queuedWithoutPath?`${source}::queued::${qpath}::${character}`:id?`${source}::id::${id}`:`${source}::${character}`;
    return {...row, id:id||row.id||'', _key:key, _character:character, _source:source, _path:path, _queue_path:qpath, _queue_status:queue?(val(raw,'status','queue_status')||val(nested,'status','queue_status')||''):(val(raw,'queue_status')||val(nested,'queue_status')||''), _queue_state:val(queue,'status')||'', _current_queue:Boolean(queue), _placeholder:queuedWithoutPath};
  }
  function mergeJob(base, incoming) {
    const out={...base};
    if(incoming._current_queue)out._current_queue=true;
    for(const [key,value] of Object.entries(incoming)){
      if(key==='_current_queue')continue;
      if(value===undefined||value===null||value==='')continue;
      if(out[key]===undefined||out[key]===null||out[key]==='')out[key]=value;
      else if(Array.isArray(value)&&Array.isArray(out[key]))out[key]=[...new Map([...out[key],...value].map(x=>[JSON.stringify(x),x])).values()];
    }
    return out;
  }
  function normalize(snapshot) {
    const map=new Map();
    // Inventory rows have actual job IDs and paths. Queue entries enrich these records;
    // queue-only character rows become explicit placeholders rather than duplicate jobs.
    for(const raw of asArray(snapshot.jobs)){
      const item=normalizedRecord(raw);
      const key=item._key;
      map.set(key,map.has(key)?mergeJob(map.get(key),item):item);
    }
    for(const q of asArray(snapshot.queues)){
      const qjobs=asArray(q.jobs);
      for(const raw of qjobs){
        const item=normalizedRecord(raw,q);
        const key=item._key;
        map.set(key,map.has(key)?mergeJob(map.get(key),item):item);
      }
      const listed=asArray(q.queued_characters||q.characters);
      for(const raw of listed){
        const row=typeof raw==='string'?{character:raw}:raw;
        const char=characterOf(row);
        if(char==='?' || [...map.values()].some(j=>j._current_queue&&j._source===String(q.source_id||'unassigned')&&j._character===char))continue;
        const item=normalizedRecord(row,q);
        if(!map.has(item._key))map.set(item._key,item);
      }
    }
    return [...map.values()].map(j=>({...j, _queue_path:j._queue_path||j.queue_path||'', _path:j._path||'', _character:j._character||'?', _source:j._source||'unassigned', _current_queue:Boolean(j._current_queue)}));
  }
  function isVerifiedLive(stage) {
    const l=stage?.liveness;
    if (l === true) return true;
    if (typeof l === 'string') {
      if (/^(live|alive|verified_live|process_live)$/i.test(l.trim())) return true;
      if (/^(stale|unknown|not_live|not_running|dead|saved)$/i.test(l.trim())) return false;
      if (/^running$/i.test(l.trim())) return Number.isInteger(Number(stage?.pid)) && Number(stage.pid)>0;
    }
    if (l && typeof l === 'object') {
      if (l.live === true || l.alive === true || l.verified === true && l.running === true) return true;
      if (l.live === false || l.alive === false || l.verified === false || l.stale === true) return false;
    }
    // If no liveness conclusion is supplied, a running status with a concrete PID is the collector's process observation.
    const livenessRecorded=l!==undefined&&l!==null&&l!=='';
    return !livenessRecorded && String(stage?.status||'').toLowerCase()==='running' && Number.isInteger(Number(stage?.pid)) && Number(stage.pid)>0;
  }
  function waitingForSlot(stage) {
    const l=stage?.liveness;
    if(l===false || l==='stale' || l==='dead' || l==='not_running' || (l&&typeof l==='object'&&(l.stale===true||l.live===false||l.alive===false)))return false;
    return stage?.waiting_for_agent_slot === true || /waiting_for_agent_slot|waiting for agent slot/i.test(String(stage?.status||''));
  }
  function allStages() {
    return state.jobs.flatMap(j=>asArray(j.active_stages).map(s=>({...s, _job:j})));
  }
  function isWaitingJob(j) { return asArray(j.active_stages).some(waitingForSlot) || /waiting_for_agent_slot/i.test(String(j.status||'')); }
  function isLiveJob(j) { return asArray(j.active_stages).some(isVerifiedLive) || (j._current_queue && /^(running|active)$/i.test(String(j._queue_status||''))); }
  function isQueuedJob(j) { return j._placeholder || /queued|pending|waiting/i.test(String(j.status||'')) || /queued|pending|waiting/i.test(String(j._queue_status||'')); }
  function displayStatus(j) {
    if(j._placeholder)return j._queue_status||j.status||'queued';
    if(j._current_queue&&statusBucket(j._queue_status)==='attention')return j._queue_status;
    if(statusBucket(j.status)==='attention')return j.status;
    return j._queue_status||j.status||'unknown';
  }
  function sortJobs(jobs) {
    const rank=j=>isLiveJob(j)?0:isWaitingJob(j)?1:statusBucket(j.status)==='attention'?2:isQueuedJob(j)?3:statusBucket(j.status)==='complete'?5:4;
    return [...jobs].sort((a,b)=>rank(a)-rank(b)||(iso(b.updated_at)?.getTime()||0)-(iso(a.updated_at)?.getTime()||0));
  }
  function reviewsFor(j) { return asArray(j.reviews); }
  function filteredJobs() {
    const q=state.query.trim().toLocaleLowerCase();
    const visible=state.showHistory?state.jobs:state.jobs.filter(j=>j._current_queue||isLiveJob(j)||isWaitingJob(j));
    return visible.filter(j=>{
      if(state.status!=='all' && statusBucket(displayStatus(j))!==state.status) return false;
      if(state.source!=='all' && String(j._source)!==state.source) return false;
      if(q){ const hay=[j._character,j._source,j.status,j._queue_status,j.id,j._path,j._queue_path,j.summary,j.issue_sync_status,...asArray(j.findings).map(x=>typeof x==='string'?x:JSON.stringify(x)),...asArray(j.issues).map(x=>x.key||x.number)].join(' ').toLocaleLowerCase(); if(!hay.includes(q)) return false; }
      return true;
    });
  }
  function updateUrl() {
    const u=new URL(location.href);
    if(state.query)u.searchParams.set('q',state.query);else u.searchParams.delete('q');
    if(state.status!=='all')u.searchParams.set('status',state.status);else u.searchParams.delete('status');
    if(state.source!=='all')u.searchParams.set('source',state.source);else u.searchParams.delete('source');
    if(state.showHistory)u.searchParams.set('history','1');else u.searchParams.delete('history');
    if(state.selected)u.hash=`job=${encodeURIComponent(state.selected)}`;else u.hash='';
    history.replaceState(null,'',u);
  }
  function restoreUrl() {
    const u=new URL(location.href); state.query=u.searchParams.get('q')||''; state.status=u.searchParams.get('status')||'all'; state.source=u.searchParams.get('source')||'all'; state.showHistory=u.searchParams.get('history')==='1';
    if(!['all','active','attention','complete','other'].includes(state.status))state.status='all';
    const m=u.hash.match(/^#job=(.*)$/); if(m){try{state.selected=decodeURIComponent(m[1]);}catch{state.selected=null;}}
    el('search').value=state.query; el('status-filter').value=state.status; el('history-toggle').checked=state.showHistory;
  }
  function queueCard(j) {
    const selected=j._key===state.selected?' selected':'';
    const reviewCount=reviewsFor(j).length;
    const active=asArray(j.active_stages).length;
    const queueStatus=j._queue_state?`queue ${statusText(j._queue_state)}`:'';
    const meta=[j._source, queueStatus, reviewCount?`${reviewCount} reviews`:'',active?`${active} stage${active===1?'':'s'}`:''].filter(Boolean).join(' · ');
    const title=j._placeholder?`${j._character} · queued (no job path yet)`:j._path||j.id||'Job';
    const cardStatus=displayStatus(j);
    return `<article class="queue-card${selected}" data-job="${escapeHtml(j._key)}" tabindex="0" role="button" aria-label="Open ${escapeHtml(j._character)} job details">
      <div class="queue-card-top"><span class="hanzi">${escapeHtml(j._character)}</span><div class="queue-title"><strong>${escapeHtml(title)}</strong><small>${escapeHtml(meta || 'Source not recorded')}</small></div><div class="queue-meta"><span class="status-badge status-${slug(cardStatus)}">${escapeHtml(statusText(cardStatus))}</span></div></div>
      ${j.summary?`<p class="queue-summary">${escapeHtml(j.summary)}</p>`:''}
      <div class="queue-footer"><span>${escapeHtml(val(j,'updated_at')?`${age(j.updated_at)} · ${absoluteTime(j.updated_at)}`:'Update time unavailable')}</span><span>${escapeHtml(j.issue_sync_status?`Issue sync ${statusText(j.issue_sync_status)}`:'')}</span></div>
    </article>`;
  }
  function renderQueues() {
    const filtered=sortJobs(filteredJobs());
    el('queue-list').innerHTML=filtered.length?filtered.map(queueCard).join(''):'<div class="empty-state">No jobs match these filters.</div>';
    const currentCount=state.jobs.filter(j=>j._current_queue||isLiveJob(j)||isWaitingJob(j)).length;
    el('queue-count').textContent=state.showHistory?`${filtered.length} shown · history included`:`${currentCount} current · history hidden`;
    el('queue-list').querySelectorAll('[data-job]').forEach(card=>{
      const open=()=>selectJob(card.dataset.job);
      card.addEventListener('click',open);card.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();open();}});
    });
  }
  function renderSources() {
    const select=el('source-filter'), current=state.source;
    const sources=[...new Set(state.jobs.map(j=>String(j._source)))].sort((a,b)=>a.localeCompare(b));
    select.innerHTML='<option value="all">All sources</option>'+sources.map(s=>`<option value="${escapeHtml(s)}">${escapeHtml(s)}</option>`).join('');
    select.value=sources.includes(current)?current:'all';state.source=select.value;
  }
  function renderStages() {
    const stages=allStages();
    const live=stages.filter(s=>isVerifiedLive(s));
    el('stage-count').innerHTML=`<i></i> ${live.length} verified live`;
    const queues=asArray(state.snapshot?.queues);
    const workerCap=queues.reduce((n,q)=>n+(numeric(q.workers)||0),0);
    const agentCap=Math.max(...queues.map(q=>numeric(q.agent_capacity)||0),...stages.map(s=>numeric(s.agent_capacity)||0),numeric(state.snapshot?.agent_capacity)||0);
    const waiting=stages.filter(waitingForSlot).length;
    el('capacity-strip').innerHTML=`<span>Queue workers <b>${workerCap||'—'} configured</b></span><span>Agent slots <b>${agentCap||'—'} capacity${waiting?` · ${waiting} waiting`:''}</b></span>`;
    if(!stages.length){el('stage-list').innerHTML='<div class="empty-state small-empty">No active stage records reported.</div>';return;}
    const rank=s=>isVerifiedLive(s)?0:waitingForSlot(s)?1:2;
    const ordered=[...stages].sort((a,b)=>rank(a)-rank(b)||(iso(b.started_at||b.updated_at)?.getTime()||0)-(iso(a.started_at||a.updated_at)?.getTime()||0));
    let previous=-1;
    const rows=ordered.map(s=>{
      const l=isVerifiedLive(s), waiting=waitingForSlot(s), role=val(s,'role')||'stage', j=s._job;
      const group=rank(s); let heading='';
      if(group!==previous){previous=group;heading=`<div class="stage-group-label">${group===0?'Verified live processes':group===1?'Waiting for agent slot':'Saved stage records'}</div>`;}
      const r=val(s,'rss_bytes')?` · ${bytes(s.rss_bytes)} RAM`:'';
      const pid=val(s,'pid')?`PID ${s.pid}`:'no process PID';
      const label=l?'LIVE':waiting?'WAITING':'SAVED';
      const stageModel=val(s,'model')||'Model not recorded';
      return `${heading}<div class="stage-row"><span class="stage-role">${escapeHtml(String(role).slice(0,1).toUpperCase())}</span><div class="stage-main"><strong>${escapeHtml(role)} · ${escapeHtml(j._character)}</strong><small>${escapeHtml(stageModel)} · ${escapeHtml(val(s,'reasoning')||'reasoning unrecorded')} · ${escapeHtml(pid+r)}${numeric(s.slot_wait_seconds)!==null?` · waiting ${Math.round(Number(s.slot_wait_seconds))}s`:''}</small></div><span class="stage-age ${waiting?'stage-waiting':l?'':'stage-saved'}" title="${escapeHtml(val(s,'started_at')?absoluteTime(s.started_at):'Start time unavailable')}">${label}<br>${escapeHtml(age(val(s,'started_at','updated_at')))}</span></div>`;
    }).join('');
    el('stage-list').innerHTML=rows;
  }
  function renderResources() {
    const m=state.snapshot?.machine||{};
    const cpus=numeric(val(m,'cpu_threads','cpu_count'));
    const load=asArray(m.load).map(numeric);
    const current=load.length?load[0]:null;
    const generated=iso(val(state.snapshot,'generated_at'));
    const sampledAt=generated?generated.getTime():Date.now();
    if(current!==null){
      const last=state.loadSamples.at(-1);
      if(!last || sampledAt>last.at)state.loadSamples.push({at:sampledAt,value:current});
      const cutoff=Date.now()-60000;
      state.loadSamples=state.loadSamples.filter(s=>s.at>=cutoff).slice(-45);
    }
    el('machine-chip').innerHTML=`<span class="chip-glyph">⌁</span><span>${cpus===null?'Machine status':`${cpus} CPU threads`}${current!==null?` · 1m load ${current.toFixed(2)}`:''}</span>`;
    const history=state.loadSamples;
    if(history.length>=2){
      const max=Math.max(1,...history.map(s=>s.value)),w=360,h=88,p=5;
      const t0=history[0].at,t1=history.at(-1).at,span=Math.max(1,t1-t0);
      const points=history.map(s=>`${p+((s.at-t0)/span)*(w-2*p)},${h-p-(s.value/max)*(h-2*p)}`).join(' ');
      const area=`${p},${h-p} ${points} ${w-p},${h-p}`;
      el('load-chart').innerHTML=`<svg viewBox="0 0 ${w} ${h}" preserveAspectRatio="none" role="img" aria-label="Sampled one-minute load average over the last minute, latest ${current}"><polygon points="${area}" fill="rgba(41,126,112,.10)"/><polyline points="${points}" fill="none" stroke="#398a78" stroke-width="2" vector-effect="non-scaling-stroke"/><circle cx="${w-p}" cy="${h-p-(history.at(-1).value/max)*(h-2*p)}" r="3" fill="#bd552f" vector-effect="non-scaling-stroke"/></svg>`;
      el('chart-axis').innerHTML='<span>Earlier sample</span><span>Now · 1m avg</span>';el('load-label').textContent='1m load sampled over last 60s';
    } else if(current!==null){
      // A single poll sample is a point-in-time average, not a history line.
      const values=load.slice(0,3).filter(v=>v!==null);
      const max=Math.max(1,...values);
      if(values.length>=2){
        const xs=[.18,.5,.82];
        const dots=values.map((v,i)=>{const x=360*xs[i],y=83-(v/max)*73;return `<circle cx="${x}" cy="${y}" r="4" fill="#bd552f" vector-effect="non-scaling-stroke"/><text x="${x+7}" y="${y-6}" fill="#627267" font-size="9">${v.toFixed(2)}</text>`}).join('');
        const periods=['1m average','5m average','15m average'];
        el('load-chart').innerHTML=`<svg viewBox="0 0 360 88" preserveAspectRatio="none" role="img" aria-label="Load averages by period: ${values.map((v,i)=>`${periods[i]} ${v}`).join(', ')}">${dots}</svg>`;
        el('chart-axis').innerHTML=values.map((_,i)=>`<span>${periods[i]}</span>`).join('');el('load-label').textContent='Current averages · separate periods';
      } else {
        const pointY=83-(current/max)*73;
        el('load-chart').innerHTML=`<svg viewBox="0 0 360 88" preserveAspectRatio="none" role="img" aria-label="Current one-minute load average ${current}; one sample"><circle cx="180" cy="${pointY}" r="4" fill="#bd552f" vector-effect="non-scaling-stroke"/><text x="188" y="${pointY-7}" fill="#627267" font-size="10">${current.toFixed(2)}</text></svg>`;
        el('chart-axis').innerHTML='<span>Single sample · 1m average</span>';el('load-label').textContent='1m average · one sample';
      }
    } else {
      el('load-chart').innerHTML='<div class="empty-state small-empty">Collector has not reported load samples.</div>';el('chart-axis').innerHTML='<span>Load sample unavailable</span>';el('load-label').textContent='Awaiting sample';
    }
    const mt=numeric(m.memory_total_bytes), ma=numeric(m.memory_available_bytes), used=mt!==null&&ma!==null?Math.max(0,mt-ma):null;
    el('memory-stat').textContent=mt!==null&&used!==null?`${bytes(used)} / ${bytes(mt)}`:'Not reported';
    el('memory-meter').style.width=mt&&used!==null?`${Math.min(100,100*used/mt)}%`:'0%';
    const st=numeric(m.swap_total_bytes), su=numeric(m.swap_used_bytes);
    el('swap-stat').textContent=st!==null&&su!==null?`${bytes(su)} / ${bytes(st)}`:'Not reported';el('swap-meter').style.width=st&&su!==null?`${Math.min(100,100*su/st)}%`:'0%';
  }
  function renderActivity() {
    const jobs=sortJobs(filteredJobs());
    el('job-count').textContent=`${jobs.length} jobs`;
    el('activity-list').innerHTML=jobs.length?jobs.slice(0,8).map(j=>`<div class="activity-row" data-job="${escapeHtml(j._key)}" tabindex="0" role="button"><span class="activity-glyph">${escapeHtml(j._character)}</span><div class="activity-main"><strong>${escapeHtml(j._placeholder?`${j._character} · queued`:j._path||j.id||'Job')} <span class="status-badge status-${slug(displayStatus(j))}">${escapeHtml(statusText(displayStatus(j)))}</span></strong><p>${escapeHtml(j.summary||[j._source,j._queue_state&&`queue ${statusText(j._queue_state)}`].filter(Boolean).join(' · '))}</p></div><time class="activity-time" title="${escapeHtml(absoluteTime(j.updated_at))}">${escapeHtml(j.updated_at?age(j.updated_at):'time unknown')}</time></div>`).join(''):'<div class="empty-state small-empty">No jobs match these filters.</div>';
    el('activity-list').querySelectorAll('[data-job]').forEach(row=>{const fn=()=>selectJob(row.dataset.job);row.addEventListener('click',fn);row.addEventListener('keydown',e=>{if(e.key==='Enter'){fn();}});});
  }
  function collectSignals() {
    const findings=[], repairs=[];
    for(const j of state.jobs){
      for(const f of asArray(j.findings))findings.push({...((typeof f==='object'&&f)||{message:f}),_job:j});
    }
    for(const r of asArray(state.snapshot?.repairs))repairs.push(r);
    return {findings,repairs};
  }
  function renderSignals() {
    const {findings,repairs}=collectSignals(); el('repair-count').textContent=`${repairs.length} repairs`;
    el('repair-list').innerHTML=repairs.length?repairs.map(r=>`<div class="signal-item repair"><strong>${escapeHtml(val(r,'pdf_page')?`PDF p.${val(r,'pdf_page')}`:asArray(r.pdf_pages).length?`PDF pp.${asArray(r.pdf_pages).join(', ')}`:'PDF page metadata unavailable')} · ${escapeHtml(val(r,'before')||'?')} → ${escapeHtml(val(r,'after')||'?')}</strong><p>${escapeHtml(val(r,'summary','description','status')||'Source correction')}</p><small>${escapeHtml(val(r,'path','updated_at')||'')}</small></div>`).join(''):'<div class="empty-state small-empty">No repair records.</div>';
    el('finding-list').innerHTML=findings.length?findings.map(f=>`<div class="signal-item"><strong>${escapeHtml(val(f,'key','id')||'Finding')}</strong><p>${escapeHtml(val(f,'details','title','verification','status','summary','claim','message','text')||'Finding detail not supplied')}</p><small>${escapeHtml(f._job?`${f._job._character} · ${f._job._source}`:val(f,'path')||'')}</small></div>`).join(''):'<div class="empty-state small-empty">No findings reported.</div>';
  }
  function renderIssues() {
    const github=state.snapshot?.github||{};
    const remote=asArray(github.issues);
    const local=[];
    for(const j of state.jobs)for(const i of asArray(j.issues))local.push({...i,_job:j});
    const errors=asArray(github.errors);
    const syncStatus=String(github.status||'not reported').toLowerCase();
    const checked=github.updated_at?absoluteTime(github.updated_at):'check time unavailable';
    const interval=numeric(github.refresh_interval_seconds);
    const isFresh=/^(fresh|ok|ready|success|live|complete|updated)$/.test(syncStatus);
    const syncTone=isFresh?'fresh':errors.length?'error':'pending';
    const syncLine=`<div class="github-sync ${syncTone}"><span class="sync-dot"></span><strong>${escapeHtml(statusText(github.status||'Not reported'))}</strong><span>Remote check ${escapeHtml(checked)}${interval?` · refresh ~${Math.round(interval/60)} min`:''}</span></div>`;
    const remoteRows=remote.map(i=>{
      const url=safeGitHubUrl(i.url), labels=asArray(i.labels).map(l=>typeof l==='string'?l:val(l,'name')).filter(Boolean);
      const labelsHtml=labels.length?`<span class="github-labels">${labels.map(l=>`<i>${escapeHtml(l)}</i>`).join('')}</span>`:'';
      const milestone=val(i.milestone,'title');
      return `<div class="github-issue"><div class="github-issue-main"><strong>${url?`<a href="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer">`:''}${escapeHtml(i.repository||'repository')} #${escapeHtml(i.number||'?')}${url?'</a>':''}</strong><p>${escapeHtml(i.title||'Untitled issue')}</p><div class="github-issue-meta"><span class="remote-state ${String(i.state||'').toUpperCase()==='OPEN'?'remote-open':'remote-closed'}">${escapeHtml(statusText(i.state||'unknown'))}</span>${milestone?`<span>Milestone: ${escapeHtml(milestone)}</span>`:''}${i.updatedAt?`<time title="${escapeHtml(absoluteTime(i.updatedAt))}">Updated ${escapeHtml(age(i.updatedAt))}</time>`:''}</div>${labelsHtml}</div></div>`;
    }).join('');
    const localRows=local.map(i=>{
      const url=safeGitHubUrl(i.url); const number=val(i,'number');
      const matches=remote.filter(r=>String(r.number)===String(number)&&(i.repository?String(r.repository)===String(i.repository):true));
      const match=matches.length===1?matches[0]:null;
      const remoteStatus=match?`Remote ${statusText(match.state)}`:matches.length>1?'Remote match ambiguous':'Remote status not matched';
      const key=val(i,'key')|| (number?`#${number}`:'Issue receipt');
      return `<div class="local-issue"><span class="local-issue-mark">${escapeHtml(i._job._character)}</span><div><strong>${url?`<a href="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer">`:''}${escapeHtml(key)}${url?'</a>':''}</strong><p>${escapeHtml(i._job._source)} · local triage ${escapeHtml(statusText(i.status||'not reported'))} · ${escapeHtml(remoteStatus)}</p></div></div>`;
    }).join('');
    const errorRows=errors.map(e=>`<div class="github-error"><strong>${escapeHtml(e.repository||'GitHub repository')}</strong><span>${escapeHtml(e.error||'Refresh failed; cached remote data may be shown.')}</span></div>`).join('');
    el('issue-count').textContent=`${remote.length} remote · ${local.length} local`;
    el('issue-list').innerHTML=`${syncLine}${errors.length?`<div class="github-errors">${errorRows}</div>`:''}<div class="github-subhead"><span>Repository issues</span><b>${remote.length}</b></div>${remote.length?`<div class="github-issues-list">${remoteRows}</div>`:'<div class="empty-state small-empty">No remote issues in the cached snapshot.</div>'}<div class="github-subhead local-subhead"><span>Local job receipts</span><b>${local.length}</b></div>${local.length?`<div class="local-issues-list">${localRows}</div>`:'<div class="empty-state small-empty">No issue receipts linked from current jobs.</div>'}`;
  }
  function renderWarnings() {
    const warnings=asArray(state.snapshot?.warnings);
    const collector=state.snapshot?.collector_status;
    const collectorStatus=typeof collector==='string'?collector:val(collector,'status','state');
    const collectorError=/error|failed|unavailable|stale/i.test(String(collectorStatus||'')) || (collector&&typeof collector==='object'&&(collector.error===true||collector.ok===false));
    const collectorMessage=typeof collector==='object'?val(collector,'message','error','summary'):'';
    const warningHtml=warnings.map(w=>`<div class="warning-item">${escapeHtml(typeof w==='string'?w:val(w,'message','summary','warning')||JSON.stringify(w))}</div>`);
    if(collectorError)warningHtml.unshift(`<div class="warning-item collector-warning"><strong>Collector ${escapeHtml(statusText(collectorStatus))}:</strong> ${escapeHtml(collectorMessage||'The displayed snapshot may contain retained data from an earlier successful scan.')}</div>`);
    el('warning-list').innerHTML=warningHtml.length?warningHtml.join(''):'<div class="healthy-note"><span>✓</span> No warnings reported by collector</div>';
    const c=state.snapshot?.coverage||{};
    const done=numeric(val(c,'verified_source_complete'));
    const total=numeric(val(c,'characters_total'));
    const ratio=done!==null&&total!==null&&total>0?Math.min(100,Math.max(0,done/total*100)):null;
    const auditedAt=val(c,'generated_at');
    el('coverage-label').textContent=ratio!==null?`${done} / ${total}`:'Not reported';
    el('coverage-meter').style.width=ratio!==null?`${ratio}%`:'0%';
    el('coverage-note').textContent=ratio!==null?`Last verified source audit · ${auditedAt?absoluteTime(auditedAt):'audit time unavailable'} · not a live certification.`:'Coverage appears only after a verified source audit is reported.';
  }
  function renderMetrics() {
    const jobs=state.jobs;
    const liveOrWaiting=jobs.filter(j=>isLiveJob(j)||isWaitingJob(j)).length;
    const queued=jobs.filter(j=>j._current_queue&&isQueuedJob(j)&&!isLiveJob(j)&&!isWaitingJob(j)).length;
    const currentJobs=jobs.filter(j=>j._current_queue);
    const attentionKinds=currentJobs.map(j=>{
      const q=String(j._queue_status||'').toLowerCase();
      const own=String(j.status||'').toLowerCase();
      const verifiedActive=asArray(j.active_stages).some(stage=>isVerifiedLive(stage)||waitingForSlot(stage));
      if(/needs_revision|needs_source_verification|blocked/.test(q)||(/needs_revision|needs_source_verification|blocked/.test(own)&&j.attention_required))return 'held';
      if(/failed|error|rejected/.test(q)||(/failed|error|rejected/.test(own)&&(j.attention_required||verifiedActive)))return 'failed';
      if(j.attention_required===true||statusBucket(displayStatus(j))==='attention')return 'other';
      return '';
    });
    const held=attentionKinds.filter(x=>x==='held').length;
    const currentFailures=attentionKinds.filter(x=>x==='failed').length;
    const otherAttention=attentionKinds.filter(x=>x==='other').length;
    const attention=held+currentFailures+otherAttention;
    const historicalAttention=jobs.filter(j=>!j._current_queue&&statusBucket(displayStatus(j))==='attention').length;
    const chars=new Set(jobs.map(j=>j._character).filter(x=>x&&x!=='?'));
    const cohortTotal=numeric(state.snapshot?.coverage?.characters_total);
    const workers=allStages().filter(isVerifiedLive).length;
    el('metric-active').textContent=String(liveOrWaiting);
    el('metric-attention').textContent=String(attention);
    el('metric-characters').textContent=String(chars.size);
    el('metric-workers').textContent=String(workers);
    el('metric-active-note').textContent=`${queued} queued · only live, waiting, or queue-running jobs counted`;
    el('metric-attention-note').textContent=`${held} held for revision · ${currentFailures} failed in current queue · ${historicalAttention} historical outcomes`;
    el('metric-characters-note').textContent=cohortTotal!==null?`${cohortTotal} cohort · ${chars.size} repository-tracked characters`:`${chars.size} repository-tracked · cohort total unavailable`;
    const qs=asArray(state.snapshot?.queues);
    const queueWorkers=qs.reduce((n,q)=>n+(numeric(q.workers)||0),0);
    const slotCap=Math.max(...qs.map(q=>numeric(q.agent_capacity)||0),...allStages().map(s=>numeric(s.agent_capacity)||0),numeric(state.snapshot?.agent_capacity)||0);
    el('metric-workers-note').textContent=`${queueWorkers||'—'} queue workers · ${slotCap||'—'} agent slots · verified running processes above`;
  }
  function renderConnection() {
    const node=el('connection'), now=Date.now(), elapsed=now-state.lastSuccess;
    node.className='connection';
    if(!state.lastSuccess){node.classList.add('is-error');node.innerHTML='<span class="pulse"></span><span>Waiting for API</span>';return;}
    const generated=iso(val(state.snapshot,'generated_at'));
    const snapshotAge=generated?now-generated.getTime():Infinity;
    const collector=state.snapshot?.collector_status;
    const collectorStatus=typeof collector==='string'?collector:val(collector,'status','state');
    const collectorFailed=/error|failed|unavailable|stale/i.test(String(collectorStatus||'')) || (collector&&typeof collector==='object'&&(collector.error===true||collector.ok===false));
    if(collectorFailed){node.classList.add('is-error');node.innerHTML=`<span class="pulse"></span><span>Collector ${escapeHtml(statusText(collectorStatus))} · cached snapshot</span>`;}
    else if(elapsed>10000 || snapshotAge>10000 || !generated){
      node.classList.add('is-stale');
      node.innerHTML=`<span class="pulse"></span><span>${!generated?'Timestamp unknown':'Snapshot stale'}</span>`;
    } else {node.innerHTML='<span class="pulse"></span><span>Live snapshot</span>';}
  }
  function renderSnapshotTime() {
    const t=val(state.snapshot,'generated_at');el('snapshot-time').textContent=t?`${absoluteTime(t)} · ${age(t)}`:'Timestamp unavailable';
    el('snapshot-time').title=t?`Collector timestamp: ${absoluteTime(t)}`:'The API did not include generated_at.';
    el('footer-meta').textContent=t?`Updated ${age(t)} · polling every 2 seconds`:'Local operations view · polling every 2 seconds';
  }
  function renderCoordination() {
    const repo=state.snapshot?.repository||{}, coord=state.snapshot?.coordination||{};
    el('repository-state').textContent=repo.branch?`${repo.branch} · ${repo.dirty_count ?? '?'} changed files · ${String(repo.head||"unknown").slice(0,12)}`:'Repository state unavailable';
    el('coordination-tasks').innerHTML=asArray(coord.tasks).map(t=>`<details class="coordination-task"><summary><strong>${escapeHtml(t.title)}</strong><span class="status-badge status-${slug(t.status)}">${escapeHtml(statusText(t.status))}</span></summary><p>${escapeHtml(t.detail)}</p><small>${escapeHtml(t.owner)}</small></details>`).join('') || '<p class="detail-copy">No coordinator task record.</p>';
    el('coordination-note').textContent=`${coord.note||'Recorded coordinator tasks; model processes are observed independently.'}${coord.updated_at?` Updated ${absoluteTime(coord.updated_at)}.`:''}`;
  }
  function render() {
    if(!state.snapshot)return;
    state.jobs=normalize(state.snapshot);renderCoordination();renderSources();renderQueues();renderStages();renderResources();renderActivity();renderSignals();renderIssues();renderWarnings();renderMetrics();renderSnapshotTime();renderConnection();
    if(state.selected&&state.jobs.some(j=>j._key===state.selected))renderDrawer(state.selected);
  }
  function artifactFile(path, filename) {
    if(!path||typeof path!=='string')return '';
    const normalized=path.replace(/\/+$/,'');
    return /\.json$/i.test(normalized)?normalized:`${normalized}/${filename}`;
  }
  function linkForArtifact(path,label='Open JSON receipt',filename='result.json') { const href=artifactUrl(artifactFile(path,filename));return href?`<a class="artifact-link" href="${escapeHtml(href)}" target="_blank" rel="noopener">${escapeHtml(label)} ↗</a>`:''; }
  function renderDrawer(key) {
    const j=state.jobs.find(x=>x._key===key); if(!j)return;
    el('drawer-title').textContent=`${j._character} · ${j._source}`;
    const stages=asArray(j.active_stages), reviews=reviewsFor(j), findings=asArray(j.findings), issues=asArray(j.issues);
    const hashes=[['Article','article_hash',val(j,'article_hash')],['Dossier','dossier_hash',val(j,'dossier_hash')]];
    const originLabel=origin=>origin==='current_job'?'Current job file':origin==='source_baseline'?'Source baseline':'Unavailable';
    const hashOrigins=j.hash_origins||{};
    const hashHtml=hashes.map(([n,key,h])=>`<div class="hash-line"><span>${n} hash <small class="hash-origin">${escapeHtml(originLabel(hashOrigins[key]||j.hash_origin||'unavailable'))}</small></span><code>${escapeHtml(fullHash(h))}</code></div>`).join('');
    const stageHtml=stages.length?stages.map(s=>`<div class="detail-row"><strong>${escapeHtml(val(s,'role')||'Stage')} · ${escapeHtml(statusText(s.status))} ${isVerifiedLive(s)?'<span class="status-badge status-active">verified live</span>':waitingForSlot(s)?'<span class="status-badge status-waiting">waiting for slot</span>':'<span class="status-badge status-other">saved stage</span>'}</strong><small>${escapeHtml(val(s,'model')||'Model unrecorded')} · ${escapeHtml(val(s,'reasoning')||'Reasoning unrecorded')} · ${escapeHtml(val(s,'pid')?`PID ${s.pid}`:'no process PID')} · RAM ${escapeHtml(bytes(s.rss_bytes))}${numeric(s.slot_wait_seconds)!==null?` · waiting ${Math.round(Number(s.slot_wait_seconds))}s`:''}</small><small>Started ${escapeHtml(absoluteTime(s.started_at))} · ${escapeHtml(val(s,'path')||'stage path unavailable')}</small>${linkForArtifact(s.path,'result.json','result.json')} ${s.path&&!/\.json$/i.test(s.path)?linkForArtifact(`${String(s.path).replace(/\/+$/,'')}/meta.json`,'meta.json'):''}</div>`).join(''):'<p class="detail-copy">No active stages are reported for this job.</p>';
    const reviewHtml=reviews.length?reviews.map(r=>{
      const pairLabel=r.current_pair===true?'Matches current pair':r.current_pair===false?'Earlier/different pair':'Current-pair match unavailable';
      const pairClass=r.current_pair===true?'pair-match':'pair-different';
      const caveat=r.current_pair===false?' · does not certify the current job':r.current_pair===undefined?' · current pair not verified':'';
      return `<div class="detail-row"><strong>${escapeHtml(val(r,'role')||'Review')} · ${escapeHtml(statusText(r.verdict||r.status||'unrecorded'))} <span class="pair-status ${pairClass}">${pairLabel}</span></strong><small>Article <code>${escapeHtml(fullHash(r.article_hash))}</code> · dossier <code>${escapeHtml(fullHash(r.dossier_hash))}</code></small>${caveat?`<small>${escapeHtml(caveat.replace(/^ · /,''))}</small>`:''}${linkForArtifact(val(r,'path','receipt_path'),'Review receipt','result.json')} ${val(r,'path','receipt_path')&&!/\.json$/i.test(String(val(r,'path','receipt_path')))?linkForArtifact(`${String(val(r,'path','receipt_path')).replace(/\/+$/,'')}/meta.json`,'meta.json'):''}</div>`;
    }).join(''):'<p class="detail-copy">No review receipts attached to this snapshot.</p>';
    const findingHtml=findings.length?findings.map(f=>`<div class="detail-row"><strong>${escapeHtml(val(f,'key','id')||'Finding')}</strong><small>${escapeHtml(val(f,'summary','claim','message','text')||JSON.stringify(f))}</small><small>${escapeHtml(val(f,'path','artifact_path')||'Finding path not recorded')}</small>${/\.json$/i.test(String(val(f,'path','artifact_path')))?linkForArtifact(val(f,'path','artifact_path'),'Open finding receipt'):''}</div>`).join(''):'<p class="detail-copy">No current findings reported.</p>';
    const issueHtml=issues.length?issues.map(i=>{const u=safeGitHubUrl(i.url);return `<div class="detail-row"><strong>${u?`<a class="artifact-link" href="${escapeHtml(u)}" target="_blank" rel="noopener noreferrer">`:''}${escapeHtml(val(i,'key')||`#${val(i,'number')||'?'}`)}${u?'</a>':''} · ${escapeHtml(statusText(i.status||'untracked'))}</strong><small>${escapeHtml(val(i,'url')||'No URL reported')} · ${escapeHtml(val(i,'number')?'Issue #'+i.number:'')}</small></div>`}).join(''):'<p class="detail-copy">No linked issues in this job snapshot.</p>';
    el('drawer-content').innerHTML=`<div class="detail-hero"><span class="detail-hanzi">${escapeHtml(j._character)}</span><div class="detail-hero-meta"><strong>${escapeHtml(statusText(displayStatus(j)))} <span class="status-badge status-${slug(displayStatus(j))}">${escapeHtml(statusText(displayStatus(j)))}</span></strong><small>${escapeHtml(j._placeholder?`Queued in ${j._queue_path||'queue'} · job directory not created`:j._path||j.id||'Job path unavailable')}</small><small>${escapeHtml(j.updated_at?`${age(j.updated_at)} · ${absoluteTime(j.updated_at)}`:'Update time unavailable')}</small></div></div>
      ${j.summary?`<section class="detail-section"><h3>Current summary</h3><div class="detail-copy">${escapeHtml(j.summary)}</div></section>`:''}
      <section class="detail-section"><h3>Content hashes</h3>${hashHtml}</section>
      <section class="detail-section"><h3>Review receipts (${reviews.length})</h3><div class="detail-list">${reviewHtml}</div></section>
      <section class="detail-section"><h3>Stages (${stages.length})</h3><div class="detail-list">${stageHtml}</div></section>
      <section class="detail-section"><h3>Findings (${findings.length})</h3><div class="detail-list">${findingHtml}</div></section>
      <section class="detail-section"><h3>GitHub issues (${issues.length})</h3><div class="detail-list">${issueHtml}</div></section>
      <section class="detail-section"><h3>Issue sync</h3><div class="detail-copy">${escapeHtml(j.issue_sync_status?statusText(j.issue_sync_status):'Not reported')}</div></section>
      ${j._path&&!j._placeholder?`<section class="detail-section"><h3>Job artifact</h3>${linkForArtifact(j._path,'status.json','status.json')}</section>`:''}`;
  }
  function selectJob(key) {
    state.selected=key;updateUrl();renderQueues();renderActivity();renderDrawer(key);el('detail-drawer').classList.add('open');el('detail-drawer').setAttribute('aria-hidden','false');el('drawer-backdrop').hidden=false;
  }
  function closeDrawer() {state.selected=null;updateUrl();el('detail-drawer').classList.remove('open');el('detail-drawer').setAttribute('aria-hidden','true');el('drawer-backdrop').hidden=true;}
  function setToast(message){const t=el('toast');t.textContent=message;t.classList.add('show');clearTimeout(state.toastTimer);state.toastTimer=setTimeout(()=>t.classList.remove('show'),2300);}
  async function poll() {
    try {
      const response=await fetch('/api/state',{cache:'no-store',headers:{'Accept':'application/json'}});
      if(!response.ok)throw new Error(`HTTP ${response.status}`);
      const data=await response.json(); if(!data||typeof data!=='object')throw new Error('Invalid snapshot');
      state.snapshot=data;state.lastSuccess=Date.now();render();
      if(state.selected&&!state.jobs.some(j=>j._key===state.selected))closeDrawer();
    } catch(err) {
      renderConnection();
      if(!state.lastSuccess){el('connection').classList.add('is-error');el('connection').innerHTML='<span class="pulse"></span><span>API unavailable</span>';}
      else if(Date.now()-state.lastSuccess>10000){el('connection').classList.add('is-stale');}
      console.warn('Dashboard snapshot fetch failed:',err);
    } finally {state.timer=setTimeout(poll,POLL_MS);}
  }
  function init() {
    restoreUrl();el('source-filter').value=state.source;
    el('search').addEventListener('input',e=>{state.query=e.target.value;updateUrl();renderQueues();renderActivity();});
    el('status-filter').addEventListener('change',e=>{state.status=e.target.value;updateUrl();renderQueues();renderActivity();});
    el('source-filter').addEventListener('change',e=>{state.source=e.target.value;updateUrl();renderQueues();renderActivity();});
    el('history-toggle').addEventListener('change',e=>{state.showHistory=e.target.checked;updateUrl();renderQueues();renderActivity();});
    el('refresh-now').addEventListener('click',()=>{clearTimeout(state.timer);poll();});
    el('drawer-close').addEventListener('click',closeDrawer);el('drawer-backdrop').addEventListener('click',closeDrawer);
    document.addEventListener('keydown',e=>{if(e.key==='Escape'&&!el('drawer-backdrop').hidden)closeDrawer();});
    if(state.selected){el('detail-drawer').classList.add('open');el('detail-drawer').setAttribute('aria-hidden','false');el('drawer-backdrop').hidden=false;}
    poll();
  }
  init();
})();
