// ── Message Rendering ─────────────────────────────────────────

function createAudioPlayer(file, autoPlay = false) {
    const container = document.createElement("div");
    container.className = "custom-audio-player";
    
    const audio = document.createElement("audio");
    audio.src = authUrl(file.url);
    audio.preload = "metadata";
    container.appendChild(audio);
    
    const playBtn = document.createElement("button");
    playBtn.className = "audio-play-btn";
    playBtn.innerHTML = '<span class="material-icons-round">play_arrow</span>';
    container.appendChild(playBtn);
    
    const progressContainer = document.createElement("div");
    progressContainer.className = "audio-progress-container";
    
    const progress = document.createElement("input");
    progress.type = "range";
    progress.className = "audio-progress-slider";
    progress.min = 0;
    progress.max = 100;
    progress.value = 0;
    progressContainer.appendChild(progress);
    container.appendChild(progressContainer);
    
    const timeLabel = document.createElement("span");
    timeLabel.className = "audio-time-label";
    timeLabel.textContent = "0:00 / 0:00";
    container.appendChild(timeLabel);
    
    function formatTime(secs) {
        if (isNaN(secs)) return "0:00";
        const m = Math.floor(secs / 60);
        const s = Math.floor(secs % 60);
        return `${m}:${s < 10 ? '0' : ''}${s}`;
    }
    
    audio.addEventListener("loadedmetadata", () => {
        timeLabel.textContent = `0:00 / ${formatTime(audio.duration)}`;
    });
    
    audio.addEventListener("timeupdate", () => {
        if (!audio.duration) return;
        const pct = (audio.currentTime / audio.duration) * 100;
        progress.value = pct;
        timeLabel.textContent = `${formatTime(audio.currentTime)} / ${formatTime(audio.duration)}`;
    });
    
    progress.addEventListener("input", (e) => {
        if (!audio.duration) return;
        const seekTo = (e.target.value / 100) * audio.duration;
        audio.currentTime = seekTo;
    });
    
    playBtn.addEventListener("click", () => {
        if (audio.paused) {
            document.querySelectorAll("audio").forEach(otherAudio => {
                if (otherAudio !== audio) otherAudio.pause();
            });
            audio.play().catch(err => console.debug("Play error:", err));
            playBtn.innerHTML = '<span class="material-icons-round">pause</span>';
        } else {
            audio.pause();
            playBtn.innerHTML = '<span class="material-icons-round">play_arrow</span>';
        }
    });
    
    audio.addEventListener("ended", () => {
        playBtn.innerHTML = '<span class="material-icons-round">play_arrow</span>';
        progress.value = 0;
    });
    
    if (autoPlay) {
        audio.addEventListener("canplaythrough", () => {
            const ttsToggle = document.getElementById("tts-toggle");
            if (ttsToggle && ttsToggle.checked) {
                if (window.speechTTS) window.speechTTS.stop();
                document.querySelectorAll("audio").forEach(otherAudio => {
                    if (otherAudio !== audio) otherAudio.pause();
                });
                audio.play().catch(err => console.debug("Autoplay blocked by browser policy"));
                playBtn.innerHTML = '<span class="material-icons-round">pause</span>';
            }
        }, { once: true });
    }
    
    return container;
}

async function downloadAttachment(url, fileName) {
    try {
        const res = await authFetch(url);
        if (!res.ok) throw new Error("Network response was not ok");
        const blob = await res.blob();
        const a = document.createElement("a");
        a.href = URL.createObjectURL(blob);
        a.download = fileName || "download";
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(a.href);
    } catch (e) {
        console.error("Download failed:", e);
    }
}

