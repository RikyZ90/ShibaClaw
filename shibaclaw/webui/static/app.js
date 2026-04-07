// Salva l'ultimo config caricato per confronto
let lastSettingsConfig = null;
/**
 * ShibaClaw WebUI — Client Application
 * Socket.IO + Markdown rendering + interactive chat
 */

// ── Auth ─────────────────────────────────────────────────────
const AUTH_KEY = "shibaclaw_token";

function getStoredToken() {
    return localStorage.getItem(AUTH_KEY) || "";
}

function setStoredToken(token) {
    localStorage.setItem(AUTH_KEY, token);
}

function clearStoredToken() {
    localStorage.removeItem(AUTH_KEY);
}

/** Add auth header to all fetch calls. */
function authHeaders(extra = {}) {
    const token = getStoredToken();
    const headers = { ...extra };
    if (token) headers["Authorization"] = "Bearer " + token;
    return headers;
}

/** Wrapper around fetch that auto-adds auth headers. */
async function authFetch(url, opts = {}) {
    opts.headers = authHeaders(opts.headers || {});
    const res = await fetch(url, opts);
    if (res.status === 401) {
        // Token expired/invalid — show login
        showLogin("Session expired. Please re-enter your token.");
        throw new Error("Unauthorized");
    }
    return res;
}

// ── State ────────────────────────────────────────────────────
const state = {
    socket: null,
    sessionId: null,
    _initialConnectDone: false,
    processing: false,
    messageCount: 0,
    queueCount: 0,
    gatewayUp: false,
    gatewayUnreachableCount: 0,
    gatewayProviderReady: true,
    agentConfigured: false,
    healthTimer: null,
    historyTimer: null,
    processGroups: {},   // msgId → { el, startTime, stepCount, collapsed }
    authRequired: false,
    stagedFiles: [],     // { name, url, type, stagedAt }
    currentFsPath: ".",  // current path for file explorer
};

let clockTimer = null;

// ── DOM References ────────────────────────────────────────────
const $ = (id) => document.getElementById(id);
const chatHistory = $("chat-history");
const chatInput = $("chat-input");
const btnSend = $("btn-send");
const welcomeScreen = $("welcome-screen");
const thinkingIndicator = $("thinking-indicator");
const thinkingText = $("thinking-text");
const statusDot = $("status-dot");
const statusText = $("status-text");
const sessionIdEl = $("session-id");
const processTooltip = $("process-tooltip");

