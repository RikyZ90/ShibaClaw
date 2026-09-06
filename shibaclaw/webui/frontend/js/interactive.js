/**
 * Interactive WebUI cards: structured ask, masked credential, progress card.
 * OpenClaw-2.0-inspired UX glued to gateway chat.interactive events.
 */

function _escapeUi(s) {
    return escapeHtml(String(s ?? ""));
}

function _removeInteractiveCard(requestId) {
    const el = document.getElementById(`interactive-${requestId}`);
    if (el) el.remove();
}

function _replyInteractive(requestId, response, sessionKey) {
    const sk =
        sessionKey ||
        (typeof state !== "undefined" && state.sessionId) ||
        "";
    realtime.emit("interactive_reply", {
        request_id: requestId,
        session_key: sk,
        response,
    });
    _removeInteractiveCard(requestId);
}

function renderAskCard(payload) {
    const requestId = payload.request_id;
    if (!requestId) return;
    const sessionKey = payload.session_key || "";
    activateChat();
    _removeInteractiveCard(requestId);

    const card = document.createElement("div");
    card.id = `interactive-${requestId}`;
    card.className = "interactive-card ask-card";

    const options = Array.isArray(payload.options) ? payload.options : [];
    const allowFree = payload.allow_free_text !== false;
    const allowSkip = payload.allow_skip !== false;

    let optionsHtml = options
        .map(
            (o) =>
                `<button type="button" class="interactive-option" data-id="${_escapeUi(o.id)}" data-label="${_escapeUi(o.label)}">${_escapeUi(o.label)}</button>`
        )
        .join("");

    card.innerHTML = `
        <div class="interactive-card-title">${_escapeUi(payload.prompt || "Question")}</div>
        <div class="interactive-options">${optionsHtml}</div>
        ${
            allowFree
                ? `<div class="interactive-freetext">
            <input type="text" class="interactive-input" placeholder="Or type a reply…" />
            <button type="button" class="interactive-send">Send</button>
           </div>`
                : ""
        }
        ${allowSkip ? `<button type="button" class="interactive-skip">Skip</button>` : ""}
    `;

    card.querySelectorAll(".interactive-option").forEach((btn) => {
        btn.addEventListener("click", () => {
            _replyInteractive(
                requestId,
                {
                    ok: true,
                    option_id: btn.dataset.id,
                    label: btn.dataset.label,
                },
                sessionKey
            );
        });
    });

    const input = card.querySelector(".interactive-input");
    const sendBtn = card.querySelector(".interactive-send");
    if (sendBtn && input) {
        const send = () => {
            const text = input.value.trim();
            if (!text) return;
            _replyInteractive(requestId, { ok: true, text }, sessionKey);
        };
        sendBtn.addEventListener("click", send);
        input.addEventListener("keydown", (e) => {
            if (e.key === "Enter") {
                e.preventDefault();
                send();
            }
        });
    }
    const skip = card.querySelector(".interactive-skip");
    if (skip) {
        skip.addEventListener("click", () => {
            _replyInteractive(
                requestId,
                { ok: true, action: "skip", skipped: true },
                sessionKey
            );
        });
    }

    chatHistory.appendChild(card);
    scrollToBottom();
}

function renderCredentialCard(payload) {
    const requestId = payload.request_id;
    if (!requestId) return;
    const sessionKey = payload.session_key || "";
    activateChat();
    _removeInteractiveCard(requestId);

    const card = document.createElement("div");
    card.id = `interactive-${requestId}`;
    card.className = "interactive-card credential-card";
    card.innerHTML = `
        <div class="interactive-card-title">${_escapeUi(payload.title || "Credential")}</div>
        ${payload.hint ? `<div class="interactive-hint">${_escapeUi(payload.hint)}</div>` : ""}
        <div class="interactive-hint">Stored as vault <code>${_escapeUi(payload.namespace || "runtime")}/${_escapeUi(payload.key || "")}</code>. Value never enters chat or the model.</div>
        <div class="interactive-freetext">
            <input type="password" class="interactive-input" autocomplete="off" placeholder="Secret value" />
            <button type="button" class="interactive-send">Store</button>
        </div>
        <button type="button" class="interactive-skip">Skip</button>
    `;

    const input = card.querySelector(".interactive-input");
    const store = () => {
        const secret = (input?.value || "").trim();
        if (!secret) return;
        _replyInteractive(requestId, { ok: true, secret }, sessionKey);
        if (input) input.value = "";
    };
    card.querySelector(".interactive-send")?.addEventListener("click", store);
    input?.addEventListener("keydown", (e) => {
        if (e.key === "Enter") {
            e.preventDefault();
            store();
        }
    });
    card.querySelector(".interactive-skip")?.addEventListener("click", () => {
        _replyInteractive(
            requestId,
            { ok: true, action: "skip", skipped: true },
            sessionKey
        );
    });

    chatHistory.appendChild(card);
    scrollToBottom();
}

function renderProgressCard(payload) {
    activateChat();
    let card = document.getElementById("session-progress-card");
    if (!card) {
        card = document.createElement("div");
        card.id = "session-progress-card";
        card.className = "interactive-card progress-card";
        chatHistory.appendChild(card);
    }
    const steps = Array.isArray(payload.steps) ? payload.steps : [];
    const status = payload.status || "working";
    card.dataset.status = status;
    card.innerHTML = `
        <div class="progress-card-header">
            <span class="progress-card-title">${_escapeUi(payload.title || "Progress")}</span>
            <span class="progress-card-status">${_escapeUi(status)}</span>
        </div>
        ${payload.detail ? `<div class="interactive-hint">${_escapeUi(payload.detail)}</div>` : ""}
        ${
            steps.length
                ? `<ol class="progress-card-steps">${steps
                      .map((s) => `<li>${_escapeUi(s)}</li>`)
                      .join("")}</ol>`
                : ""
        }
    `;
    if (status === "done" || status === "error") {
        // Keep card visible but mark complete; next turn can overwrite.
    }
    scrollToBottom();
}

function handleInteractivePayload(payload) {
    if (!payload || typeof payload !== "object") return;
    const kind = payload.kind;
    if (kind === "ask") renderAskCard(payload);
    else if (kind === "credential") renderCredentialCard(payload);
    else if (kind === "progress_card") renderProgressCard(payload);
}

window.handleInteractivePayload = handleInteractivePayload;
window.renderProgressCard = renderProgressCard;
