// ── Channel icons & labels for grouping ─────────────────────
const CHANNEL_META = {
    webui:    { icon: "language",        label: "Web UI" },
    telegram: { icon: "send",            label: "Telegram" },
    discord:  { icon: "forum",           label: "Discord" },
    slack:    { icon: "tag",             label: "Slack" },
    api:      { icon: "api",             label: "API" },
    cli:      { icon: "terminal",        label: "CLI" },
    _default: { icon: "chat_bubble",     label: "Other" }
};
const RECENT_COUNT = 4;

const _channelCollapsed = {};

function _extractChannel(key) {
    const idx = key.indexOf(":");
    return idx > 0 ? key.substring(0, idx).toLowerCase() : "_default";
}

function _channelInfo(ch) {
    return CHANNEL_META[ch] || { icon: CHANNEL_META._default.icon, label: ch.charAt(0).toUpperCase() + ch.slice(1) };
}

function _buildSessionEl(sess) {
    const el = document.createElement("div");
    el.className = "history-item";
    el.dataset.sessionKey = sess.key;
    if (sess.key === state.sessionId) el.classList.add("active");

    const date = new Date(sess.created_at).toLocaleDateString();
    const time = new Date(sess.updated_at).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
    const name = sess.nickname || sess.key;
    const safeKey = encodeURIComponent(sess.key);
    const safeName = escapeHtml(name);

    el.innerHTML = `
        <div class="session-info">
            <div class="session-name">${safeName}</div>
            <div class="session-meta">${date} ${time}</div>
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
    el.querySelector(".rename-action").addEventListener("click", () => renameSessionPrompt(sess.key, name));
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
            moreBtn.onclick = () => {
                remaining.forEach(s => list.insertBefore(_buildSessionEl(s), moreBtn));
                moreBtn.remove();
            };
            list.appendChild(moreBtn);
        }
    } catch(e) {
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

function _formatSchedule(s) {
    if (s.kind === "cron") {
        const tz = s.tz ? ` (${s.tz})` : "";
        return `cron: ${s.expr}${tz}`;
    }
    if (s.kind === "every" && s.everyMs) {
        const ms = s.everyMs;
        if (ms % 3600000 === 0) return `every ${ms / 3600000}h`;
        if (ms % 60000 === 0) return `every ${ms / 60000}m`;
        if (ms % 1000 === 0) return `every ${ms / 1000}s`;
        return `every ${ms}ms`;
    }
    if (s.kind === "at" && s.atMs) {
        return new Date(s.atMs).toLocaleString([], {month:"short", day:"numeric", hour:"2-digit", minute:"2-digit"});
    }
    return s.kind;
}

function _timeAgo(ms) {
    if (!ms) return "";
    const sec = Math.floor((Date.now() - ms) / 1000);
    if (sec < 60) return "just now";
    if (sec < 3600) return `${Math.floor(sec / 60)}m ago`;
    if (sec < 86400) return `${Math.floor(sec / 3600)}h ago`;
    return `${Math.floor(sec / 86400)}d ago`;
}

function _cronStatusClass(job) {
    if (!job.enabled) return "st-disabled";
    if (job.state.lastStatus === "error") return "st-error";
    if (job.state.lastStatus === "ok") return "st-ok";
    return "st-pending";
}

async function loadCronSection() {
    const list = $("cron-list");
    const count = $("cron-count");
    try {
        const res = await authFetch("/api/cron/jobs");
        const data = await res.json();
        const jobs = data.jobs || [];
        count.textContent = jobs.length;

        if (jobs.length === 0) {
            list.innerHTML = `<div class="auto-empty">No scheduled jobs</div>`;
            return;
        }

        list.innerHTML = "";
        for (const job of jobs) {
            const row = document.createElement("div");
            row.className = "auto-row";
            const stCls = _cronStatusClass(job);
            const meta = job.state.lastRunAtMs ? _timeAgo(job.state.lastRunAtMs) : _formatSchedule(job.schedule);
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
                    await authFetch(`/api/cron/jobs/${encodeURIComponent(job.id)}/trigger`, {method: "POST"});
                } catch(_) {}
                await loadCronSection();
            });
            list.appendChild(row);
        }
    } catch(e) {
        list.innerHTML = `<div class="auto-empty">Error loading jobs</div>`;
    }
}

async function loadHeartbeatSection() {
    const list = $("heartbeat-list");
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
            list.innerHTML = `<div class="auto-empty">Heartbeat disabled</div>`;
            return;
        }

        badge.className = "automation-badge " + (data.last_error ? "badge-error" : (data.running ? "badge-ok" : "badge-off"));
        badge.textContent = data.last_error ? "error" : (data.running ? "active" : "idle");

        let info = `<div class="auto-hb-info">`;
        info += `<span class="hb-label">Interval:</span> ${data.interval_s}s<br>`;
        if (data.last_check_ms) info += `<span class="hb-label">Last check:</span> ${_timeAgo(data.last_check_ms)} — ${data.last_action || "?"}<br>`;
        if (data.last_run_ms) info += `<span class="hb-label">Last run:</span> ${_timeAgo(data.last_run_ms)}<br>`;
        if (data.last_error) info += `<span class="hb-label">Error:</span> ${escapeHtml(data.last_error)}<br>`;
        info += `<span class="hb-label">File:</span> ${data.heartbeat_file_exists ? `<a class="hb-file-link" href="#" onclick="openHeartbeatFile(event)">HEARTBEAT.md</a>` : "missing"}`;
        info += `</div>`;
        info += `<div class="auto-row"><button class="btn-auto-trigger" id="btn-hb-trigger" title="Run heartbeat now">▶ Trigger</button></div>`;

        list.innerHTML = info;
        $("btn-hb-trigger").addEventListener("click", async (e) => {
            const btn = e.currentTarget;
            btn.disabled = true;
            btn.textContent = "…";
            try {
                await authFetch("/api/heartbeat/trigger", {method: "POST"});
            } catch(_) {}
            await loadHeartbeatSection();
        });
    } catch(e) {
        badge.className = "automation-badge badge-off";
        badge.textContent = "";
        list.innerHTML = `<div class="auto-empty">Error loading status</div>`;
    }
}

function initAutomationSections() {
    const cronHeader = $("cron-header");
    const hbHeader = $("heartbeat-header");
    if (cronHeader) {
        cronHeader.addEventListener("click", () => _toggleAutoSection("cron", cronHeader));
        if (_autoCollapsed["cron"]) { cronHeader.classList.add("collapsed"); $("cron-list").classList.add("collapsed"); }
    }
    if (hbHeader) {
        hbHeader.addEventListener("click", () => _toggleAutoSection("heartbeat", hbHeader));
        if (_autoCollapsed["heartbeat"]) { hbHeader.classList.add("collapsed"); $("heartbeat-list").classList.add("collapsed"); }
    }
    loadCronSection();
    loadHeartbeatSection();
}

window.toggleSessionMenu = function(event, btn, key) {
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

window.renameSessionPrompt = async function(key, currentName) {
    const newName = await shibaDialog("prompt", "Rename Session", "Enter new name for session:", { defaultValue: currentName, confirmText: "Rename" });
    if (newName && newName !== currentName) {
        renameSession(key, newName);
    }
};

async function renameSession(key, nickname) {
    try {
        const res = await authFetch(`/api/sessions/${encodeURIComponent(key)}`, {
            method: "PATCH",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({ nickname })
        });
        if (res.ok) {
            if (key === state.sessionId) {
                setSessionLabel(nickname || key);
            }
            await loadHistory();
        }
    } catch(e) { console.error("Rename error:", e); }
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
    } catch(e) { return; }

    renameSession(state.sessionId, title);
}

async function shibaDialog(type, title, message, { confirmText = "Confirm", danger = false, defaultValue = "" } = {}) {
    return new Promise(resolve => {
        const backdrop = document.getElementById("confirm-dialog");
        const msgEl = document.getElementById("confirm-message");
        const okBtn = document.getElementById("confirm-ok");
        const cancelBtn = document.getElementById("confirm-cancel");

        document.getElementById("confirm-title").textContent = title;
        msgEl.innerHTML = message;
        
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

window.deleteSession = async function(key) {
    const ok = await shibaDialog("confirm", "Delete Session", "This session will be permanently deleted.", { confirmText: "Delete", danger: true });
    if (!ok) return;

    removeSessionFromUI(key);
    if (state.sessionId === key) state.socket.emit("new_session");

    try {
        await authFetch(`/api/sessions/${encodeURIComponent(key)}`, { method: "DELETE" });
    } catch(e) { console.error("Delete error:", e); }
};

window.archiveSession = async function(key) {
    const ok = await shibaDialog("confirm", "Archive Session", "This session will run the same consolidation flow as /new and then be removed.", { confirmText: "Archive" });
    if (!ok) return;

    removeSessionFromUI(key);
    if (state.sessionId === key) state.socket.emit("new_session");

    try {
        await authFetch(`/api/sessions/${encodeURIComponent(key)}/archive`, { method: "POST" });
    } catch(e) { console.error("Archive error:", e); }
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
    if (state.processing) {
        state.processing = false;
        setWorkingState(false);
        updateSendButton();
        clearTimeout(state._typingBubbleTimeout);
        hideTypingBubble();
        hideThinking();
    }
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
        } catch(e) {
            if (el.textContent && el.textContent.includes(sessionId)) el.classList.add("active");
        }
    }

    try {
        const res = await authFetch(`/api/sessions/${encodeURIComponent(sessionId)}`);
        const data = await res.json();
        console.debug("[SHIBA] loadSession:", sessionId, "messages:", data.messages?.length || 0);
        
        setSessionLabel(data.nickname || sessionId);
        state.profileId = data.profile_id || "default";
        if (typeof window.syncProfileSelection === "function") {
            await window.syncProfileSelection(state.profileId);
        }
        
        chatHistory.innerHTML = "";
        state.messageCount = 0;
        Object.values(state.processGroups).forEach(pg => {
            if (pg && pg.timer) clearInterval(pg.timer);
        });
        state.processGroups = {};
        
        const messages = Array.isArray(data.messages) ? data.messages : [];
        if (messages.length > 0) {
            activateChat();

            try { refreshTokenBadge(); } catch(e) { /* ignore */ }

            let turnSteps = [];
            let turnId = 0;
            let pgCount = 0;

            let lastUserContent = null;

            for (const msg of messages) {
                if (!msg || !msg.role) continue;
                if (msg.role === "user") {
                    if (!msg.content || msg.content === lastUserContent) continue;
                    lastUserContent = msg.content;

                    const hasExeSteps = turnSteps.some(s => s.badge === "EXE");
                    if (turnSteps.length > 0 && hasExeSteps) {
                        renderProcessGroupFromHistory(turnId, turnSteps);
                        pgCount++;
                    }
                    turnSteps = [];
                    turnId++;
                    const group = createMessageGroup("user");
                    const bubble = document.createElement("div");
                    bubble.className = "message-bubble";
                    
                    if (msg.content) {
                        bubble.innerHTML = renderMarkdown(msg.content);
                        enhanceCodeBlocks(bubble);
                    }

                    const attachments = msg.metadata?.attachments || [];
                    attachments.forEach(file => {
                        if (file.type && file.type.startsWith("image/")) {
                            const img = document.createElement("img");
                            img.src = file.url;
                            img.onclick = () => window.open(file.url, "_blank");
                            bubble.appendChild(img);
                        } else {
                            const link = document.createElement("a");
                            link.href = "#";
                            link.className = "file-attachment-link";
                            link.innerHTML = `
                                <span class="material-icons-round">insert_drive_file</span>
                                <span>${file.name || "attachment"}</span>
                            `;
                            link.addEventListener("click", (e) => {
                                e.preventDefault();
                                downloadAttachment(file.url, file.name);
                            });
                            bubble.appendChild(link);
                        }
                    });

                    group.querySelector(".message-content").appendChild(bubble);
                    if (msg.timestamp) addTimestamp(group, msg.timestamp);
                    chatHistory.appendChild(group);

                } else if (msg.role === "assistant") {
                    const hasTc = msg.tool_calls && msg.tool_calls.length > 0;
                    const hasContent = !!msg.content;
                    const hasReasoning = !!msg.reasoning_content;

                    if (hasReasoning) {
                        const preview = (msg.reasoning_content?.slice?.(0, 120)) || "";
                        turnSteps.push({ badge: "GEN", text: preview });
                    }
                    if (hasTc) {
                        for (const tc of msg.tool_calls) {
                            const fn = tc.function?.name || "tool";
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
                            } catch { /* ignore parse errors */ }
                            turnSteps.push({ badge: "EXE", text: fn + args });
                        }
                    }

                    if (hasContent && !hasTc) {
                        const hasExeSteps = turnSteps.some(s => s.badge === "EXE");
                        if (turnSteps.length > 0 && hasExeSteps) {
                            renderProcessGroupFromHistory(turnId, turnSteps);
                            pgCount++;
                        }
                        turnSteps = [];
                        const group = createMessageGroup("agent");
                        const bubble = document.createElement("div");
                        bubble.className = "message-bubble";
                        bubble.innerHTML = renderMarkdown(msg.content);
                        enhanceCodeBlocks(bubble);

                        const attachments = msg.metadata?.attachments || [];
                        attachments.forEach(file => {
                            if (file.type && file.type.startsWith("image/")) {
                                const img = document.createElement("img");
                                img.src = file.url;
                                img.onclick = () => window.open(file.url, "_blank");
                                bubble.appendChild(img);
                            } else {
                                const link = document.createElement("a");
                                link.href = "#";
                                link.className = "file-attachment-link";
                                link.innerHTML = `
                                    <span class="material-icons-round">insert_drive_file</span>
                                    <span>${file.name || "attachment"}</span>
                                `;
                                link.addEventListener("click", (e) => {
                                    e.preventDefault();
                                    downloadAttachment(file.url, file.name);
                                });
                                bubble.appendChild(link);
                            }
                        });

                        group.querySelector(".message-content").appendChild(bubble);
                        if (msg.timestamp) addTimestamp(group, msg.timestamp);
                        chatHistory.appendChild(group);
                    }

                } else if (msg.role === "tool") {
                }
            }
            if (turnSteps.length > 0 && turnSteps.some(s => s.badge === "EXE")) {
                renderProcessGroupFromHistory(turnId, turnSteps);
                pgCount++;
            }

            console.debug("[SHIBA] loadSession rendered:", pgCount, "process groups,", 
                chatHistory.querySelectorAll(".process-group").length, "in DOM");
            scrollToBottom();
        } else {
            chatHistory.classList.remove("active");
            welcomeScreen.style.display = "";
        }
    } catch(e) {
        console.debug("[SHIBA] Error loading session:", e);
    } finally {
        if (state.socket && state.socket.connected) {
            state.socket.emit("switch_session", { session_id: sessionId });
        }
    }
}

window.openModal = async function(id) {
    const modal = $(id);
    if (!modal) return;
    modal.classList.add("active");
    
    if (id === "context-modal") {
        if (!state.sessionId) {
            $("context-content").innerHTML = "<div class='loader'>No active session</div>";
            return;
        }
        $("context-content").innerHTML = `<div class="loader">Loading context...</div>`;
        try {
            const res = await authFetch(`/api/context?session_id=${encodeURIComponent(state.sessionId)}`);
            const data = await res.json();
            const t = data.tokens || {};
            const tokenCard = buildTokenCard(t);
            $("context-content").innerHTML = tokenCard + renderMarkdown(data.context);
            enhanceCodeBlocks($("context-content"));
            updateTokenBadge(t);
        } catch(e) {
            $("context-content").innerHTML = "Error loading context.";
        }
    } else if (id === "settings-modal") {
        $("settings-loading").style.display = "flex";
        document.querySelectorAll(".settings-panel").forEach(p => p.style.display = "none");
        try {
            const res = await authFetch("/api/settings");
            const cfg = await res.json();
            if (cfg.error) throw cfg.error;
            window._shibaConfig = cfg;
            populateSettings(cfg);
            $("settings-loading").style.display = "none";
            let startTab = "agent";
            try { startTab = localStorage.getItem("shibaclaw_settings_tab") || "agent"; } catch(e) {}
            switchSettingsTab(startTab);
        } catch(e) {
            $("settings-loading").innerHTML = `<span class="material-icons-round" style="color:var(--accent-red)">error</span> Failed to load settings`;
        }
    } else if (id === "fs-modal") {
        await loadFs(state.currentFsPath || ".");
        if (state.fsOpenTarget) {
            const target = state.fsOpenTarget;
            state.fsOpenTarget = null;
            openFileEditor(target, target.split(/[\\/\\]/).pop());
        }
    }
};

window.openHeartbeatFile = function(event) {
    if (event && event.preventDefault) event.preventDefault();
    const filePath = "HEARTBEAT.md";
    const dir = filePath.includes("/") ? filePath.replace(/\\/g, "/").split("/").slice(0, -1).join("/") : ".";
    state.currentFsPath = dir || ".";
    state.fsOpenTarget = filePath;
    openModal("fs-modal");
};

window.closeModal = function(id) {
    const modal = $(id);
    if (modal) modal.classList.remove("active");
};

window.openOnboardFromSettings = function() {
    closeModal("settings-modal");
    openOnboardWizard();
};

window.switchSettingsTab = function(tab) {
    document.querySelectorAll(".settings-sidebar-item").forEach(t => t.classList.remove("active"));
    const sidebarEl = document.querySelector(`.settings-sidebar-item[data-tab="${tab}"]`);
    if (sidebarEl) sidebarEl.classList.add("active");
    document.querySelectorAll(".settings-tab").forEach(t => t.classList.remove("active"));
    const tabEl = document.querySelector(`.settings-tab[data-tab="${tab}"]`);
    if (tabEl) tabEl.classList.add("active");
    document.querySelectorAll(".settings-panel").forEach(p => p.style.display = "none");
    const panel = $("panel-" + tab);
    if (panel) panel.style.display = "block";
    if (tab === "oauth") loadOAuthPanel();
    if (tab === "update") loadUpdatePanel();
    if (tab === "skills") loadSkillsPanel();
    try { localStorage.setItem("shibaclaw_settings_tab", tab); } catch(e) {}
};

/* ── Skills panel ── */
window._skillsData = [];
window._skillsPinnedList = [];
window._skillsMaxPinned = 5;

async function loadSkillsPanel() {
    const listEl = document.getElementById("skills-list");
    try {
        const res = await authFetch("/api/skills");
        if (!res.ok) {
            if (listEl) listEl.innerHTML = '<div style="color:#e57373;font-size:13px;padding:12px">Failed to load skills (HTTP ' + res.status + ')</div>';
            return;
        }
        const data = await res.json();
        window._skillsData = data.skills || [];
        window._skillsPinnedList = data.pinned_skills || [];
        window._skillsMaxPinned = data.max_pinned_skills || 5;
        renderSkillsPanel();
    } catch(e) {
        console.error("loadSkillsPanel", e);
        if (listEl) listEl.innerHTML = '<div style="color:#e57373;font-size:13px;padding:12px">Error loading skills</div>';
    }
}

function renderSkillsPanel() {
    const skills = window._skillsData;
    const pinned = window._skillsPinnedList;
    var alwaysActive = skills.filter(function(s) { return s.always || pinned.includes(s.name); });
    var alwaysNames = alwaysActive.map(function(s) { return s.name; });

    var counter = document.getElementById("skills-pin-counter");
    if (counter) counter.textContent = alwaysActive.length + " / " + window._skillsMaxPinned;

    var pinnedList = document.getElementById("skills-pinned-list");
    if (pinnedList) {
        if (alwaysActive.length === 0) {
            pinnedList.innerHTML = '<span style="color:var(--text-secondary);font-size:12px">No always-active skills</span>';
        } else {
            pinnedList.innerHTML = alwaysActive.map(function(s) {
                var canUnpin = !s.always;
                var closeBtn = canUnpin
                    ? ' <span class="material-icons-round" style="font-size:14px;cursor:pointer;vertical-align:middle" onclick="toggleSkillPin(\'' + escHtml(s.name) + '\', false)">close</span>'
                    : ' <span class="material-icons-round" style="font-size:14px;vertical-align:middle;opacity:0.4" title="Set in SKILL.md">lock</span>';
                return '<span class="skills-pinned-chip">' + escHtml(s.name) + closeBtn + '</span>';
            }).join("");
        }
    }

    var listEl = document.getElementById("skills-list");
    if (!listEl) return;
    var q = ((document.getElementById("skills-search") || {}).value || "").toLowerCase();
    var filtered = q ? skills.filter(function(s) { return s.name.toLowerCase().includes(q) || (s.description || "").toLowerCase().includes(q); }) : skills;
    if (filtered.length === 0) {
        listEl.innerHTML = '<div style="color:var(--text-secondary);font-size:13px;padding:12px">No skills found.</div>';
        return;
    }
    listEl.innerHTML = filtered.map(function(s) { return renderSkillCard(s, alwaysNames); }).join("");
}

function escHtml(s) { const d = document.createElement("div"); d.textContent = s; return d.innerHTML; }

function renderSkillCard(skill, activeNames) {
    var isActive = activeNames.includes(skill.name);
    var isYamlAlways = skill.always;
    var badgeClass = skill.source === "builtin" ? "builtin" : "workspace";
    var availClass = skill.available ? "" : " unavailable";
    var pinBtn = isYamlAlways
        ? '<span class="material-icons-round" style="font-size:16px;color:var(--shiba-gold);opacity:0.6" title="Always active (SKILL.md)">lock</span>'
        : '<span class="material-icons-round" style="font-size:16px;cursor:pointer;color:' + (isActive ? 'var(--shiba-gold)' : 'var(--text-secondary)') + '" title="' + (isActive ? 'Unpin' : 'Pin as always active') + '" onclick="toggleSkillPin(\'' + escHtml(skill.name) + '\', ' + !isActive + ')">' + (isActive ? 'push_pin' : 'add_circle_outline') + '</span>';
    var deleteBtn = skill.source === "workspace"
        ? '<span class="material-icons-round" style="font-size:16px;cursor:pointer;color:var(--text-secondary)" title="Delete" onclick="deleteSkill(\'' + escHtml(skill.name) + '\')">delete</span>'
        : '';
    return '<div class="skill-card' + availClass + '">' +
        '<div class="skill-card-body">' +
            '<div class="skill-card-name">' + escHtml(skill.name) + ' <span class="skill-badge ' + badgeClass + '">' + escHtml(skill.source) + '</span></div>' +
            '<div class="skill-card-desc">' + escHtml(skill.description || 'No description') + '</div>' +
            (skill.missing_requirements ? '<div style="font-size:11px;color:#e57373;margin-top:2px">Missing: ' + escHtml(skill.missing_requirements) + '</div>' : '') +
        '</div>' +
        '<div class="skill-card-actions">' + pinBtn + deleteBtn + '</div>' +
    '</div>';
}

window.toggleSkillPin = async function(name, pin) {
    let list = [...window._skillsPinnedList];
    if (pin) {
        if (list.length >= window._skillsMaxPinned) { alert("Max pinned skills reached (" + window._skillsMaxPinned + ")"); return; }
        if (!list.includes(name)) list.push(name);
    } else {
        list = list.filter(n => n !== name);
    }
    try {
        const res = await authFetch("/api/skills/pin", { method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({ pinned_skills: list }) });
        if (!res.ok) { const d = await res.json().catch(() => ({})); alert(d.error || "Pin failed"); return; }
        window._skillsPinnedList = list;
        renderSkillsPanel();
    } catch(e) { console.error("toggleSkillPin", e); }
};

window.deleteSkill = async function(name) {
    if (!confirm("Delete skill '" + name + "'? This cannot be undone.")) return;
    try {
        const res = await authFetch("/api/skills/" + encodeURIComponent(name), { method: "DELETE" });
        const d = await res.json().catch(() => ({}));
        if (!res.ok) { alert(d.error || "Delete failed"); return; }
        loadSkillsPanel();
    } catch(e) { console.error("deleteSkill", e); }
};

window.handleSkillsFileSelect = function(event) {
    const fileInput = event.target;
    const nameEl = document.getElementById("skills-import-filename");
    const importBtn = document.getElementById("skills-import-btn");
    if (fileInput.files.length) {
        if (nameEl) nameEl.textContent = fileInput.files[0].name;
        if (importBtn) importBtn.disabled = false;
    } else {
        if (nameEl) nameEl.textContent = "No file selected";
        if (importBtn) importBtn.disabled = true;
    }
};

window.importSkills = async function() {
    const fileInput = document.getElementById("skills-import-file");
    if (!fileInput || !fileInput.files.length) return;
    const el = document.getElementById("skills-import-result");
    const form = new FormData();
    form.append("file", fileInput.files[0]);
    form.append("conflict", "overwrite");
    if (el) { el.style.display = "block"; el.innerHTML = '<span style="color:var(--text-secondary)">Importing...</span>'; }
    try {
        const res = await authFetch("/api/skills/import", { method: "POST", body: form });
        const d = await res.json();
        if (!res.ok) { if (el) el.innerHTML = '<span style="color:#e57373">' + escHtml(d.error || "Error") + '</span>'; return; }
        if (el) el.innerHTML = '<span style="color:#4ade80">Imported ' + (d.imported_count || 0) + ' skill(s)</span>';
        fileInput.value = "";
        var nameEl = document.getElementById("skills-import-filename");
        if (nameEl) nameEl.textContent = "No file selected";
        document.getElementById("skills-import-btn").disabled = true;
        loadSkillsPanel();
    } catch(e) {
        console.error("importSkills", e);
        if (el) { el.style.display = "block"; el.innerHTML = '<span style="color:#e57373">Network error</span>'; }
    }
};

document.addEventListener("DOMContentLoaded", function() {
    document.addEventListener("input", function(e) {
        if (e.target && e.target.id === "skills-search") renderSkillsPanel();
    });
});

/* ── end Skills panel ── */

async function loadOAuthPanel() {
    const list = document.getElementById("oauth-list");
    if (!list) return;
    const providers = [
        { name: "github_copilot", label: "GitHub Copilot", icon: "code", desc: "Authenticate via GitHub device flow. Uses native OAuth orchestration." },
        { name: "openai_codex", label: "OpenAI Codex", icon: "psychology", desc: "Authenticate via OAuth CLI kit. Requires oauth-cli-kit package." },
    ];
    list.innerHTML = "";
    for (const p of providers) {
        const card = document.createElement("div");
        card.className = "accordion";
        card.innerHTML = `
            <div class="accordion-header" onclick="this.parentElement.classList.toggle('open')">
                <div class="accordion-title">
                    <span class="material-icons-round" style="font-size:18px">${p.icon}</span>
                    ${p.label}
                </div>
                <div class="accordion-right">
                    <span class="acc-badge off" id="oauth-badge-${p.name}">Checking...</span>
                    <span class="material-icons-round accordion-arrow">expand_more</span>
                </div>
            </div>
            <div class="accordion-body">
                <div class="field-row" style="grid-template-columns:1fr">
                    <span style="font-size:12px;color:var(--text-secondary)">${p.desc}</span>
                </div>
                <div style="display:flex;gap:8px;padding:0.5rem 0">
                    <button class="btn-primary btn-sm" id="btn-oauth-login-${p.name}">
                        <span class="material-icons-round" style="font-size:14px;vertical-align:middle">login</span> Login
                    </button>
                </div>
                <div class="oauth-logs" id="oauth-logs-${p.name}" style="display:none;height:260px;overflow-y:scroll;overflow-x:hidden;background:var(--bg-primary);border-radius:6px;padding:12px;font-size:12px;font-family:'JetBrains Mono',monospace;color:var(--text-secondary);margin-top:4px;border:1px solid var(--border-color);white-space:pre-wrap;line-height:1.6"></div>
            </div>`;
        list.appendChild(card);

        document.getElementById("btn-oauth-login-" + p.name).addEventListener("click", async () => {
            const btn = document.getElementById("btn-oauth-login-" + p.name);
            const badge = document.getElementById("oauth-badge-" + p.name);
            const logsEl = document.getElementById("oauth-logs-" + p.name);
            btn.disabled = true; btn.innerHTML = '<span class="material-icons-round spin" style="font-size:14px;vertical-align:middle">progress_activity</span> Contacting...';
            logsEl.style.display = "block"; logsEl.innerHTML = "Requesting device code...\n";
            const loginBtnHtml = '<span class="material-icons-round" style="font-size:14px;vertical-align:middle">login</span> Login';
            try {
                const resp = await authFetch("/api/oauth/login", { method:"POST", headers:{"Content-Type":"application/json"}, body: JSON.stringify({provider:p.name}) });
                const jd = await resp.json();
                if (jd.error) {
                    logsEl.textContent = "Error: " + jd.error;
                    btn.disabled = false; btn.innerHTML = loginBtnHtml;
                    return;
                }

                if (jd.user_code && jd.verification_uri) {
                    badge.textContent = "Awaiting auth..."; badge.className = "acc-badge off";
                    btn.innerHTML = '<span class="material-icons-round spin" style="display:inline-block;width:14px;height:14px;line-height:14px;font-size:14px;vertical-align:middle">progress_activity</span> Waiting for auth...';
                    const codeId = "oauth-code-" + Date.now();
                    logsEl.innerHTML =
                        `<div style="text-align:center;padding:12px 0">` +
                        `<div style="display:flex;align-items:center;justify-content:center;gap:16px;flex-wrap:wrap">` +
                          `<a href="${jd.verification_uri}" target="_blank" style="display:inline-flex;align-items:center;gap:6px;color:var(--bg-primary);background:var(--shiba-gold);padding:8px 16px;border-radius:8px;font-size:13px;font-weight:600;text-decoration:none;transition:opacity .2s" onmouseover="this.style.opacity='0.85'" onmouseout="this.style.opacity='1'">` +
                            `<span class="material-icons-round" style="font-size:16px">open_in_new</span> Open GitHub` +
                          `</a>` +
                          `<div style="position:relative;display:inline-flex;align-items:center;background:var(--bg-secondary);border:2px solid var(--shiba-gold);border-radius:10px;padding:6px 12px 6px 16px;gap:10px;cursor:pointer" onclick="navigator.clipboard.writeText('${jd.user_code}');const t=document.getElementById('${codeId}-tip');t.textContent='Copied!';setTimeout(()=>t.textContent='Click to copy',1500)" title="Click to copy code">` +
                            `<span style="font-size:26px;font-weight:700;letter-spacing:5px;color:var(--shiba-gold);font-family:'JetBrains Mono',monospace">${jd.user_code}</span>` +
                            `<span class="material-icons-round" style="font-size:18px;color:var(--text-muted)">content_copy</span>` +
                          `</div>` +
                        `</div>` +
                        `<div id="${codeId}-tip" style="margin-top:6px;font-size:11px;color:var(--text-muted)">Click to copy</div>` +
                        `<div style="margin-top:10px;display:flex;align-items:center;justify-content:center;gap:6px;font-size:12px;color:var(--text-muted)">` +
                          `<span class="material-icons-round spin" style="display:inline-block;width:14px;height:14px;line-height:14px;font-size:14px">progress_activity</span> Waiting for authorization...` +
                        `</div>` +
                        `</div>`;
                }

                if (jd.job_id) {
                    const poll = setInterval(async () => {
                        try {
                            const r2 = await authFetch("/api/oauth/job/" + jd.job_id);
                            const j = await r2.json();
                            if (!j.job) return;

                            if (j.job.status === "done") {
                                clearInterval(poll);
                                badge.textContent = "Configured"; badge.className = "acc-badge on";
                                btn.disabled = false; btn.innerHTML = loginBtnHtml;
                                logsEl.innerHTML = `<div style="color:#4ade80;font-weight:600;text-align:center;padding:12px">✅ Authentication successful!</div>`;
                            } else if (j.job.status === "error") {
                                clearInterval(poll);
                                badge.textContent = "Error"; badge.className = "acc-badge off";
                                btn.disabled = false; btn.innerHTML = loginBtnHtml;
                                const logs = (j.job.logs || []).join("\n");
                                logsEl.innerHTML = `<div style="color:#f87171;padding:8px;white-space:pre-wrap">${logs}</div>`;
                            } else if (j.job.status === "awaiting_code" && j.job.auth_url && !logsEl.querySelector('.codex-auth-ui')) {
                                badge.textContent = "Awaiting auth..."; badge.className = "acc-badge off";
                                btn.innerHTML = '<span class="material-icons-round spin" style="display:inline-block;width:14px;height:14px;line-height:14px;font-size:14px;vertical-align:middle">progress_activity</span> Waiting...';
                                const inputId = "codex-input-" + jd.job_id;
                                const submitId = "codex-submit-" + jd.job_id;
                                logsEl.innerHTML =
                                    `<div class="codex-auth-ui" style="text-align:center;padding:12px 0">` +
                                    `<div style="font-size:13px;color:var(--text-secondary);margin-bottom:10px">Click the button below to sign in with OpenAI:</div>` +
                                    `<a href="${j.job.auth_url}" target="_blank" style="display:inline-flex;align-items:center;gap:6px;color:var(--bg-primary);background:var(--shiba-gold);padding:8px 16px;border-radius:8px;font-size:13px;font-weight:600;text-decoration:none;transition:opacity .2s" onmouseover="this.style.opacity='0.85'" onmouseout="this.style.opacity='1'">` +
                                      `<span class="material-icons-round" style="font-size:16px">open_in_new</span> Open OpenAI Login` +
                                    `</a>` +
                                    `<div style="margin-top:14px;padding:10px 14px;border-radius:8px;background:var(--bg-tertiary);text-align:left;font-size:12px;line-height:1.6;color:var(--text-secondary)">` +
                                      `<strong style="color:var(--shiba-gold)">📋 After login</strong>, your browser will redirect to a URL like:<br>` +
                                      `<code style="font-size:11px;color:var(--text-primary);background:var(--bg-secondary);padding:2px 6px;border-radius:4px;word-break:break-all">http://localhost:1455/auth/callback?code=<span style="color:var(--shiba-gold);font-weight:700">AUTH_CODE_HERE</span>&amp;state=...</code><br>` +
                                      `Paste the <strong>entire URL</strong> in the field below — the code will be extracted automatically.` +
                                    `</div>` +
                                    `<div style="margin-top:12px;display:flex;gap:8px;align-items:center;justify-content:center">` +
                                      `<input id="${inputId}" type="text" class="form-input" placeholder="Paste the full callback URL here..." style="flex:1;max-width:400px;font-size:12px;font-family:'JetBrains Mono',monospace">` +
                                      `<button id="${submitId}" class="btn-primary btn-sm" style="white-space:nowrap">` +
                                        `<span class="material-icons-round" style="font-size:14px;vertical-align:middle">send</span> Submit` +
                                      `</button>` +
                                    `</div>` +
                                    `<div style="margin-top:8px;display:flex;align-items:center;justify-content:center;gap:6px;font-size:11px;color:var(--text-muted)">` +
                                      `<span class="material-icons-round spin" style="display:inline-block;width:14px;height:14px;line-height:14px;font-size:14px">progress_activity</span> Waiting for authorization...` +
                                    `</div>` +
                                    `</div>`;
                                setTimeout(() => {
                                    const submitBtn = document.getElementById(submitId);
                                    const inputEl = document.getElementById(inputId);
                                    if (submitBtn && inputEl) {
                                        const doSubmit = async () => {
                                            const code = inputEl.value.trim();
                                            if (!code) return;
                                            submitBtn.disabled = true; submitBtn.textContent = "Sending...";
                                            try {
                                                await authFetch("/api/oauth/code", { method:"POST", headers:{"Content-Type":"application/json"}, body: JSON.stringify({job_id: jd.job_id, code}) });
                                                inputEl.value = ""; inputEl.placeholder = "Code submitted, waiting...";
                                            } catch { submitBtn.disabled = false; submitBtn.textContent = "Submit"; }
                                        };
                                        submitBtn.addEventListener("click", doSubmit);
                                        inputEl.addEventListener("keydown", e => { if (e.key === "Enter") doSubmit(); });
                                    }
                                }, 50);
                            }
                        } catch { /* keep polling */ }
                    }, 2000);
                } else if (!jd.user_code) {
                    logsEl.textContent = jd.error || "Unknown response";
                    btn.disabled = false; btn.innerHTML = loginBtnHtml;
                }
            } catch(e) {
                logsEl.textContent = "Error: " + e;
                btn.disabled = false; btn.innerHTML = loginBtnHtml;
            }
        });
    }

    _refreshOAuthStatus();
}

