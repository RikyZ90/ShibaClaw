// ── Channel icons & labels for grouping ─────────────────────
const CHANNEL_META = {
    webui: { icon: "language", label: "Web UI" },
    telegram: { icon: "send", label: "Telegram" },
    discord: { icon: "forum", label: "Discord" },
    slack: { icon: "tag", label: "Slack" },
    api: { icon: "api", label: "API" },
    cli: { icon: "terminal", label: "CLI" },
    automation: { icon: "autorenew", label: "Automation" },
    heartbeat: { icon: "autorenew", label: "Recurring" },
    cron: { icon: "schedule_send", label: "One-time" },
    _default: { icon: "chat_bubble", label: "Other" }
};
const RECENT_COUNT = 4;

const _channelCollapsed = {};

function _extractChannel(key) {
    const rawKey = (key || "").trim();
    const idx = rawKey.indexOf(":");
    if (idx > 0) {
        return rawKey.substring(0, idx).toLowerCase();
    }
    if (rawKey) {
        return "automation";
    }
    return "_default";
}

function _channelInfo(ch) {
    return CHANNEL_META[ch] || { icon: CHANNEL_META._default.icon, label: ch.charAt(0).toUpperCase() + ch.slice(1) };
}

function _sessionKeyTail(key) {
    const rawKey = key || "";
    const idx = rawKey.indexOf(":");
    return idx >= 0 ? rawKey.substring(idx + 1) : rawKey;
}