// ── Marked.js Configuration ──────────────────────────────────
if (typeof marked !== "undefined") {
    marked.setOptions({
        breaks: true,
        gfm: true,
        highlight: function (code, lang) {
            if (typeof hljs !== "undefined" && lang && hljs.getLanguage(lang)) {
                try {
                    return hljs.highlight(code, { language: lang }).value;
                } catch (e) { /* fallback */ }
            }
            return code;
        },
    });
}

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
        console.log("WebSocket connected.");
        fetchStatus();
        hideThinking();
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
        // On auto-reconnect, the server reassigns based on the original query param
        // (set when io() was called). If the user has since switched sessions we must
        // NOT override their current selection — just resync the server key instead.
        if (state._initialConnectDone) {
            // Reconnect: tell the server to use whatever session the client is on now.
            if (state.sessionId && state.sessionId !== data.session_id) {
                console.debug("[SHIBA] reconnect — resyncing server to client session:", state.sessionId);
                socket.emit("switch_session", { session_id: state.sessionId });
            }
            return;
        }
        state._initialConnectDone = true;

        state.sessionId = data.session_id;
        sessionIdEl.textContent = data.session_id;
        localStorage.setItem("shiba_session_id", data.session_id);
        
        // If we rejoined an existing session, fetch history
        if (data.session_id) {
            console.debug("[SHIBA] connected event → loadSession:", data.session_id);
            loadSession(data.session_id);
        }
    });

    socket.on("agent_thinking", (data) => {
        clearTimeout(state._typingBubbleTimeout);
        hideTypingBubble();
        showThinking(data.content);
        addProcessStep(data.id, data.content, "GEN");
    });

    socket.on("agent_tool", (data) => {
        clearTimeout(state._typingBubbleTimeout);
        hideTypingBubble();
        showThinking(data.content);
        addProcessStep(data.id, data.content, "EXE");
    });

    socket.on("agent_response", (data) => {
        console.debug("[SHIBA] agent_response:", data.id, "processGroups:", Object.keys(state.processGroups));
        clearTimeout(state._typingBubbleTimeout);
        hideTypingBubble();
        hideThinking();
        collapseProcessGroup(data.id);
        addAgentMessage(data.id, data.content, data.attachments || []);
        // decrement queued counter if any
        if (state.queueCount && state.queueCount > 0) state.queueCount = Math.max(0, state.queueCount - 1);
        updateQueueIndicator();
        state.processing = false;
        setWorkingState(false);
        updateSendButton();
        autoTitleSession();
        loadHistory();
        refreshTokenBadge();
        console.debug("[SHIBA] after agent_response, process groups in DOM:", chatHistory.querySelectorAll(".process-group").length);
    });

    socket.on("error", (data) => {
        clearTimeout(state._typingBubbleTimeout);
        hideTypingBubble();
        hideThinking();
        addAgentMessage("error", `⚠️ ${data.message}`);
        state.processing = false;
        setWorkingState(false);
        updateSendButton();
    });

    socket.on("message_queued", (data) => {
        // Server tells us the position in queue
        state.queueCount = data.position || (state.queueCount + 1);
        updateQueueIndicator();
    });

    socket.on("message_ack", (data) => {
        // Agent started processing — set working state
        setWorkingState(true);
        clearTimeout(state._typingBubbleTimeout);
        state._typingBubbleTimeout = setTimeout(() => showTypingBubble(), 150);
    });

    socket.on("session_reset", (data) => {
        // Clear all process group timers to prevent memory leak
        Object.values(state.processGroups).forEach(pg => {
            if (pg && pg.timer) clearInterval(pg.timer);
        });
        state.processGroups = {};
        state.sessionId = data.session_id;
        sessionIdEl.textContent = data.session_id;
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

// ── Message Rendering ─────────────────────────────────────────
function addUserMessage(content, attachments = []) {
    activateChat();
    const group = createMessageGroup("user");
    const bubble = document.createElement("div");
    bubble.className = "message-bubble";
    
    if (content) {
        bubble.innerHTML = renderMarkdown(content);
        enhanceCodeBlocks(bubble);
    }
    
    // Add attachments to UI
    attachments.forEach(file => {
        if (file.type.startsWith("image/")) {
            const img = document.createElement("img");
            img.src = file.url;
            img.onclick = () => window.open(file.url, "_blank");
            bubble.appendChild(img);
        } else {
            const link = document.createElement("a");
            link.href = file.url;
            link.target = "_blank";
            link.className = "file-attachment-link";
            link.innerHTML = `
                <span class="material-icons-round">insert_drive_file</span>
                <span>${file.name}</span>
            `;
            bubble.appendChild(link);
        }
    });

    group.querySelector(".message-content").appendChild(bubble);
    addTimestamp(group);
    chatHistory.appendChild(group);
    scrollToBottom();
}

function addAgentMessage(id, content, attachments = []) {
    activateChat();

    const group = createMessageGroup("agent");
    const bubble = document.createElement("div");
    bubble.className = "message-bubble";

    // Render markdown
    bubble.innerHTML = renderMarkdown(content);
    enhanceCodeBlocks(bubble);

    // Add attachments to UI
    attachments.forEach(file => {
        if (file.type && file.type.startsWith("image/")) {
            const img = document.createElement("img");
            img.src = file.url;
            img.onclick = () => window.open(file.url, "_blank");
            bubble.appendChild(img);
        } else {
            const link = document.createElement("a");
            link.href = file.url;
            link.target = "_blank";
            link.className = "file-attachment-link";
            link.innerHTML = `
                <span class="material-icons-round">insert_drive_file</span>
                <span>${file.name || "attachment"}</span>
            `;
            bubble.appendChild(link);
        }
    });

    group.querySelector(".message-content").appendChild(bubble);
    addTimestamp(group);
    chatHistory.appendChild(group);
    scrollToBottom();
}

// ── Process Groups (collapsible thinking/tool steps) ──────────
function addProcessStep(msgId, content, badge) {
    activateChat();

    let pg = state.processGroups[msgId];
    if (!pg) {
        // Create process group container
        const container = document.createElement("div");
        container.id = `pg-${msgId}`;
        container.className = "process-group expanded";

        const header = document.createElement("div");
        header.className = "process-group-header";
        header.onclick = () => toggleProcessGroup(msgId);
        header.innerHTML = `
            <span class="pg-expand-icon"></span>
            <span class="pg-title">Processing...</span>
            <span class="step-badge ${badge}">${badge}</span>
            <span class="pg-metrics">
                <span class="material-icons-round" style="font-size:13px">schedule</span>
                <span class="pg-time">0s</span>
                <span class="material-icons-round" style="font-size:13px;margin-left:8px">footprint</span>
                <span class="pg-count">0</span>
            </span>
        `;
        container.appendChild(header);

        const stepsContainer = document.createElement("div");
        stepsContainer.className = "pg-content";
        container.appendChild(stepsContainer);

        chatHistory.appendChild(container);

        pg = {
            el: container,
            stepsEl: stepsContainer,
            headerEl: header,
            startTime: Date.now(),
            stepCount: 0,
            genCount: 0,
            exeCount: 0,
            collapsed: false,
            timer: setInterval(() => updateProcessGroupTime(msgId), 1000),
        };
        state.processGroups[msgId] = pg;
    }

    pg.stepCount++;
    pg.headerEl.querySelector(".pg-count").textContent = pg.stepCount;
    if (badge === "GEN") pg.genCount++;
    else if (badge === "EXE") pg.exeCount++;

    // Update the main badge to the latest step type
    const badgeEl = pg.headerEl.querySelector(".step-badge");
    badgeEl.className = `step-badge ${badge}`;
    badgeEl.textContent = badge;

    // Update title with latest step text
    const title = pg.headerEl.querySelector(".pg-title");
    title.textContent = truncate(content, 60);
    title.dataset.tooltip = content;
    title.classList.add("shiny-text");

    // Add the step row
    const step = document.createElement("div");
    step.className = "pg-step";
    step.innerHTML = `
        <span class="step-badge ${badge}">${badge}</span>
        <span class="pg-step-text">${escapeHtml(truncate(content, 200))}</span>
    `;
    step.querySelector(".pg-step-text").dataset.tooltip = content;

    pg.stepsEl.appendChild(step);
    scrollToBottom();
}

function updateProcessGroupTime(msgId) {
    const pg = state.processGroups[msgId];
    if (!pg) return;
    const elapsed = Math.round((Date.now() - pg.startTime) / 1000);
    const min = Math.floor(elapsed / 60);
    const sec = elapsed % 60;
    pg.headerEl.querySelector(".pg-time").textContent =
        min > 0 ? `${min}:${String(sec).padStart(2, "0")}` : `${sec}s`;
}

function collapseProcessGroup(msgId) {
    const pg = state.processGroups[msgId];
    if (!pg) return;
    clearInterval(pg.timer);

    // Finalize time
    updateProcessGroupTime(msgId);

    // Remove shiny animation from title
    const title = pg.headerEl.querySelector(".pg-title");
    title.classList.remove("shiny-text");

    // Mark as completed — collapse
    pg.el.classList.remove("expanded");
    pg.el.classList.add("completed");

    // Update badge to END
    const badgeEl = pg.headerEl.querySelector(".step-badge");
    badgeEl.className = "step-badge END";
    badgeEl.textContent = "END";

    // Add summary (e.g. "1 thinking · 2 tool") to match history style
    const summaryParts = [];
    if (pg.genCount > 0) summaryParts.push(`${pg.genCount} thinking`);
    if (pg.exeCount > 0) summaryParts.push(`${pg.exeCount} tool`);
    if (summaryParts.length > 0) {
        let summaryEl = pg.headerEl.querySelector(".pg-summary");
        if (!summaryEl) {
            summaryEl = document.createElement("span");
            summaryEl.className = "pg-summary";
            pg.headerEl.querySelector(".pg-metrics").appendChild(summaryEl);
        }
        summaryEl.textContent = summaryParts.join(" · ");
    }

    pg.collapsed = true;
}

function toggleProcessGroup(msgId) {
    const pg = state.processGroups[msgId];
    if (!pg) return;
    pg.el.classList.toggle("expanded");
}

// Render a static (already-completed) process group from session history
function renderProcessGroupFromHistory(turnId, steps) {
    const id = `hist-${turnId}`;
    const container = document.createElement("div");
    container.className = "process-group completed";
    container.id = `pg-${id}`;

    const header = document.createElement("div");
    header.className = "process-group-header";
    header.onclick = () => {
        container.classList.toggle("expanded");
    };

    const lastStep = steps[steps.length - 1];
    const genCount = steps.filter(s => s.badge === "GEN").length;
    const exeCount = steps.filter(s => s.badge === "EXE").length;
    const summaryParts = [];
    if (genCount > 0) summaryParts.push(`${genCount} thinking`);
    if (exeCount > 0) summaryParts.push(`${exeCount} tool`);

    header.innerHTML = `
        <span class="pg-expand-icon"></span>
        <span class="pg-title">${escapeHtml(truncate(lastStep.text, 60))}</span>
        <span class="step-badge END">END</span>
        <span class="pg-metrics">
            <span class="material-icons-round" style="font-size:13px">footprint</span>
            <span class="pg-count">${steps.length}</span>
            <span class="pg-summary">${summaryParts.join(" · ")}</span>
        </span>
    `;
    container.appendChild(header);
    header.querySelector(".pg-title").dataset.tooltip = lastStep.text;

    const stepsContainer = document.createElement("div");
    stepsContainer.className = "pg-content";
    for (const step of steps) {
        const row = document.createElement("div");
        row.className = "pg-step";
        row.innerHTML = `
            <span class="step-badge ${step.badge}">${step.badge}</span>
            <span class="pg-step-text">${escapeHtml(truncate(step.text, 200))}</span>
        `;
        row.querySelector(".pg-step-text").dataset.tooltip = step.text;
        stepsContainer.appendChild(row);
    }
    container.appendChild(stepsContainer);
    chatHistory.appendChild(container);
}

function createMessageGroup(type) {
    state.messageCount++;
    const group = document.createElement("div");
    group.className = `message-group ${type}`;

    const avatar = document.createElement("div");
    avatar.className = "message-avatar";
    if (type === "user") {
        // No user avatar icon, only ShibaClaw agent avatar remains.
        avatar.style.display = "none";
    } else {
        const img = document.createElement("img");
        img.src = "/static/shibaclaw_logo.png";
        img.alt = "ShibaClaw";
        avatar.appendChild(img);
    }
    group.appendChild(avatar);

    const prev = chatHistory ? chatHistory.lastElementChild : null;
    const prevIsProcessGroup = prev && prev.classList.contains("process-group");
    const prevGroup = prevIsProcessGroup ? chatHistory.children[chatHistory.children.length - 2] : prev;
    const sameType = prevGroup && prevGroup.classList.contains("message-group") && prevGroup.classList.contains(type);
    if (!sameType) group.classList.add("show-avatar");

    const content = document.createElement("div");
    content.className = "message-content";
    group.appendChild(content);

    return group;
}

function addTimestamp(group, dateStr) {
    const time = document.createElement("div");
    time.className = "message-time";
    const d = dateStr ? new Date(dateStr) : new Date();
    time.textContent = d.toLocaleTimeString([], {
        hour: "2-digit",
        minute: "2-digit",
    });
    group.querySelector(".message-content").appendChild(time);
}

// ── Markdown Rendering ────────────────────────────────────────
function renderMarkdown(text) {
    if (!text) return "";
    
    let content = text;

    // If it's a string, try to see if it's actually stringified JSON (common in history persistence)
    if (typeof content === "string" && content.trim().startsWith("[") && content.trim().endsWith("]")) {
        try {
            const parsed = JSON.parse(content);
            if (Array.isArray(parsed)) content = parsed;
        } catch (e) { /* not JSON, continue with original string */ }
    }

    // If content is an array of blocks (either originally or after parsing), extract the text
    if (Array.isArray(content)) {
        content = content
            .filter(block => block && block.type === "text")
            .map(block => block.text)
            .join("\n");
    }

    // Cleanup redundant internal technical tags like [image: /path/to/...]
    if (typeof content === "string") {
        content = content.replace(/\[image:\s*[^\]]+\]/gi, "").trim();
    }

    if (typeof marked !== "undefined") {
        try {
            return marked.parse(content);
        } catch (e) {
            console.error("Markdown parse error:", e);
        }
    }
    return escapeHtml(content).replace(/\n/g, "<br>");
}

function enhanceCodeBlocks(container) {
    container.querySelectorAll("pre").forEach((pre) => {
        const code = pre.querySelector("code");
        if (!code) return;

        // Detect language
        const langClass = [...code.classList].find((c) => c.startsWith("language-"));
        const lang = langClass ? langClass.replace("language-", "") : "";

        // Highlight if not already done
        if (typeof hljs !== "undefined" && !code.classList.contains("hljs")) {
            if (lang && hljs.getLanguage(lang)) {
                code.innerHTML = hljs.highlight(code.textContent, { language: lang }).value;
            } else {
                hljs.highlightElement(code);
            }
        }

        // Add header with language label and copy button
        if (!pre.querySelector(".code-block-header")) {
            const header = document.createElement("div");
            header.className = "code-block-header";
            header.innerHTML = `
                <span>${lang || "code"}</span>
                <button class="btn-copy-code" onclick="copyCode(this)">Copy</button>
            `;
            pre.insertBefore(header, pre.firstChild);
        }
    });
}

// ── Modals & APIs ─────────────────────────────────────────────
async function fetchStatus() {
    try {
        const res = await authFetch("/api/status?_t=" + Date.now());
        let oauthConfigured = false;
        // Check OAuth providers
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

            // Update sidebar version display
            const versionEl = $("sidebar-version");
            if (versionEl && data.version) versionEl.textContent = "v" + data.version;

            // This prevents the UI from flipping back to "Gateway Down" 
            // after the backend just told us we are ready.
            if (data.agent_configured || oauthConfigured) {
                state.gatewayUp = true;
                state.gatewayUnreachableCount = 0;
            }

            if ((data.agent_configured || oauthConfigured) && state.socket && state.socket.connected) {
                if (!state.processing) {
                    // Only say ready if the gateway is also up (or we are on bare metal where they are the same)
                    // If we just got a config success, we should check health soon
                    if (state.gatewayUp || state.agentConfigured) {
                        setStatusIndicator("ready");
                    } else {
                        setStatusIndicator("gateway-down");
                    }
                }
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
    const wasGatewayUp = state.gatewayUp;
    let reachable = false;

    try {
        const res = await authFetch("/api/gateway-health?_t=" + Date.now());
        const data = await res.json();
        reachable = data.reachable === true;
        state.gatewayProviderReady = data.provider_ready !== false;
    } catch(e) {
        reachable = false;
        state.gatewayProviderReady = true;
    }

    // Important: if we're disconnected from WebUI server, that takes priority
    if (!state.socket || !state.socket.connected) {
        state.gatewayUp = false; // assumed down if we can't even talk to our backend
        state.gatewayUnreachableCount = 2;
        if (!state.processing) setStatusIndicator("disconnected");
        return;
    }

    if (reachable) {
        state.gatewayUnreachableCount = 0;
        state.gatewayUp = true;
    } else {
        // Se l'agente è configurato, aumentiamo la tolleranza (10 errori)
        const maxFailures = state.agentConfigured ? 10 : 3;
        state.gatewayUnreachableCount = Math.min(maxFailures, state.gatewayUnreachableCount + 1);
        if (state.gatewayUnreachableCount >= maxFailures) {
            state.gatewayUp = false;
        }
    }

    if (!state.processing) {
        if (!state.gatewayUp) {
            // Mostra "Gateway Down" solo dopo aver raggiunto la nuova soglia
            const maxFailures = state.agentConfigured ? 10 : 3;
            if (state.gatewayUnreachableCount >= maxFailures) {
                setStatusIndicator("gateway-down");
            }
        } else {
            // Gateway is up — check if provider is ready
            if (state.gatewayProviderReady === false) {
                setStatusIndicator("model-offline");
            } else if (statusText.textContent === "Gateway Down" || statusText.textContent === "Model Offline") {
                // Restoration check
                fetchStatus();
            } else if (statusText.textContent === "Shiba ready") {
                // stable
            } else if (statusText.textContent !== "Working...") {
                fetchStatus();
            }
        }
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
        // Restore based on actual state
        if (!state.socket || !state.socket.connected) {
            setStatusIndicator("disconnected");
        } else if (!state.gatewayUp && !state.agentConfigured) {
            setStatusIndicator("gateway-down");
        } else {
            setStatusIndicator("ready");
        }
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

        // Poll until gateway comes back (up to 30s)
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

// Track collapsed state across reloads
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

    // Bind events programmatically to avoid JS injection via session names/keys
    // (escapeHtml does not escape quotes, so inline onclick with string literals is unsafe)
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

/* ── Automation: Cron & Heartbeat ───────────────────────────── */

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
    
    // Close all other dropdowns
    document.querySelectorAll(".session-dropdown").forEach(d => d.classList.remove("active"));
    document.querySelectorAll(".btn-session-menu").forEach(b => b.classList.remove("active"));
    
    if (!isActive && dropdown) {
        dropdown.classList.add("active");
        btn.classList.add("active");
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
            // Update the header immediately if we renamed the active session
            if (key === state.sessionId) {
                sessionIdEl.textContent = nickname || key;
            }
            await loadHistory();
        }
    } catch(e) { console.error("Rename error:", e); }
}

// ── Auto-title: generate nickname from first user message ─────
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

// ── Custom dialog logic ──────────────────────────────────────
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

// ── Instant-remove helper ─────────────────────────────────
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

// Close dropdowns on outside click
document.addEventListener("click", () => {
    document.querySelectorAll(".session-dropdown").forEach(d => d.classList.remove("active"));
    document.querySelectorAll(".btn-session-menu").forEach(b => b.classList.remove("active"));
});

async function loadSession(sessionId) {
    if (state.processing) {
        console.debug("[SHIBA] loadSession skipped — processing in progress");
        return;
    }
    state.sessionId = sessionId;
    localStorage.setItem("shiba_session_id", sessionId);

    // Notify the server so future messages are stored in the correct session.
    if (state.socket && state.socket.connected) {
        state.socket.emit("switch_session", { session_id: sessionId });
    }
    
    // Select in sidebar (use data-session-key for reliability)
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
            // fallback: mark by text if data attribute missing
            if (el.textContent && el.textContent.includes(sessionId)) el.classList.add("active");
        }
    }

    try {
        const res = await authFetch(`/api/sessions/${encodeURIComponent(sessionId)}`);
        const data = await res.json();
        console.debug("[SHIBA] loadSession:", sessionId, "messages:", data.messages?.length || 0);
        
        // Show nickname in header if available
        sessionIdEl.textContent = data.nickname || sessionId;
        
        chatHistory.innerHTML = "";
        state.messageCount = 0;
        // Clear any old process group timers before resetting
        Object.values(state.processGroups).forEach(pg => {
            if (pg && pg.timer) clearInterval(pg.timer);
        });
        state.processGroups = {};
        
        const messages = Array.isArray(data.messages) ? data.messages : [];
        if (messages.length > 0) {
            activateChat();

            // Refresh context/token badge for this session
            try { refreshTokenBadge(); } catch(e) { /* ignore */ }

            // Group messages into turns: each user msg starts a new turn
            // Process groups are built from reasoning + tool_calls within a turn
            let turnSteps = [];
            let turnId = 0;
            let pgCount = 0;

            let lastUserContent = null;

            for (const msg of messages) {
                if (!msg || !msg.role) continue;
                if (msg.role === "user") {
                    // Skip duplicate consecutive user messages
                    if (!msg.content || msg.content === lastUserContent) continue;
                    lastUserContent = msg.content;

                    // Flush any pending process group from previous turn
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

                    // Render attachments in history if present
                    const attachments = msg.metadata?.attachments || [];
                    attachments.forEach(file => {
                        if (file.type && file.type.startsWith("image/")) {
                            const img = document.createElement("img");
                            img.src = file.url;
                            img.onclick = () => window.open(file.url, "_blank");
                            bubble.appendChild(img);
                        } else {
                            const link = document.createElement("a");
                            link.href = file.url;
                            link.target = "_blank";
                            link.className = "file-attachment-link";
                            link.innerHTML = `
                                <span class="material-icons-round">insert_drive_file</span>
                                <span>${file.name || "attachment"}</span>
                            `;
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

                    // Collect reasoning as GEN step
                    if (hasReasoning) {
                        const preview = (msg.reasoning_content?.slice?.(0, 120)) || "";
                        turnSteps.push({ badge: "GEN", text: preview });
                    }
                    // Collect tool calls as EXE steps (include args preview like live rendering)
                    if (hasTc) {
                        for (const tc of msg.tool_calls) {
                            const fn = tc.function?.name || "tool";
                            let args = "";
                            try {
                                const raw = tc.function?.arguments;
                                if (raw) {
                                    const parsed = typeof raw === "string" ? JSON.parse(raw) : raw;
                                    // Build a preview like: exec("cd /root/... && npx ...")
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

                    // Final content with NO tool calls = final reply → flush & render
                    if (hasContent && !hasTc) {
                        // Only render process group if it has EXE steps (actual tool use)
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

                        // Render agent attachments in history
                        const attachments = msg.metadata?.attachments || [];
                        attachments.forEach(file => {
                            if (file.type && file.type.startsWith("image/")) {
                                const img = document.createElement("img");
                                img.src = file.url;
                                img.onclick = () => window.open(file.url, "_blank");
                                bubble.appendChild(img);
                            } else {
                                const link = document.createElement("a");
                                link.href = file.url;
                                link.target = "_blank";
                                link.className = "file-attachment-link";
                                link.innerHTML = `
                                    <span class="material-icons-round">insert_drive_file</span>
                                    <span>${file.name || "attachment"}</span>
                                `;
                                bubble.appendChild(link);
                            }
                        });

                        group.querySelector(".message-content").appendChild(bubble);
                        if (msg.timestamp) addTimestamp(group, msg.timestamp);
                        chatHistory.appendChild(group);
                    }
                    // If has tool_calls, content is just preamble — skip rendering it as a message

                } else if (msg.role === "tool") {
                    // Tool results are already represented by their tool_call — skip adding extra steps
                }
            }
            // Flush remaining steps (agent still working — only if there are tool steps)
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
    }
}

// Global modal triggers
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
            switchSettingsTab("agent");
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
    document.querySelectorAll(".settings-tab").forEach(t => t.classList.remove("active"));
    const tabEl = document.querySelector(`.settings-tab[data-tab="${tab}"]`);
    if (tabEl) tabEl.classList.add("active");
    document.querySelectorAll(".settings-panel").forEach(p => p.style.display = "none");
    const panel = $("panel-" + tab);
    if (panel) panel.style.display = "block";
    if (tab === "oauth") loadOAuthPanel();
    if (tab === "update") loadUpdatePanel();
};

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

        // Login — triggers device flow and shows code + URL
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

                // If we got user_code + verification_uri back (GitHub Copilot), show them immediately
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
                                // OpenAI Codex: show URL + paste input
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
                                // Wire up submit button
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

    // Auto-load status (lightweight, no login trigger)
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

function populateSettings(cfg) {
        // Salva una copia del config attuale per confronto dopo il salvataggio
        lastSettingsConfig = JSON.parse(JSON.stringify(cfg));
    const d = cfg.agents?.defaults || {};
    $("s-agent-provider").value = d.provider || "";
    $("s-agent-model").value = d.model || "";
    $("s-agent-temp").value = d.temperature ?? 0.1;
    $("s-agent-maxTokens").value = d.maxTokens ?? 8192;
    $("s-agent-ctxTokens").value = d.contextWindowTokens ?? 65536;
    $("s-agent-maxIter").value = d.maxToolIterations ?? 40;
    $("s-agent-workspace").value = d.workspace || "~/.shibaclaw/workspace";
    $("s-agent-reasoning").value = d.reasoningEffort || "";

    // Providers — collapsible accordion cards
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

    // Tools
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

    // Gateway
    const gw = cfg.gateway || {};
    $("s-gw-host").value = gw.host || "127.0.0.1";
    $("s-gw-port").value = gw.port ?? 19999;
    const hb = gw.heartbeat || {};
    $("s-gw-hbEnabled").checked = hb.enabled !== false;
    $("s-gw-hbInterval").value = hb.intervalS ?? 1800;

    // Channels
    const ch = cfg.channels || {};
    $("s-ch-sendProgress").checked = ch.sendProgress !== false;
    $("s-ch-sendToolHints").checked = !!ch.sendToolHints;

    // Build channel accordion cards
    const detail = $("channels-detail");
    detail.innerHTML = "";
    const skip = ["sendProgress", "sendToolHints"];

    // Email field configuration with human-readable labels and sections
    const EMAIL_FIELD_CONFIG = {
        // INBOUND (IMAP)
        imapHost:       { label: "IMAP Server",       section: "inbound",  type: "text",     placeholder: "imap.gmail.com" },
        imapPort:       { label: "IMAP Port",          section: "inbound",  type: "number",   placeholder: "993" },
        imapUsername:   { label: "IMAP Username",      section: "inbound",  type: "text",     placeholder: "email@gmail.com" },
        imapPassword:   { label: "IMAP Password",      section: "inbound",  type: "password", placeholder: "App password" },
        imapUseSsl:     { label: "IMAP SSL",           section: "inbound",  type: "boolean" },
        imapMailbox:    { label: "IMAP Mailbox",       section: "inbound",  type: "text",     placeholder: "INBOX" },
        // OUTBOUND (SMTP)
        smtpHost:       { label: "SMTP Server",        section: "outbound", type: "text",     placeholder: "smtp.gmail.com" },
        smtpPort:       { label: "SMTP Port",          section: "outbound", type: "number",   placeholder: "587" },
        smtpUsername:   { label: "SMTP Username",      section: "outbound", type: "text",     placeholder: "email@gmail.com" },
        smtpPassword:   { label: "SMTP Password",      section: "outbound", type: "password", placeholder: "App password" },
        smtpUseTls:     { label: "SMTP STARTTLS",      section: "outbound", type: "boolean" },
        smtpUseSsl:     { label: "SMTP SSL",           section: "outbound", type: "boolean" },
        fromAddress:    { label: "From Address",       section: "outbound", type: "text",     placeholder: "shibaclaw@gmail.com" },
        // GENERAL
        autoReplyEnabled:       { label: "Auto Reply",           section: "general", type: "boolean" },
        pollIntervalSeconds:    { label: "Poll Interval (sec)",  section: "general", type: "number",  placeholder: "30" },
        markSeen:               { label: "Mark as Read",         section: "general", type: "boolean" },
        maxBodyChars:           { label: "Max Body Length",      section: "general", type: "number",  placeholder: "12000" },
        subjectPrefix:          { label: "Reply Prefix",         section: "general", type: "text",    placeholder: "Re: " },
        allowFrom:              { label: "Allowed Senders",      section: "general", type: "array",   placeholder: "email1@test.com, email2@test.com" },
    };

    function formatEmailFields(fieldsHtml, config, cc) {
        const sections = { inbound: [], outbound: [], general: [] };
        
        for (const [key, val] of Object.entries(cc)) {
            if (key === "enabled") continue;
            
            let valStr = "";
            let originalType = typeof val;
            if (Array.isArray(val)) {
                originalType = "array";
                valStr = val.join(", ");
            } else if (val !== null && originalType === "object") {
                originalType = "object";
                valStr = JSON.stringify(val);
            } else {
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
        return fieldsHtml;
    }

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
            <div class="field-row">
                <label>Consent Granted</label>
                <label class="toggle"><input type="checkbox" class="ch-field" data-ch="${name}" data-key="consentGranted" data-type="boolean" ${(cc.consentGranted || cc.consent_granted) ? "checked" : ""}><span class="toggle-slider"></span></label>
            </div>
        `;

        // Use custom layout for email channel
        if (name === "email" && EMAIL_FIELD_CONFIG) {
            // Group fields by section
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
            
            // Build sections HTML
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
            // Generic fallback for other channels
            for (const [key, val] of Object.entries(cc)) {
                if (key === "enabled") continue;
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
}

window.saveSettings = async function() {
    // Rebuild the config from form fields
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
        }
    };

    // Collect provider fields
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

    // Collect channel enabled toggles and other dynamically generated fields
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

        // Mostra sempre il popup di restart dopo aver salvato i settings
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

// ── Typing Bubble (shown while agent is working, before any event) ──
function showTypingBubble() {
    if (document.getElementById("typing-bubble")) return; // prevent duplicates
    activateChat();
    const group = createMessageGroup("agent");
    group.id = "typing-bubble";
    group.innerHTML = group.innerHTML; // keep avatar
    const content = group.querySelector(".message-content");
    const bubble = document.createElement("div");
    bubble.className = "message-bubble typing-bubble";
    bubble.innerHTML = `
        <div class="typing-dots-inline">
            <span></span><span></span><span></span>
        </div>`;
    content.appendChild(bubble);
    chatHistory.appendChild(group);
    scrollToBottom();
}

function hideTypingBubble() {
    const el = document.getElementById("typing-bubble");
    if (el) el.remove();
}

function scrollToBottom() {
    requestAnimationFrame(() => {
        chatHistory.scrollTop = chatHistory.scrollHeight;
    });
}

function updateSendButton() {
    const hasText = chatInput.value.trim().length > 0;
    btnSend.disabled = !hasText || state.processing;
}

function autoResizeInput() {
    chatInput.style.height = "auto";
    chatInput.style.height = Math.min(chatInput.scrollHeight, 200) + "px";
}

// ── Utility Functions ─────────────────────────────────────────
function escapeHtml(str) {
    const div = document.createElement("div");
    div.textContent = str;
    return div.innerHTML;
}

function truncate(str, maxLen) {
    if (!str) return "";
    return str.length > maxLen ? str.slice(0, maxLen) + "…" : str;
}

function fmtTokens(n) {
    if (n >= 1000) return (n / 1000).toFixed(1).replace(/\.0$/, "") + "k";
    return String(n);
}

function usageTier(pct) {
    if (pct < 40) return "low";
    if (pct < 70) return "mid";
    if (pct < 90) return "high";
    return "crit";
}

function usageColor(pct) {
    if (pct < 40) return "#4ade80";
    if (pct < 70) return "var(--shiba-gold)";
    if (pct < 90) return "#f97316";
    return "#ef4444";
}

function buildTokenCard(t) {
    const pct = t.usage_pct || 0;
    const tier = usageTier(pct);
    return `
    <div class="context-token-card">
        <h3>📊 Token Estimate</h3>
        <table class="context-token-table">
            <tr><td>System Prompt</td><td>~${(t.system_prompt || 0).toLocaleString()}</td></tr>
            <tr><td>Tool definitions</td><td>~${(t.tools || 0).toLocaleString()}</td></tr>
            <tr><td>Session messages</td><td>~${(t.messages || 0).toLocaleString()}</td></tr>
            <tr class="total"><td>Total</td><td>~${(t.total || 0).toLocaleString()}</td></tr>
        </table>
        ${t.context_window > 0 ? `
        <div class="context-usage-bar">
            <div class="context-usage-fill" style="width:${pct}%; background:${usageColor(pct)};"></div>
        </div>
        <div class="context-usage-label">
            <span>${fmtTokens(t.total)} / ${fmtTokens(t.context_window)}</span>
            <span style="color:${usageColor(pct)}">${pct}%</span>
        </div>` : ""}
    </div>`;
}

function updateTokenBadge(t) {
    const badge = $("token-badge");
    const text = $("token-badge-text");
    if (!badge || !text || !t) return;
    const pct = t.usage_pct ?? 0;
    const tier = usageTier(pct);
    badge.className = "token-badge usage-" + tier;
    text.textContent = `${fmtTokens(t.total ?? 0)} / ${fmtTokens(t.context_window ?? 0)} · ${pct}%`;
}

// Auto-refresh token badge on page load and after messages
async function refreshTokenBadge() {
    if (!state.sessionId) return;
    try {
        const res = await authFetch(`/api/context?session_id=${encodeURIComponent(state.sessionId)}&summary=1`);
        if (!res.ok) return;
        const data = await res.json();
        if (data.tokens) updateTokenBadge(data.tokens);
    } catch(e) { /* silent */ }
}

// ── Global Functions (called from HTML) ───────────────────────
window.copyCode = function (btn) {
    const pre = btn.closest("pre");
    const code = pre.querySelector("code");
    if (code) {
        navigator.clipboard.writeText(code.textContent).then(() => {
            btn.textContent = "Copied!";
            setTimeout(() => (btn.textContent = "Copy"), 2000);
        });
    }
};

// ── Send Message ─────────────────────────────────────────────
function sendMessage() {
    const content = chatInput.value.trim();
    if ((!content && state.stagedFiles.length === 0) || state.processing) return;

    state.processing = true;
    updateSendButton();

    try {
        const attachments = [...state.stagedFiles];
        addUserMessage(content, attachments);
        
        state.socket.emit("user_message", { 
            content,
            attachments: attachments.map(a => ({
                name: a.name,
                url: a.url,
                type: a.type
            }))
        });

        // Clear input and staging
        chatInput.value = "";
        state.stagedFiles = [];
        updateStagingUI();
        autoResizeInput();
    } catch(e) {
        console.error("Send error:", e);
        state.processing = false;
        updateSendButton();
    }
}

// ── File Handling ─────────────────────────────────────────────
function initFileHandlers() {
    const btnAttach = $("btn-attach");
    const fileInput = $("file-input");
    const dragOverlay = $("drag-overlay");

    console.debug("[SHIBA] Initializing file handlers", { btnAttach: !!btnAttach, fileInput: !!fileInput });
    if (btnAttach && fileInput) {
        btnAttach.onclick = () => fileInput.click();
        fileInput.onchange = (e) => {
            handleFileUpload(e.target.files);
            fileInput.value = ""; // reset
        };
    }

    // Drag and Drop
    window.addEventListener("dragover", (e) => {
        e.preventDefault();
        dragOverlay.classList.add("active");
    });

    window.addEventListener("dragleave", (e) => {
        if (e.relatedTarget === null || !dragOverlay.contains(e.relatedTarget)) {
            dragOverlay.classList.remove("active");
        }
    });

    window.addEventListener("drop", (e) => {
        e.preventDefault();
        dragOverlay.classList.remove("active");
        handleFileUpload(e.dataTransfer.files);
    });

    // Paste from clipboard
    window.addEventListener("paste", (e) => {
        const items = e.clipboardData.items;
        const files = [];
        for (let item of items) {
            if (item.kind === "file") {
                files.push(item.getAsFile());
            }
        }
        console.debug("[SHIBA] Paste event", { count: files.length });
        if (files.length > 0) handleFileUpload(files);
    });
}

async function handleFileUpload(files) {
    console.debug("[SHIBA] handleFileUpload", files);
    if (!files || files.length === 0) return;

    for (const file of files) {
        const formData = new FormData();
        formData.append("file", file);

        try {
            const res = await authFetch("/api/upload", {
                method: "POST",
                body: formData
            });

            if (res.ok) {
                const data = await res.json();
                const uploadedFile = data.files[0];
                state.stagedFiles.push({
                    name: uploadedFile.filename,
                    url: uploadedFile.url,
                    type: file.type,
                    stagedAt: Date.now()
                });
                updateStagingUI();
            } else {
                const err = await res.json();
                shibaDialog("alert", "Upload Failed", `Could not upload ${file.name}: ${err.error}`, { danger: true });
            }
        } catch (e) {
            console.error("Upload error:", e);
        }
    }
}

function updateStagingUI() {
    const container = $("attachment-staging");
    if (!container) return;

    container.innerHTML = "";
    if (state.stagedFiles.length === 0) {
        container.style.display = "none";
        return;
    }

    container.style.display = "flex";
    state.stagedFiles.forEach((file, idx) => {
        const item = document.createElement("div");
        item.className = "staged-file";
        
        let thumb = `<span class="material-icons-round">insert_drive_file</span>`;
        if (file.type.startsWith("image/")) {
            thumb = `<img src="${file.url}" class="staged-file-thumb">`;
        }

        item.innerHTML = `
            ${thumb}
            <span class="staged-file-name" title="${file.name}">${file.name}</span>
            <button class="btn-remove-staged" onclick="removeStagedFile(${idx})">
                <span class="material-icons-round">close</span>
            </button>
        `;
        container.appendChild(item);
    });
}

window.removeStagedFile = function(idx) {
    state.stagedFiles.splice(idx, 1);
    updateStagingUI();
};

// ── File Explorer ─────────────────────────────────────────────
window.loadFs = async function(path = ".") {
    const list = $("fs-content");
    const breadcrumb = $("fs-breadcrumb");
    if (!list) return;

    state.currentFsPath = path;
    list.innerHTML = `<div style="padding:2rem;text-align:center;color:var(--text-muted)">
        <span class="material-icons-round spin">progress_activity</span>
    </div>`;

    // Render breadcrumb
    const parts = path.split(/[/\\]/).filter(p => p && p !== ".");
    let bcHtml = `<span class="breadcrumb-item" onclick="loadFs('.')">root</span>`;
    let currentPartPath = "";
    parts.forEach((p, i) => {
        currentPartPath += (i === 0 ? "" : "/") + p;
        bcHtml += ` <span class="material-icons-round" style="font-size:12px">chevron_right</span> `;
        bcHtml += `<span class="breadcrumb-item" onclick="loadFs('${currentPartPath.replace(/'/g, "\\'")}')">${p}</span>`;
    });
    breadcrumb.innerHTML = bcHtml;

    try {
        const res = await authFetch(`/api/fs/explore?path=${encodeURIComponent(path)}`);
        const data = await res.json();

        if (data.error) {
            list.innerHTML = `<div style="padding:2rem;color:var(--accent-red)">${data.error}</div>`;
            return;
        }

        list.innerHTML = "";
        
        // Parent directory link
        if (path !== "." && path !== "/" && parts.length > 0) {
            const parentPath = parts.slice(0, -1).join("/") || ".";
            const row = document.createElement("div");
            row.className = "fs-item";
            row.onclick = () => loadFs(parentPath);
            row.innerHTML = `
                <span class="material-icons-round fs-item-icon">folder_open</span>
                <span class="fs-item-name">..</span>
                <span></span><span></span>
            `;
            list.appendChild(row);
        }

        data.items.forEach(f => {
            const row = document.createElement("div");
            row.className = `fs-item ${f.is_dir ? "is-dir" : ""}`;
            
            const icon = f.is_dir ? "folder" : "insert_drive_file";
            const size = f.is_dir ? "" : formatSize(f.size);
            const mtime = new Date(f.mtime * 1000).toLocaleString();

            row.onclick = () => {
                if (f.is_dir) {
                    loadFs(f.path);
                } else {
                    openFileEditor(f.path, f.name);
                }
            };

            row.innerHTML = `
                <span class="material-icons-round fs-item-icon">${icon}</span>
                <span class="fs-item-name" title="${f.name}">${f.name}</span>
                <span class="fs-item-size">${size}</span>
                <span class="fs-item-mtime">${mtime}</span>
            `;
            list.appendChild(row);
        });

    } catch (e) {
        list.innerHTML = `<div style="padding:2rem;color:var(--accent-red)">Error loading files</div>`;
    }
};

function formatSize(bytes) {
    if (bytes === 0) return "0 B";
    const k = 1024;
    const sizes = ["B", "KB", "MB", "GB", "TB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + " " + sizes[i];
}

// ── File Editor ───────────────────────────────────────────────
const TEXT_EXTENSIONS = /\.(txt|md|py|js|ts|jsx|tsx|json|yaml|yml|toml|sh|bash|zsh|env|cfg|conf|ini|html|css|scss|xml|csv|log|rst|Dockerfile|gitignore|editorconfig|lock|sql|go|rs|rb|java|c|cpp|h|php)$/i;

window.openFileEditor = async function(filePath, fileName) {
    const content = $("fs-content");
    const breadcrumb = $("fs-breadcrumb");
    if (!content) return;

    content.innerHTML = `<div style="padding:2rem;text-align:center;color:var(--text-muted)">
        <span class="material-icons-round spin">progress_activity</span>
    </div>`;

    const parts = state.currentFsPath.split(/[\/\\]/).filter(p => p && p !== ".");
    let bcHtml = `<span class="breadcrumb-item" onclick="loadFs('.')">root</span>`;
    let cur = "";
    parts.forEach((p, i) => {
        cur += (i === 0 ? "" : "/") + p;
        const cp = cur;
        bcHtml += ` <span class="material-icons-round" style="font-size:12px">chevron_right</span> `;
        bcHtml += `<span class="breadcrumb-item" onclick="loadFs('${cp.replace(/'/g, "\\'")}')">${p}</span>`;
    });
    bcHtml += ` <span class="material-icons-round" style="font-size:12px">chevron_right</span> <span class="breadcrumb-item active">${fileName}</span>`;
    breadcrumb.innerHTML = bcHtml;

    const isText = TEXT_EXTENSIONS.test(fileName);
    if (!isText) {
        content.innerHTML = `<div style="padding:3rem;text-align:center;color:var(--text-muted)">
            <span class="material-icons-round" style="font-size:48px;display:block;margin-bottom:8px">insert_drive_file</span>
            <p>Binary file — preview not available</p>
        </div>`;
        return;
    }

    try {
        const res = await authFetch(`/api/file-get?path=${encodeURIComponent(filePath)}&_t=${Date.now()}`);
        if (!res.ok) {
            const err = await res.json().catch(() => ({ error: res.statusText }));
            content.innerHTML = `<div style="padding:2rem;color:var(--accent-red)">${err.error || "Error loading file"}</div>`;
            return;
        }
        const text = await res.text();

        content.innerHTML = `
            <div class="file-editor-toolbar">
                <span class="file-editor-name">${fileName}</span>
                <span id="save-status" class="file-editor-status"></span>
                <button class="btn-edit-mode" id="btn-refresh-file" title="Reload file from disk">
                    <span class="material-icons-round" style="font-size:15px">refresh</span>
                </button>
                <button class="btn-edit-mode" id="btn-download-file" title="Download file">
                    <span class="material-icons-round" style="font-size:15px">download</span>
                </button>
                <button class="btn-edit-mode" id="btn-edit-mode" title="Enter edit mode">
                    <span class="material-icons-round" style="font-size:15px">edit</span> Edit
                </button>
                <button class="btn-primary btn-sm" id="btn-save-file" style="display:none">
                    <span class="material-icons-round" style="font-size:14px">save</span> Save
                </button>
            </div>
            <textarea class="file-editor-area" id="file-editor-textarea" spellcheck="false" readonly></textarea>
        `;
        const ta = document.getElementById("file-editor-textarea");
        const btnEdit = document.getElementById("btn-edit-mode");
        const btnSave = document.getElementById("btn-save-file");
        const btnRefresh = document.getElementById("btn-refresh-file");
        const btnDownload = document.getElementById("btn-download-file");
        btnDownload.onclick = () => {
            const blob = new Blob([ta.value], { type: "text/plain;charset=utf-8" });
            const a = document.createElement("a");
            a.href = URL.createObjectURL(blob);
            a.download = fileName;
            a.click();
            URL.revokeObjectURL(a.href);
        };
        ta.value = text;
        btnRefresh.onclick = async () => {
            btnRefresh.disabled = true;
            // Reset to read-only view
            ta.setAttribute("readonly", "");
            btnEdit.classList.remove("active");
            btnEdit.innerHTML = `<span class="material-icons-round" style="font-size:15px">edit</span> Edit`;
            btnSave.style.display = "none";
            const ss = document.getElementById("save-status");
            if (ss) ss.textContent = "";
            try {
                const r = await authFetch(`/api/file-get?path=${encodeURIComponent(filePath)}&_t=${Date.now()}`);
                if (r.ok) ta.value = await r.text();
            } finally {
                btnRefresh.disabled = false;
            }
        };
        btnEdit.onclick = () => {
            const isEditing = !ta.hasAttribute("readonly");
            if (isEditing) {
                // back to read-only
                ta.setAttribute("readonly", "");
                btnEdit.classList.remove("active");
                btnEdit.innerHTML = `<span class="material-icons-round" style="font-size:15px">edit</span> Edit`;
                btnSave.style.display = "none";
            } else {
                ta.removeAttribute("readonly");
                ta.focus();
                btnEdit.classList.add("active");
                btnEdit.innerHTML = `<span class="material-icons-round" style="font-size:15px">visibility</span> View`;
                btnSave.style.display = "";
            }
        };
        btnSave.onclick = () => saveFile(filePath);
    } catch (e) {
        content.innerHTML = `<div style="padding:2rem;color:var(--accent-red)">Error: ${e.message}</div>`;
    }
};

window.saveFile = async function(filePath) {
    const textarea = document.getElementById("file-editor-textarea");
    const status = $("save-status");
    if (!textarea || !status) return;
    const btn = $("btn-save-file");
    if (btn) btn.disabled = true;
    status.textContent = "Saving\u2026";
    status.style.color = "";

    const body = { path: filePath, content: textarea.value };

    try {
        const res = await authFetch("/api/file-save", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body)
        });
        const data = await res.json().catch(() => ({}));
        if (!res.ok) {
            throw new Error(data.error || `Server error ${res.status}`);
        }
        if (data.error) throw new Error(data.error);
        status.style.color = "";
        status.textContent = `Saved! (${data.bytes ?? "?"} bytes \u2192 ${data.path ?? filePath})`;
        setTimeout(() => { status.textContent = ""; }, 4000);
    } catch (e) {
        console.error("[file-save] error", e);
        status.style.color = "var(--accent-red, #f38ba8)";
        status.textContent = "\u274c " + e.message;
    } finally {
        if (btn) btn.disabled = false;
    }
};

(function initChatWidth() {
    const STORAGE_KEY = "shibaclaw_chat_width";
    const DEFAULT = 860;
    const root = document.documentElement;

    const saved = parseInt(localStorage.getItem(STORAGE_KEY)) || DEFAULT;
    root.style.setProperty("--chat-width", saved + "px");

    function applyWidth(px) {
        root.style.setProperty("--chat-width", px + "px");
        document.querySelectorAll(".width-preset").forEach(btn => {
            btn.classList.toggle("active", parseInt(btn.dataset.width) === px);
        });
        localStorage.setItem(STORAGE_KEY, px);
    }

    document.addEventListener("DOMContentLoaded", () => {
        const toggleBtn = document.getElementById("btn-width-toggle");
        const popover   = document.getElementById("width-popover");

        applyWidth(saved);

        toggleBtn.addEventListener("click", (e) => {
            e.stopPropagation();
            popover.classList.toggle("open");
        });
        document.addEventListener("click", (e) => {
            if (!toggleBtn.contains(e.target) && !popover.contains(e.target)) {
                popover.classList.remove("open");
            }
        });
        document.querySelectorAll(".width-preset").forEach(btn => {
            btn.addEventListener("click", () => {
                applyWidth(parseInt(btn.dataset.width));
            });
        });
    });
})();

// ── Event Listeners ───────────────────────────────────────────
function initListeners() {
    chatHistory.addEventListener("mouseover", (e) => {
        const target = e.target.closest(".pg-step-text[data-tooltip], .pg-title[data-tooltip]");
        if (!target || !chatHistory.contains(target)) return;

        processTooltip.textContent = target.dataset.tooltip || "";
        processTooltip.hidden = false;

        const rect = target.getBoundingClientRect();
        const tooltipRect = processTooltip.getBoundingClientRect();
        let left = rect.left;
        let top = rect.bottom + 8;

        if (left + tooltipRect.width > window.innerWidth - 12) {
            left = window.innerWidth - tooltipRect.width - 12;
        }
        if (left < 12) {
            left = 12;
        }
        if (top + tooltipRect.height > window.innerHeight - 12) {
            top = rect.top - tooltipRect.height - 8;
        }
        if (top < 12) {
            top = 12;
        }

        processTooltip.style.left = `${left}px`;
        processTooltip.style.top = `${top}px`;
    });

    chatHistory.addEventListener("mouseout", (e) => {
        const target = e.target.closest(".pg-step-text[data-tooltip], .pg-title[data-tooltip]");
        if (!target || !chatHistory.contains(target)) return;
        processTooltip.hidden = true;
    });

    window.addEventListener("scroll", () => {
        processTooltip.hidden = true;
    }, true);

    window.addEventListener("resize", () => {
        processTooltip.hidden = true;
    });

    // Send button
    btnSend.addEventListener("click", sendMessage);

    // Input
    chatInput.addEventListener("input", () => {
        updateSendButton();
        autoResizeInput();
    });

    chatInput.addEventListener("keydown", (e) => {
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });

    // New session
    $("btn-new-session").addEventListener("click", () => {
        state.socket.emit("new_session");
    });

    // Quick commands
    document.querySelectorAll(".btn-command[data-command]").forEach((btn) => {
        btn.addEventListener("click", () => {
            const cmd = btn.dataset.command;
            chatInput.value = cmd;
            sendMessage();
        });
    });

    // Stop button (below input)
    $("btn-stop").addEventListener("click", () => {
        if (state.processing) {
            state.socket.emit("stop_agent");
            state.processing = false;
            setWorkingState(false);
            clearTimeout(state._typingBubbleTimeout);
            hideTypingBubble();
            hideThinking();
            updateSendButton();
        }
    });

    // Welcome hint cards
    document.querySelectorAll(".hint-card").forEach((card) => {
        card.addEventListener("click", () => {
            chatInput.value = card.dataset.hint;
            sendMessage();
        });
    });

    // Mobile sidebar toggle
    $("mobile-menu-btn").addEventListener("click", () => {
        $("sidebar").classList.toggle("open");
    });

    // Sidebar toggle (inside sidebar)
    $("sidebar-toggle").addEventListener("click", () => {
        $("sidebar").classList.toggle("open");
    });

    // Close modals on backdrop click
    document.querySelectorAll(".modal-backdrop").forEach(bg => {
        bg.addEventListener("click", (e) => {
            if (e.target === bg && bg.dataset.backdropClose !== "false") {
                bg.classList.remove("active");
            }
        });
    });

    // Clock
    function updateClock() {
        const clockEl = $("clock");
        if (!clockEl) return;
        const now = new Date();
        clockEl.textContent = now.toLocaleTimeString([], {
            hour: "2-digit",
            minute: "2-digit",
        });
    }

    function startClock() {
        if (clockTimer) {
            clearTimeout(clockTimer);
        }

        const tick = () => {
            updateClock();
            const now = new Date();
            const elapsedMs = now.getSeconds() * 1000 + now.getMilliseconds();
            const delay = Math.max(1000, 60000 - elapsedMs);
            clockTimer = window.setTimeout(tick, delay + 50);
        };

        tick();
    }

    startClock();
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

// ── Initialize ────────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", async () => {
    // Wire up login form
    const loginBtn = document.getElementById("btn-login");
    const loginInput = document.getElementById("login-token");
    const logoutBtn = document.getElementById("btn-logout");

    if (loginBtn) {
        loginBtn.addEventListener("click", () => {
            const token = loginInput.value.trim();
            if (token) attemptLogin(token);
        });
    }
    if (loginInput) {
        loginInput.addEventListener("keydown", (e) => {
            if (e.key === "Enter") {
                const token = loginInput.value.trim();
                if (token) attemptLogin(token);
            }
        });
    }
    if (logoutBtn) {
        logoutBtn.addEventListener("click", logout);
    }

    // Check if auth is required
    try {
        const res = await fetch("/api/auth/status");
        const data = await res.json();
        state.authRequired = data.auth_required;

        if (!data.auth_required) {
            // Auth disabled — start directly
            startApp();
            return;
        }

        // Check stored token
        const storedToken = getStoredToken();
        if (storedToken) {
            const verifyRes = await fetch("/api/auth/verify", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ token: storedToken }),
            });
            const verifyData = await verifyRes.json();
            if (verifyData.valid) {
                hideLogin();
                startApp();
                return;
            }
        }

        // No valid token — show login
        showLogin();
    } catch (e) {
        // Can't reach server — start anyway (will show errors naturally)
        startApp();
    }
});

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

        const toast = document.createElement("div");
        toast.style.cssText = "position:fixed;top:20px;left:50%;transform:translateX(-50%);z-index:9999;background:#4ade80;color:#000;padding:12px 24px;border-radius:10px;font-weight:600;font-size:14px;box-shadow:0 4px 20px rgba(0,0,0,0.3);animation:fadeIn .3s";
        toast.textContent = "\u2713 Setup complete! Shiba is ready to hunt.";
        document.body.appendChild(toast);
        setTimeout(() => toast.remove(), 4000);
    } catch(e) {
        btn.style.width = "";
        btn.disabled = false;
        btn.innerHTML = '<span class="material-icons-round" style="font-size:16px;vertical-align:middle">check</span> Finish Setup';
        await shibaDialog("alert", "Error", "Setup failed: " + e, { danger: true });
    }
};
