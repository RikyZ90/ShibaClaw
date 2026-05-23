// ── Automation Panel ──────────────────────────────────────────────────────────
// Replaces the old cron + heartbeat sidebar sections with a unified modal.
//
// Public surface used by ui_panels.js / main.js:
//   loadAutomationPanel()   – refresh job list + status badge
//   openJobForm(jobId?)     – open create/edit form
//   closeJobForm()          – close form
//   saveJobForm()           – submit create/update
//   onJobKindChange()       – toggle form sections
//   onSchedKindChange()     – toggle schedule fields
//   onDeliverChange()       – toggle delivery fields
// ---------------------------------------------------------------------------

// ── helpers ─────────────────────────────────────────────────────────────────

function _autoTimeAgo(ms) {
    if (!ms) return '';
    const sec = Math.floor((Date.now() - ms) / 1000);
    if (sec < 60) return 'just now';
    if (sec < 3600) return `${Math.floor(sec / 60)}m ago`;
    if (sec < 86400) return `${Math.floor(sec / 3600)}h ago`;
    return `${Math.floor(sec / 86400)}d ago`;
}

function _autoFormatSchedule(s) {
    if (!s) return '?';
    if (s.kind === 'cron') return `cron: ${s.expr || s.expression || ''}`;
    if (s.kind === 'every') {
        const ms = s.everyMs || s.every_ms || 0;
        if (ms % 3600000 === 0) return `every ${ms / 3600000}h`;
        if (ms % 60000 === 0) return `every ${ms / 60000}m`;
        if (ms % 1000 === 0) return `every ${ms / 1000}s`;
        return `every ${ms}ms`;
    }
    if (s.kind === 'at') {
        const atMs = s.atMs || s.at_ms || 0;
        return atMs ? new Date(atMs).toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }) : 'once';
    }
    return s.kind || '?';
}

function _autoStatusClass(job) {
    if (!job.enabled) return 'st-disabled';
    const st = (job.state || {}).lastStatus || (job.state || {}).last_status;
    if (st === 'error') return 'st-error';
    if (st === 'ok') return 'st-ok';
    return 'st-pending';
}

// ── state ────────────────────────────────────────────────────────────────────

let _autoJobs = [];
let _autoEditingId = null;

// ── load + render list ───────────────────────────────────────────────────────

