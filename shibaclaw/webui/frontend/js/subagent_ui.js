/** Session-scoped delegation cards. All task content is rendered as plain text. */
window.subagentUI = {
    sessions: new Map(),
    pendingCancels: new Set(),
    sessionKey: '',
    terminal: new Set(['succeeded', 'failed', 'cancelled', 'timed_out', 'incomplete']),
    labels: {
        running: ['In progress', 'In corso'], succeeded: ['Completed', 'Completato'],
        failed: ['Failed', 'Errore'], cancelled: ['Cancelled', 'Annullato'],
        timed_out: ['Timed out', 'Tempo scaduto'], incomplete: ['Incomplete', 'Incompleto'],
        executing: ['Execution', 'Esecuzione'], auditing: ['Audit', 'Verifica'],
        details: ['Task details', 'Dettagli del task'], cancel: ['Cancel task', 'Annulla task'],
        cancel_error: ['Could not cancel the task. Reconnecting may help.', 'Impossibile annullare il task. Prova a riconnetterti.'],
        disconnected: ['Connection lost · status may be outdated', 'Connessione persa · stato da aggiornare'],
    },
    text(key) {
        const lang = typeof currentLanguage === 'string' ? currentLanguage : (document.documentElement.lang || navigator.language || 'en');
        return (this.labels[key] || [key, key])[lang.startsWith('it') ? 1 : 0];
    },
    key(value) { return String(value || '').replace(/^webui:/, '').trim(); },
    node(tag, cls, text) {
        const el = document.createElement(tag);
        if (cls) el.className = cls;
        if (text !== undefined) el.textContent = text;
        return el;
    },
    init() {
        this.container = document.getElementById('subagent-feedback-container');
        this.avatarBtn = document.getElementById('subagent-avatar-btn');
        this.drawer = document.getElementById('subagent-drawer');
        if (this.avatarBtn) {
            this.avatarBtn.setAttribute('role', 'button');
            this.avatarBtn.setAttribute('tabindex', '0');
            this.avatarBtn.setAttribute('aria-expanded', 'false');
            const toggle = () => {
                const open = this.drawer?.classList.toggle('open');
                this.avatarBtn.setAttribute('aria-expanded', String(!!open));
            };
            this.avatarBtn.addEventListener('click', toggle);
            this.avatarBtn.addEventListener('keydown', e => {
                if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); toggle(); }
                if (e.key === 'Escape') this.closeDrawer();
            });
        }
        document.addEventListener('click', e => {
            if (this.container && !this.container.contains(e.target)) this.closeDrawer();
        });
        this.timer = setInterval(() => this.tick(), 1000);
    },
    closeDrawer() {
        this.drawer?.classList.remove('open');
        this.avatarBtn?.setAttribute('aria-expanded', 'false');
    },
    selectSession(value) {
        this.sessionKey = this.key(value);
        this.needsSync = true;
        if (!this.sessions.has(this.sessionKey)) this.sessions.set(this.sessionKey, new Map());
        document.querySelectorAll('.subagent-run-card').forEach(el => el.remove());
        this.closeDrawer();
        this.render();
    },
    receive(data, render = true) {
        const row = data.metadata || data;
        const key = this.key(row.session_key || data.session_key);
        if (!key || !row.task_id) return;
        if (!this.sessions.has(key)) this.sessions.set(key, new Map());
        const rows = this.sessions.get(key);
        const old = rows.get(row.task_id);
        if (old && ((row.revision || 0) < (old.revision || 0) ||
            (this.terminal.has(old.status) && !this.terminal.has(row.status)))) return;
        rows.set(row.task_id, { ...old, ...row });
        const completed = [...rows.values()].filter(item => this.terminal.has(item.status));
        completed.slice(0, Math.max(0, completed.length - 100)).forEach(item => rows.delete(item.task_id));
        if (this.terminal.has(row.status)) this.pendingCancels.delete(row.task_id);
        if (render && key === this.sessionKey) this.render();
    },
    snapshot(data) {
        const key = this.key(data.session_key);
        if (data.snapshot_at && this.sessions.has(key)) {
            const ids = new Set((data.tasks || []).map(row => row.task_id));
            for (const [id, row] of this.sessions.get(key)) {
                if (!ids.has(id) && row.started_at <= data.snapshot_at) {
                    this.sessions.get(key).delete(id);
                    if (key === this.sessionKey) document.getElementById(`task-run-${id}`)?.remove();
                }
            }
        }
        // Merge by revision: progress may arrive while the snapshot is in flight.
        for (const row of data.tasks || []) this.receive({ ...row, session_key: data.session_key }, false);
        if (key === this.sessionKey) { this.offline = false; this.needsSync = false; this.lastSync = Date.now(); this.render(); }
    },
    setConnected(connected) { this.offline = !connected; this.render(); },
    rows() { return [...(this.sessions.get(this.sessionKey)?.values() || [])]; },
    render() {
        const rows = this.rows();
        const active = rows.filter(row => !this.terminal.has(row.status));
        if (this.container) this.container.style.display = active.length ? 'flex' : 'none';
        if (!active.length) this.closeDrawer();
        if (this.avatarBtn) {
            this.avatarBtn.setAttribute('aria-label', `${active.length} active tasks`);
            this.avatarBtn.setAttribute('title', `${active.length} active tasks`);
            let count = this.avatarBtn.querySelector('.subagent-count');
            if (!count) { count = this.node('span', 'subagent-count'); this.avatarBtn.appendChild(count); }
            count.textContent = String(active.length);
        }
        if (this.drawer) {
            this.drawer.replaceChildren();
            active.forEach(row => {
                const item = this.node('div', 'subagent-task');
                item.appendChild(this.node('div', 'subagent-task-header', row.label));
                item.appendChild(this.node('div', 'subagent-task-status', this.statusText(row)));
                this.drawer.appendChild(item);
            });
        }
        const history = document.getElementById('chat-history');
        if (!history) return;
        // Preserve the reader's position; no forced scroll for background updates.
        const pinned = history.scrollHeight - history.clientHeight - history.scrollTop < 80;
        const visibleIds = new Set(rows.map(row => row.task_id));
        history.querySelectorAll('.subagent-run-card').forEach(card => {
            if (!visibleIds.has(card.getAttribute('data-task-id'))) card.remove();
        });
        for (const row of rows) this.renderCard(history, row);
        this.tick();
        if (pinned && rows.length && typeof scrollToBottom === 'function') scrollToBottom();
    },
    statusText(row) {
        if (this.offline && !this.terminal.has(row.status)) return this.text('disconnected');
        const phase = row.kind === 'mea' ? ` · ${this.text(row.phase || 'executing')}` : '';
        return `${this.text(row.status || 'running')}${phase}${row.current_tool ? ` · ${row.current_tool}` : ''}`;
    },
    renderCard(history, row) {
        const id = `task-run-${row.task_id}`;
        let card = document.getElementById(id);
        if (card && card._runRevision === row.revision && card._runOffline === !!this.offline) return;
        const focused = card?.contains?.(document.activeElement);
        const focusCancel = focused && document.activeElement?.classList.contains('subagent-run-cancel');
        const open = card?.querySelector('.subagent-run-details')?.open || false;
        if (!card) {
            card = this.node('article', 'subagent-run-card');
            card.setAttribute('id', id);
            card.setAttribute('data-task-id', row.task_id);
            const nextMessage = [...history.children].find(node => Number(node.getAttribute('data-message-at')) > row.started_at);
            if (nextMessage) history.insertBefore(card, nextMessage);
            else history.appendChild(card);
        }
        card._runRevision = row.revision;
        card._runOffline = !!this.offline;
        card.setAttribute('data-status', row.status);
        card.setAttribute('data-parent-turn', row.parent_turn_id || '');
        card.replaceChildren();
        const header = this.node('div', 'subagent-run-header');
        header.appendChild(this.node('strong', '', row.label || row.task_id));
        const duration = this.node('span', 'subagent-run-duration');
        duration.setAttribute('data-started', row.started_at || 0);
        duration.setAttribute('data-finished', row.finished_at || 0);
        header.appendChild(duration);
        card.appendChild(header);
        card.appendChild(this.node('p', 'subagent-run-summary', (row.task || '').slice(0, 160)));
        card.appendChild(this.node('div', 'subagent-run-status', this.statusText(row)));
        const details = this.node('details', 'subagent-run-details');
        details.open = open;
        details.appendChild(this.node('summary', '', this.text('details')));
        details.appendChild(this.node('p', 'subagent-run-task', row.task || ''));
        if (row.steps?.length) {
            const steps = this.node('ol', 'subagent-run-steps');
            row.steps.forEach(step => steps.appendChild(this.node('li', '', step.tool)));
            details.appendChild(steps);
        }
        if (row.verdict) details.appendChild(this.node('p', '', row.verdict));
        if (row.result) details.appendChild(this.node('pre', 'subagent-run-result', row.result));
        if (row.error) details.appendChild(this.node('pre', 'subagent-run-error', row.error));
        card.appendChild(details);
        if (!this.terminal.has(row.status)) {
            const cancel = this.node('button', 'subagent-run-cancel', this.text('cancel'));
            cancel.type = 'button';
            cancel.disabled = !!this.offline || this.pendingCancels.has(row.task_id);
            cancel.addEventListener('click', () => {
                cancel.disabled = true;
                this.pendingCancels.add(row.task_id);
                const sent = realtime.emit('subagent_cancel', { task_id: row.task_id });
                if (sent === false) this.cancelAck({ task_id: row.task_id, session_key: row.session_key, cancelled: false });
            });
            card.appendChild(cancel);
        }
        if (focused) {
            const target = focusCancel ? card.querySelector('.subagent-run-cancel') : null;
            (target && !target.disabled ? target : details.querySelector('summary'))?.focus({ preventScroll: true });
        }
    },
    cancelAck(data) {
        if (this.key(data.session_key) !== this.sessionKey) return;
        const card = document.getElementById(`task-run-${data.task_id}`);
        if (!data.cancelled) this.pendingCancels.delete(data.task_id);
        if (!data.cancelled && card) {
            card.appendChild(this.node('p', 'subagent-run-error', this.text('cancel_error')));
            const button = card.querySelector('.subagent-run-cancel');
            if (button) button.disabled = false;
        }
    },
    tick() {
        // Recover a lost terminal event or a gateway restart without reloading
        // the browser. This never invokes an LLM and only polls pending work.
        if (typeof realtime !== 'undefined' && realtime.connected && this.sessionKey &&
            (this.needsSync || this.rows().some(row => !this.terminal.has(row.status))) &&
            Date.now() - (this.lastSync || 0) > 15000) {
            this.lastSync = Date.now();
            realtime.emit('subagent_sync', {});
        }
        document.querySelectorAll('.subagent-run-duration').forEach(el => {
            const start = Number(el.getAttribute('data-started'));
            const end = Number(el.getAttribute('data-finished')) || Date.now() / 1000;
            const secs = Math.max(0, Math.floor(end - start));
            el.textContent = `${Math.floor(secs / 60)}:${String(secs % 60).padStart(2, '0')}`;
        });
    },
};
document.addEventListener('DOMContentLoaded', () => window.subagentUI.init());
