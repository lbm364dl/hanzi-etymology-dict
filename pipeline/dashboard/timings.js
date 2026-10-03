/* Recorded durations, never inferred model billing or CPU time. */
(() => {
  const epoch = value => {
    if (value === null || value === undefined || value === '') return null;
    if (typeof value === 'number') return value < 1e12 ? value : value / 1000;
    const result = Date.parse(value); return Number.isFinite(result) ? result / 1000 : null;
  };
  function analyze(job, jobs, now = Date.now() / 1000) {
    const path = job._path || job.path;
    const queue = job.queue || {};
    const start = epoch(queue.started_at || job.started_at);
    const finish = epoch(queue.finished_at || job.finished_at);
    const queueStatus = job._queue_status || queue.status || job.status;
    const running = /^(running|active)$/.test(queueStatus || '');
    const wall = start !== null && (finish !== null || running) ? Math.max(0, (finish ?? now) - start) : null;
    const records = new Map();
    for (const owner of jobs) {
      const ownerPath = owner._path || owner.path;
      if (!path || !(ownerPath === path || ownerPath?.startsWith(path + '/'))) continue;
      for (const stage of owner.stage_history || []) {
        const began = epoch(stage.queued_at ?? stage.started_at);
        // Imported receipts and earlier attempts do not describe this queue attempt.
        if (start !== null && (began === null || began < start)) continue;
        if (finish !== null && began !== null && began > finish) continue;
        records.set(stage.path, stage);
      }
    }
    const stages = [...records.values()].sort((a,b) => (epoch(a.queued_at ?? a.started_at) || 0) - (epoch(b.queued_at ?? b.started_at) || 0));
    const roles = new Map(); let model = 0, wait = 0, unknown = 0, failed = 0;
    for (const stage of stages) {
      const row = roles.get(stage.role || 'stage') || {role:stage.role || 'stage', seconds:0, wait:0, count:0, failed:0};
      row.count++;
      let slot = Number(stage.slot_wait_seconds || 0);
      let seconds = Number(stage.elapsed_seconds);
      const waiting = stage.status === 'waiting_for_agent_slot';
      if (waiting) { slot = Number(stage.elapsed_seconds || 0); seconds = 0; }
      if (stage.elapsed_seconds === null || stage.elapsed_seconds === undefined || stage.liveness === 'stale' && !stage.finished_at) { seconds = 0; unknown++; }
      if (!Number.isFinite(seconds)) { seconds = 0; unknown++; }
      if (!Number.isFinite(slot)) slot = 0;
      if (stage.status === 'failed') { failed++; row.failed++; }
      row.seconds += seconds; row.wait += slot; model += seconds; wait += slot;
      roles.set(row.role,row);
    }
    const ranked = [...roles.values()].sort((a,b) => b.seconds - a.seconds);
    return {wall, model, wait, unknown, failed, stages, roles:ranked,
      attempts:queue.attempts ?? job.attempts ?? null, scope:start === null ? 'recorded history' : 'latest queue attempt',
      slowest:ranked[0]?.role || null};
  }
  globalThis.PipelineTimings = {analyze};
})();
