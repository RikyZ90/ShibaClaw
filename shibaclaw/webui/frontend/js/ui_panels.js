// ── Channel icons & labels for grouping ─────────────────────
const CHANNEL_META = {
    webui: { icon: "language" },
    telegram: { icon: "send" },
    discord: { icon: "forum" },
    slack: { icon: "tag" },
    api: { icon: "api" },
    cli: { icon: "terminal" },
    automation: { icon: "autorenew" },
    heartbeat: { icon: "autorenew" },
    cron: { icon: "schedule_send" },
    _default: { icon: "chat_bubble" }
};
const _CHANNEL_LABEL_FB = {
    webui: "Web UI", telegram: "Telegram", discord: "Discord", slack: "Slack",
    api: "API", cli: "CLI", automation: "Automation", heartbeat: "Recurring",
    cron: "One-time", other: "Other"
};
function _channelLabel(ch) {
    const key = ch === "_default" ? "sessions.channel.other" : `sessions.channel.${ch}`;
    return (typeof t === "function" ? t(key) : _CHANNEL_LABEL_FB[ch === "_default" ? "other" : ch])
        || _CHANNEL_LABEL_FB[ch === "_default" ? "other" : ch]
        || ch.charAt(0).toUpperCase() + ch.slice(1);
}
const CHANNEL_ORDER = ["telegram", "webui", "automation", "heartbeat", "cron", "cli", "api", "discord", "slack"];

let _sessionSearchQuery = "";
let _sessionSearchWired = false;
let _sessionsCache = [];

const _channelCollapsed = JSON.parse(localStorage.getItem("sessionChannelCollapsed") || "{}");

function _saveChannelCollapsed() {
    localStorage.setItem("sessionChannelCollapsed", JSON.stringify(_channelCollapsed));
}

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
    const meta = CHANNEL_META[ch] || CHANNEL_META._default;
    return { icon: meta.icon, label: _channelLabel(ch === "_default" ? "other" : ch) };
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

function _sessionUpdatedMs(sess) {
    let iso = (sess && (sess.updated_at || sess.created_at)) || "";
    if (!iso) return 0;
    // Older session records may contain naive UTC ISO timestamps.
    if (/^\d{4}-\d{2}-\d{2}T/.test(iso) && !/[zZ]|[+-]\d{2}:?\d{2}$/.test(iso)) {
        iso += "Z";
    }
    const ms = Date.parse(iso);
    return Number.isFinite(ms) ? ms : 0;
}

function _formatSessionWhen(sess) {
    const ms = _sessionUpdatedMs(sess);
    if (!ms) return "";
    return new Date(ms).toLocaleString(undefined, {
        day: "2-digit",
        month: "2-digit",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
    });
}

function _buildSessionEl(sess) {
    const el = document.createElement("div");
    el.className = "history-item";
    el.dataset.sessionKey = sess.key;
    if (sess.key === state.sessionId) el.classList.add("active");

    const when = _formatSessionWhen(sess);
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
                <div class="session-meta">${when}</div>
            </div>
        </div>
        <div class="session-actions">
            <button class="btn-session-menu">
                <span class="material-icons-round">more_vert</span>
            </button>
            <div class="session-dropdown" data-session-key="${safeKey}">
                <div class="dropdown-item rename-action">
                    <span class="material-icons-round">edit</span> ${escapeHtml(typeof t === "function" ? t("sessions.rename") : "Rename")}
                </div>
                <div class="dropdown-item archive-action">
                    <span class="material-icons-round">archive</span> ${escapeHtml(typeof t === "function" ? t("sessions.archive") : "Archive")}
                </div>
                <div class="dropdown-item danger delete-action">
                    <span class="material-icons-round">delete</span> ${escapeHtml(typeof t === "function" ? t("sessions.delete") : "Delete")}
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
    _saveChannelCollapsed();
    const items = headerEl.nextElementSibling;
    if (_channelCollapsed[ch]) {
        headerEl.classList.add("collapsed");
        items.classList.add("collapsed");
        items.style.maxHeight = "";
    } else {
        headerEl.classList.remove("collapsed");
        items.classList.remove("collapsed");
        items.style.maxHeight = items.scrollHeight + "px";
    }
}

