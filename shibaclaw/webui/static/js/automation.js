// ── Automation Panel ──────────────────────────────────────────────────────────
// Unified automation modal: job list + create/edit form.
//
// Public surface used by ui_panels.js / main.js:
//   loadAutomationPanel()   – refresh job list + status badge
//   openJobForm(jobId?)     – open create/edit form
//   closeJobForm()          – close form
//   saveJobForm()           – submit create/update
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
let _currentAutoTab = 'active';

// ── load + render list ───────────────────────────────────────────────────────

async function loadAutomationPanel() {
    const listEl = document.getElementById('automation-job-list');
    const statusText = document.getElementById('automation-status-text');
    const statusRow = document.getElementById('automation-status-row');
    const badgeMini = document.getElementById('automation-badge-mini');

    if (!listEl) return;
    listEl.innerHTML = '<div class="automation-loading">Loading jobs...</div>';

    try {
        const [statusRes, jobsRes, taskMdRes] = await Promise.all([
            authFetch('/api/automation/status'),
            authFetch('/api/automation/jobs'),
            authFetch(`/api/file-get?path=TASK.md&_t=${Date.now()}`).catch(() => ({ok: false}))
        ]);

        if (!statusRes.ok || !jobsRes.ok) {
            throw new Error(`API Error: ${statusRes.status} / ${jobsRes.status}`);
        }

        const statusData = await statusRes.json();
        const jobsData = await jobsRes.json();

        let globalHb = null;
        // Hide system heartbeat job from UI natively, but save a ref to it
        _autoJobs = (jobsData.jobs || []).filter(job => {
            const isHeartbeat = (job.payload || {}).kind === 'heartbeat';
            if (isHeartbeat && (job.name === 'Heartbeat' || job.name === 'heartbeat')) {
                globalHb = job;
                return false;
            }
            return true;
        });

        if (taskMdRes && taskMdRes.ok) {
            let taskMd = await taskMdRes.text();
            let previous;
            do {
                previous = taskMd;
                taskMd = taskMd.replace(/<!--[\s\S]*?-->/g, '');
            } while (taskMd !== previous);
            
            let relevant = taskMd;
            const activeMatch = /^##\s+Active Tasks\s*$/im.exec(taskMd);
            if (activeMatch) {
                relevant = taskMd.slice(activeMatch.index + activeMatch[0].length);
                const boundary = /^##\s+(Completed|Notes)\s*$/im.exec(relevant);
                if (boundary) {
                    relevant = relevant.slice(0, boundary.index);
                }
            }
            
            const headingRe = /^(?:##\s*Task:\s*([^\n]+)|###\s*Task:\s*([^\n]+)|##\s+([^\n#][^\n]*))\s*$/igm;
            let match;
            const virtualJobs = [];
            while ((match = headingRe.exec(relevant)) !== null) {
                const name = (match[1] || match[2] || match[3] || '').trim();
                if (!name) continue;
                
                const isManaged = _autoJobs.some(j => (j.name || '').trim().toLowerCase() === name.toLowerCase());
                if (!isManaged) {
                    virtualJobs.push({
                        id: `v-${Date.now()}-${Math.random().toString(36).substr(2, 5)}`,
                        name: name,
                        enabled: globalHb ? globalHb.enabled : true,
                        schedule: globalHb ? globalHb.schedule : { kind: 'every', everyMs: 30 * 60 * 1000 },
                        payload: { kind: 'heartbeat' },
                        state: globalHb ? globalHb.state : {},
                        isVirtual: true
                    });
                }
            }
            _autoJobs.push(...virtualJobs);
        }

        if (statusData.reachable === false) {
            if (statusRow) statusRow.className = 'automation-status-row status-offline';
            if (statusText) statusText.textContent = 'Gateway unreachable';
        } else {
            const running = _autoJobs.filter(j => j.enabled).length;
            if (statusRow) statusRow.className = 'automation-status-row status-online';
            if (statusText) statusText.textContent = `${running} active job${running !== 1 ? 's' : ''} · ${_autoJobs.length} total`;
        }

        if (badgeMini) {
            const errCount = _autoJobs.filter(j => (j.state || {}).lastStatus === 'error' || (j.state || {}).last_status === 'error').length;
            if (errCount > 0) {
                badgeMini.textContent = errCount;
                badgeMini.style.display = '';
                badgeMini.className = 'automation-badge-mini badge-error';
            } else if (_autoJobs.length > 0) {
                badgeMini.textContent = _autoJobs.length;
                badgeMini.style.display = '';
                badgeMini.className = 'automation-badge-mini badge-normal';
            } else {
                badgeMini.style.display = 'none';
            }
        }

        const clearBtn = document.getElementById('btn-auto-clear-completed');
        if (clearBtn) {
            const hasCompleted = _autoJobs.some(job => {
                const hasRun = ((job.state || {}).lastRunAtMs || (job.state || {}).last_run_at_ms || 0) > 0;
                const isOneShotDone = (job.schedule.kind === 'at' && hasRun);
                return !job.enabled || isOneShotDone;
            });
            clearBtn.style.display = (_currentAutoTab === 'completed' && hasCompleted) ? 'flex' : 'none';
        }

        if (!listEl) return;

        const filteredJobs = _autoJobs.filter(job => {
            if (!job.id) return false;
            if (_currentAutoTab === 'active') {
                return job.enabled || (job.schedule.kind === 'at' && (job.state || {}).next_run_at_ms > 0);
            } else {
                const hasRun = ((job.state || {}).lastRunAtMs || (job.state || {}).last_run_at_ms || 0) > 0;
                const isOneShotDone = (job.schedule.kind === 'at' && hasRun);
                return !job.enabled || isOneShotDone;
            }
        });

        if (filteredJobs.length === 0) {
            const emptyMsg = _currentAutoTab === 'active'
                ? 'No active automation jobs.'
                : 'No completed automation jobs.';
            listEl.innerHTML = `
                <div class="automation-empty-state">
                    <span class="material-icons-round">${_currentAutoTab === 'active' ? 'event_repeat' : 'check_circle'}</span>
                    <p>${emptyMsg}<br>${_currentAutoTab === 'active' ? 'Click <strong>New Job</strong> to create one.' : ''}</p>
                </div>`;
            return;
        }

        listEl.innerHTML = '';
        for (const job of filteredJobs) {
            const row = document.createElement('div');

            let rowClass = 'auto-job-row';
            if (!job.enabled) rowClass += ' disabled';
            if (_currentAutoTab === 'completed') {
                const hasRun = ((job.state || {}).lastRunAtMs || (job.state || {}).last_run_at_ms || 0) > 0;
                const isOneShotDone = (job.schedule.kind === 'at' && hasRun);
                if (!job.enabled || isOneShotDone) rowClass += ' completed';
            }
            row.className = rowClass;

            const stCls = _autoStatusClass(job);
            const state = job.state || {};
            const lastRun = state.lastRunAtMs || state.last_run_at_ms;
            const meta = lastRun ? _autoTimeAgo(lastRun) : _autoFormatSchedule(job.schedule);
            const isHeartbeat = (job.payload || {}).kind === 'heartbeat';
            const kindIcon = isHeartbeat ? 'autorenew' : 'schedule_send';
            const kindLabel = isHeartbeat ? 'Heartbeat' : 'Scheduled';
            const isSystemHeartbeat = isHeartbeat && (job.name === 'Heartbeat' || job.name === 'heartbeat');

            let displayName = job.name || job.id;
            if (isSystemHeartbeat) displayName = 'Heartbeat (System)';
            const safeName = escapeHtml(displayName);
            const lastErr = escapeHtml((state.lastError || state.last_error || '').slice(0, 120));

            row.innerHTML = `
                <div class="auto-job-left">
                    <div class="auto-status ${stCls}" title="${stCls.replace('st-', '')}"></div>
                    <span class="material-icons-round auto-kind-icon" title="${kindLabel}">${kindIcon}</span>
                </div>
                <div class="auto-job-center">
                    <div class="auto-job-name">${safeName} ${job.isVirtual ? '<span class="automation-badge-mini" style="margin-left:8px;font-size:10px;opacity:0.7;vertical-align:middle;">TASK.md</span>' : ''}</div>
                    <div class="auto-job-meta">${escapeHtml(meta)}${lastErr ? ` · <span class="auto-err">${lastErr}</span>` : ''}</div>
                </div>
                <div class="auto-job-actions">
                    ${job.isVirtual ? '' : `<label class="toggle auto-toggle" title="${job.enabled ? 'Disable' : 'Enable'}">
                        <input type="checkbox" class="auto-enable-cb" data-id="${escapeHtml(job.id)}" ${job.enabled ? 'checked' : ''}>
                        <span class="toggle-slider"></span>
                    </label>`}
                    <button class="btn-icon auto-btn-trigger" title="Run now" data-id="${escapeHtml(job.id)}">
                        <span class="material-icons-round">play_arrow</span>
                    </button>
                    <button class="btn-icon auto-btn-edit" title="${job.isVirtual ? 'Upgrade to independent job' : 'Edit'}" data-id="${escapeHtml(job.id)}">
                        <span class="material-icons-round">${job.isVirtual ? 'upgrade' : 'edit'}</span>
                    </button>
                    ${!isSystemHeartbeat ? `<button class="btn-icon auto-btn-delete danger" title="Delete" data-id="${escapeHtml(job.id)}">
                        <span class="material-icons-round">delete</span>
                    </button>` : ''}
                </div>`;

            if (!job.isVirtual) {
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
            }

            row.querySelector('.auto-btn-trigger').addEventListener('click', async () => {
                try {
                    const targetId = job.isVirtual && globalHb ? globalHb.id : job.id;
                    await authFetch(`/api/automation/jobs/${encodeURIComponent(targetId)}/trigger`, { method: 'POST' });
                } catch (_) { }
                await loadAutomationPanel();
            });

            row.querySelector('.auto-btn-edit').addEventListener('click', () => {
                if (job.isVirtual) {
                    openJobForm();
                    setTimeout(() => {
                        const nameInput = document.getElementById('ajf-name');
                        if (nameInput) nameInput.value = job.name;
                        const msgInput = document.getElementById('ajf-message');
                        if (msgInput) msgInput.value = `Please execute the active task named "${job.name}"`;
                        const kindSelect = document.getElementById('ajf-sched-kind');
                        if (kindSelect) {
                            kindSelect.value = 'every';
                            onSchedKindChange();
                        }
                    }, 50);
                } else {
                    openJobForm(job.id);
                }
            });

            const delBtn = row.querySelector('.auto-btn-delete');
            if (delBtn) {
                delBtn.addEventListener('click', async () => {
                    const ok = await shibaDialog('confirm', 'Delete job', `Delete "${job.name || job.id}"?`, { confirmText: 'Delete', danger: true });
                    if (!ok) return;
                    try {
                        if (!job.isVirtual) {
                            await authFetch(`/api/automation/jobs/${encodeURIComponent(job.id)}`, { method: 'DELETE' });
                        }
                        if (job.name) await _removeFromTaskMd(job.name);
                    } catch (_) { }
                    await loadAutomationPanel();
                });
            }

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

    const _resetMap = {
        'ajf-name': '',
        'ajf-sched-kind': 'every',
        'ajf-every-min': '30',
        'ajf-cron-expr': '',
        'ajf-tz': '',
        'ajf-at-dt': '',
        'ajf-message': '',
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

    onSchedKindChange();
    onDeliverChange();

    document.getElementById('automation-job-list').style.display = 'none';
    document.querySelector('.automation-modal-toolbar').style.display = 'none';
    const tabs = document.querySelector('.automation-tabs');
    if (tabs) tabs.style.display = 'none';
    form.style.display = 'flex';
    document.getElementById('ajf-name').focus();
};

function _autoFillForm(job) {
    document.getElementById('ajf-name').value = job.name || '';

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
            const el = document.getElementById('ajf-at-dt');
            if (el) el.value = new Date(d - d.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
        }
    }
    document.getElementById('ajf-tz').value = sched.tz || '';

    const payload = job.payload || {};
    document.getElementById('ajf-message').value = payload.message || '';

    const deliver = !!(payload.deliver);
    document.getElementById('ajf-deliver').checked = deliver;
    document.getElementById('ajf-channel').value = payload.channel || '';
    document.getElementById('ajf-target-id').value = payload.to || (payload.targets ? Object.values(payload.targets)[0] : '') || '';
    document.getElementById('ajf-session-key').value = payload.sessionKey || payload.session_key || '';

    const profEl = document.getElementById('ajf-profile');
    if (profEl) profEl.value = payload.profileId || payload.profile_id || '';

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
    const tabs = document.querySelector('.automation-tabs');
    if (tabs) tabs.style.display = '';
    _autoEditingId = null;
};

window.switchAutoTab = function (tab) {
    _currentAutoTab = tab;
    document.querySelectorAll('.auto-tab').forEach(el => {
        el.classList.toggle('active', el.dataset.tab === tab);
    });
    loadAutomationPanel();
};

window.clearCompletedJobs = async function () {
    const completedJobs = _autoJobs.filter(job => {
        const hasRun = ((job.state || {}).lastRunAtMs || (job.state || {}).last_run_at_ms || 0) > 0;
        const isOneShotDone = (job.schedule.kind === 'at' && hasRun);
        return !job.enabled || isOneShotDone;
    });

    if (completedJobs.length === 0) return;

    const ok = await shibaDialog('confirm', 'Clear Completed', `Delete ${completedJobs.length} completed or disabled jobs?`, { confirmText: 'Clear All', danger: true });
    if (!ok) return;

    try {
        await Promise.all(completedJobs.map(async job => {
            await authFetch(`/api/automation/jobs/${encodeURIComponent(job.id)}`, { method: 'DELETE' });
            if (job.name) await _removeFromTaskMd(job.name);
        }));
    } catch (e) {
        console.error("Error clearing completed jobs:", e);
    }
    await loadAutomationPanel();
};

// ── form field watchers ──────────────────────────────────────────────────────

window.onSchedKindChange = function () {
    const kind = document.getElementById('ajf-sched-kind').value;
    document.getElementById('ajf-sched-every').style.display = kind === 'every' ? '' : 'none';
    document.getElementById('ajf-sched-cron').style.display = kind === 'cron' ? '' : 'none';
    document.getElementById('ajf-sched-at').style.display = kind === 'at' ? '' : 'none';

    const tzRow = document.getElementById('ajf-tz-row');
    if (tzRow) tzRow.style.display = kind === 'cron' ? '' : 'none';
};

window.onDeliverChange = function () {
    const deliver = document.getElementById('ajf-deliver').checked;
    document.getElementById('ajf-delivery-fields').style.display = deliver ? '' : 'none';
};

// ── save ─────────────────────────────────────────────────────────────────────

window.saveJobForm = async function () {
    const saveBtn = document.getElementById('ajf-save-btn');
    if (saveBtn) { saveBtn.disabled = true; saveBtn.textContent = 'Saving...'; }

    try {
        const name = (document.getElementById('ajf-name').value || '').trim() || 'Job';
        const message = (document.getElementById('ajf-message').value || '').trim();
        const schedKind = document.getElementById('ajf-sched-kind').value;
        const deliver = document.getElementById('ajf-deliver').checked;
        const channel = (document.getElementById('ajf-channel').value || '').trim();
        const targetId = (document.getElementById('ajf-target-id').value || '').trim();
        const sessionKey = (document.getElementById('ajf-session-key').value || '').trim();
        const profileId = (document.getElementById('ajf-profile').value || '').trim();
        const deleteAfterRun = document.getElementById('ajf-delete-after').checked;
        const enabled = document.getElementById('ajf-enabled').checked;

        // Build schedule
        let schedule;
        if (schedKind === 'every') {
            const mins = parseInt(document.getElementById('ajf-every-min').value, 10) || 30;
            schedule = { kind: 'every', everyMs: mins * 60000 };
        } else if (schedKind === 'cron') {
            const expr = (document.getElementById('ajf-cron-expr').value || '').trim();
            const tz = (document.getElementById('ajf-tz').value || '').trim();
            if (!expr) {
                shibaDialog('alert', 'Validation', 'Cron expression is required.', { danger: true });
                return;
            }
            schedule = { kind: 'cron', expr, tz: tz || null };
        } else if (schedKind === 'at') {
            const dtVal = document.getElementById('ajf-at-dt').value;
            if (!dtVal) {
                shibaDialog('alert', 'Validation', 'Date/time is required for one-shot jobs.', { danger: true });
                return;
            }
            const atMs = new Date(dtVal).getTime();
            if (isNaN(atMs)) {
                shibaDialog('alert', 'Validation', 'Invalid date/time.', { danger: true });
                return;
            }
            schedule = { kind: 'at', atMs };
        } else {
            shibaDialog('alert', 'Validation', 'Invalid schedule type.', { danger: true });
            return;
        }

        const payload = {
            kind: 'scheduled',
            message,
            deliver,
            channel: deliver ? (channel || null) : null,
            to: deliver && !channel ? (targetId || null) : null,
            targets: (deliver && channel && targetId) ? { [channel]: targetId } : {},
            sessionKey: sessionKey || null,
            profileId: profileId || null,
        };

        const body = {
            name,
            enabled,
            deleteAfterRun,
            schedule,
            payload,
        };

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

async function _removeFromTaskMd(taskName) {
    try {
        let taskMd = '';
        try {
            const resp = await authFetch(`/api/file-get?path=TASK.md&_t=${Date.now()}`);
            if (resp.ok) taskMd = await resp.text();
        } catch (_) { return; }

        if (!taskMd) return;

        const escapedName = taskName.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
        const reExisting = new RegExp(`(^|\\r?\\n)(?:###?\\s*Task:\\s*${escapedName}|##\\s+${escapedName})\\s*\\r?\\n[\\s\\S]*?(?=\\r?\\n#+\\s+|$)`, 'gi');
        const cleaned = taskMd.replace(reExisting, '').replace(/(?:\r?\n){3,}/g, '\n\n').trim() + '\n';

        if (cleaned !== taskMd) {
            await authFetch('/api/file-save', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ path: 'TASK.md', content: cleaned }),
            });
        }
    } catch (e) {
        console.warn('Failed to clean TASK.md:', e);
    }
}

// ── openModal hook ────────────────────────────────────────────────────────────
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

function initAutomation() {
    patchOpenModal();
    loadAutomationPanel(); // Load immediately to populate badge
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initAutomation);
} else {
    initAutomation();
}