function _escapeRegExp(text) {
    return text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function _cleanSessionTitle(name, sessionKey) {
    const rawName = (name || "").trim();
    const rawKey = (sessionKey || "").trim();
    const fallback = _sessionKeyTail(rawKey).trim();

    if (!rawName) return fallback;
    if (!rawKey.includes(":")) return rawName;

    const channel = _extractChannel(rawKey);
    const channelLabel = _channelInfo(channel).label;
    const prefixes = Array.from(new Set([
        channel,
        channelLabel,
        channelLabel.replace(/\s+/g, "")
    ].filter(Boolean)));

    let cleaned = rawName;
    prefixes.forEach((prefix) => {
        cleaned = cleaned.replace(new RegExp(`^${_escapeRegExp(prefix)}(?:_|:)\\s*`, "i"), "");
    });
    cleaned = cleaned.trim();

    return cleaned || fallback || rawName;
}

function _getSessionChannelLabel(sessionKey) {
    const rawKey = (sessionKey || "").trim();
    if (!rawKey.includes(":")) return "";
    return _channelInfo(_extractChannel(rawKey)).label;
}

function _appendHistoryAttachment(container, file) {
    if (!file) return;
    if (file.type && file.type.startsWith("image/")) {
        const img = document.createElement("img");
        img.src = authUrl(file.url);
        img.onload = () => { if (typeof scrollToBottom === 'function') scrollToBottom(); };
        img.onclick = () => window.open(authUrl(file.url), "_blank");
        container.appendChild(img);
        if (typeof scrollToBottom === 'function') scrollToBottom();
        return;
    }

    const link = buildFileAttachmentLink(file, () => {
        downloadAttachment(file.url, file.name || "attachment");
    });
    container.appendChild(link);
}

function _isCurrentSessionLoad(loadSeq, sessionId) {
    return state.sessionLoadSeq === loadSeq && state.sessionId === sessionId;
}

function _clearOAuthPoll(scope) {
    const polls = state.oauthPolls || (state.oauthPolls = {});
    if (!polls[scope]) return;
    clearInterval(polls[scope]);
    delete polls[scope];
}

function _clearOAuthPollsByPrefix(prefix) {
    const polls = state.oauthPolls || {};
    Object.keys(polls).forEach((scope) => {
        if (!prefix || scope.startsWith(prefix)) {
            _clearOAuthPoll(scope);
        }
    });
}

function _clearAllOAuthPolls() {
    _clearOAuthPollsByPrefix("");
}

window.clearAllOAuthPolls = _clearAllOAuthPolls;

function _startOAuthJobPoll(scope, jobId, onUpdate) {
    _clearOAuthPoll(scope);
    const polls = state.oauthPolls || (state.oauthPolls = {});
    let inFlight = false;
    let pollCount = 0;
    const MAX_POLLS = 150; // 5 minutes at 2s interval — prevents infinite polling
    polls[scope] = setInterval(async () => {
        if (++pollCount > MAX_POLLS) {
            console.warn("OAuth poll for", scope, "exceeded max attempts, stopping.");
            _clearOAuthPoll(scope);
            return;
        }
        if (inFlight) return;
        inFlight = true;
        try {
            const r2 = await authFetch("/api/oauth/job/" + jobId);
            const payload = await r2.json();
            if (!payload.job) return;
            if (await onUpdate(payload.job)) {
                _clearOAuthPoll(scope);
            }
        } catch (_) {
            // Keep polling until the flow finishes or is explicitly cleaned up.
        } finally {
            inFlight = false;
        }
    }, 2000);
}

async function _loadContextModalContent() {
    const contentEl = $("context-content");
    if (!contentEl) return;

    if (!state.sessionId) {
        contentEl.innerHTML = "<div class='loader'>No active session</div>";
        return;
    }

    const sessionId = state.sessionId;
    contentEl.innerHTML = `<div class="loader">Loading context...</div>`;
    try {
        const res = await authFetch(`/api/context?session_id=${encodeURIComponent(sessionId)}`);
        const data = await res.json();
        if (!state.contextModalOpen || state.sessionId !== sessionId) return;
        const t = data.tokens || {};
        const tokenCard = buildTokenCard(t);
        contentEl.innerHTML = tokenCard + renderMarkdown(data.context);
        enhanceCodeBlocks(contentEl);
        updateTokenBadge(t);
    } catch (e) {
        if (!state.contextModalOpen || state.sessionId !== sessionId) return;
        contentEl.innerHTML = "Error loading context.";
    }
}

function _buildSessionEl(sess) {
    const el = document.createElement("div");
    el.className = "history-item";
    el.dataset.sessionKey = sess.key;
    if (sess.key === state.sessionId) el.classList.add("active");

    const date = new Date(sess.created_at).toLocaleDateString();
    const time = new Date(sess.updated_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    const name = sess.nickname || sess.key;
    const displayName = _cleanSessionTitle(name, sess.key);
    const channel = _extractChannel(sess.key);
    const channelLabel = _channelInfo(channel).label;
    const safeKey = encodeURIComponent(sess.key);
    const safeName = escapeHtml(displayName);
    const safeChannelLabel = escapeHtml(channelLabel);

    // Skip empty channels but otherwise render badged tag
    const channelTag = channelLabel ? `<span class="ob-badge badge-channel-${escapeHtml(channel)} session-channel-tag">${safeChannelLabel}</span>` : "";

    el.innerHTML = `
        <div class="session-info">
            <div class="session-name">${safeName}</div>
            <div class="session-subline">
                ${channelTag}
                <div class="session-meta">${date} ${time}</div>
            </div>
        </div>
        <div class="session-actions">
            <button class="btn-session-menu">
                <span class="material-icons-round">more_vert</span>
            </button>
            <div class="session-dropdown" data-session-key="${safeKey}">
                <div class="dropdown-item rename-action">
                    <span class="material-icons-round">edit</span> Rename
                </div>
                <div class="dropdown-item archive-action">
                    <span class="material-icons-round">archive</span> Archive
                </div>
                <div class="dropdown-item danger delete-action">
                    <span class="material-icons-round">delete</span> Delete
                </div>
            </div>
        </div>
    `;

    const infoEl = el.querySelector(".session-info");
    infoEl.addEventListener("click", () => selectSession(sess.key, infoEl));
    el.querySelector(".btn-session-menu").addEventListener("click", (e) => toggleSessionMenu(e, e.currentTarget, sess.key));
    el.querySelector(".rename-action").addEventListener("click", () => renameSessionPrompt(sess.key, displayName));
    el.querySelector(".archive-action").addEventListener("click", () => archiveSession(sess.key));
    el.querySelector(".delete-action").addEventListener("click", () => deleteSession(sess.key));

    return el;
}

function _toggleChannelGroup(ch, headerEl) {
    _channelCollapsed[ch] = !_channelCollapsed[ch];
    const items = headerEl.nextElementSibling;
    if (_channelCollapsed[ch]) {
        headerEl.classList.add("collapsed");
        items.classList.add("collapsed");
    } else {
        headerEl.classList.remove("collapsed");
        items.classList.remove("collapsed");
        items.style.maxHeight = items.scrollHeight + "px";
    }
}

async function loadHistory() {
    const list = $("history-list");
    try {
        const res = await authFetch("/api/sessions");
        const data = await res.json();
        list.innerHTML = "";

        if (!data.sessions || data.sessions.length === 0) {
            list.innerHTML = `<div class="history-item">No past sessions</div>`;
            return;
        }

        const sessions = data.sessions;
        const visibleSessions = sessions.slice(0, RECENT_COUNT);
        const remaining = sessions.slice(RECENT_COUNT);

        visibleSessions.forEach(s => list.appendChild(_buildSessionEl(s)));

        if (remaining.length > 0) {
            const moreBtn = document.createElement("button");
            moreBtn.className = "btn-show-more";
            moreBtn.innerHTML = `<span class="material-icons-round">expand_more</span> Show ${remaining.length} more`;
            moreBtn.onclick = (e) => {
                e.stopPropagation();
                remaining.forEach(s => list.insertBefore(_buildSessionEl(s), moreBtn));
                moreBtn.remove();
            };
            list.appendChild(moreBtn);
        }
    } catch (e) {
        list.innerHTML = `<div class="history-item">Error loading history</div>`;
    }
}


const _autoCollapsed = JSON.parse(localStorage.getItem("autoCollapsed") || "{}");

function _saveAutoCollapsed() {
    localStorage.setItem("autoCollapsed", JSON.stringify(_autoCollapsed));
}

function _toggleAutoSection(key, headerEl) {
    _autoCollapsed[key] = !_autoCollapsed[key];
    const items = headerEl.nextElementSibling;
    if (_autoCollapsed[key]) {
        headerEl.classList.add("collapsed");
        items.classList.add("collapsed");
    } else {
        headerEl.classList.remove("collapsed");
        items.classList.remove("collapsed");
        items.style.maxHeight = items.scrollHeight + "px";
    }
    _saveAutoCollapsed();
}

// _formatSchedule, _timeAgo, _cronStatusClass → consolidated in utils.js as formatSchedule, timeAgo, jobStatusClass

async function loadCronSection() {
    const list = $("cron-list");
    if (!list) return;
    const count = $("cron-count");
    try {
        const res = await authFetch("/api/cron/jobs");
        const data = await res.json();
        const jobs = data.jobs || [];
        if (count) count.textContent = jobs.length;

        if (jobs.length === 0) {
            list.innerHTML = `<div class="auto-empty">No one-time jobs</div>`;
            return;
        }

        list.innerHTML = "";
        for (const job of jobs) {
            const row = document.createElement("div");
            row.className = "auto-row";
            const stCls = jobStatusClass(job);
            const meta = job.state.lastRunAtMs ? timeAgo(job.state.lastRunAtMs) : formatSchedule(job.schedule);
            const safeName = escapeHtml(job.name || job.payload.message.slice(0, 30));
            row.innerHTML = `
                <div class="auto-status ${stCls}"></div>
                <div class="auto-name" title="${escapeHtml(job.payload.message)}">${safeName}</div>
                <div class="auto-meta">${escapeHtml(meta)}</div>
                <button class="btn-auto-trigger" title="Run now">▶</button>
            `;
            row.querySelector(".btn-auto-trigger").addEventListener("click", async (e) => {
                const btn = e.currentTarget;
                btn.disabled = true;
                btn.textContent = "…";
                try {
                    await authFetch(`/api/cron/jobs/${encodeURIComponent(job.id)}/trigger`, { method: "POST" });
                } catch (_) { }
                await loadCronSection();
            });
            list.appendChild(row);
        }
    } catch (e) {
        list.innerHTML = `<div class="auto-empty">Error loading one-time jobs</div>`;
    }
}

async function loadHeartbeatSection() {
    const list = $("heartbeat-list");
    if (!list) return;
    const badge = $("heartbeat-badge");
    try {
        const res = await authFetch("/api/heartbeat/status");
        const data = await res.json();

        if (!data.reachable) {
            badge.className = "automation-badge badge-off";
            badge.textContent = "offline";
            list.innerHTML = `<div class="auto-empty">Gateway unreachable</div>`;
            return;
        }

        if (!data.enabled) {
            badge.className = "automation-badge badge-off";
            badge.textContent = "off";
            list.innerHTML = `<div class="auto-empty">Recurring check disabled</div>`;
            return;
        }

        badge.className = "automation-badge " + (data.last_error ? "badge-error" : (data.running ? "badge-ok" : "badge-off"));
        badge.textContent = data.last_error ? "error" : (data.running ? "active" : "idle");

        let info = `<div class="auto-hb-info">`;
        info += `<span class="hb-label">Interval:</span> ${data.interval_min}min<br>`;
        if (data.session_key) info += `<span class="hb-label">Session:</span> ${escapeHtml(data.session_key)}<br>`;
        if (data.profile_id) info += `<span class="hb-label">Profile:</span> ${escapeHtml(data.profile_id)}<br>`;
        if (data.targets && Object.keys(data.targets).length) info += `<span class="hb-label">Targets:</span> ${escapeHtml(Object.entries(data.targets).map(([channel, target]) => `${channel}:${target}`).join(", "))}<br>`;
        if (data.last_check_ms) info += `<span class="hb-label">Last check:</span> ${timeAgo(data.last_check_ms)} — ${data.last_action || "?"}<br>`;
        if (data.last_run_ms) info += `<span class="hb-label">Last run:</span> ${timeAgo(data.last_run_ms)}<br>`;
        if (data.last_error) info += `<span class="hb-label">Error:</span> ${escapeHtml(data.last_error)}<br>`;
        info += `<span class="hb-label">File:</span> ${data.heartbeat_file_exists ? `<a class="hb-file-link" href="#" onclick="openHeartbeatFile(event)">TASK.md</a>` : "missing"}`;
        info += `</div>`;
        info += `<div class="auto-row"><button class="btn-auto-trigger" id="btn-hb-trigger" title="Run recurring check now">▶ Trigger</button></div>`;

        list.innerHTML = info;
        $("btn-hb-trigger").addEventListener("click", async (e) => {
            const btn = e.currentTarget;
            btn.disabled = true;
            btn.textContent = "…";
            try {
                await authFetch("/api/heartbeat/trigger", { method: "POST" });
            } catch (_) { }
            await loadHeartbeatSection();
        });
    } catch (e) {
        badge.className = "automation-badge badge-off";
        badge.textContent = "";
        list.innerHTML = `<div class="auto-empty">Error loading status</div>`;
    }
}

function initAutomationSections() {
    const cronHeader = $("cron-header");
    const hbHeader = $("heartbeat-header");
    if (!state.automationInitialized) {
        if (cronHeader) {
            cronHeader.addEventListener("click", () => _toggleAutoSection("cron", cronHeader));
            if (_autoCollapsed["cron"]) { cronHeader.classList.add("collapsed"); $("cron-list").classList.add("collapsed"); }
        }
        if (hbHeader) {
            hbHeader.addEventListener("click", () => _toggleAutoSection("heartbeat", hbHeader));
            if (_autoCollapsed["heartbeat"]) { hbHeader.classList.add("collapsed"); $("heartbeat-list").classList.add("collapsed"); }
        }
        state.automationInitialized = true;
    }
    loadCronSection();
    loadHeartbeatSection();
}

window.toggleSessionMenu = function (event, btn, key) {
    event.stopPropagation();
    const safeKey = encodeURIComponent(key);
    const dropdown = document.querySelector(`.session-dropdown[data-session-key="${safeKey}"]`);
    const isActive = dropdown && dropdown.classList.contains("active");

    document.querySelectorAll(".session-dropdown").forEach(d => {
        d.classList.remove("active");
        d.style.top = "";
        d.style.bottom = "";
        d.style.marginBottom = "";
    });
    document.querySelectorAll(".btn-session-menu").forEach(b => b.classList.remove("active"));

    if (!isActive && dropdown) {
        dropdown.classList.add("active");
        btn.classList.add("active");

        const container = dropdown.closest('.history-section');
        if (container) {
            const containerRect = container.getBoundingClientRect();
            const rect = dropdown.getBoundingClientRect();

            if (rect.bottom > containerRect.bottom) {
                dropdown.style.top = "auto";
                dropdown.style.bottom = "100%";
                dropdown.style.marginBottom = "4px";
            }
        }
    }
};

window.renameSessionPrompt = async function (key, currentName) {
    const newName = await shibaDialog("prompt", "Rename Session", "Enter new name for session:", { defaultValue: currentName, confirmText: "Rename" });
    if (newName && newName !== currentName) {
        renameSession(key, newName);
    }
};

async function renameSession(key, nickname) {
    try {
        const res = await authFetch(`/api/sessions/${encodeURIComponent(key)}`, {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ nickname })
        });
        if (res.ok) {
            if (key === state.sessionId) {
                setSessionLabel(nickname || key);
            }
            await loadHistory();
        }
    } catch (e) { console.error("Rename error:", e); }
}

