// ── Streaming helpers ────────────────────────────────────────
function _discardStreamBubble(msgId) {
    const mid = msgId || "stream";
    _cancelScheduledStreamRender(mid);
    const bubble = document.getElementById("stream-bubble-" + mid);
    if (bubble) {
        const group = bubble.closest(".message-group");
        if (group) group.remove();
        bubble.remove();
    }
    if (state._streamBuffers) delete state._streamBuffers[mid];
}

function _cancelScheduledStreamRender(msgId) {
    const mid = msgId || "stream";
    const frames = state._streamRenderFrames || {};
    if (frames[mid]) {
        cancelAnimationFrame(frames[mid]);
        delete frames[mid];
    }
}

function _scheduleStreamRender(msgId, bubble) {
    const mid = msgId || "stream";
    const frames = state._streamRenderFrames || (state._streamRenderFrames = {});
    if (frames[mid]) return;
    frames[mid] = requestAnimationFrame(() => {
        delete frames[mid];
        const target = (bubble && bubble.isConnected) ? bubble : document.getElementById("stream-bubble-" + mid);
        if (!target) return;
        target.innerHTML = renderMarkdown(state._streamBuffers[mid] || "");
        enhanceCodeBlocks(target);
        scrollToBottom();
    });
}

function _clearAllStreamRenders() {
    const frames = state._streamRenderFrames || {};
    Object.keys(frames).forEach((mid) => _cancelScheduledStreamRender(mid));
}

function _appendAgentAttachment(container, file) {
    if (file.type && file.type.startsWith("image/")) {
        const img = document.createElement("img");
        img.src = file.url;
        img.onclick = () => window.open(file.url, "_blank");
        container.appendChild(img);
        return;
    }

    const link = buildFileAttachmentLink(file, () => {
        downloadAttachment(file.url, file.name || "file");
    });
    container.appendChild(link);
}

