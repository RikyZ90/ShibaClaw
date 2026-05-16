const notificationCenter = (() => {
    const store = new Map();
    const dom = {};
    let initialized = false;
    let hiddenResponseSignature = "";
    let hiddenResponseAt = 0;
    let _renderRafId = 0;

    function _cacheDom() {
        dom.root = $("notification-center");
        dom.bell = $("notification-bell");
        dom.badge = $("notification-badge");
        dom.dropdown = $("notification-dropdown");
        dom.list = $("notification-list");
        dom.subtitle = $("notification-subtitle");
        dom.markAll = $("notification-mark-all");
        dom.clearAll = $("notification-clear-all");
    }

    function _ordered() {
        return Array.from(store.values()).sort((a, b) => (b.timestamp || 0) - (a.timestamp || 0));
    }

    function _counts() {
        const items = _ordered();
        return {
            total: items.length,
            unread: items.filter(item => !item.read).length,
        };
    }

    function _relativeTime(timestamp) {
        if (!timestamp) return "Just now";
        const diff = Math.max(0, Math.floor(Date.now() / 1000) - timestamp);
        if (diff < 10) return "Just now";
        if (diff < 60) return `${diff}s ago`;
        if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
        if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
        return new Date(timestamp * 1000).toLocaleDateString();
    }

    function _notificationIcon(item) {
        const kind = item.kind || item.source || "notification";
        const icons = {
            update: "system_update",
            cron: "schedule_send",
            heartbeat: "favorite",
            agent_response: "chat",
            memory_compact: "auto_fix_high",
            memory_compacted: "auto_fix_high",
        };
        return icons[kind] || "notifications";
    }

    function _notificationTypeLabel(item) {
        const kind = item.kind || item.source || "notification";
        const labels = {
            update: "Update",
            cron: "Cron",
            heartbeat: "Heartbeat",
            agent_response: "Agent response",
            memory_compact: "Memory",
            memory_compacted: "Memory",
        };
        return labels[kind] || (kind.replace(/_/g, " ").replace(/\b\w/g, ch => ch.toUpperCase()));
    }

    function _upsert(notification) {
        if (!notification || !notification.id) return;
        store.set(notification.id, notification);
    }

    function _replaceAll(items) {
        store.clear();
        (items || []).forEach(_upsert);
    }

    function _setOpen(open) {
        if (!dom.root) return;
        dom.root.classList.toggle("is-open", open);
        if (dom.dropdown) dom.dropdown.setAttribute("aria-hidden", String(!open));
    }

    function _renderEmpty(message) {
        if (!dom.list) return;
        dom.list.innerHTML = `<div class="notification-empty">${escapeHtml(message)}</div>`;
    }

    function _renderItem(item) {
        const wrapper = document.createElement("div");
        wrapper.className = `notification-item${item.read ? "" : " is-unread"}`;

        const action = item.action || { kind: "none", label: "", target: "" };
        const sessionPill = item.session_key
            ? `<span class="notification-pill"><span class="material-icons-round" style="font-size:12px">forum</span>${escapeHtml(truncate(item.session_key, 28))}</span>`
            : "";
        const typePill = `<span class="notification-pill"><span class="material-icons-round" style="font-size:12px">label</span>${escapeHtml(_notificationTypeLabel(item))}</span>`;

        wrapper.innerHTML = `
            <div class="notification-item-icon">
                <span class="material-icons-round">${_notificationIcon(item)}</span>
            </div>
            <div class="notification-item-body">
                <div class="notification-item-header">
                    <div class="notification-item-title">${escapeHtml(item.title || "Notification")}</div>
                    <div class="notification-item-time">${escapeHtml(_relativeTime(item.timestamp))}</div>
                </div>
                <div class="notification-item-message">${escapeHtml(item.message || "")}</div>
                <div class="notification-item-meta">
                    ${typePill}
                    ${sessionPill}
                </div>
            </div>
            <div class="notification-item-actions"></div>
        `;

        const actionsEl = wrapper.querySelector(".notification-item-actions");
        if (action && action.kind && action.kind !== "none") {
            const actionBtn = document.createElement("button");
            actionBtn.type = "button";
            actionBtn.className = "notification-item-btn";
            actionBtn.textContent = action.label || "Open";
            actionBtn.addEventListener("click", async (event) => {
                event.stopPropagation();
                await _markRead(item.id, true);
                await _runAction(item);
            });
            actionsEl.appendChild(actionBtn);
        }

        const dismissBtn = document.createElement("button");
        dismissBtn.type = "button";
        dismissBtn.className = "notification-item-btn is-secondary";
        dismissBtn.textContent = "Dismiss";
        dismissBtn.addEventListener("click", async (event) => {
            event.stopPropagation();
            await _deleteNotification(item.id);
        });
        actionsEl.appendChild(dismissBtn);

        wrapper.addEventListener("click", async () => {
            await _markRead(item.id, true);
            if (action && action.kind && action.kind !== "none") {
                await _runAction(item);
            }
        });

        return wrapper;
    }

    function _renderNow() {
        if (!dom.root || !dom.badge || !dom.list || !dom.subtitle) return;
        const items = _ordered();
        const counts = _counts();

        dom.badge.hidden = counts.unread === 0;
        dom.badge.textContent = counts.unread > 99 ? "99+" : String(counts.unread || 0);
        dom.subtitle.textContent = counts.total === 0
            ? "No notifications yet"
            : counts.unread > 0
                ? `${counts.unread} unread of ${counts.total}`
                : `${counts.total} notifications`;

        dom.list.innerHTML = "";
        if (items.length === 0) {
            _renderEmpty("No notifications yet.");
            return;
        }

        const fragment = document.createDocumentFragment();
        items.forEach(item => fragment.appendChild(_renderItem(item)));
        dom.list.appendChild(fragment);
    }

    function _render() {
        if (_renderRafId) return;
        _renderRafId = requestAnimationFrame(() => {
            _renderRafId = 0;
            _renderNow();
        });
    }

    async function _refresh() {
        if (!dom.root) return;
        try {
            const res = await authFetch("/api/v1/notifications?limit=60");
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const data = await res.json();
            _replaceAll(data.notifications || []);
            _render();
        } catch (e) {
            _renderEmpty("Failed to load notifications.");
        }
    }

    async function _markRead(notificationId, silent = false) {
        if (!notificationId) return;
        const item = store.get(notificationId);
        if (item) {
            item.read = true;
            _upsert(item);
            _render();
        }
        try {
            await authFetch("/api/v1/notifications", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ operation: "mark_read", id: notificationId }),
            });
        } catch (e) {
            if (!silent) console.error("mark notification read", e);
        }
    }

    async function _markAllRead() {
        for (const item of store.values()) item.read = true;
        _render();
        try {
            await authFetch("/api/v1/notifications", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ operation: "mark_all_read" }),
            });
        } catch (e) {
            console.error("mark all notifications read", e);
        }
    }

    async function _deleteNotification(notificationId) {
        if (!notificationId) return;
        store.delete(notificationId);
        _render();
        try {
            await authFetch(`/api/v1/notifications?id=${encodeURIComponent(notificationId)}`, {
                method: "DELETE",
            });
        } catch (e) {
            console.error("delete notification", e);
        }
    }

    async function _clearAll() {
        store.clear();
        _render();
        try {
            await authFetch("/api/v1/notifications", { method: "DELETE" });
        } catch (e) {
            console.error("clear notifications", e);
        }
    }

    async function _runAction(item) {
        const action = item.action || { kind: "none", target: "" };
        if (!action.kind || action.kind === "none") return;

        window.focus();
        _setOpen(false);

        if (action.kind === "session" && action.target && typeof loadSession === "function") {
            await loadSession(action.target);
            return;
        }
        if (action.kind === "settings-tab" && action.target) {
            if (typeof openModal === "function") openModal("settings-modal");
            window.setTimeout(() => {
                if (typeof switchSettingsTab === "function") switchSettingsTab(action.target);
            }, 0);
            return;
        }
        if (action.kind === "url" && action.target) {
            window.open(action.target, "_blank", "noopener,noreferrer");
            return;
        }
        if (action.kind === "command" && action.target) {
            try {
                await navigator.clipboard.writeText(action.target);
            } catch (e) {
                console.error("copy notification command", e);
            }
        }
    }

    function _extractNotification(payload) {
        if (!payload) return null;
        if (payload.metadata && payload.metadata.id) return payload.metadata;
        if (payload.id && payload.message) return payload;
        return null;
    }

    function _handleRealtimeNotification(payload) {
        const notification = _extractNotification(payload);
        if (!notification) return;
        // Don't add bell noise for agent_response when the user is actively
        // focused on that exact session — they see the response directly in chat.
        if (
            notification.kind === "agent_response" &&
            notification.session_key &&
            notification.session_key === String(state.sessionId || "").trim() &&
            !document.hidden && document.hasFocus()
        ) {
            return;
        }
        _upsert(notification);
        _render();

        if (dom.bell && !dom.root.classList.contains("is-open")) {
            dom.bell.classList.remove("is-ringing");
            void dom.bell.offsetWidth; // trigger reflow
            dom.bell.classList.add("is-ringing");
        }
    }

    async function _createHiddenResponseNotification(data) {
        const sessionKey = data.session_key || state.sessionId;
        const message = truncate((data.content || "").replace(/\s+/g, " ").trim(), 180);
        if (!message || !sessionKey) return;

        const signature = `${sessionKey}:${data.id || message}`;
        const now = Date.now();
        if (hiddenResponseSignature === signature && now - hiddenResponseAt < 3000) {
            return;
        }
        hiddenResponseSignature = signature;
        hiddenResponseAt = now;

        try {
            const res = await authFetch("/api/v1/notifications", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    source: "agent_response",
                    kind: "agent_response",
                    title: "Agent response ready",
                    message,
                    session_key: sessionKey,
                    action: { kind: "session", label: "Open session", target: sessionKey },
                    metadata: { category: "agent_response" },
                    dedupe_key: `agent-response:${sessionKey}:${data.id || message}`,
                }),
            });
            const payload = await res.json().catch(() => ({}));
            if (payload.notification) {
                _upsert(payload.notification);
                _render();
            }
        } catch (e) {
            console.error("create hidden response notification", e);
        }
    }

    function _shouldNotifyForAgentResponse(data) {
        if (!data || !data.content) return false;
        if (document.hidden || !document.hasFocus()) return true;

        const responseSessionKey = String(data.session_key || "").trim();
        const activeSessionKey = String(state.sessionId || "").trim();
        if (!responseSessionKey) return false;
        if (!activeSessionKey) return true;
        return responseSessionKey !== activeSessionKey;
    }

    function _handleAgentResponse(data) {
        if (!_shouldNotifyForAgentResponse(data)) return;
        void _createHiddenResponseNotification(data);
    }

    function _bindRealtime() {
        if (typeof realtime === "undefined" || !realtime) return;
        realtime.on("notification", _handleRealtimeNotification);
        realtime.on("agent_response", _handleAgentResponse);
    }

    function _bindListeners() {
        if (!dom.bell || !dom.dropdown) return;

        dom.bell.addEventListener("click", (event) => {
            event.stopPropagation();
            const nextState = !dom.root.classList.contains("is-open");
            _setOpen(nextState);
        });

        dom.dropdown.addEventListener("click", (event) => event.stopPropagation());

        document.addEventListener("click", () => {
            _setOpen(false);
        });

        if (dom.markAll) {
            dom.markAll.addEventListener("click", async (event) => {
                event.stopPropagation();
                await _markAllRead();
            });
        }

        if (dom.clearAll) {
            dom.clearAll.addEventListener("click", async (event) => {
                event.stopPropagation();
                await _clearAll();
            });
        }
    }

    async function init() {
        _cacheDom();
        if (!dom.root) return;

        if (!initialized) {
            initialized = true;
            _bindListeners();
            _bindRealtime();
        }

        await _refresh();
    }

    function reset() {
        store.clear();
        _setOpen(false);
        _render();
    }

    return {
        init,
        refresh: _refresh,
        reset,
    };
})();

window.initNotificationCenter = function () {
    return notificationCenter.init();
};

window.refreshNotificationCenter = function () {
    return notificationCenter.refresh();
};

window.resetNotificationCenter = function () {
    return notificationCenter.reset();
};
