/**
 * Telegram-style chat history:
 * - open already on latest messages (no visible scroll-down)
 * - older messages prepend on scroll-up
 * - top flex spacer pushes short threads to the bottom without breaking scroll
 */
(function () {
    const PAGE = 30;
    const SPACER_CLASS = "chat-history-spacer";
    let store = null;
    let loadingMore = false;
    let scrollWired = false;

    function ensureStyles() {
        if (document.getElementById("chat-history-window-css")) return;
        const s = document.createElement("style");
        s.id = "chat-history-window-css";
        s.textContent = `
.chat-history.chat-pinning {
    scroll-behavior: auto !important;
    opacity: 0 !important;
    pointer-events: none;
}
.chat-history > .${SPACER_CLASS} {
    flex: 1 1 auto;
    min-height: 0;
    width: 100%;
    pointer-events: none;
}
`;
        document.head.appendChild(s);
    }

    function chatEl() {
        return document.getElementById("chat-history");
    }

    function ensureSpacer(el) {
        let spacer = el.querySelector(":scope > ." + SPACER_CLASS);
        if (!spacer) {
            spacer = document.createElement("div");
            spacer.className = SPACER_CLASS;
            spacer.setAttribute("aria-hidden", "true");
            el.insertBefore(spacer, el.firstChild);
        } else if (el.firstChild !== spacer) {
            el.insertBefore(spacer, el.firstChild);
        }
        return spacer;
    }

    function firstContentNode(el) {
        const spacer = el.querySelector(":scope > ." + SPACER_CLASS);
        let node = spacer ? spacer.nextSibling : el.firstChild;
        while (node && node.nodeType !== 1) node = node.nextSibling;
        return node;
    }

    function wireScroll() {
        const el = chatEl();
        if (!el || scrollWired) return;
        scrollWired = true;
        el.addEventListener(
            "scroll",
            () => {
                if (!store || loadingMore || store.renderedFrom <= 0) return;
                if (el.classList.contains("chat-pinning")) return;
                if (el.scrollTop > 80) return;
                prependOlder();
            },
            { passive: true }
        );
    }

    function _nextLiveTurnId(kind) {
        if (!store || !store.parsedMessages.length) return 1;
        const last = store.parsedMessages[store.parsedMessages.length - 1];
        if (kind === "user") return (last.turnId || 0) + 1;
        return last.turnId || 1;
    }

    function appendLiveParsed(type, data) {
        if (!store || store.sessionId !== state.sessionId) return;
        if (
            typeof _isCurrentSessionLoad === "function" &&
            !_isCurrentSessionLoad(store.loadSeq, store.sessionId)
        ) {
            return;
        }
        store.parsedMessages.push({
            type,
            data,
            turnId: _nextLiveTurnId(type),
        });
    }

    // Expose for api_socket agent_response (covers streaming + non-streaming).
    window._historyWindowAppendLive = appendLiveParsed;

    // Local WebUI sends go through addUserMessage, not a dedicated WS event.
    if (typeof addUserMessage === "function") {
        const _origAddUserMessage = addUserMessage;
        addUserMessage = function (content, attachments = []) {
            const result = _origAddUserMessage(content, attachments);
            try {
                appendLiveParsed("user", {
                    role: "user",
                    content: content || "",
                    attachments: attachments || [],
                });
            } catch (e) {
                /* keep chat render path resilient */
            }
            return result;
        };
        window.addUserMessage = addUserMessage;
    }

    function groupsForRange(from, to) {
        const msgs = store.parsedMessages.slice(from, to);
        if (!msgs.length) return [];
        let minTurn = msgs[0].turnId;
        let maxTurn = msgs[0].turnId;
        for (const m of msgs) {
            if (m.turnId < minTurn) minTurn = m.turnId;
            if (m.turnId > maxTurn) maxTurn = m.turnId;
        }
        return store.parsedGroups.filter((g) => g.turnId >= minTurn && g.turnId <= maxTurn);
    }

    function renderRange(from, to, atStart) {
        const msgs = store.parsedMessages.slice(from, to);
        if (!msgs.length) return;
        if (
            typeof _isCurrentSessionLoad === "function" &&
            !_isCurrentSessionLoad(store.loadSeq, store.sessionId)
        ) {
            return;
        }
        const groups = groupsForRange(from, to);
        const frag = document.createDocumentFragment();
        _renderSessionHistory(msgs, groups, frag, store.loadSeq, store.sessionId);
        const el = chatEl();
        if (!el) return;
        ensureSpacer(el);
        if (atStart) {
            const anchor = firstContentNode(el);
            if (anchor) el.insertBefore(frag, anchor);
            else el.appendChild(frag);
        } else {
            el.appendChild(frag);
        }
    }

    function prependOlder() {
        if (!store || loadingMore || store.renderedFrom <= 0) return;
        if (
            typeof _isCurrentSessionLoad === "function" &&
            !_isCurrentSessionLoad(store.loadSeq, store.sessionId)
        ) {
            return;
        }
        loadingMore = true;
        try {
            const el = chatEl();
            if (!el) return;
            el.style.scrollBehavior = "auto";
            const prevH = el.scrollHeight;
            const prevT = el.scrollTop;
            const newFrom = Math.max(0, store.renderedFrom - PAGE);
            renderRange(newFrom, store.renderedFrom, true);
            store.renderedFrom = newFrom;
            el.scrollTop = prevT + (el.scrollHeight - prevH);
        } finally {
            loadingMore = false;
        }
    }

    function snapNow(el) {
        el.style.scrollBehavior = "auto";
        el.scrollTop = el.scrollHeight;
    }

    function waitFrame() {
        return new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));
    }

    function waitImages(el, ms) {
        const imgs = Array.from(el.querySelectorAll("img")).filter((img) => !img.complete);
        if (!imgs.length) return Promise.resolve();
        return Promise.race([
            Promise.all(
                imgs.map(
                    (img) =>
                        new Promise((res) => {
                            img.addEventListener("load", res, { once: true });
                            img.addEventListener("error", res, { once: true });
                        })
                )
            ),
            new Promise((r) => setTimeout(r, ms)),
        ]);
    }

    async function revealAtBottom(el, loadSeq, sessionId) {
        ensureStyles();
        ensureSpacer(el);
        el.classList.add("chat-pinning");
        snapNow(el);
        await waitFrame();
        if (
            typeof _isCurrentSessionLoad === "function" &&
            !_isCurrentSessionLoad(loadSeq, sessionId)
        ) {
            return;
        }
        snapNow(el);
        await waitImages(el, 400);
        if (
            typeof _isCurrentSessionLoad === "function" &&
            !_isCurrentSessionLoad(loadSeq, sessionId)
        ) {
            return;
        }
        snapNow(el);
        el.classList.remove("chat-pinning");
        el.style.scrollBehavior = "";
    }

    if (typeof loadSession !== "function") {
        console.warn("[SHIBA] chat_history_window: loadSession not found");
        return;
    }

    async function loadSessionWindowed(sessionId) {
        if (typeof window.showWorkspaceChat === "function") window.showWorkspaceChat();
        ensureStyles();
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
        window.subagentUI?.selectSession(sessionId);
        localStorage.setItem("shiba_session_id", sessionId);
        store = null;

        document.querySelectorAll(".history-item").forEach((node) => node.classList.remove("active"));
        const list = $("history-list");
        if (list) {
            const encodedId = encodeURIComponent(sessionId);
            for (const node of list.children) {
                try {
                    const dropdown = node.querySelector(".session-dropdown");
                    if (dropdown && dropdown.dataset && dropdown.dataset.sessionKey === encodedId) {
                        node.classList.add("active");
                    }
                } catch (e) {
                    if (node.textContent && node.textContent.includes(sessionId)) {
                        node.classList.add("active");
                    }
                }
            }
        }

        const el = chatEl();
        try {
            const res = await authFetch(`/api/sessions/${encodeURIComponent(sessionId)}`);
            const data = await res.json();
            if (!_isCurrentSessionLoad(loadSeq, sessionId)) return;

            _syncSessionUI(data, loadSeq, sessionId);
            if (!_isCurrentSessionLoad(loadSeq, sessionId)) return;

            if (el) {
                el.classList.add("chat-pinning");
                el.classList.remove("chat-anchored");
                el.innerHTML = "";
                ensureSpacer(el);
            }
            state.messageCount = 0;
            Object.values(state.processGroups || {}).forEach((pg) => {
                if (pg && pg.timer) clearInterval(pg.timer);
            });
            state.processGroups = {};

            const messages = Array.isArray(data.messages) ? data.messages : [];
            if (!messages.length) {
                if (el) {
                    el.classList.remove("active", "chat-pinning", "chat-anchored");
                    el.innerHTML = "";
                }
                if (welcomeScreen) welcomeScreen.style.display = "";
                return;
            }

            activateChat();
            if (el) el.classList.add("chat-pinning");
            try {
                refreshTokenBadge();
            } catch (e) {
                /* ignore */
            }

            const { parsedMessages, parsedGroups } = _parseSessionMessages(
                messages,
                loadSeq,
                sessionId
            );
            if (!_isCurrentSessionLoad(loadSeq, sessionId)) return;

            if (typeof ensureTelegramOwnerIds === "function") {
                await ensureTelegramOwnerIds();
            }
            if (!_isCurrentSessionLoad(loadSeq, sessionId)) return;

            const total = parsedMessages.length;
            const from = Math.max(0, total - PAGE);
            store = {
                sessionId,
                loadSeq,
                parsedMessages,
                parsedGroups,
                renderedFrom: from,
            };
            wireScroll();
            renderRange(from, total, false);
            if (!_isCurrentSessionLoad(loadSeq, sessionId)) return;
            if (el) await revealAtBottom(el, loadSeq, sessionId);
        } catch (e) {
            if (_isCurrentSessionLoad(loadSeq, sessionId)) {
                console.debug("[SHIBA] Error loading session (windowed):", e);
            }
            if (el) el.classList.remove("chat-pinning");
        } finally {
            if (realtime && realtime.connected && _isCurrentSessionLoad(loadSeq, sessionId)) {
                window.subagentUI?.render();
                realtime.emit("switch_session", { session_id: sessionId });
            }
        }
    }

    loadSession = loadSessionWindowed;
    window.loadSession = loadSessionWindowed;
    console.debug("[SHIBA] chat_history_window: installed (spacer + pin-bottom)");
})();