async function _refreshOAuthStatus() {
    try {
        const r = await authFetch("/api/oauth/providers");
        const data = await r.json();
        for (const p of (data.providers || [])) {
            const badge = document.getElementById("oauth-badge-" + p.name);
            if (!badge) continue;
            const ok = p.status === "configured";
            badge.textContent = ok ? "Configured" : (p.status === "missing_dependency" ? "Missing dep" : "Not configured");
            badge.className = "acc-badge " + (ok ? "on" : "off");
        }
    } catch { /* silent */ }
}

function _addProviderOption(sel, value, label) {
    if (sel.querySelector(`option[value="${value}"]`)) return;
    const opt = document.createElement("option");
    opt.value = value;
    opt.textContent = label || value.charAt(0).toUpperCase() + value.slice(1);
    sel.appendChild(opt);
}

async function _populateOAuthProviders(sel, current) {
    try {
        const r = await authFetch("/api/oauth/providers");
        const data = await r.json();
        for (const p of (data.providers || [])) {
            if (p.status === "configured") _addProviderOption(sel, p.name, p.label);
        }
        if (current) sel.value = current;
    } catch { /* silent */ }
}

function populateSettings(cfg) {
    lastSettingsConfig = JSON.parse(JSON.stringify(cfg));
    const d = cfg.agents?.defaults || {};
    const oauthNames = new Set(["github_copilot", "openai_codex"]);
    const sel = $("s-agent-provider");
    sel.innerHTML = "";
    _addProviderOption(sel, "auto", "Auto");
    for (const [name, pc] of Object.entries(cfg.providers || {})) {
        if (oauthNames.has(name)) continue;
        if (pc.apiKey || pc.apiBase) _addProviderOption(sel, name);
    }
    const current = d.provider || "auto";
    _addProviderOption(sel, current);
    sel.value = current;
    _populateOAuthProviders(sel, current);

    $("s-agent-model").value = d.model || "";
    const dl = $("model-history-list");
    dl.innerHTML = "";
    for (const m of JSON.parse(localStorage.getItem("shibaclaw_model_history") || "[]")) {
        const opt = document.createElement("option");
        opt.value = m;
        dl.appendChild(opt);
    }
    $("s-agent-temp").value = d.temperature ?? 0.1;
    $("s-agent-maxTokens").value = d.maxTokens ?? 8192;
    $("s-agent-ctxTokens").value = d.contextWindowTokens ?? 65536;
    $("s-agent-maxIter").value = d.maxToolIterations ?? 40;
    $("s-agent-workspace").value = d.workspace || "~/.shibaclaw/workspace";
    $("s-agent-reasoning").value = d.reasoningEffort || "";

    // Audio settings
    const au = cfg.audio || {};
    $("s-audio-providerUrl").value = au.providerUrl || "";
    $("s-audio-apiKey").value = au.apiKey || "";
    $("s-audio-model").value = au.model || "";
    // sync TTS toggle with config value (with localStorage as fallback)
    const ttsFromConfig = au.ttsEnabled !== undefined ? au.ttsEnabled : (localStorage.getItem("shibaclaw_tts_enabled") === "true");
    $("tts-toggle").checked = ttsFromConfig;
    if (window.speechTTS) window.speechTTS.enabled = ttsFromConfig;

    const prov = cfg.providers || {};
    const list = $("providers-list");
    list.innerHTML = "";
    for (const [name, pc] of Object.entries(prov)) {
        const hasKey = !!(pc.apiKey);
        const displayName = name.replace(/([A-Z])/g, " $1").replace(/^./, s => s.toUpperCase());
        const card = document.createElement("div");
        card.className = "accordion";
        card.innerHTML = `
            <div class="accordion-header" onclick="this.parentElement.classList.toggle('open')">
                <div class="accordion-title">
                    <span class="material-icons-round" style="font-size:18px">key</span>
                    ${displayName}
                </div>
                <div class="accordion-right">
                    <span class="acc-badge ${hasKey ? 'on' : 'off'}">${hasKey ? 'Configured' : 'Not set'}</span>
                    <span class="material-icons-round accordion-arrow">expand_more</span>
                </div>
            </div>
            <div class="accordion-body">
                <div class="field-row">
                    <label>API Key</label>
                    <input type="password" class="form-input prov-key" data-prov="${name}" value="${pc.apiKey || ""}" placeholder="sk-...">
                </div>
                <div class="field-row">
                    <label>API Base URL</label>
                    <input type="text" class="form-input prov-base" data-prov="${name}" value="${pc.apiBase || ""}" placeholder="(default)">
                </div>
            </div>`;
        list.appendChild(card);
    }

    const tw = cfg.tools?.web || {};
    const ts = tw.search || {};
    $("s-tool-searchProvider").value = ts.provider || "brave";
    $("s-tool-searchKey").value = ts.apiKey || "";
    $("s-tool-searchMax").value = ts.maxResults ?? 5;
    $("s-tool-proxy").value = tw.proxy || "";
    const te = cfg.tools?.exec || {};
    $("s-tool-execEnable").checked = te.enable !== false;
    $("s-tool-execTimeout").value = te.timeout ?? 60;
    $("s-tool-restrict").checked = !!cfg.tools?.restrictToWorkspace;

    const gw = cfg.gateway || {};
    $("s-gw-host").value = gw.host || "127.0.0.1";
    $("s-gw-port").value = gw.port ?? 19999;
    const hb = gw.heartbeat || {};
    $("s-gw-hbEnabled").checked = hb.enabled !== false;
    $("s-gw-hbInterval").value = hb.intervalS ?? 1800;

    const ch = cfg.channels || {};
    $("s-ch-sendProgress").checked = ch.sendProgress !== false;
    $("s-ch-sendToolHints").checked = !!ch.sendToolHints;

    const detail = $("channels-detail");
    detail.innerHTML = "";
    const skip = ["sendProgress", "sendToolHints"];

    const EMAIL_FIELD_CONFIG = {
        imapHost:       { label: "IMAP Server",       section: "inbound",  type: "text",     placeholder: "imap.gmail.com" },
        imapPort:       { label: "IMAP Port",          section: "inbound",  type: "number",   placeholder: "993" },
        imapUsername:   { label: "IMAP Username",      section: "inbound",  type: "text",     placeholder: "email@gmail.com" },
        imapPassword:   { label: "IMAP Password",      section: "inbound",  type: "password", placeholder: "App password" },
        imapUseSsl:     { label: "IMAP SSL",           section: "inbound",  type: "boolean" },
        imapMailbox:    { label: "IMAP Mailbox",       section: "inbound",  type: "text",     placeholder: "INBOX" },
        smtpHost:       { label: "SMTP Server",        section: "outbound", type: "text",     placeholder: "smtp.gmail.com" },
        smtpPort:       { label: "SMTP Port",          section: "outbound", type: "number",   placeholder: "587" },
        smtpUsername:   { label: "SMTP Username",      section: "outbound", type: "text",     placeholder: "email@gmail.com" },
        smtpPassword:   { label: "SMTP Password",      section: "outbound", type: "password", placeholder: "App password" },
        smtpUseTls:     { label: "SMTP STARTTLS",      section: "outbound", type: "boolean" },
        smtpUseSsl:     { label: "SMTP SSL",           section: "outbound", type: "boolean" },
        fromAddress:    { label: "From Address",       section: "outbound", type: "text",     placeholder: "shibaclaw@gmail.com" },
        autoReplyEnabled:       { label: "Auto Reply",           section: "general", type: "boolean" },
        pollIntervalSeconds:    { label: "Poll Interval (sec)",  section: "general", type: "number",  placeholder: "30" },
        markSeen:               { label: "Mark as Read",         section: "general", type: "boolean" },
        maxBodyChars:           { label: "Max Body Length",      section: "general", type: "number",  placeholder: "12000" },
        subjectPrefix:          { label: "Reply Prefix",         section: "general", type: "text",    placeholder: "Re: " },
        allowFrom:              { label: "Allowed Senders",      section: "general", type: "array",   placeholder: "email1@test.com, email2@test.com" },
    };

    for (const [name, cc] of Object.entries(ch)) {
        if (skip.includes(name) || typeof cc !== "object") continue;
        const enabled = cc.enabled === true;
        const displayName = name.charAt(0).toUpperCase() + name.slice(1);
        const card = document.createElement("div");
        card.className = "accordion";
        
        let fieldsHtml = `
            <div class="field-row">
                <label>Enabled</label>
                <label class="toggle"><input type="checkbox" class="ch-enabled" data-ch="${name}" ${enabled ? "checked" : ""}><span class="toggle-slider"></span></label>
            </div>
        `;
        if (name === "email") {
            fieldsHtml += `
            <div class="field-row">
                <label>Authorize IMAP/SMTP access</label>
                <label class="toggle"><input type="checkbox" class="ch-field" data-ch="${name}" data-key="consentGranted" data-type="boolean" ${(cc.consentGranted || cc.consent_granted) ? "checked" : ""}><span class="toggle-slider"></span></label>
                <span style="font-size:11px;color:var(--text-muted);margin-left:4px">Required to allow ShibaClaw to read and send emails on your behalf</span>
            </div>
            `;
        }

        if (name === "email" && EMAIL_FIELD_CONFIG) {
            const sections = { inbound: [], outbound: [], general: [] };
            
            for (const [key, val] of Object.entries(cc)) {
                if (key === "enabled" || key === "consentGranted" || key === "consent_granted") continue;
                
                const fieldConfig = EMAIL_FIELD_CONFIG[key] || EMAIL_FIELD_CONFIG[key.replace(/([A-Z])/g, (m) => m.toLowerCase())] || null;
                const section = fieldConfig?.section || "general";
                const label = fieldConfig?.label || key;
                const inputType = fieldConfig?.type || "text";
                const placeholder = fieldConfig?.placeholder || "";
                
                let valStr = "";
                let originalType = typeof val;
                if (Array.isArray(val)) {
                    originalType = "array";
                    valStr = val.join(", ");
                } else if (val !== null && originalType === "object") {
                    originalType = "object";
                    valStr = JSON.stringify(val);
                } else {
                    if (val === null) originalType = "string";
                    valStr = val === null ? "" : String(val);
                }
                
                let inputHtml = "";
                if (originalType === "boolean" || fieldConfig?.type === "boolean") {
                    inputHtml = `
                        <div class="field-row">
                            <label>${label}</label>
                            <label class="toggle"><input type="checkbox" class="ch-field" data-ch="${name}" data-key="${key}" data-type="boolean" ${valStr === "true" || val === true ? "checked" : ""}><span class="toggle-slider"></span></label>
                        </div>`;
                } else {
                    const isPassword = fieldConfig?.type === "password" || key.toLowerCase().includes("password") || key.toLowerCase().includes("secret");
                    const safeVal = String(valStr).replace(/"/g, '"');
                    inputHtml = `
                        <div class="field-row">
                            <label>${label}</label>
                            <input type="${isPassword ? "password" : (fieldConfig?.type || "text")}" class="form-input ch-field" data-ch="${name}" data-key="${key}" data-type="${originalType}" value="${safeVal}" placeholder="${placeholder}">
                        </div>
                    `;
                }
                
                if (!sections[section]) sections[section] = [];
                sections[section].push(inputHtml);
            }
            
            const sectionLabels = {
                inbound: '📥 Email IN (IMAP)',
                outbound: '📤 Email OUT (SMTP)',
                general: '⚙️ General'
            };
            
            for (const [sectionKey, sectionFields] of Object.entries(sections)) {
                if (sectionFields.length > 0) {
                    fieldsHtml += `<div style="padding: 8px 0 4px; font-weight: 600; color: var(--text-muted); font-size: 13px; border-bottom: 1px solid var(--border-color); margin-bottom: 4px;">${sectionLabels[sectionKey] || sectionKey}</div>`;
                    fieldsHtml += sectionFields.join("");
                }
            }
        } else {
            for (const [key, val] of Object.entries(cc)) {
                if (key === "enabled" || key === "consentGranted" || key === "consent_granted") continue;
                let inputType = "text";
                let valStr = "";
                let originalType = typeof val;
                if (Array.isArray(val)) {
                    originalType = "array";
                    valStr = val.join(", ");
                } else if (val !== null && originalType === "object") {
                    originalType = "object";
                    valStr = JSON.stringify(val);
                } else {
                    if (val === null) originalType = "string";
                    valStr = val === null ? "" : String(val);
                }
                
                if (originalType === "boolean") {
                    fieldsHtml += `
                        <div class="field-row">
                            <label>${key}</label>
                            <label class="toggle"><input type="checkbox" class="ch-field" data-ch="${name}" data-key="${key}" data-type="boolean" ${val ? "checked" : ""}><span class="toggle-slider"></span></label>
                        </div>`;
                    continue;
                }
                
                const lowerKey = key.toLowerCase();
                if (lowerKey.includes("token") || lowerKey.includes("secret") || lowerKey.includes("password")) {
                    inputType = "password";
                }
                
                const safeVal = String(valStr).replace(/"/g, '"');
                fieldsHtml += `
                    <div class="field-row">
                        <label>${key}</label>
                        <input type="${inputType}" class="form-input ch-field" data-ch="${name}" data-key="${key}" data-type="${originalType}" value="${safeVal}">
                    </div>
                `;
            }
        }

        const iconMap = {
            telegram: "send",
            discord: "forum",
            slack: "tag",
            whatsapp: "chat",
            webui: "language",
            cli: "terminal",
            email: "email",
        };
        const iconName = iconMap[name] || "chat";

        card.innerHTML = `
            <div class="accordion-header" onclick="this.parentElement.classList.toggle('open')">
                <div class="accordion-title">
                    <span class="material-icons-round" style="font-size:18px">${iconName}</span>
                    ${displayName}
                </div>
                <div class="accordion-right">
                    <span class="acc-badge ${enabled ? 'on' : 'off'}">${enabled ? 'ON' : 'OFF'}</span>
                    <span class="material-icons-round accordion-arrow">expand_more</span>
                </div>
            </div>
            <div class="accordion-body">
                ${fieldsHtml}
            </div>`;
        detail.appendChild(card);
    }

    const mcpServers = cfg.tools?.mcpServers || {};
    const mcpList = $("mcp-servers-list");
    mcpList.innerHTML = "";
    if (Object.keys(mcpServers).length === 1 && Object.keys(mcpServers)[0] === "mcp") {
        const note = document.createElement("div");
        note.className = "settings-note";
        note.innerHTML = "<b>Nota:</b> Questo è un esempio di server MCP. Modifica direttamente questo blocco per configurare il tuo server personalizzato.";
        mcpList.appendChild(note);
    }
    for (const [name, sc] of Object.entries(mcpServers)) {
        mcpList.appendChild(buildMcpServerCard(name, sc));
    }
}

function buildMcpServerCard(name, sc) {
    const card = document.createElement("div");
    card.className = "accordion mcp-server-card";
    const escName = name.replace(/"/g, "&quot;");
    card.innerHTML = `
        <div class="accordion-header" onclick="this.parentElement.classList.toggle('open')">
            <div class="accordion-title">
                <span class="material-icons-round" style="font-size:18px">hub</span>
                <span class="mcp-server-title">${escName}</span>
            </div>
            <div class="accordion-right">
                <button type="button" class="btn-icon" onclick="event.stopPropagation();removeMcpServer(this)" title="Remove">
                    <span class="material-icons-round" style="font-size:16px;color:var(--accent-red)">delete</span>
                </button>
                <span class="material-icons-round accordion-arrow">expand_more</span>
            </div>
        </div>
        <div class="accordion-body">
            <div class="field-row"><label>Server Name</label><input type="text" class="form-input mcp-name" value="${escName}" placeholder="my-server"></div>
            <div class="field-row"><label>Type</label>
                <select class="form-input mcp-type">
                    <option value="" ${!sc.type ? "selected" : ""}>Auto-detect</option>
                    <option value="stdio" ${sc.type === "stdio" ? "selected" : ""}>stdio</option>
                    <option value="sse" ${sc.type === "sse" ? "selected" : ""}>sse</option>
                    <option value="streamableHttp" ${sc.type === "streamableHttp" ? "selected" : ""}>streamableHttp</option>
                </select>
            </div>
            <div class="field-row"><label>Command</label><input type="text" class="form-input mcp-command" value="${(sc.command || "").replace(/"/g, "&quot;")}" placeholder="npx, node, python..."></div>
            <div class="field-row"><label>Args</label><input type="text" class="form-input mcp-args" value="${(sc.args || []).join(", ")}" placeholder="arg1, arg2, ..."></div>
            <div class="field-row"><label>URL</label><input type="text" class="form-input mcp-url" value="${(sc.url || "").replace(/"/g, "&quot;")}" placeholder="http://localhost:3000/sse"></div>
            <div class="field-row"><label>Headers (JSON)</label><input type="text" class="form-input mcp-headers" value="${Object.keys(sc.headers || {}).length ? JSON.stringify(sc.headers).replace(/"/g, "&quot;") : ""}" placeholder='{"Authorization": "Bearer ..."}'></div>
            <div class="field-row"><label>Env Vars (JSON)</label><input type="text" class="form-input mcp-env" value="${Object.keys(sc.env || {}).length ? JSON.stringify(sc.env).replace(/"/g, "&quot;") : ""}" placeholder='{"API_KEY": "..."}'></div>
            <div class="field-row"><label>Tool Timeout (s)</label><input type="number" class="form-input mcp-timeout" value="${sc.tool_timeout ?? 30}"></div>
            <div class="field-row"><label>Enabled Tools</label><input type="text" class="form-input mcp-tools" value="${(sc.enabled_tools || ["*"]).join(", ")}" placeholder="*, tool_name, ..."></div>
        </div>`;
    return card;
}

function collectMcpServers() {
    const result = {};
    document.querySelectorAll(".mcp-server-card").forEach(card => {
        const name = card.querySelector(".mcp-name").value.trim();
        if (!name) return;
        const parseJson = val => { try { return JSON.parse(val || "{}"); } catch { return {}; } };
        result[name] = {
            type: card.querySelector(".mcp-type").value || null,
            command: card.querySelector(".mcp-command").value,
            args: card.querySelector(".mcp-args").value ? card.querySelector(".mcp-args").value.split(",").map(s => s.trim()).filter(Boolean) : [],
            url: card.querySelector(".mcp-url").value,
            headers: parseJson(card.querySelector(".mcp-headers").value),
            env: parseJson(card.querySelector(".mcp-env").value),
            tool_timeout: parseInt(card.querySelector(".mcp-timeout").value) || 30,
            enabled_tools: card.querySelector(".mcp-tools").value ? card.querySelector(".mcp-tools").value.split(",").map(s => s.trim()).filter(Boolean) : ["*"],
        };
    });
    return result;
}

window.addMcpServer = function() {
    const card = buildMcpServerCard("", { args: [], enabled_tools: ["*"], tool_timeout: 30 });
    card.classList.add("open");
    $("mcp-servers-list").appendChild(card);
    card.querySelector(".mcp-name").focus();
};

window.removeMcpServer = function(btn) {
    btn.closest(".mcp-server-card").remove();
};

window.saveSettings = async function() {
    const modelVal = $("s-agent-model").value.trim();
    if (modelVal) {
        const hist = JSON.parse(localStorage.getItem("shibaclaw_model_history") || "[]");
        const updated = [modelVal, ...hist.filter(m => m !== modelVal)].slice(0, 10);
        localStorage.setItem("shibaclaw_model_history", JSON.stringify(updated));
    }
    const patch = {
        agents: { defaults: {
            provider: $("s-agent-provider").value,
            model: $("s-agent-model").value,
            temperature: parseFloat($("s-agent-temp").value),
            maxTokens: parseInt($("s-agent-maxTokens").value),
            contextWindowTokens: parseInt($("s-agent-ctxTokens").value),
            maxToolIterations: parseInt($("s-agent-maxIter").value),
            workspace: $("s-agent-workspace").value,
            reasoningEffort: $("s-agent-reasoning").value || null,
            pinnedSkills: window._skillsPinnedList || [],
            maxPinnedSkills: window._skillsMaxPinned || 5,
        }},
        providers: {},
        tools: {
            web: {
                proxy: $("s-tool-proxy").value || null,
                search: {
                    provider: $("s-tool-searchProvider").value,
                    apiKey: $("s-tool-searchKey").value,
                    maxResults: parseInt($("s-tool-searchMax").value),
                }
            },
            exec: {
                enable: $("s-tool-execEnable").checked,
                timeout: parseInt($("s-tool-execTimeout").value),
            },
            restrictToWorkspace: $("s-tool-restrict").checked,
            mcpServers: collectMcpServers(),
        },
        gateway: {
            host: $("s-gw-host").value,
            port: parseInt($("s-gw-port").value),
            heartbeat: {
                enabled: $("s-gw-hbEnabled").checked,
                intervalS: parseInt($("s-gw-hbInterval").value),
            }
        },
        channels: {
            sendProgress: $("s-ch-sendProgress").checked,
            sendToolHints: $("s-ch-sendToolHints").checked,
        },
        audio: {
            providerUrl: $("s-audio-providerUrl").value || null,
            apiKey: $("s-audio-apiKey").value || null,
            model: $("s-audio-model").value || "whisper-large-v3-turbo",
            ttsEnabled: $("tts-toggle").checked,
        }
    };

    document.querySelectorAll(".prov-key").forEach(el => {
        const name = el.dataset.prov;
        if (!patch.providers[name]) patch.providers[name] = {};
        patch.providers[name].apiKey = el.value;
    });
    document.querySelectorAll(".prov-base").forEach(el => {
        const name = el.dataset.prov;
        if (!patch.providers[name]) patch.providers[name] = {};
        patch.providers[name].apiBase = el.value || null;
    });

    document.querySelectorAll(".ch-enabled").forEach(el => {
        const name = el.dataset.ch;
        if (!patch.channels[name]) patch.channels[name] = {};
        patch.channels[name].enabled = el.checked;
    });
    document.querySelectorAll(".ch-field").forEach(el => {
        const name = el.dataset.ch;
        const key = el.dataset.key;
        const type = el.dataset.type;
        if (!patch.channels[name]) patch.channels[name] = {};
        
        let val;
        if (type === "boolean") {
            val = el.checked;
        } else if (type === "array") {
            val = el.value ? el.value.split(",").map(s => s.trim()).filter(s => s) : [];
        } else if (type === "object") {
            try { val = JSON.parse(el.value); } catch(e) { val = {}; }
        } else if (type === "number") {
            val = Number(el.value);
        } else {
            val = el.value;
        }
        patch.channels[name][key] = val;
    });

    try {
        const res = await authFetch("/api/settings", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify(patch)
        });
        const data = await res.json();
        if (!res.ok) throw data.error || "Save failed";
        closeModal("settings-modal");
        fetchStatus();

        const ok = await shibaDialog("confirm", "Settings Saved", "Restart gateway to apply changes?", { confirmText: "Restart" });
        if (ok) {
            authFetch("/api/gateway-restart", { method: "POST" });
        }
    } catch(e) {
        shibaDialog("alert", "Error", "Error saving settings: " + e, { confirmText: "Close", danger: true });
    }
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


// ── Login/Logout UI ───────────────────────────────────────────
function syncFooterActions() {
    const logoutBtn = document.getElementById("btn-logout");
    if (logoutBtn) logoutBtn.hidden = !state.authRequired;
}

function showLogin(errorMsg = "") {
    const overlay = document.getElementById("login-overlay");
    const appContainer = document.getElementById("app-container");
    const errorEl = document.getElementById("login-error");
    const tokenInput = document.getElementById("login-token");

    overlay.style.display = "flex";
    appContainer.style.display = "none";

    if (errorMsg) {
        errorEl.textContent = errorMsg;
        errorEl.style.display = "block";
        // Shake animation
        const card = overlay.querySelector(".login-card");
        card.classList.remove("shake");
        void card.offsetWidth; // force reflow
        card.classList.add("shake");
    } else {
        errorEl.style.display = "none";
    }

    setTimeout(() => tokenInput.focus(), 100);
}

function hideLogin() {
    const overlay = document.getElementById("login-overlay");
    const appContainer = document.getElementById("app-container");
    overlay.style.display = "none";
    appContainer.style.display = "";
}

async function attemptLogin(token) {
    try {
        const res = await fetch("/api/auth/verify", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ token }),
        });
        const data = await res.json();
        if (data.valid) {
            setStoredToken(token);
            hideLogin();
            startApp();
            return true;
        } else {
            showLogin("Invalid token. Check the terminal output.");
            return false;
        }
    } catch (e) {
        showLogin("Connection error. Is the server running?");
        return false;
    }
}