function _renderMessageBubble(content, attachments = [], autoPlayAudio = false) {
    const bubble = document.createElement("div");
    bubble.className = "message-bubble";

    if (content) {
        bubble.innerHTML = renderMarkdown(content);
        try { bubble.setAttribute("data-raw-content", typeof content === "string" ? content : JSON.stringify(content)); } catch (e) { }
        enhanceCodeBlocks(bubble);
    }

    attachments.forEach(file => {
        const isImage = typeof file.type === "string" && file.type.startsWith("image/");
        const isAudio = typeof file.type === "string" && file.type.startsWith("audio/");
        if (isImage) {
            const img = document.createElement("img");
            img.src = authUrl(file.url);
            img.onload = () => { if (typeof scrollToBottom === 'function') scrollToBottom(); };
            img.onclick = () => window.open(authUrl(file.url), "_blank");
            bubble.appendChild(img);
        } else if (isAudio) {
            const player = createAudioPlayer(file, autoPlayAudio);
            bubble.appendChild(player);
        } else {
            const link = buildFileAttachmentLink(file, () => {
                downloadAttachment(file.url, file.name || "attachment");
            });
            bubble.appendChild(link);
        }
    });

    return bubble;
}

function addUserMessage(content, attachments = []) {
    activateChat();
    const group = createMessageGroup("user");
    const bubble = _renderMessageBubble(content, attachments, false);
    group.querySelector(".message-content").appendChild(bubble);
    addTimestamp(group);
    chatHistory.appendChild(group);
    scrollToBottom();
}

function addAgentMessage(id, content, attachments = []) {
    activateChat();
    const group = createMessageGroup("agent");
    const bubble = _renderMessageBubble(content, attachments, true);
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
        header.onclick = () => {
            const pg = container.pgData;
            if (pg) pg.el.classList.toggle("expanded");
        };
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
        container.pgData = pg;
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
    delete state.processGroups[msgId];
}


function renderProcessGroupFromHistory(turnId, steps, targetContainer = chatHistory) {
    const id = `hist-${turnId}`;
    const groupEl = document.createElement("div");
    groupEl.className = "process-group completed";
    groupEl.id = `pg-${id}`;

    const header = document.createElement("div");
    header.className = "process-group-header";
    header.onclick = () => {
        groupEl.classList.toggle("expanded");
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
    groupEl.appendChild(header);

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
    groupEl.appendChild(stepsContainer);
    targetContainer.appendChild(groupEl);
}

function createMessageGroup(type, targetContainer = chatHistory) {
    state.messageCount++;
    const group = document.createElement("div");
    group.className = `message-group ${type}`;

    const avatar = document.createElement("div");
    avatar.className = "message-avatar";
    if (type === "user") {
        avatar.style.display = "none";
    } else {
        const img = document.createElement("img");
        img.src = state.profileAvatar || DEFAULT_AVATAR;
        img.alt = "ShibaClaw";
        img.className = "agent-avatar-img";
        avatar.appendChild(img);
    }
    group.appendChild(avatar);

    const prev = targetContainer ? targetContainer.lastElementChild : null;
    const prevIsProcessGroup = prev && prev.classList.contains("process-group");
    const prevGroup = prevIsProcessGroup ? targetContainer.children[targetContainer.children.length - 2] : prev;
    const sameType = prevGroup && prevGroup.classList.contains("message-group") && prevGroup.classList.contains(type);
    if (!sameType) group.classList.add("show-avatar");

    const content = document.createElement("div");
    content.className = "message-content";
    group.appendChild(content);

    return group;
}

function addTimestamp(group, dateStr) {
    const d = dateStr ? new Date(dateStr) : new Date();
    const time = document.createElement("div");
    time.className = "message-time";
    time.textContent = d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });

    const meta = document.createElement("div");
    meta.className = "message-meta";
    meta.appendChild(time);

    const copyBtn = document.createElement("button");
    copyBtn.className = "btn-copy-msg";
    copyBtn.type = "button";
    copyBtn.setAttribute('aria-label', 'Copy message');
    copyBtn.title = "Copy message";
    copyBtn.innerHTML = '<span class="material-icons-round" style="font-size:14px">content_copy</span>';
    copyBtn.addEventListener('click', (e) => { e.stopPropagation(); window.copyMessage(copyBtn); });
    meta.appendChild(copyBtn);

    const contentEl = group.querySelector(".message-content");
    contentEl.appendChild(meta);
}


