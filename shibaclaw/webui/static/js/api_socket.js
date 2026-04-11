// ── Socket.IO Connection ─────────────────────────────────────
function initSocket() {
    const savedSessionId = localStorage.getItem("shiba_session_id");
    const token = getStoredToken();
    
    state.socket = io({
        transports: ["websocket", "polling"],
        reconnection: true,
        reconnectionDelay: 1000,
        reconnectionAttempts: 10,
        query: savedSessionId ? { session_id: savedSessionId } : {},
        auth: token ? { token } : {},
    });

    const { socket } = state;

    socket.on("connect", () => {
        state.socket.connected = true;
        fetchStatus();
    });

    socket.on("disconnect", () => {
        state.socket.connected = false;
        statusDot.className = "status-dot disconnected";
        statusText.textContent = "Disconnected";
        hideTypingBubble();
        hideThinking();
        state.processing = false;
        updateSendButton();
        console.log("WebSocket disconnected.");
    });

    socket.on("connect_error", (err) => {
        if (err && err.message === "Unauthorized") {
            console.warn("Socket.IO auth rejected — showing login");
            socket.disconnect();
            showLogin("Invalid token. Please try again.");
        }
    });

    socket.on("connected", (data) => {
        if (state._initialConnectDone) {
            if (state.sessionId && state.sessionId !== data.session_id) {
                socket.emit("switch_session", { session_id: state.sessionId });
            }
            return;
        }
        state._initialConnectDone = true;
        state.sessionId = data.session_id;
        setSessionLabel(data.session_id);
        localStorage.setItem("shiba_session_id", data.session_id);
        if (data.session_id) {
            loadSession(data.session_id);
        }
    });

    socket.on("agent_thinking", (data) => {
        if (data.session_key && data.session_key !== state.sessionId) return;
        clearTimeout(state._typingBubbleTimeout);
        hideTypingBubble();
        showThinking(data.content);
        addProcessStep(data.id, data.content, "GEN");
    });

    socket.on("agent_tool", (data) => {
        if (data.session_key && data.session_key !== state.sessionId) return;
        clearTimeout(state._typingBubbleTimeout);
        hideTypingBubble();
        showThinking(data.content);
        addProcessStep(data.id, data.content, "EXE");
    });

    socket.on("agent_response", (data) => {
        if (data.session_key && data.session_key !== state.sessionId) return;
        clearTimeout(state._typingBubbleTimeout);
        hideTypingBubble();
        hideThinking();
        collapseProcessGroup(data.id);
        addAgentMessage(data.id, data.content, data.attachments || []);
        
        // Play text-to-speech if enabled
        if (window.speechTTS && window.speechTTS.enabled && data.content) {
            window.speechTTS.play(data.content);
        }

        if (state.queueCount && state.queueCount > 0) state.queueCount = Math.max(0, state.queueCount - 1);
        updateQueueIndicator();
        state.processing = false;
        setWorkingState(false);
        updateSendButton();
        autoTitleSession();
        loadHistory();
        refreshTokenBadge();
    });

    socket.on("error", (data) => {
        if (data.session_key && data.session_key !== state.sessionId) return;
        clearTimeout(state._typingBubbleTimeout);
        hideTypingBubble();
        hideThinking();
        addAgentMessage("error", `⚠️ ${data.message}`);
        state.processing = false;
        setWorkingState(false);
        updateSendButton();
    });

    socket.on("message_queued", (data) => {
        state.queueCount = data.position || (state.queueCount + 1);
        updateQueueIndicator();
    });

    socket.on("message_ack", (data) => {
        if (data.session_key && data.session_key !== state.sessionId) return;
        setWorkingState(true);
        clearTimeout(state._typingBubbleTimeout);
        state._typingBubbleTimeout = setTimeout(() => showTypingBubble(), 150);
    });

    socket.on("session_reset", (data) => {
        Object.values(state.processGroups).forEach(pg => {
            if (pg && pg.timer) clearInterval(pg.timer);
        });
        state.processGroups = {};
        state.sessionId = data.session_id;
        setSessionLabel(data.session_id);
        localStorage.setItem("shiba_session_id", data.session_id);
        chatHistory.innerHTML = "";
        chatHistory.classList.remove("active");
        welcomeScreen.style.display = "";
        state.messageCount = 0;
        clearTimeout(state._typingBubbleTimeout);
        hideTypingBubble();
        hideThinking();
        refreshTokenBadge();
    });



    socket.on("session_status", (data) => {
        if (data.session_key && data.session_key !== state.sessionId) return;
        if (data.processing) {
            state.processing = true;
            setWorkingState(true);
            
            if (data.msg_id && state.processGroups[data.msg_id]) {
                const pg = state.processGroups[data.msg_id];
                if (pg.timer) clearInterval(pg.timer);
                if (pg.el) pg.el.remove();
                delete state.processGroups[data.msg_id];
            }
            
            const events = data.events || [];
            for (const evt of events) {
                if (evt.type === "agent_thinking") {
                    showThinking(evt.content);
                    addProcessStep(evt.id, evt.content, "GEN");
                } else if (evt.type === "agent_tool") {
                    showThinking(evt.content);
                    addProcessStep(evt.id, evt.content, "EXE");
                }
            }
            if (events.length > 0) {
                showThinking(events[events.length - 1].content);
            }
        }
    });
}