function _wireSessionSearch() {
    const input = $("session-search");
    if (!input || _sessionSearchWired) return;
    _sessionSearchWired = true;
    if (_sessionSearchQuery) input.value = _sessionSearchQuery;
    let msgSearchTimer = null;
    input.addEventListener("input", () => {
        _sessionSearchQuery = input.value || "";
        _renderSessionsList();
        clearTimeout(msgSearchTimer);
        const q = (_sessionSearchQuery || "").trim();
        if (q.length < 2) {
            _clearMessageHits();
            return;
        }
        msgSearchTimer = setTimeout(() => _searchMessageBodies(q), 280);
    });
}

function _clearMessageHits() {
    const el = document.getElementById("session-msg-hits");
    if (el) el.remove();
}

async function _searchMessageBodies(q) {
    try {
        const res = await authFetch(
            `/api/sessions/search?q=${encodeURIComponent(q)}&limit=12`
        );
        if (!res.ok) return;
        const data = await res.json();
        _renderMessageHits(data.hits || [], q);
    } catch {
        /* ignore */
    }
}

function _renderMessageHits(hits, q) {
    _clearMessageHits();
    const list = $("history-list");
    if (!list || !hits.length) return;
    const wrap = document.createElement("div");
    wrap.id = "session-msg-hits";
    wrap.className = "session-msg-hits";
    for (const hit of hits) {
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "session-msg-hit";
        const key = hit.session_key || "";
        btn.innerHTML = `<strong>${escapeHtml(_cleanSessionTitle(key, key))}</strong> · ${escapeHtml(hit.role || "")}<br>${escapeHtml(hit.snippet || "")}`;
        btn.addEventListener("click", () => {
            if (typeof loadSession === "function") loadSession(key);
        });
        wrap.appendChild(btn);
    }
    list.prepend(wrap);
}

function _sessionMatchesQuery(sess, q) {
    if (!q) return true;
    const name = sess.nickname || sess.key || "";
    const display = _cleanSessionTitle(name, sess.key);
    const hay = `${display} ${name} ${sess.key || ""}`.toLowerCase();
    return hay.includes(q);
}

function _sortedChannelKeys(groups) {
    const keys = Object.keys(groups);
    keys.sort((a, b) => {
        const ia = CHANNEL_ORDER.indexOf(a);
        const ib = CHANNEL_ORDER.indexOf(b);
        const ra = ia === -1 ? 999 : ia;
        const rb = ib === -1 ? 999 : ib;
        if (ra !== rb) return ra - rb;
        return a.localeCompare(b);
    });
    return keys;
}

function _renderSessionsList() {
    const list = $("history-list");
    if (!list) return;
    _wireSessionSearch();

    const searchEl = $("session-search");
    if (searchEl && document.activeElement !== searchEl) {
        searchEl.value = _sessionSearchQuery;
    }

    const q = (_sessionSearchQuery || "").trim().toLowerCase();
    const sessions = (_sessionsCache || []).filter((s) => _sessionMatchesQuery(s, q));

    list.innerHTML = "";

    if (!_sessionsCache.length) {
        list.innerHTML = `<div class="history-empty">${escapeHtml(typeof t === "function" ? t("sessions.empty") : "No past sessions")}</div>`;
        return;
    }
    if (!sessions.length) {
        list.innerHTML = `<div class="history-empty">${escapeHtml(typeof t === "function" ? t("sessions.no_matches") : "No matches")}</div>`;
        return;
    }

    const groups = {};
    for (const sess of sessions) {
        const ch = _extractChannel(sess.key);
        (groups[ch] || (groups[ch] = [])).push(sess);
    }

    for (const ch of _sortedChannelKeys(groups)) {
        const info = _channelInfo(ch);
        const items = groups[ch];
        const collapsed = !!_channelCollapsed[ch];

        const header = document.createElement("div");
        header.className = "channel-group-header" + (collapsed ? " collapsed" : "");
        header.innerHTML = `
            <span class="material-icons-round">${escapeHtml(info.icon)}</span>
            <span>${escapeHtml(info.label)}</span>
            <span class="group-count">${items.length}</span>
            <span class="material-icons-round group-chevron">expand_more</span>
        `;

        const itemsEl = document.createElement("div");
        itemsEl.className = "channel-group-items" + (collapsed ? " collapsed" : "");
        items.sort((a, b) => _sessionUpdatedMs(b) - _sessionUpdatedMs(a));
        items.forEach((s) => itemsEl.appendChild(_buildSessionEl(s)));

        header.addEventListener("click", () => _toggleChannelGroup(ch, header));
        list.appendChild(header);
        list.appendChild(itemsEl);

        if (!collapsed) {
            // After layout so scrollHeight is correct.
            requestAnimationFrame(() => {
                itemsEl.style.maxHeight = itemsEl.scrollHeight + "px";
            });
        }
    }
}