async function autoTitleSession() {
    if (!state.sessionId) return;
    const firstUser = chatHistory.querySelector(".message-group.user .message-bubble");
    if (!firstUser) return;

    const text = firstUser.textContent?.trim();
    if (!text) return;

    let title = text
        .replace(/\n+/g, " ")
        .replace(/\s+/g, " ")
        .trim();
    if (title.length > 45) title = title.slice(0, 42) + "...";

    try {
        const res = await authFetch(`/api/sessions/${encodeURIComponent(state.sessionId)}`);
        if (!res.ok) return;
        const data = await res.json();
        if (data.nickname) return;
    } catch (e) { return; }

    renameSession(state.sessionId, title);
}

async function shibaDialog(type, title, message, { confirmText = "Confirm", danger = false, defaultValue = "" } = {}) {
    return new Promise(resolve => {
        const backdrop = document.getElementById("confirm-dialog");
        const msgEl = document.getElementById("confirm-message");
        const okBtn = document.getElementById("confirm-ok");
        const cancelBtn = document.getElementById("confirm-cancel");

        document.getElementById("confirm-title").textContent = title;
        msgEl.textContent = message ?? "";

        let inputEl = null;
        if (type === "prompt") {
            inputEl = document.createElement("input");
            inputEl.type = "text";
            inputEl.className = "form-input";
            inputEl.style.marginTop = "16px";
            inputEl.style.width = "100%";
            inputEl.style.fontSize = "14px";
            inputEl.style.padding = "10px";
            inputEl.value = defaultValue;
            msgEl.appendChild(inputEl);
        }

        okBtn.textContent = confirmText;
        okBtn.className = danger ? "btn-danger" : "btn-primary";
        cancelBtn.style.display = (type === "alert") ? "none" : "";

        function cleanup(result) {
            backdrop.classList.remove("active");
            okBtn.removeEventListener("click", onOk);
            cancelBtn.removeEventListener("click", onCancel);
            backdrop.removeEventListener("click", onBackdrop);
            if (inputEl) inputEl.removeEventListener("keydown", onKeydown);
            resolve(result);
        }

        function onOk() {
            if (type === "prompt") cleanup(inputEl.value);
            else cleanup(true);
        }
        function onCancel() { cleanup(type === "prompt" ? null : false); }
        function onBackdrop(e) { if (e.target === backdrop) onCancel(); }
        function onKeydown(e) {
            if (e.key === "Enter") onOk();
            if (e.key === "Escape") onCancel();
        }

        okBtn.addEventListener("click", onOk);
        cancelBtn.addEventListener("click", onCancel);
        backdrop.addEventListener("click", onBackdrop);
        if (inputEl) {
            inputEl.addEventListener("keydown", onKeydown);
            setTimeout(() => inputEl.focus(), 50);
        } else {
            setTimeout(() => okBtn.focus(), 50);
        }

        backdrop.classList.add("active");
    });
}