// ── WebSocket Connection (via realtime.js adapter) ───────────
function initSocket() {
    // Expose as state.socket for backward compatibility with UI checks
    state.socket = realtime;

    if (state.socketHandlersInitialized) {
        realtime.connect(getStoredToken());
        return;
    }

    state.socketHandlersInitialized = true;

    realtime.on("connected", (data) => {
        fetchStatus();

        if (state._initialConnectDone) {
            if (state.sessionId && state.sessionId !== data.session_id) {
                realtime.emit("switch_session", { session_id: state.sessionId });
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

    realtime.on("disconnect", () => {
        statusDot.className = "status-dot disconnected";
        statusText.textContent = "Disconnected";
        hideTypingBubble();
        hideThinking();
        _clearAllStreamRenders();
        state._streamBuffers = {};
        state.processing = false;
        updateSendButton();
        console.log("WebSocket disconnected.");
    });

    realtime.on("agent_thinking", (data) => {
        if (data.session_key && data.session_key !== state.sessionId) return;
        clearTimeout(state._typingBubbleTimeout);
        hideTypingBubble();
        showThinking(data.content);
        addProcessStep(data.id, data.content, "GEN");
        // If streaming was in progress, discard the partial bubble (model chose tools)
        _discardStreamBubble(data.id);
    });

    realtime.on("agent_tool", (data) => {
        if (data.session_key && data.session_key !== state.sessionId) return;
        clearTimeout(state._typingBubbleTimeout);
        hideTypingBubble();
        showThinking(data.content);
        addProcessStep(data.id, data.content, "EXE");
        // If streaming was in progress, discard the partial bubble (model chose tools)
        _discardStreamBubble(data.id);
    });

    // ── Streaming response chunks ──
    realtime.on("agent_response_chunk", (data) => {
        if (data.session_key && data.session_key !== state.sessionId) return;
        clearTimeout(state._typingBubbleTimeout);
        hideTypingBubble();

        // Accumulate streamed text per message id
        if (!state._streamBuffers) state._streamBuffers = {};
        const mid = data.id || "stream";
        state._streamBuffers[mid] = (state._streamBuffers[mid] || "") + (data.content || "");

        // Get or create the streaming bubble
        let bubble = document.getElementById("stream-bubble-" + mid);
        if (!bubble) {
            collapseProcessGroup(mid);
            activateChat();
            const group = createMessageGroup("agent");
            bubble = document.createElement("div");
            bubble.className = "message-bubble";
            bubble.id = "stream-bubble-" + mid;
            group.querySelector(".message-content").appendChild(bubble);
            addTimestamp(group);
            chatHistory.appendChild(group);
        }

        _scheduleStreamRender(mid, bubble);
    });

    realtime.on("agent_response", (data) => {
        if (data.session_key && data.session_key !== state.sessionId) return;
        clearTimeout(state._typingBubbleTimeout);
        hideTypingBubble();
        hideThinking();
        collapseProcessGroup(data.id);

        // If streaming already created the bubble, finalize it with the complete content
        const mid = data.id || "stream";
        const streamBubble = document.getElementById("stream-bubble-" + mid);
        _cancelScheduledStreamRender(mid);
        if (streamBubble) {
            // Clean up stream buffer
            if (state._streamBuffers) delete state._streamBuffers[mid];
            // Re-render with final content (which may include <think> stripping, etc.)
            if (data.content) {
                streamBubble.innerHTML = renderMarkdown(data.content);
                enhanceCodeBlocks(streamBubble);
            }
            streamBubble.removeAttribute("id"); // Remove stream id marker

            // Append any attachments
            if (data.attachments && data.attachments.length) {
                data.attachments.forEach(file => {
                    _appendAgentAttachment(streamBubble, file);
                });
            }
        } else {
            addAgentMessage(data.id, data.content, data.attachments || []);
        }
        
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

    realtime.on("error", (data) => {
        if (data.session_key && data.session_key !== state.sessionId) return;
        clearTimeout(state._typingBubbleTimeout);
        hideTypingBubble();
        hideThinking();
        addAgentMessage("error", `⚠️ ${data.message}`);
        state.processing = false;
        setWorkingState(false);
        updateSendButton();
    });

    realtime.on("message_queued", (data) => {
        state.queueCount = data.position || (state.queueCount + 1);
        updateQueueIndicator();
    });

    realtime.on("message_ack", (data) => {
        if (data.session_key && data.session_key !== state.sessionId) return;
        setWorkingState(true);
        clearTimeout(state._typingBubbleTimeout);
        state._typingBubbleTimeout = setTimeout(() => showTypingBubble(), 150);
    });

    realtime.on("session_reset", (data) => {
        Object.values(state.processGroups).forEach(pg => {
            if (pg && pg.timer) clearInterval(pg.timer);
        });
        state.processGroups = {};
        state.sessionId = data.session_id;
        state.activeModelId = "";
        _clearAllStreamRenders();
        state._streamBuffers = {};
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
        if (typeof updateModelSelectorDisplay === "function") {
            void updateModelSelectorDisplay("");
        }
    });

    realtime.on("session_status", (data) => {
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
                if (evt.type === "agent_thinking" || evt.type === "thinking") {
                    showThinking(evt.content);
                    addProcessStep(evt.id, evt.content, "GEN");
                } else if (evt.type === "agent_tool" || evt.type === "tool") {
                    showThinking(evt.content);
                    addProcessStep(evt.id, evt.content, "EXE");
                }
            }
            if (events.length > 0) {
                showThinking(events[events.length - 1].content);
            }
        }
    });

    realtime.connect(getStoredToken());
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
            if (isConfigured && realtime.connected) {
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
    if (state.processing) return;
    if (!realtime.connected) {
        state.gatewayUp = false;
        state.gatewayKnown = true;
        setStatusIndicator("disconnected");
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
    if (!realtime.connected) {
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