function logout() {
    clearStoredToken();
    if (state.socket) {
        state.socket.disconnect();
        state.socket = null;
    }
    if (state.healthTimer) {
        clearInterval(state.healthTimer);
        state.healthTimer = null;
    }
    if (state.historyTimer) {
        clearInterval(state.historyTimer);
        state.historyTimer = null;
    }
    const logoutBtn = document.getElementById("btn-logout");
    if (logoutBtn) logoutBtn.hidden = true;
    showLogin();
}

function startApp() {
    initSocket();
    initListeners();
    fetchStatus();
    loadHistory();
    initAutomationSections();
    refreshTokenBadge();
    initFileHandlers();
    initOnboardWizard();
    chatInput.focus();

    syncFooterActions();

    // Gateway health check every 5s
    checkGatewayHealth();
    if (state.healthTimer) clearInterval(state.healthTimer);
    state.healthTimer = setInterval(checkGatewayHealth, 5000);

    // Auto-refresh history every 30s
    if (state.historyTimer) clearInterval(state.historyTimer);
    state.historyTimer = setInterval(loadHistory, 30000);

    // Auto-refresh automation every 30s
    if (state.autoTimer) clearInterval(state.autoTimer);
    state.autoTimer = setInterval(() => { loadCronSection(); loadHeartbeatSection(); }, 30000);
}