function removeSessionFromUI(key) {
    const safeKey = encodeURIComponent(key);
    const dropdown = document.querySelector(`.session-dropdown[data-session-key="${safeKey}"]`);
    if (!dropdown) return;
    const item = dropdown.closest(".history-item");
    if (item) {
        item.style.transition = "opacity 0.2s, transform 0.2s";
        item.style.opacity = "0";
        item.style.transform = "translateX(-20px)";
        setTimeout(() => item.remove(), 200);
    }
}

window.deleteSession = async function (key) {
    const ok = await shibaDialog("confirm", "Delete Session", "This session will be permanently deleted.", { confirmText: "Delete", danger: true });
    if (!ok) return;

    removeSessionFromUI(key);
    if (state.sessionId === key) realtime.emit("new_session");

    try {
        await authFetch(`/api/sessions/${encodeURIComponent(key)}`, { method: "DELETE" });
    } catch (e) { console.error("Delete error:", e); }
};

window.archiveSession = async function (key) {
    const ok = await shibaDialog("confirm", "Archive Session", "This session will run the same consolidation flow as /new and then be removed.", { confirmText: "Archive" });
    if (!ok) return;

    removeSessionFromUI(key);
    if (state.sessionId === key) realtime.emit("new_session");

    try {
        await authFetch(`/api/sessions/${encodeURIComponent(key)}/archive`, { method: "POST" });
    } catch (e) { console.error("Archive error:", e); }
};

