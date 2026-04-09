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