// ── Update Panel ──────────────────────────────────────────────
let _updateState = { manifestUrl: null };

async function loadUpdatePanel(force = false) {
    const panel = $("panel-update");
    if (!panel) return;
    panel.innerHTML = `<div class="update-checking"><span class="material-icons-round spin">progress_activity</span> Checking for updates...</div>`;

    try {
        const url = "/api/update/check" + (force ? "?force=1" : "");
        const res = await authFetch(url);
        const data = await res.json();

        if (data.error) {
            panel.innerHTML = `<div class="update-error"><span class="material-icons-round">error_outline</span> ${escapeHtml(data.error)}<br><button class="btn-secondary" style="margin-top:12px" onclick="loadUpdatePanel(true)">Retry</button></div>`;
            return;
        }

        const checkedAt = data.checked_at ? new Date(data.checked_at * 1000).toLocaleString() : "—";

        if (!data.update_available) {
            panel.innerHTML = `
                <div class="update-ok">
                    <span class="material-icons-round" style="font-size:48px;color:var(--accent-green)">check_circle</span>
                    <div class="update-ok-text">You're up to date</div>
                    <div class="update-version-row">
                        <span class="update-badge current">v${escapeHtml(data.current)}</span>
                    </div>
                    <div class="update-meta">Last checked: ${checkedAt}</div>
                    <button class="btn-secondary" style="margin-top:16px" onclick="loadUpdatePanel(true)">
                        <span class="material-icons-round" style="font-size:14px;vertical-align:middle">refresh</span> Check again
                    </button>
                </div>`;
            return;
        }

        // Update available — load manifest for details
        let manifestSection = "";

        if (data.manifest_url) {
            try {
                const mRes = await authFetch("/api/update/manifest?url=" + encodeURIComponent(data.manifest_url));
                const mData = await mRes.json();
                const manifest = mData.manifest || {};
                const personal = mData.personal_files || [];

                if (manifest.release_notes) {
                    manifestSection = `
                        <div class="update-notes">
                            <div class="update-notes-title"><span class="material-icons-round">article</span> What's new</div>
                            <div class="update-notes-body">${escapeHtml(manifest.release_notes)}</div>
                        </div>`;
                }

                if (personal.length > 0) {
                    const items = personal.map(f => {
                        const note = f.note ? ` <span class="update-file-note">— ${escapeHtml(f.note)}</span>` : "";
                        return `<li><span class="material-icons-round" style="font-size:14px;vertical-align:middle;color:var(--accent-orange)">description</span> <code>${escapeHtml(f.path)}</code>${note}</li>`;
                    }).join("");
                    manifestSection += `
                        <div class="update-personal">
                            <div class="update-personal-title"><span class="material-icons-round">folder_open</span> Files changed by this release</div>
                            <ul class="update-personal-list">${items}</ul>
                            <div class="update-personal-note">If you customized any of these tracked files, back them up before updating. After the update, run <code>shibaclaw onboard</code> again to refresh them. If you keep personal information in these files, save a copy first so you can restore it afterward.</div>
                        </div>`;
                }
            } catch (e) {
                manifestSection = `<div class="update-notes" style="color:var(--text-muted);font-size:12px">Could not load update details.</div>`;
            }
        }

        const pipCmd = `pip install --upgrade shibaclaw`;
        const dockerCmd = `docker compose pull && docker compose up -d`;

        panel.innerHTML = `
            <div class="update-available">
                <div class="update-version-row">
                    <span class="update-badge current">v${escapeHtml(data.current)}</span>
                    <span class="material-icons-round" style="color:var(--text-muted)">arrow_forward</span>
                    <span class="update-badge latest">v${escapeHtml(data.latest)}</span>
                </div>
                ${manifestSection}
                <div class="update-notes" style="margin-top:16px">
                    <div class="update-notes-title"><span class="material-icons-round">terminal</span> How to update</div>
                    <div style="margin-top:8px;font-size:13px;color:var(--text-muted)">pip / bare metal</div>
                    <div class="update-cmd-row">
                        <code id="cmd-pip">${pipCmd}</code>
                        <button class="btn-link" onclick="navigator.clipboard.writeText('${pipCmd}')" title="Copy"><span class="material-icons-round" style="font-size:16px">content_copy</span></button>
                    </div>
                    <div style="margin-top:10px;font-size:13px;color:var(--text-muted)">Docker</div>
                    <div class="update-cmd-row">
                        <code id="cmd-docker">${dockerCmd}</code>
                        <button class="btn-link" onclick="navigator.clipboard.writeText('${dockerCmd}')" title="Copy"><span class="material-icons-round" style="font-size:16px">content_copy</span></button>
                    </div>
                </div>
                <div class="update-actions" style="margin-top:16px">
                    ${data.release_url ? `<a href="${escapeHtml(data.release_url)}" target="_blank" class="btn-secondary">
                        <span class="material-icons-round" style="font-size:14px;vertical-align:middle">open_in_new</span> Release notes
                    </a>` : ""}
                </div>
                <div class="update-meta">Last checked: ${checkedAt} · <button class="btn-link" onclick="loadUpdatePanel(true)">Check again</button></div>
            </div>`;
    } catch (e) {
        panel.innerHTML = `<div class="update-error"><span class="material-icons-round">error_outline</span> Failed to check for updates.<br><button class="btn-secondary" style="margin-top:12px" onclick="loadUpdatePanel(true)">Retry</button></div>`;
    }
}