async function loadAutomationPanel() {
    const listEl = document.getElementById('automation-job-list');
    const statusText = document.getElementById('automation-status-text');
    const statusRow = document.getElementById('automation-status-row');
    const badgeMini = document.getElementById('automation-badge-mini');

    if (!listEl) return;
    listEl.innerHTML = '<div class="automation-loading">Loading jobs...</div>';

    try {
        const [statusRes, jobsRes] = await Promise.all([
            authFetch('/api/automation/status'),
            authFetch('/api/automation/jobs'),
        ]);
        
        if (!statusRes.ok || !jobsRes.ok) {
            throw new Error(`API Error: ${statusRes.status} / ${jobsRes.status}`);
        }

        const statusData = await statusRes.json();
        const jobsData = await jobsRes.json();
        _autoJobs = jobsData.jobs || [];

        // ── status row ────────────────────────────────────────────────────────
        if (statusData.reachable === false) {
            if (statusRow) statusRow.className = 'automation-status-row status-offline';
            if (statusText) statusText.textContent = 'Gateway unreachable';
        } else {
            const running = _autoJobs.filter(j => j.enabled).length;
            if (statusRow) statusRow.className = 'automation-status-row status-online';
            if (statusText) statusText.textContent = `${running} active job${running !== 1 ? 's' : ''} · ${_autoJobs.length} total`;
        }

        // ── sidebar mini badge ────────────────────────────────────────────────
        if (badgeMini) {
            const errCount = _autoJobs.filter(j => (j.state || {}).lastStatus === 'error' || (j.state || {}).last_status === 'error').length;
            if (errCount > 0) {
                badgeMini.textContent = errCount;
                badgeMini.style.display = '';
                badgeMini.style.background = 'var(--accent-red)';
            } else if (_autoJobs.length > 0) {
                badgeMini.textContent = _autoJobs.length;
                badgeMini.style.display = '';
                badgeMini.style.background = 'var(--text-muted)';
            } else {
                badgeMini.style.display = 'none';
            }
        }

        // ── job list ──────────────────────────────────────────────────────────
        if (!listEl) return;
        if (_autoJobs.length === 0) {
            listEl.innerHTML = `
                <div class="automation-empty-state">
                    <span class="material-icons-round">event_repeat</span>
                    <p>No automation jobs yet.<br>Click <strong>New Job</strong> to create one.</p>
                </div>`;
            return;
        }

        listEl.innerHTML = '';
        for (const job of _autoJobs) {
            const row = document.createElement('div');
            row.className = 'auto-job-row' + (job.enabled ? '' : ' disabled');
            const stCls = _autoStatusClass(job);
            const state = job.state || {};
            const lastRun = state.lastRunAtMs || state.last_run_at_ms;
            const meta = lastRun ? _autoTimeAgo(lastRun) : _autoFormatSchedule(job.schedule);
            const kindIcon = job.payload?.kind === 'heartbeat' ? 'favorite' : 'schedule_send';
            const kindLabel = job.payload?.kind === 'heartbeat' ? 'heartbeat' : 'scheduled';
            const safeName = escapeHtml(job.name || job.id);
            const lastErr = escapeHtml((state.lastError || state.last_error || '').slice(0, 120));

            row.innerHTML = `
                <div class="auto-job-left">
                    <div class="auto-status ${stCls}" title="${stCls.replace('st-', '')}"></div>
                    <span class="material-icons-round auto-kind-icon" title="${kindLabel}">${kindIcon}</span>
                </div>
                <div class="auto-job-center">
                    <div class="auto-job-name">${safeName}</div>
                    <div class="auto-job-meta">${escapeHtml(meta)}${lastErr ? ` · <span class="auto-err">${lastErr}</span>` : ''}</div>
                </div>
                <div class="auto-job-actions">
                    <label class="toggle auto-toggle" title="${job.enabled ? 'Disable' : 'Enable'}">
                        <input type="checkbox" class="auto-enable-cb" data-id="${escapeHtml(job.id)}" ${job.enabled ? 'checked' : ''}>
                        <span class="toggle-slider"></span>
                    </label>
                    <button class="btn-icon auto-btn-trigger" title="Run now" data-id="${escapeHtml(job.id)}">
                        <span class="material-icons-round">play_arrow</span>
                    </button>
                    <button class="btn-icon auto-btn-edit" title="Edit" data-id="${escapeHtml(job.id)}">
                        <span class="material-icons-round">edit</span>
                    </button>
                    <button class="btn-icon auto-btn-delete danger" title="Delete" data-id="${escapeHtml(job.id)}">
                        <span class="material-icons-round">delete</span>
                    </button>
                </div>`;

            // ── enable toggle ──────────────────────────────────────────────
            row.querySelector('.auto-enable-cb').addEventListener('change', async (e) => {
                const cb = e.currentTarget;
                cb.disabled = true;
                try {
                    await authFetch(`/api/automation/jobs/${encodeURIComponent(job.id)}`, {
                        method: 'PATCH',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ enabled: cb.checked }),
                    });
                } catch (_) { cb.checked = !cb.checked; }
                cb.disabled = false;
                await loadAutomationPanel();
            });

            // ── trigger ────────────────────────────────────────────────────
            row.querySelector('.auto-btn-trigger').addEventListener('click', async (e) => {
                const btn = e.currentTarget;
                btn.disabled = true;
                try {
                    await authFetch(`/api/automation/jobs/${encodeURIComponent(job.id)}/trigger`, { method: 'POST' });
                } catch (_) { }
                await loadAutomationPanel();
            });

            // ── edit ───────────────────────────────────────────────────────
            row.querySelector('.auto-btn-edit').addEventListener('click', () => openJobForm(job.id));

            // ── delete ─────────────────────────────────────────────────────
            row.querySelector('.auto-btn-delete').addEventListener('click', async () => {
                const ok = await shibaDialog('confirm', 'Delete job', `Delete "${job.name || job.id}"?`, { confirmText: 'Delete', danger: true });
                if (!ok) return;
                try {
                    await authFetch(`/api/automation/jobs/${encodeURIComponent(job.id)}`, { method: 'DELETE' });
                } catch (_) { }
                await loadAutomationPanel();
            });

            listEl.appendChild(row);
        }
    } catch (e) {
        if (statusText) statusText.textContent = 'Error loading jobs';
        if (listEl) listEl.innerHTML = `<div class="automation-empty-state"><span class="material-icons-round" style="color:var(--accent-red)">error</span><p>Failed to load automation jobs.</p></div>`;
    }
}