document.addEventListener("click", () => {
    document.querySelectorAll(".session-dropdown").forEach(d => {
        d.classList.remove("active");
        d.style.top = "";
        d.style.bottom = "";
        d.style.marginBottom = "";
    });
    document.querySelectorAll(".btn-session-menu").forEach(b => b.classList.remove("active"));
});

async function loadSession(sessionId) {
    if (typeof closeSettingsView === "function") closeSettingsView();
    if (state.processing) {
        state.processing = false;
        setWorkingState(false);
        updateSendButton();
        clearTimeout(state._typingBubbleTimeout);
        hideTypingBubble();
        hideThinking();
    }
    const loadSeq = (state.sessionLoadSeq || 0) + 1;
    state.sessionLoadSeq = loadSeq;
    state.sessionId = sessionId;
    localStorage.setItem("shiba_session_id", sessionId);

    document.querySelectorAll(".history-item").forEach(el => el.classList.remove("active"));
    const items = $("history-list").children;
    const encodedId = encodeURIComponent(sessionId);
    for (let el of items) {
        try {
            const dropdown = el.querySelector('.session-dropdown');
            if (dropdown && dropdown.dataset && dropdown.dataset.sessionKey === encodedId) {
                el.classList.add('active');
            }
        } catch (e) {
            if (el.textContent && el.textContent.includes(sessionId)) el.classList.add("active");
        }
    }

    try {
        const res = await authFetch(`/api/sessions/${encodeURIComponent(sessionId)}`);
        const data = await res.json();
        if (!_isCurrentSessionLoad(loadSeq, sessionId)) return;
        console.debug("[SHIBA] loadSession:", sessionId, "messages:", data.messages?.length || 0);

        _syncSessionUI(data, loadSeq, sessionId);
        if (!_isCurrentSessionLoad(loadSeq, sessionId)) return;

        chatHistory.innerHTML = "";
        state.messageCount = 0;
        Object.values(state.processGroups).forEach(pg => {
            if (pg && pg.timer) clearInterval(pg.timer);
        });
        state.processGroups = {};

        const messages = Array.isArray(data.messages) ? data.messages : [];
        if (messages.length > 0) {
            activateChat();
            try { refreshTokenBadge(); } catch (e) { /* ignore */ }

            const { parsedMessages, parsedGroups } = _parseSessionMessages(messages, loadSeq, sessionId);
            if (!_isCurrentSessionLoad(loadSeq, sessionId)) return;

            const fragment = document.createDocumentFragment();
            _renderSessionHistory(parsedMessages, parsedGroups, fragment, loadSeq, sessionId);
            
            if (!_isCurrentSessionLoad(loadSeq, sessionId)) return;
            chatHistory.appendChild(fragment);

            console.debug("[SHIBA] loadSession rendered:", parsedGroups.length, "process groups");
            scrollToBottom();
        } else {
            chatHistory.classList.remove("active");
            welcomeScreen.style.display = "";
        }
    } catch (e) {
        if (_isCurrentSessionLoad(loadSeq, sessionId)) {
            console.debug("[SHIBA] Error loading session:", e);
        }
    } finally {
        if (realtime.connected && _isCurrentSessionLoad(loadSeq, sessionId)) {
            realtime.emit("switch_session", { session_id: sessionId });
        }
    }
}