// ── Markdown Rendering ────────────────────────────────────────
function renderMarkdown(text) {
    if (!text) return "";

    let content = text;

    if (typeof content === "string" && content.trim().startsWith("[") && content.trim().endsWith("]")) {
        try {
            const parsed = JSON.parse(content);
            if (Array.isArray(parsed)) content = parsed;
        } catch (e) { }
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
            let processedContent = content;
            const codeBlocks = [];
            const inlineCodes = [];

            processedContent = processedContent.replace(/```[\s\S]*?```/g, (match) => {
                codeBlocks.push(match);
                return `__CODE_BLOCK_PLACEHOLDER_${codeBlocks.length - 1}__`;
            });

            processedContent = processedContent.replace(/`[^`]+`/g, (match) => {
                inlineCodes.push(match);
                return `__INLINE_CODE_PLACEHOLDER_${inlineCodes.length - 1}__`;
            });

            // Preferences cached externally via refreshThoughtPrefs()
            let hideThoughts = _cachedHideThoughts;
            let collapseThoughts = _cachedCollapseThoughts;

            processedContent = processedContent.replace(/<think>([\s\S]*?)<\/think>/gi, (match, p1) => {
                let restoredP1 = p1;
                restoredP1 = restoredP1.replace(/__INLINE_CODE_PLACEHOLDER_(\d+)__/g, (m, idx) => inlineCodes[parseInt(idx, 10)]);
                restoredP1 = restoredP1.replace(/__CODE_BLOCK_PLACEHOLDER_(\d+)__/g, (m, idx) => codeBlocks[parseInt(idx, 10)]);
                if (hideThoughts) return "";
                const innerParsed = marked.parse(restoredP1.trim());
                const detailsOpen = collapseThoughts ? "" : " open";
                return `<details class="thought-block"${detailsOpen}><summary><span class="material-icons-round" style="font-size:14px">psychology</span>Ragionamento concluso</summary><div class="thought-content">${innerParsed}</div></details>\n\n`;
            });

            if (processedContent.match(/<think>([\s\S]*)$/i) && !processedContent.match(/<\/think>/i)) {
                processedContent = processedContent.replace(/<think>([\s\S]*)$/i, (match, p1) => {
                    if (hideThoughts) return "";
                    let restoredP1 = p1;
                    restoredP1 = restoredP1.replace(/__INLINE_CODE_PLACEHOLDER_(\d+)__/g, (m, idx) => inlineCodes[parseInt(idx, 10)]);
                    restoredP1 = restoredP1.replace(/__CODE_BLOCK_PLACEHOLDER_(\d+)__/g, (m, idx) => codeBlocks[parseInt(idx, 10)]);
                    const innerParsed = marked.parse(restoredP1.trim());
                    const detailsOpen = collapseThoughts ? "" : " open";
                    return `<details class="thought-block"${detailsOpen}><summary><span class="material-icons-round" style="font-size:14px">psychology</span>Ragionamento in corso...<span class="typing-dots-inline" style="margin-left:8px"><span></span><span></span><span></span></span></summary><div class="thought-content">${innerParsed}</div></details>\n\n`;
                });
            }

            const mentions = [];
            // Format mentions as beautiful chips
            processedContent = processedContent.replace(/@(kb|mcp|app):(?:"([^"]+)"|([^\s<]+))/gi, (match, type, name1, name2) => {
                const name = name1 || name2;
                let icon = "dns";
                let t = type.toLowerCase();
                let colorClass = "";
                if (t === "kb") { icon = "menu_book"; colorClass = "mention-kb"; }
                else if (t === "app" || t === "mcp") { icon = "apps"; colorClass = "mention-app"; }
                mentions.push(`<span class="mention-chip-inline ${colorClass}"><span class="material-icons-round">${icon}</span>${name}</span>`);
                return `@@MENTION_PLACEHOLDER_${mentions.length - 1}@@`;
            });

            processedContent = processedContent.replace(/__INLINE_CODE_PLACEHOLDER_(\d+)__/g, (match, p1) => {
                return inlineCodes[parseInt(p1, 10)];
            });

            processedContent = processedContent.replace(/__CODE_BLOCK_PLACEHOLDER_(\d+)__/g, (match, p1) => {
                return codeBlocks[parseInt(p1, 10)];
            });

            let finalHtml = marked.parse(processedContent);
            
            finalHtml = finalHtml.replace(/@@MENTION_PLACEHOLDER_(\d+)@@/g, (match, p1) => {
                return mentions[parseInt(p1, 10)];
            });
            
            if (typeof DOMPurify !== "undefined") {
                finalHtml = DOMPurify.sanitize(finalHtml, {
                    ADD_ATTR: ['target']
                });
            }
            
            return finalHtml;
        } catch (e) {
            console.error("Markdown parse error:", e);
        }
    }

    return escapeHtml(content).replace(/\n/g, "<br>");
}

function enhanceMarkdownTables(container) {
    container.querySelectorAll("table").forEach((table) => {
        if (table.parentElement && table.parentElement.classList.contains("table-scroll")) return;

        const wrapper = document.createElement("div");
        wrapper.className = "table-scroll";
        table.parentNode.insertBefore(wrapper, table);
        wrapper.appendChild(table);
    });
}

function enhanceCodeBlocks(container) {
    enhanceMarkdownTables(container);

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
    if (scrollToBottom._frame) return;
    
    // Do not force scroll if the user is scrolling up to read history
    const threshold = 150;
    const isNearBottom = chatHistory.scrollHeight - chatHistory.scrollTop - chatHistory.clientHeight < threshold;
    if (!isNearBottom && chatHistory.scrollTop > 0) return;

    scrollToBottom._frame = requestAnimationFrame(() => {
        scrollToBottom._frame = null;
        chatHistory.scrollTop = chatHistory.scrollHeight;
    });
}

function updateSendButton() {
    const hasText = chatInput.value.trim().length > 0;
    btnSend.disabled = !hasText;
    
    const iconSpan = btnSend.querySelector(".material-icons-round");
    if (iconSpan) {
        if (state.processing) {
            iconSpan.textContent = "navigation";
            btnSend.title = "Steer the agent";
        } else {
            iconSpan.textContent = "send";
            btnSend.title = hasText ? "Send message" : "Type a message to send";
        }
    }
}

function autoResizeInput() {
    chatInput.style.height = "auto";
    chatInput.style.height = Math.min(chatInput.scrollHeight, 200) + "px";
}


// ── Send Message ─────────────────────────────────────────────
function sendMessage() {
    const content = chatInput.value.trim();
    if (!content && state.stagedFiles.length === 0) return;

    if (!realtime.connected) {
        addAgentMessage("error", "⚠️ WebSocket disconnected. Wait for reconnect or reload the window.");
        if (!state.processing) {
            state.processing = false;
            updateSendButton();
        }
        return;
    }

    if (state.gatewayKnown && !state.gatewayUp) {
        addAgentMessage("error", "⚠️ Gateway offline or unreachable. Restart the desktop app or the gateway.");
        if (!state.processing) {
            state.processing = false;
            updateSendButton();
        }
        return;
    }

    const wasProcessing = state.processing;
    state.processing = true;
    updateSendButton();

    try {
        const attachments = [...state.stagedFiles];
        addUserMessage(content, attachments);

        const sent = realtime.emit("message", {
            content,
            attachments: attachments.map(a => ({
                name: a.name,
                url: a.url,
                type: a.type,
                mode: a.mode
            }))
        });

        if (!sent) {
            throw new Error("Realtime connection is not open.");
        }

        chatInput.value = "";
        state.stagedFiles = [];
        updateStagingUI();
        autoResizeInput();
        updateSendButton();
    } catch (e) {
        console.error("Send error:", e);
        addAgentMessage("error", `⚠️ ${e.message || "Failed to send message."}`);
        if (!wasProcessing) {
            state.processing = false;
        }
        updateSendButton();
    }
}