// ── Onboard Wizard ──────────────────────────────────────────
const _ob = { step: 1, provider: null, providers: [], templates: { existing: [] } };

function initOnboardWizard() {
    const eye = document.getElementById("ob-eye-toggle");
    const keyInput = document.getElementById("ob-api-key");
    if (eye && keyInput) {
        eye.addEventListener("click", () => {
            const show = keyInput.type === "password";
            keyInput.type = show ? "text" : "password";
            eye.querySelector("span").textContent = show ? "visibility" : "visibility_off";
        });
    }
}

window.openOnboardWizard = async function() {
    _ob.step = 1;
    _ob.provider = null;
    _ob._lastModelProvider = null;
    document.getElementById("ob-api-key").value = "";
    document.getElementById("ob-model-input").value = "";
    document.getElementById("ob-btn-finish").style.width = "";
    _obShowStep(1);
    openModal("onboard-modal");
    await _obLoadProviders();
    await _obLoadTemplates();
};

async function _obLoadProviders() {
    const grid = document.getElementById("ob-provider-grid");
    grid.innerHTML = '<div style="text-align:center;padding:2rem;color:var(--text-muted)"><span class="material-icons-round spin">progress_activity</span></div>';
    try {
        const res = await authFetch("/api/onboard/providers");
        const data = await res.json();
        _ob.providers = data.providers || [];
        _ob.currentProvider = data.current_provider;
        _ob.currentModel = data.current_model;
        _obRenderGrid();
    } catch(e) {
        grid.innerHTML = '<p style="color:var(--accent-red)">Failed to load providers</p>';
    }
}