function _syncSessionUI(data, loadSeq, sessionId) {
    setSessionLabel(data.nickname || sessionId);
    state.profileId = data.profile_id || "default";
    if (typeof window.syncProfileSelection === "function") {
        window.syncProfileSelection(state.profileId);
    }
    if (typeof updateModelSelectorDisplay === "function") {
        updateModelSelectorDisplay(data.model || "");
    }
    if (typeof window.setActiveKBs === "function") {
        window.setActiveKBs(data.knowledge_bases || []);
    }
}

function _parseSessionMessages(messages, loadSeq, sessionId) {
    let turnSteps = [];
    let turnId = 0;
    let lastUserContent = null;
    const parsedMessages = [];
    const parsedGroups = [];

    for (const msg of messages) {
        if (!_isCurrentSessionLoad(loadSeq, sessionId)) return { parsedMessages: [], parsedGroups: [] };
        if (!msg || !msg.role) continue;
        
        if (msg.role === "user") {
            if (msg.metadata && msg.metadata.hidden) continue;
            if (!msg.content || msg.content === lastUserContent) continue;
            lastUserContent = msg.content;

            const hasExeSteps = turnSteps.some(s => s.badge === "EXE");
            if (turnSteps.length > 0 && hasExeSteps) {
                parsedGroups.push({ turnId, steps: [...turnSteps] });
            }
            turnSteps = [];
            turnId++;
            
            parsedMessages.push({ type: "user", data: msg, turnId });

        } else if (msg.role === "assistant") {
            const hasTc = msg.tool_calls && msg.tool_calls.length > 0;
            const hasContent = !!msg.content;
            const hasReasoning = !!msg.reasoning_content;

            if (hasReasoning) {
                const preview = (msg.reasoning_content?.slice?.(0, 120)) || "";
                turnSteps.push({ badge: "GEN", text: preview });
            }

            let msgToolCall = null;
            if (hasTc) {
                for (const tc of msg.tool_calls) {
                    const fn = tc.function?.name || "tool";
                    if (fn === "message") {
                        msgToolCall = tc;
                    } else {
                        let args = "";
                        try {
                            const raw = tc.function?.arguments;
                            if (raw) {
                                const parsed = typeof raw === "string" ? JSON.parse(raw) : raw;
                                const vals = Object.values(parsed);
                                if (vals.length > 0) {
                                    const preview = String(vals[0]).replace(/\n/g, " ");
                                    args = `("${truncate(preview, 60)}")`;
                                }
                            }
                        } catch { }
                        turnSteps.push({ badge: "EXE", text: fn + args });
                    }
                }
            }

            if (hasContent) {
                const hasExeSteps = turnSteps.some(s => s.badge === "EXE");
                if (turnSteps.length > 0 && hasExeSteps) {
                    parsedGroups.push({ turnId, steps: [...turnSteps] });
                    turnSteps = [];
                }
                parsedMessages.push({ type: "agent", data: msg, turnId });
            }

            if (msgToolCall) {
                const hasExeSteps = turnSteps.some(s => s.badge === "EXE");
                if (turnSteps.length > 0 && hasExeSteps) {
                    parsedGroups.push({ turnId, steps: [...turnSteps] });
                    turnSteps = [];
                }
                parsedMessages.push({ type: "tool_message", data: { msg, toolCall: msgToolCall }, turnId });
            }

            if (!hasContent && !msgToolCall && turnSteps.length > 0) {
                parsedGroups.push({ turnId, steps: [...turnSteps] });
                turnSteps = [];
            }
        }
    }
    if (turnSteps.length > 0 && turnSteps.some(s => s.badge === "EXE")) {
        parsedGroups.push({ turnId, steps: [...turnSteps] });
    }

    return { parsedMessages, parsedGroups };
}

