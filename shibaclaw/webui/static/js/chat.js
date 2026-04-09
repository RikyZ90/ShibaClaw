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

    bubble.innerHTML = renderMarkdown(content);
    enhanceCodeBlocks(bubble);

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

    const badgeEl = pg.headerEl.querySelector(".step-badge");
    badgeEl.className = `step-badge ${badge}`;
    badgeEl.textContent = badge;

    const title = pg.headerEl.querySelector(".pg-title");
    title.textContent = truncate(content, 60);
    title.classList.add("shiny-text");

    const step = document.createElement("div");
    step.className = "pg-step";
    step.innerHTML = `
        <span class="step-badge ${badge}">${badge}</span>
        <span class="pg-step-text">${escapeHtml(truncate(content, 300))}</span>
    `;

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

    updateProcessGroupTime(msgId);

    const title = pg.headerEl.querySelector(".pg-title");
    title.classList.remove("shiny-text");

    pg.el.classList.remove("expanded");
    pg.el.classList.add("completed");

    const badgeEl = pg.headerEl.querySelector(".step-badge");
    badgeEl.className = "step-badge END";
    badgeEl.textContent = "END";

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

    const stepsContainer = document.createElement("div");
    stepsContainer.className = "pg-content";
    for (const step of steps) {
        const row = document.createElement("div");
        row.className = "pg-step";
        row.innerHTML = `
            <span class="step-badge ${step.badge}">${step.badge}</span>
            <span class="pg-step-text">${escapeHtml(truncate(step.text, 300))}</span>
        `;
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

    if (typeof content === "string" && content.trim().startsWith("[") && content.trim().endsWith("]")) {
        try {
            const parsed = JSON.parse(content);
            if (Array.isArray(parsed)) content = parsed;
        } catch (e) { /* not JSON, continue with original string */ }
    }

    if (Array.isArray(content)) {
        content = content
            .filter(block => block && block.type === "text")
            .map(block => block.text)
            .join("\n");
    }

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

        const langClass = [...code.classList].find((c) => c.startsWith("language-"));
        const lang = langClass ? langClass.replace("language-", "") : "";

        if (typeof hljs !== "undefined" && !code.classList.contains("hljs")) {
            if (lang && hljs.getLanguage(lang)) {
                code.innerHTML = hljs.highlight(code.textContent, { language: lang }).value;
            } else {
                hljs.highlightElement(code);
            }
        }

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


// ── Typing Bubble (shown while agent is working, before any event) ──
function showTypingBubble() {
    if (document.getElementById("typing-bubble")) return;
    activateChat();
    const group = createMessageGroup("agent");
    group.id = "typing-bubble";
    group.innerHTML = group.innerHTML;
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