async function _obLoadTemplates() {
    try {
        const res = await authFetch("/api/onboard/templates");
        const data = await res.json();
        _ob.templates = { existing: data.existing_files || [], new_files: data.new_files || [] };
    } catch(e) { _ob.templates = { existing: [], new_files: [] }; }
}

function _obRenderGrid() {
    const grid = document.getElementById("ob-provider-grid");
    grid.innerHTML = "";
    const ICONS = {
        openrouter:"route", anthropic:"psychology", openai:"auto_awesome", gemini:"diamond",
        deepseek:"explore", groq:"speed", ollama:"dns", github_copilot:"code"
    };
    for (const p of _ob.providers) {
        const card = document.createElement("div");
        card.className = "provider-card" + (p.name === _ob.currentProvider ? " selected" : "");
        card.dataset.name = p.name;
        let badge = "";
        if (p.status === "env_detected") badge = '<span class="ob-badge env">ENV</span>';
        else if (p.status === "configured") badge = '<span class="ob-badge configured">Configured</span>';
        else if (p.status === "oauth_ok") badge = '<span class="ob-badge oauth">OAuth \u2713</span>';
        else if (p.is_local) badge = '<span class="ob-badge local">Local</span>';
        else if (p.is_oauth) badge = '<span class="ob-badge oauth">OAuth</span>';
        const icon = ICONS[p.name] || "smart_toy";
        card.innerHTML = `
            <div class="pc-icon"><span class="material-icons-round">${icon}</span></div>
            <div class="pc-info">
                <div class="pc-name">${p.label}${badge}</div>
                <div class="pc-note">${p.env_key ? 'env: ' + p.env_key : (p.is_local ? 'No key needed' : (p.is_oauth ? 'OAuth login' : ''))}</div>
            </div>`;
        card.addEventListener("click", () => {
            grid.querySelectorAll(".provider-card").forEach(c => c.classList.remove("selected"));
            card.classList.add("selected");
            _ob.provider = p;
        });
        if (p.name === _ob.currentProvider) _ob.provider = p;
        grid.appendChild(card);
    }
}