function _renderSessionHistory(parsedMessages, parsedGroups, fragment, loadSeq, sessionId) {
    let currentGroupIdx = 0;

    for (const item of parsedMessages) {
        if (!_isCurrentSessionLoad(loadSeq, sessionId)) return;
        
        // Render any pending process groups for this turn
        while (currentGroupIdx < parsedGroups.length && parsedGroups[currentGroupIdx].turnId <= item.turnId) {
            const pg = parsedGroups[currentGroupIdx];
            renderProcessGroupFromHistory(pg.turnId, pg.steps, fragment);
            currentGroupIdx++;
        }

        if (item.type === "user") {
            const group = createMessageGroup("user", fragment);
            const bubble = document.createElement("div");
            bubble.className = "message-bubble";

            if (item.data.content) {
                bubble.innerHTML = renderMarkdown(item.data.content);
                try { bubble.setAttribute("data-raw-content", typeof item.data.content === "string" ? item.data.content : JSON.stringify(item.data.content)); } catch (e) { }
                enhanceCodeBlocks(bubble);
            }

            const attachments = item.data.metadata?.attachments || [];
            attachments.forEach(file => _appendHistoryAttachment(bubble, file));

            group.querySelector(".message-content").appendChild(bubble);
            if (item.data.timestamp) addTimestamp(group, item.data.timestamp);
            fragment.appendChild(group);

        } else if (item.type === "agent") {
            const group = createMessageGroup("agent", fragment);
            const bubble = document.createElement("div");
            bubble.className = "message-bubble";
            bubble.innerHTML = renderMarkdown(item.data.content);
            try { bubble.setAttribute("data-raw-content", typeof item.data.content === "string" ? item.data.content : JSON.stringify(item.data.content)); } catch (e) { }
            enhanceCodeBlocks(bubble);

            let attachments = item.data.metadata?.attachments ? [...item.data.metadata.attachments] : [];
            if (item.data.metadata?.media && Array.isArray(item.data.metadata.media)) {
                item.data.metadata.media.forEach(p => {
                    const name = p.split(/[/\\]/).pop();
                    let type = "application/octet-stream";
                    if (name.match(/\.(png|jpe?g|gif|webp|svg)$/i)) type = "image/png";
                    attachments.push({ name: name, url: "/api/file-get?path=" + encodeURIComponent(p), type: type });
                });
            }
            attachments.forEach(file => _appendHistoryAttachment(bubble, file));

            group.querySelector(".message-content").appendChild(bubble);
            if (item.data.timestamp) addTimestamp(group, item.data.timestamp);
            fragment.appendChild(group);

        } else if (item.type === "tool_message") {
            let toolContent = "";
            let toolMedia = [];
            try {
                const args = typeof item.data.toolCall.function.arguments === "string"
                    ? JSON.parse(item.data.toolCall.function.arguments)
                    : item.data.toolCall.function.arguments;
                toolContent = args.content || "";
                toolMedia = args.media || [];
            } catch (e) {
                console.error("Failed to parse message tool args:", e);
            }

            const group = createMessageGroup("agent", fragment);
            const bubble = document.createElement("div");
            bubble.className = "message-bubble";
            bubble.innerHTML = renderMarkdown(toolContent);
            try { bubble.setAttribute("data-raw-content", typeof toolContent === "string" ? toolContent : JSON.stringify(toolContent)); } catch (e) { }
            enhanceCodeBlocks(bubble);

            let attachments = [];
            toolMedia.forEach(p => {
                const name = p.split(/[/\\]/).pop();
                let type = "application/octet-stream";
                if (name.match(/\.(png|jpe?g|gif|webp|svg)$/i)) type = "image/png";
                attachments.push({ name: name, url: "/api/file-get?path=" + encodeURIComponent(p), type: type });
            });
            attachments.forEach(file => _appendHistoryAttachment(bubble, file));

            group.querySelector(".message-content").appendChild(bubble);
            if (item.data.msg.timestamp) addTimestamp(group, item.data.msg.timestamp);
            fragment.appendChild(group);
        }
    }

    // Render any remaining process groups
    while (currentGroupIdx < parsedGroups.length) {
        const pg = parsedGroups[currentGroupIdx];
        renderProcessGroupFromHistory(pg.turnId, pg.steps, fragment);
        currentGroupIdx++;
    }
}