async function loadHistory() {
    const list = $("history-list");
    try {
        const res = await authFetch("/api/sessions");
        const data = await res.json();
        _sessionsCache = data.sessions || [];
        _renderSessionsList();
    } catch (e) {
        if (list) list.innerHTML = `<div class="history-empty">${escapeHtml(typeof t === "function" ? t("sessions.load_error") : "Error loading history")}</div>`;
    }
}
window.loadHistory = loadHistory;
window._renderSessionsList = _renderSessionsList;


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
    document.querySelectorAll(".history-item").forEach(item => item.classList.remove("has-active-dropdown"));

    if (!isActive && dropdown) {
        dropdown.classList.add("active");
        btn.classList.add("active");

        const historyItem = btn.closest(".history-item");
        if (historyItem) {
            historyItem.classList.add("has-active-dropdown");
        }

        const container = dropdown.closest('.history-section');
        if (container) {
            const containerRect = container.getBoundingClientRect();
            const rect = dropdown.getBoundingClientRect();

            if (rect.bottom > containerRect.bottom - 10 || rect.bottom > window.innerHeight - 10) {
                dropdown.style.top = "auto";
                dropdown.style.bottom = "100%";
                dropdown.style.marginBottom = "4px";
            }
        }
    }
};

window.renameSessionPrompt = async function (key, currentName) {
    const newName = await shibaDialog("prompt",
        typeof t === "function" ? t("sessions.rename_title") : "Rename Session",
        typeof t === "function" ? t("sessions.rename_prompt") : "Enter new name for session:",
        { defaultValue: currentName, confirmText: typeof t === "function" ? t("sessions.rename") : "Rename" });
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
    const ok = await shibaDialog("confirm",
        typeof t === "function" ? t("sessions.delete_title") : "Delete Session",
        typeof t === "function" ? t("sessions.delete_body") : "This session will be permanently deleted.",
        { confirmText: typeof t === "function" ? t("sessions.delete") : "Delete", danger: true });
    if (!ok) return;

    removeSessionFromUI(key);
    if (state.sessionId === key) realtime.emit("new_session");

    try {
        await authFetch(`/api/sessions/${encodeURIComponent(key)}`, { method: "DELETE" });
    } catch (e) { console.error("Delete error:", e); }
};