function updateQueueIndicator() {
    const existing = document.getElementById('queue-indicator');
    if (state.queueCount && state.queueCount > 0) {
        if (existing) {
            existing.textContent = state.queueCount;
        } else {
            const badge = document.createElement('span');
            badge.id = 'queue-indicator';
            badge.className = 'queue-indicator';
            badge.textContent = state.queueCount;
            badge.style.cssText = 'background:#ff8c00;color:#fff;padding:2px 6px;border-radius:12px;font-size:12px;margin-left:8px';
            if (btnSend && btnSend.parentNode) btnSend.parentNode.insertBefore(badge, btnSend.nextSibling);
        }
    } else {
        if (existing) existing.remove();
    }
}


// ── Modals & APIs ─────────────────────────────────────────────
async function fetchStatus() {
    try {
        const res = await authFetch("/api/status?_t=" + Date.now());
        let oauthConfigured = false;
        try {
            const oauthRes = await authFetch("/api/oauth/providers?_t=" + Date.now());
            if (oauthRes.ok) {
                const oauthData = await oauthRes.json();
                oauthConfigured = (oauthData.providers || []).some(p => p.status === "configured");
            }
        } catch {}
        if (res.ok) {
            const data = await res.json();
            state.agentConfigured = data.agent_configured;

            const versionEl = $("sidebar-version");
            if (versionEl && data.version) versionEl.textContent = "v" + data.version;

            const isConfigured = data.agent_configured || oauthConfigured;
            if (isConfigured && state.socket && state.socket.connected) {
                state.gatewayUp = true;
                state.gatewayKnown = true;
                state.gatewayUnreachableCount = 0;
                setStatusIndicator("ready");
                closeModal("onboard-modal");
                state.onboardModalShown = false;
            } else {
                setStatusIndicator("not-configured");
                if (!data.agent_configured && !oauthConfigured && !state.onboardModalShown) {
                    state.onboardModalShown = true;
                    openOnboardWizard();
                }
            }
        }
    } catch(e) {
        setStatusIndicator("disconnected");
    }
}


// ── Gateway Health Polling ─────────────────────────────────────
async function checkGatewayHealth() {
    if (!state.socket || !state.socket.connected) {
        state.gatewayUp = false;
        state.gatewayKnown = true;
        if (!state.processing) setStatusIndicator("disconnected");
        return;
    }

    let reachable = false;
    let providerReady = true;

    try {
        const res = await authFetch("/api/gateway-health?_t=" + Date.now());
        const data = await res.json();
        reachable = data.reachable === true;
        providerReady = data.provider_ready !== false;
    } catch(e) {
        reachable = false;
        providerReady = true;
    }

    state.gatewayKnown = true;
    state.gatewayProviderReady = providerReady;

    if (reachable) {
        state.gatewayUp = true;
        state.gatewayUnreachableCount = 0;
    } else {
        const maxFailures = state.agentConfigured ? 10 : 3;
        state.gatewayUnreachableCount = Math.min(maxFailures, state.gatewayUnreachableCount + 1);

        if (state.gatewayUnreachableCount >= maxFailures) {
            state.gatewayUp = false;
        }
    }

    if (!state.processing) {
        updateUIFromHealthState();
    }
}

function updateUIFromHealthState() {
    if (!state.socket || !state.socket.connected) {
        setStatusIndicator("disconnected");
        return;
    }

    if (!state.gatewayKnown) {
        return;
    }

    if (state.gatewayUp) {
        if (!state.gatewayProviderReady) {
            setStatusIndicator("model-offline");
        } else {
            setStatusIndicator("ready");
        }
        return;
    }

    if (state.gatewayUnreachableCount >= (state.agentConfigured ? 10 : 3)) {
        setStatusIndicator("gateway-down");
        return;
    }
}

function setStatusIndicator(mode) {
    switch(mode) {
        case "ready":
            statusDot.className = "status-dot connected";
            statusText.textContent = "Shiba ready";
            break;
        case "working":
            statusDot.className = "status-dot working";
            statusText.textContent = "Working...";
            break;
        case "gateway-down":
            statusDot.className = "status-dot gateway-down";
            statusText.textContent = "Gateway Down";
            break;
        case "model-offline":
            statusDot.className = "status-dot model-offline";
            statusText.textContent = "Model Offline";
            break;
        case "not-configured":
            statusDot.className = "status-dot disconnected";
            statusText.textContent = "Not Configured";
            break;
        case "disconnected":
        default:
            statusDot.className = "status-dot disconnected";
            statusText.textContent = "Disconnected";
            break;
    }
}

function setWorkingState(working) {
    const stopBtn = $("btn-stop");
    if (stopBtn) {
        stopBtn.disabled = !working;
        stopBtn.classList.toggle("active", working);
    }
    if (working) {
        setStatusIndicator("working");
    } else {
        updateUIFromHealthState();
    }
}


// ── Gateway Restart ───────────────────────────────────────────
window.restartGateway = async function() {
    const btn = $("btn-restart");
    if (btn.classList.contains("restarting")) return;

    btn.classList.add("restarting");
    statusText.textContent = "Restarting...";
    statusDot.className = "status-dot restarting";

    try {
        const res = await authFetch("/api/gateway-restart", { method: "POST" });
        const data = await res.json();
        if (!res.ok) throw data.error || "Restart failed";

        let tries = 0;
        const poll = setInterval(async () => {
            tries++;
            try {
                const h = await authFetch("/api/gateway-health?_t=" + Date.now());
                const hd = await h.json();
                if (hd.reachable) {
                    clearInterval(poll);
                    btn.classList.remove("restarting");
                    setStatusIndicator("ready");
                    fetchStatus();
                    return;
                }
            } catch(e) {}
            if (tries > 15) {
                clearInterval(poll);
                btn.classList.remove("restarting");
                setStatusIndicator("gateway-down");
            }
        }, 2000);
    } catch(e) {
        btn.classList.remove("restarting");
        setStatusIndicator("gateway-down");
        console.error("Restart error:", e);
    }
};