window.openModal = async function (id) {
    if (id === "settings-modal") {
        window.openSettingsView();
        return;
    }
    const modal = $(id);
    if (!modal) return;
    modal.classList.add("active");

    if (typeof window.closeSidebarOnMobile === "function") {
        window.closeSidebarOnMobile();
    }

    // Dispatch event so decoupled modules (e.g. connected_apps) can hook into modal opening
    document.dispatchEvent(new CustomEvent('shiba-modal-opened', { detail: { id } }));

    if (id === "context-modal") {
        state.contextModalOpen = true;
        await _loadContextModalContent();
    } else if (id === "fs-modal") {
        await loadFs(state.currentFsPath || ".");
        if (state.fsOpenTarget) {
            const target = state.fsOpenTarget;
            state.fsOpenTarget = null;
            openFileEditor(target, target.split(/[\\/\\]/).pop());
        }
    } else if (id === "changelog-modal") {
        const contentEl = $("changelog-content");
        contentEl.innerHTML = '<div class="loader">Fetching release notes...</div>';

        try {
            const version = $("sidebar-version").textContent.replace("v", "").trim();
            const hasResolvedVersion = version && version !== "loading...";

            let releaseUrl = hasResolvedVersion
                ? `https://api.github.com/repos/RikyZ90/ShibaClaw/releases/tags/v${version}`
                : "https://api.github.com/repos/RikyZ90/ShibaClaw/releases/latest";
            let res = await fetch(releaseUrl);

            if (!res.ok && hasResolvedVersion) {
                // fallback to latest
                res = await fetch("https://api.github.com/repos/RikyZ90/ShibaClaw/releases/latest");
            }

            if (res.ok) {
                const data = await res.json();

                // Show github button
                const btn = $("changelog-github-btn");
                if (btn && data.html_url) {
                    btn.href = data.html_url;
                    btn.style.display = "inline-flex";
                }

                if (data.body) {
                    contentEl.innerHTML = renderMarkdown(data.body);
                } else {
                    contentEl.innerHTML = '<div style="color:var(--text-secondary)">No release notes available.</div>';
                }
            } else {
                throw new Error("Could not fetch release notes.");
            }
        } catch (e) {
            console.error("Changelog fetch error:", e);
            contentEl.innerHTML = `<div style="color:var(--accent-red);padding:1rem;">Failed to load release notes. Please check your connection or visit <a href="https://github.com/RikyZ90/ShibaClaw/releases" target="_blank" style="color:var(--shiba-gold)">GitHub</a>.</div>`;
        }
    }
};

window.openChangelog = function () {
    openModal("changelog-modal");
};

window.openHeartbeatFile = async function (event) {
    if (event && event.preventDefault) event.preventDefault();
    const filePath = "TASK.md";
    const dir = filePath.includes("/") ? filePath.replace(/\\/g, "/").split("/").slice(0, -1).join("/") : ".";
    state.currentFsPath = dir || ".";
    state.fsOpenTarget = filePath;
    openModal("fs-modal");
};

window.closeModal = function (id) {
    const modal = $(id);
    if (!modal) return;
    if (id === "context-modal") {
        state.contextModalOpen = false;
    }
    if (id === "settings-modal") {
        window.closeSettingsView();
        return;
    }
    if (id === "onboard-modal") {
        _clearOAuthPollsByPrefix("onboard:");
    }
    modal.classList.remove("active");
};

// ── UI Helpers ────────────────────────────────────────────────
function activateChat() {
    welcomeScreen.style.display = "none";
    chatHistory.classList.add("active");
}

function showThinking(text) {
    hideTypingBubble();
    thinkingIndicator.classList.add("active");
    thinkingText.textContent = truncate(text, 80);
}

function hideThinking() {
    thinkingIndicator.classList.remove("active");
    thinkingText.textContent = "Thinking...";
}


// ── Onboard Wizard ──────────────────────────────────────────
/* ── Model Selector (Chat Window) ────────────────────────────────── */
/* ── Heartbeat panel ── */
async function loadHeartbeatSettingsPanel() {
    const profileSelect = $("s-hb-profile");
    if (!profileSelect) return;
    try {
        const res = await authFetch("/api/profiles");
        if (res.ok) {
            const data = await res.json();
            const profiles = data.profiles || [];
            let html = '<option value="">Default (inherit)</option>';
            for (const p of profiles) {
                html += `<option value="${escapeHtml(p.id)}">${escapeHtml(p.label)}</option>`;
            }
            const currentVal = profileSelect.value;
            profileSelect.innerHTML = html;
            profileSelect.value = currentVal; // Restore selection after populating
        }
    } catch (e) {
        console.error("loadHeartbeatSettingsPanel profiles fetch failed", e);
    }
}
