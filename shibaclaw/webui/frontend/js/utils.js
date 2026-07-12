// ── Utility Functions ─────────────────────────────────────────
function escapeHtml(str) {
    const div = document.createElement("div");
    div.textContent = str ?? "";
    return div.innerHTML;
}
window.escapeHtml = escapeHtml;

// ── Shared formatting helpers (used by ui_panels, automation, etc.) ──
function timeAgo(ms) {
    if (!ms) return "";
    const sec = Math.floor((Date.now() - ms) / 1000);
    if (sec < 60) return "just now";
    if (sec < 3600) return `${Math.floor(sec / 60)}m ago`;
    if (sec < 86400) return `${Math.floor(sec / 3600)}h ago`;
    return `${Math.floor(sec / 86400)}d ago`;
}

function formatSchedule(s) {
    if (!s) return "?";
    if (s.kind === "cron") {
        const expr = s.expr || s.expression || "";
        const tz = s.tz ? ` (${s.tz})` : "";
        return `cron: ${expr}${tz}`;
    }
    if (s.kind === "every") {
        const ms = s.everyMs || s.every_ms || 0;
        if (ms % 3600000 === 0) return `every ${ms / 3600000}h`;
        if (ms % 60000 === 0) return `every ${ms / 60000}m`;
        if (ms % 1000 === 0) return `every ${ms / 1000}s`;
        return `every ${ms}ms`;
    }
    if (s.kind === "at") {
        const atMs = s.atMs || s.at_ms || 0;
        return atMs ? new Date(atMs).toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" }) : "once";
    }
    return s.kind || "?";
}

function jobStatusClass(job) {
    if (!job.enabled) return "st-disabled";
    const st = (job.state || {}).lastStatus || (job.state || {}).last_status;
    if (st === "error") return "st-error";
    if (st === "ok") return "st-ok";
    return "st-pending";
}

// ── Cached thought preferences (avoids localStorage reads per message) ──
let _cachedHideThoughts = false;
let _cachedCollapseThoughts = false;

function refreshThoughtPrefs() {
    try { _cachedHideThoughts = localStorage.getItem("shibaclaw_hide_thoughts") === "true"; } catch (e) { }
    try { _cachedCollapseThoughts = localStorage.getItem("shibaclaw_collapse_thoughts") === "true"; } catch (e) { }
}
refreshThoughtPrefs();

function createMaterialIcon(name, className = "material-icons-round") {
    const icon = document.createElement("span");
    icon.className = className;
    icon.textContent = name;
    return icon;
}

function buildFileAttachmentLink(file, onOpen) {
    const link = document.createElement("a");
    link.href = "#";
    link.className = "file-attachment-link";
    link.title = file?.name || "attachment";
    link.appendChild(createMaterialIcon("insert_drive_file"));

    const label = document.createElement("span");
    label.textContent = file?.name || "attachment";
    link.appendChild(label);

    link.addEventListener("click", (e) => {
        e.preventDefault();
        if (typeof onOpen === "function") {
            onOpen();
        }
    });

    return link;
}


// ── Marked.js Configuration ──────────────────────────────────
if (typeof marked !== "undefined") {
    const safeMarkedRenderer = new marked.Renderer();
    safeMarkedRenderer.html = function (token) {
        if (typeof token === "string") {
            return escapeHtml(token);
        }
        return escapeHtml(token?.text ?? token?.raw ?? "");
    };

    marked.setOptions({
        breaks: true,
        gfm: true,
        renderer: safeMarkedRenderer,
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
    const fill = $("token-badge-fill");
    if (!badge || !text || !t) return;
    const pct = t.usage_pct ?? 0;
    const tier = usageTier(pct);
    badge.className = "token-badge usage-" + tier;
    if (fill) fill.style.width = `${pct}%`;
    text.textContent = `${fmtTokens(t.total ?? 0)} / ${fmtTokens(t.context_window ?? 0)} · ${pct}%`;
}

async function refreshTokenBadge() {
    if (!state.sessionId) return;
    try {
        const res = await authFetch(`/api/context?session_id=${encodeURIComponent(state.sessionId)}&summary=1`);
        if (!res.ok) return;
        const data = await res.json();
        if (data.tokens) updateTokenBadge(data.tokens);
    } catch (e) { /* silent */ }
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


function fallbackCopy(text, onSuccess) {
    try {
        const ta = document.createElement('textarea');
        ta.value = text || "";
        ta.style.position = 'fixed';
        ta.style.left = '-9999px';
        ta.setAttribute('aria-hidden', 'true');
        document.body.appendChild(ta);
        ta.focus();
        ta.select();
        document.execCommand('copy');
        document.body.removeChild(ta);
        if (typeof onSuccess === 'function') onSuccess();
    } catch (e) { console.error('fallbackCopy failed', e); }
}

window.copyMessage = function (btn) {
    try {
        const group = (btn && btn.closest) ? btn.closest('.message-group') : null;
        const bubble = group ? group.querySelector('.message-bubble') : null;
        let raw = bubble ? bubble.getAttribute('data-raw-content') : null;
        if (!raw && bubble) raw = bubble.textContent || '';
        if (!raw) return;

        const giveFeedback = () => {
            const prev = btn.innerHTML;
            btn.innerHTML = '<span class="material-icons-round">check</span>';
            setTimeout(() => { try { btn.innerHTML = prev; } catch (e) { } }, 1200);
        };

        if (navigator.clipboard && navigator.clipboard.writeText) {
            navigator.clipboard.writeText(raw).then(giveFeedback).catch(() => fallbackCopy(raw, giveFeedback));
        } else {
            fallbackCopy(raw, giveFeedback);
        }
    } catch (e) { console.error('copyMessage', e); }
};