// ── form open / close ────────────────────────────────────────────────────────

window.openJobForm = async function (jobId) {
    _autoEditingId = jobId || null;
    const form = document.getElementById('automation-job-form');
    const title = document.getElementById('automation-form-title');
    if (!form) return;

    // Reset fields safely
    const _resetMap = {
        'ajf-name': '',
        'ajf-kind': 'scheduled',
        'ajf-sched-kind': 'every',
        'ajf-every-min': '30',
        'ajf-cron-expr': '',
        'ajf-tz': '',
        'ajf-message': '',
        'ajf-hb-file': '',
        'ajf-deliver': false,
        'ajf-channel': '',
        'ajf-target-id': '',
        'ajf-session-key': '',
        'ajf-delete-after': false,
        'ajf-enabled': true,
    };
    for (const [id, val] of Object.entries(_resetMap)) {
        const el = document.getElementById(id);
        if (!el) continue;
        if (el.type === 'checkbox') {
            el.checked = !!val;
        } else {
            el.value = val;
        }
    }

    // Load profiles into select
    const profSel = document.getElementById('ajf-profile');
    if (profSel && profSel.options.length <= 1) {
        try {
            const r = await authFetch('/api/profiles');
            if (r.ok) {
                const d = await r.json();
                for (const p of (d.profiles || [])) {
                    const opt = document.createElement('option');
                    opt.value = p.id;
                    opt.textContent = p.label || p.id;
                    profSel.appendChild(opt);
                }
            }
        } catch (_) { }
    }

    if (jobId) {
        title.textContent = 'Edit Job';
        const job = _autoJobs.find(j => j.id === jobId);
        if (job) _autoFillForm(job);
    } else {
        title.textContent = 'New Job';
    }

    onJobKindChange();
    onSchedKindChange();
    onDeliverChange();

    document.getElementById('automation-job-list').style.display = 'none';
    document.querySelector('.automation-modal-toolbar').style.display = 'none';
    form.style.display = 'flex';
    document.getElementById('ajf-name').focus();
};