window.archiveSession = async function (key) {
    const ok = await shibaDialog("confirm",
        typeof t === "function" ? t("sessions.archive_title") : "Archive Session",
        typeof t === "function" ? t("sessions.archive_body") : "This session will run the same consolidation flow as /new and then be removed.",
        { confirmText: typeof t === "function" ? t("sessions.archive") : "Archive" });
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
    document.querySelectorAll(".history-item").forEach(item => item.classList.remove("has-active-dropdown"));
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

            if (typeof ensureTelegramOwnerIds === "function") {
                await ensureTelegramOwnerIds();
            }
            if (!_isCurrentSessionLoad(loadSeq, sessionId)) return;

            const fragment = document.createDocumentFragment();
            _renderSessionHistory(parsedMessages, parsedGroups, fragment, loadSeq, sessionId);
            
            if (!_isCurrentSessionLoad(loadSeq, sessionId)) return;
            chatHistory.appendChild(fragment);

            // Open already at the latest messages before the first paint.
            chatHistory.scrollTop = chatHistory.scrollHeight;
            console.debug("[SHIBA] loadSession rendered:", parsedGroups.length, "process groups");
            scrollToBottom({ force: true });
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
    if (typeof window.updateReasoningSelectorDisplay === "function") {
        window.updateReasoningSelectorDisplay(data.reasoning_effort || null, data.model || "");
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
            const hasMedia = !!(msg.metadata && msg.metadata.media && msg.metadata.media.length);
            if ((!msg.content && !hasMedia) || (msg.content && msg.content === lastUserContent)) continue;
            if (msg.content) lastUserContent = msg.content;

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
        while (currentGroupIdx < parsedGroups.length && (item.type === "user" ? parsedGroups[currentGroupIdx].turnId < item.turnId : parsedGroups[currentGroupIdx].turnId <= item.turnId)) {
            const pg = parsedGroups[currentGroupIdx];
            renderProcessGroupFromHistory(pg.turnId, pg.steps, fragment);
            currentGroupIdx++;
        }

        if (item.type === "user") {
            const cls = (typeof classifySessionMessage === "function")
                ? classifySessionMessage(item.data, sessionId)
                : { type: "user", label: null };
            const group = createMessageGroup(cls.type, fragment, { label: cls.label });
            const bubble = document.createElement("div");
            bubble.className = "message-bubble";

            if (item.data.content) {
                bubble.innerHTML = renderMarkdown(item.data.content);
                try { bubble.setAttribute("data-raw-content", typeof item.data.content === "string" ? item.data.content : JSON.stringify(item.data.content)); } catch (e) { }
                enhanceCodeBlocks(bubble);
            }

            let attachments = item.data.metadata?.attachments
                ? [...item.data.metadata.attachments]
                : [];
            if (!attachments.length && Array.isArray(item.data.metadata?.media)) {
                item.data.metadata.media.forEach(p => {
                    const name = p.split(/[/\\]/).pop();
                    let type = "application/octet-stream";
                    if (name.match(/\.(png|jpe?g|gif|webp|svg)$/i)) type = "image/png";
                    else if (name.match(/\.(mp3|ogg|wav|m4a)$/i)) type = "audio/mpeg";
                    else if (name.match(/\.(mp4|webm|mov)$/i)) type = "video/mp4";
                    attachments.push({
                        name,
                        url: "/api/file-get?path=" + encodeURIComponent(p),
                        type,
                    });
                });
            }
            attachments.forEach(file => _appendHistoryAttachment(bubble, file));

            group.querySelector(".message-content").appendChild(bubble);
            if (item.data.timestamp) addTimestamp(group, item.data.timestamp);
            fragment.appendChild(group);

        } else if (item.type === "agent") {
            const group = createMessageGroup("agent", fragment, { label: "Shiba" });
            const bubble = document.createElement("div");
            bubble.className = "message-bubble";
            bubble.innerHTML = renderMarkdown(item.data.content);
            try { bubble.setAttribute("data-raw-content", typeof item.data.content === "string" ? item.data.content : JSON.stringify(item.data.content)); } catch (e) { }
            enhanceCodeBlocks(bubble);

            let attachments = item.data.metadata?.attachments ? [...item.data.metadata.attachments] : [];
            if (!attachments.length && Array.isArray(item.data.metadata?.media)) {
                item.data.metadata.media.forEach(p => {
                    const name = p.split(/[/\\]/).pop();
                    let type = "application/octet-stream";
                    if (name.match(/\.(png|jpe?g|gif|webp|svg)$/i)) type = "image/png";
                    else if (name.match(/\.(mp3|ogg|wav|m4a)$/i)) type = "audio/mpeg";
                    else if (name.match(/\.(mp4|webm|mov)$/i)) type = "video/mp4";
                    attachments.push({
                        name,
                        url: "/api/file-get?path=" + encodeURIComponent(p),
                        type,
                    });
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

            const group = createMessageGroup("agent", fragment, { label: "Shiba" });
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
