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

function _finalizeStreamBubble(msgId) {
    const mid = msgId || "stream";
    _cancelScheduledStreamRender(mid);
    const bubble = document.getElementById("stream-bubble-" + mid);
    if (bubble) {
        if (state._streamBuffers && state._streamBuffers[mid]) {
            bubble.innerHTML = renderMarkdown(state._streamBuffers[mid]);
            enhanceCodeBlocks(bubble);
            try { bubble.setAttribute('data-raw-content', state._streamBuffers[mid] || ''); } catch (e) { }
        }
        bubble.removeAttribute("id");
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
        try {
            if (state._streamBuffers && state._streamBuffers[mid]) {
                target.setAttribute('data-raw-content', state._streamBuffers[mid]);
            } else {
                target.removeAttribute('data-raw-content');
            }
        } catch (e) { }
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
        img.onload = () => { if (typeof scrollToBottom === 'function') scrollToBottom(); };
        img.onclick = () => window.open(file.url, "_blank");
        container.appendChild(img);
        if (typeof scrollToBottom === 'function') scrollToBottom();
        return;
    }

    if (file.type && file.type.startsWith("audio/")) {
        const player = createAudioPlayer(file, true);
        container.appendChild(player);
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
        // We no longer add a destructive GEN block if we have a stream bubble,
        // we just finalize it so it stays natively on screen.
        _finalizeStreamBubble(data.id);

        // Only fallback to showThinking if there was no stream bubble at all
        // to avoid duplicating text.
        showThinking("Sto riflettendo...");
    });

    realtime.on("agent_tool", (data) => {
        if (data.session_key && data.session_key !== state.sessionId) return;
        clearTimeout(state._typingBubbleTimeout);
        hideTypingBubble();
        showThinking(data.content);
        addProcessStep(data.id, data.content, "EXE");
        // Finalize any pending stream bubble before tool execution
        _finalizeStreamBubble(data.id);
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
            try { bubble.setAttribute('data-raw-content', state._streamBuffers[mid] || ''); } catch (e) { }
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
                try { streamBubble.setAttribute('data-raw-content', data.content || ''); } catch (e) { }
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

        // Play text-to-speech if enabled and no audio file is attached
        const hasAudioAttachment = data.attachments && data.attachments.some(file => typeof file.type === "string" && file.type.startsWith("audio/"));
        if (window.speechTTS && window.speechTTS.enabled && data.content && !hasAudioAttachment) {
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

    realtime.on("system_event", (data) => {
        if (data.event === "update_progress") {
            if (typeof window.updateDownloadProgress === "function") {
                window.updateDownloadProgress(data.data.percent);
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
        if (res.ok) {
            const data = await res.json();
            state.agentConfigured = data.agent_configured;

            const versionEl = $("sidebar-version");
            if (versionEl && data.version) versionEl.textContent = "v" + data.version;

            const isConfigured = (data.agent_configured || data.oauth_configured) && data.model;

            // Popola il mini-widget in basso
            const chEl = document.getElementById("summary-channels");
            const prEl = document.getElementById("summary-provider");
            const resEl = document.getElementById("summary-restrict-badge");

            const chDot = document.getElementById("summary-ch-dot");
            const prDot = document.getElementById("summary-provider-dot");
            const resDot = document.getElementById("summary-restrict-dot");

            if (data.active_channels && data.active_channels.length > 0) {
                if (chEl) chEl.textContent = data.active_channels.join(", ");
                if (chDot) chDot.className = "status-dot connected";
            } else {
                if (chEl) chEl.textContent = "WebUI";
                if (chDot) chDot.className = "status-dot connected";
            }

            if (data.provider) {
                if (prEl) prEl.textContent = data.provider;
                if (prDot) prDot.className = "status-dot connected";
            } else {
                if (prEl) prEl.textContent = "N/A";
                if (prDot) prDot.className = "status-dot disconnected";
            }

            if (resEl) {
                const isRestricted = data.restrict_workspace;
                resEl.textContent = isRestricted ? "ON" : "OFF";
                if (resDot) resDot.className = isRestricted ? "status-dot connected" : "status-dot disconnected";
            }

            if (isConfigured && realtime.connected) {
                state.gatewayUp = true;
                state.gatewayKnown = true;
                state.gatewayUnreachableCount = 0;
                setStatusIndicator("ready");
                closeModal("onboard-modal");
                state.onboardModalShown = false;
            } else {
                setStatusIndicator("not-configured");
                if (!isConfigured) {
                    console.log("Triggering onboarding wizard (not fully configured)");
                    openOnboardWizard();
                }
            }
        }
    } catch (e) {
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
    } catch (e) {
        reachable = false;
        providerReady = true;
    }

    let anyJobRunning = false;
    if (reachable) {
        try {
            const jobsRes = await authFetch("/api/automation/jobs?_t=" + Date.now());
            if (jobsRes.ok) {
                const jobsData = await jobsRes.json();
                const jobs = jobsData.jobs || [];
                anyJobRunning = jobs.some(j => (j.state || {}).last_status === "running" || (j.state || {}).lastStatus === "running");
            }
        } catch (e) { }
    }

    state.gatewayKnown = true;
    state.gatewayProviderReady = providerReady;
    state.anyJobRunning = anyJobRunning;

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
        if (!state.agentConfigured) {
            setStatusIndicator("not-configured");
        } else if (!state.gatewayProviderReady) {
            setStatusIndicator("model-offline");
        } else if (state.anyJobRunning) {
            setStatusIndicator("working");
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
    switch (mode) {
        case "ready":
            statusDot.className = "status-dot connected";
            statusText.textContent = "Shiba ready";
            break;
        case "working":
            statusDot.className = "status-dot working";
            statusText.textContent = "Executing...";
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
window.restartGateway = async function () {
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
            } catch (e) { }
            if (tries > 15) {
                clearInterval(poll);
                btn.classList.remove("restarting");
                setStatusIndicator("gateway-down");
            }
        }, 2000);
    } catch (e) {
        btn.classList.remove("restarting");
        setStatusIndicator("gateway-down");
        console.error("Restart error:", e);
    }
};