function _autoFillForm(job) {
    document.getElementById('ajf-name').value = job.name || '';
    const payload = job.payload || {};
    document.getElementById('ajf-kind').value = payload.kind || 'scheduled';

    const sched = job.schedule || {};
    document.getElementById('ajf-sched-kind').value = sched.kind || 'every';
    if (sched.kind === 'every') {
        const ms = sched.everyMs || sched.every_ms || 1800000;
        document.getElementById('ajf-every-min').value = Math.round(ms / 60000);
    } else if (sched.kind === 'cron') {
        document.getElementById('ajf-cron-expr').value = sched.expr || sched.expression || '';
    } else if (sched.kind === 'at') {
        const atMs = sched.atMs || sched.at_ms || 0;
        if (atMs) {
            const d = new Date(atMs);
            document.getElementById('ajf-at-dt').value = new Date(d - d.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
        }
    }
    document.getElementById('ajf-tz').value = sched.tz || '';
    document.getElementById('ajf-message').value = payload.message || '';
    document.getElementById('ajf-hb-file').value = payload.heartbeatFile || payload.heartbeat_file || '';

    const deliver = !!(payload.deliver);
    document.getElementById('ajf-deliver').checked = deliver;
    document.getElementById('ajf-channel').value = payload.channel || '';
    document.getElementById('ajf-target-id').value = payload.to || (payload.targets ? Object.values(payload.targets)[0] : '') || '';
    document.getElementById('ajf-session-key').value = payload.sessionKey || payload.session_key || '';
    document.getElementById('ajf-profile').value = payload.profileId || payload.profile_id || '';
    document.getElementById('ajf-delete-after').checked = !!(job.deleteAfterRun || job.delete_after_run);
    document.getElementById('ajf-enabled').checked = job.enabled !== false;
}

window.closeJobForm = function () {
    const form = document.getElementById('automation-job-form');
    if (form) form.style.display = 'none';
    const list = document.getElementById('automation-job-list');
    if (list) list.style.display = '';
    const toolbar = document.querySelector('.automation-modal-toolbar');
    if (toolbar) toolbar.style.display = '';
    _autoEditingId = null;
};

// ── form field watchers ──────────────────────────────────────────────────────

window.onJobKindChange = function () {
    const kind = document.getElementById('ajf-kind').value;
    document.getElementById('ajf-section-scheduled').style.display = kind === 'scheduled' ? '' : 'none';
    document.getElementById('ajf-section-heartbeat').style.display = kind === 'heartbeat' ? '' : 'none';
};

window.onSchedKindChange = function () {
    const kind = document.getElementById('ajf-sched-kind').value;
    document.getElementById('ajf-sched-every').style.display = kind === 'every' ? '' : 'none';
    document.getElementById('ajf-sched-cron').style.display = kind === 'cron' ? '' : 'none';
    document.getElementById('ajf-sched-at').style.display = kind === 'at' ? '' : 'none';
};

window.onDeliverChange = function () {
    const deliver = document.getElementById('ajf-deliver').checked;
    document.getElementById('ajf-delivery-fields').style.display = deliver ? '' : 'none';
};

// ── save ─────────────────────────────────────────────────────────────────────

window.saveJobForm = async function () {
    const saveBtn = document.getElementById('ajf-save-btn');
    if (saveBtn) { saveBtn.disabled = true; saveBtn.textContent = 'Saving...'; }

    const schedKind = document.getElementById('ajf-sched-kind').value;
    let schedule = { kind: schedKind };
    if (schedKind === 'every') {
        schedule.everyMs = parseInt(document.getElementById('ajf-every-min').value) * 60000;
    } else if (schedKind === 'cron') {
        schedule.expr = document.getElementById('ajf-cron-expr').value.trim();
    } else if (schedKind === 'at') {
        const dtVal = document.getElementById('ajf-at-dt').value;
        schedule.atMs = dtVal ? new Date(dtVal).getTime() : 0;
    }
    const tzVal = document.getElementById('ajf-tz').value.trim();
    if (tzVal) schedule.tz = tzVal;

    const kind = document.getElementById('ajf-kind').value;
    const deliver = document.getElementById('ajf-deliver').checked;
    const channel = document.getElementById('ajf-channel').value;
    const targetId = document.getElementById('ajf-target-id').value.trim();

    const payload = {
        kind,
        message: document.getElementById('ajf-message').value,
        heartbeatFile: document.getElementById('ajf-hb-file').value.trim() || null,
        deliver,
        channel: deliver ? (channel || null) : null,
        to: deliver && !channel ? (targetId || null) : null,
        targets: (deliver && channel && targetId) ? { [channel]: targetId } : {},
        sessionKey: document.getElementById('ajf-session-key').value.trim() || null,
        profileId: document.getElementById('ajf-profile').value || null,
    };

    const body = {
        name: document.getElementById('ajf-name').value.trim() || 'Job',
        enabled: document.getElementById('ajf-enabled').checked,
        deleteAfterRun: document.getElementById('ajf-delete-after').checked,
        schedule,
        payload,
    };

    try {
        let res;
        if (_autoEditingId) {
            res = await authFetch(`/api/automation/jobs/${encodeURIComponent(_autoEditingId)}`, {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body),
            });
        } else {
            res = await authFetch('/api/automation/jobs', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body),
            });
        }
        const data = await res.json();
        if (!res.ok) throw data.error || `HTTP ${res.status}`;
        closeJobForm();
        await loadAutomationPanel();
    } catch (e) {
        if (typeof shibaDialog === 'function') {
            shibaDialog('alert', 'Error', 'Failed to save job: ' + e, { danger: true });
        } else {
            alert('Failed to save job: ' + e);
        }
    } finally {
        if (saveBtn) {
            saveBtn.disabled = false;
            saveBtn.innerHTML = '<span class="material-icons-round" style="font-size:15px;vertical-align:middle">save</span> Save';
        }
    }
};

// ── openModal hook ────────────────────────────────────────────────────────────
// Called from index.html: openModal('automation-modal')
// We hook into the existing openModal in ui_panels.js by patching.
function patchOpenModal() {
    const _origOpenModal = window.openModal;
    window.openModal = async function (id) {
        if (id === 'automation-modal') {
            const modal = document.getElementById('automation-modal');
            if (modal) modal.classList.add('active');
            if (typeof window.closeSidebarOnMobile === 'function') window.closeSidebarOnMobile();
            closeJobForm();
            await loadAutomationPanel();
            return;
        }
        if (_origOpenModal) return _origOpenModal(id);
    };
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', patchOpenModal);
} else {
    patchOpenModal();
}