function _obShowStep(n) {
    _ob.step = n;
    for (let i = 1; i <= 4; i++) {
        const panel = document.getElementById("ob-step-" + i);
        if (panel) panel.style.display = i === n ? "" : "none";
        const dot = document.querySelector(`.ob-step[data-step="${i}"]`);
        if (dot) {
            dot.classList.toggle("active", i === n);
            dot.classList.toggle("done", i < n);
        }
    }
    document.getElementById("ob-btn-back").style.display = n > 1 ? "" : "none";
    document.getElementById("ob-btn-next").style.display = n < 4 ? "" : "none";
    document.getElementById("ob-btn-finish").style.display = n === 4 ? "" : "none";

    if (n === 2) _obSetupStep2();
    if (n === 3) _obSetupStep3();
    if (n === 4) _obSetupStep4();
}

function _obSetupStep2() {
    const p = _ob.provider;
    if (!p) return;
    const keySection = document.getElementById("ob-key-section");
    const oauthSection = document.getElementById("ob-oauth-section");
    const localSection = document.getElementById("ob-local-section");
    keySection.style.display = "none";
    oauthSection.style.display = "none";
    localSection.style.display = "none";

    if (p.is_local) {
        localSection.style.display = "";
    } else if (p.is_oauth) {
        oauthSection.style.display = "";
        document.getElementById("ob-key-title").textContent = p.label + " \u2014 OAuth";
        const btn = document.getElementById("ob-oauth-btn");
        const statusEl = document.getElementById("ob-oauth-status");
        if (p.status === "oauth_ok") {
            statusEl.innerHTML = '<span style="color:#4ade80"><span class="material-icons-round" style="font-size:16px;vertical-align:middle">check_circle</span> Already authenticated</span>';
        } else {
            statusEl.innerHTML = "";
            btn.onclick = async () => {
                btn.disabled = true;
                btn.innerHTML = '<span class="material-icons-round spin" style="font-size:16px;vertical-align:middle">progress_activity</span> Starting...';
                try {
                    const resp = await authFetch("/api/oauth/login", { method:"POST", headers:{"Content-Type":"application/json"}, body: JSON.stringify({provider:p.name}) });
                    const jd = await resp.json();
                    if (jd.user_code && jd.verification_uri) {
                        statusEl.innerHTML = '<div style="text-align:center;margin-top:1rem">' +
                            '<a href="' + jd.verification_uri + '" target="_blank" class="btn-primary" style="display:inline-flex;align-items:center;gap:6px;text-decoration:none">' +
                            '<span class="material-icons-round" style="font-size:16px">open_in_new</span> Open GitHub</a>' +
                            '<div style="margin-top:10px;font-size:22px;letter-spacing:3px;font-weight:700;color:var(--shiba-gold);font-family:monospace;cursor:pointer" ' +
                            'onclick="navigator.clipboard.writeText(\'' + jd.user_code + '\')" title="Click to copy">' + jd.user_code + '</div>' +
                            '<div style="margin-top:8px;font-size:11px;color:var(--text-muted)">' +
                            '<span class="material-icons-round spin" style="font-size:14px;vertical-align:middle">progress_activity</span> Waiting for auth...</div></div>';
                    }
                    if (jd.job_id) {
                        const poll = setInterval(async () => {
                            try {
                                const r2 = await authFetch("/api/oauth/job/" + jd.job_id);
                                const j = await r2.json();
                                if (j.job && j.job.status === "done") {
                                    clearInterval(poll);
                                    statusEl.innerHTML = '<span style="color:#4ade80"><span class="material-icons-round" style="font-size:16px;vertical-align:middle">check_circle</span> Authenticated!</span>';
                                    btn.disabled = false;
                                    btn.innerHTML = '<span class="material-icons-round" style="font-size:16px;vertical-align:middle">check</span> Done';
                                } else if (j.job && j.job.status === "error") {
                                    clearInterval(poll);
                                    statusEl.innerHTML = '<span style="color:#f87171">Authentication failed</span>';
                                    btn.disabled = false;
                                    btn.innerHTML = '<span class="material-icons-round" style="font-size:16px;vertical-align:middle">lock_open</span> Retry';
                                }
                            } catch(ex) {}
                        }, 2000);
                    }
                } catch(e) {
                    statusEl.innerHTML = '<span style="color:#f87171">Error: ' + e + '</span>';
                    btn.disabled = false;
                    btn.innerHTML = '<span class="material-icons-round" style="font-size:16px;vertical-align:middle">lock_open</span> Retry';
                }
            };
        }
    } else {
        keySection.style.display = "";
        document.getElementById("ob-key-title").textContent = p.label + " \u2014 API Key";
        document.getElementById("ob-key-hint").textContent = p.env_key ? "You can also set the " + p.env_key + " environment variable." : "";
        if (p.status === "env_detected" || p.status === "configured") {
            document.getElementById("ob-api-key").placeholder = "Leave blank to keep current key";
        } else {
            document.getElementById("ob-api-key").value = "";
            document.getElementById("ob-api-key").placeholder = "sk-...";
        }
    }
}

function _obSetupStep3() {
    const p = _ob.provider;
    if (!p) return;
    document.getElementById("ob-model-hint").textContent = "Provider: " + p.label + ". Check the provider docs for available models.";
    const modelInput = document.getElementById("ob-model-input");
    if (!modelInput.value || _ob._lastModelProvider !== p.name) {
        _ob._lastModelProvider = p.name;
        modelInput.value = (_ob.currentProvider === p.name && _ob.currentModel) ? _ob.currentModel : p.default_model;
    }
}

function _obSetupStep4() {
    const p = _ob.provider;
    document.getElementById("ob-sum-provider").textContent = p ? p.label : "\u2014";
    document.getElementById("ob-sum-model").textContent = document.getElementById("ob-model-input").value || "\u2014";

    const tplSection = document.getElementById("ob-tpl-section");
    const tplList = document.getElementById("ob-tpl-list");
    if (_ob.templates.existing.length > 0) {
        tplSection.style.display = "";
        tplList.innerHTML = "";
        for (const f of _ob.templates.existing) {
            const item = document.createElement("label");
            item.className = "ob-tpl-item";
            item.innerHTML = '<input type="checkbox" value="' + f + '"> <span class="material-icons-round" style="font-size:16px;color:var(--text-muted)">description</span> ' + f;
            tplList.appendChild(item);
        }
    } else {
        tplSection.style.display = "none";
    }
}

window.obGoStep = function(dir) {
    let next = _ob.step + dir;
    if (next < 1) return;

    if (_ob.step === 1 && dir > 0 && !_ob.provider) {
        const grid = document.getElementById("ob-provider-grid");
        grid.style.animation = "none"; grid.offsetHeight; grid.style.animation = "shake 0.3s";
        return;
    }

    if (next === 2 && dir > 0 && _ob.provider && _ob.provider.is_local) {
        next = 3;
    }
    if (next === 2 && dir < 0 && _ob.provider && _ob.provider.is_local) {
        next = 1;
    }

    if (next > 4) return;
    _obShowStep(next);
};

window.obSubmit = async function() {
    const btn = document.getElementById("ob-btn-finish");
    btn.style.width = btn.offsetWidth + "px";
    btn.disabled = true;
    btn.innerHTML = '<span class="material-icons-round spin" style="font-size:16px;vertical-align:middle">progress_activity</span> Saving...';

    const overwrite = [];
    document.querySelectorAll("#ob-tpl-list input:checked").forEach(cb => overwrite.push(cb.value));

    try {
        const res = await authFetch("/api/onboard/submit", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({
                provider: _ob.provider.name,
                api_key: document.getElementById("ob-api-key").value.trim(),
                model: document.getElementById("ob-model-input").value.trim(),
                overwrite_templates: overwrite,
            })
        });
        const data = await res.json();
        if (!res.ok) throw data.error || "Setup failed";

        btn.style.width = "";
        closeModal("onboard-modal");
        state.onboardModalShown = false;
        fetchStatus();
        loadHistory();
    } catch(e) {
        btn.style.width = "";
        btn.disabled = false;
        btn.innerHTML = '<span class="material-icons-round" style="font-size:16px;vertical-align:middle">check</span> Finish Setup';
        await shibaDialog("alert", "Error", "Setup failed: " + e, { danger: true });
    }
};

