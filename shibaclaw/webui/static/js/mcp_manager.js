/* ── MCP Server Manager Panel ─────────────────────────────────────────────
 *  Renders inside #panel-mcp (Settings → MCP Servers tab).
 *  Provides full CRUD + test-connection + OAuth 2.1 auto-discovery.
 * ───────────────────────────────────────────────────────────────────────── */

(function () {
    "use strict";

    // ── state ────────────────────────────────────────────────────────────────
    let _servers = [];          // [{_name, type, command, args, url, ...}]
    let _editingName = null;    // null = new server, string = existing name
    let _dirty = false;         // unsaved changes in editor
    let _testTimers = {};       // name → timeout id
    let _oauthPopup = null;     // reference to OAuth popup window
    let _oauthPollInterval = null;  // setInterval id for OAuth polling

    // ── entry point ──────────────────────────────────────────────────────────
    window.loadMcpManagerPanel = async function () {
        _checkOAuthCallback();
        await _fetchAndRender();
    };

    // ── OAuth callback detection ──────────────────────────────────────────────
    function _checkOAuthCallback() {
        const params = new URLSearchParams(window.location.search);
        if (params.has("mcp_oauth")) {
            _toastSuccess("✅ OAuth conectado con éxito!");
            // Clean URL
            const url = new URL(window.location.href);
            url.searchParams.delete("mcp_oauth");
            window.history.replaceState({}, "", url.toString());
        } else if (params.has("mcp_oauth_error")) {
            const err = params.get("mcp_oauth_error") || "unknown error";
            _toastError(`❌ OAuth error: ${err}`);
            const url = new URL(window.location.href);
            url.searchParams.delete("mcp_oauth_error");
            window.history.replaceState({}, "", url.toString());
        }
    }

    // ── safe fetch (no SyntaxError on non-JSON) ───────────────────────────────
    async function _safeFetch(url, opts) {
        const res = await authFetch(url, opts);
        let data = {};
        try {
            data = await res.json();
        } catch (_) {
            data = {};
        }
        return { res, data };
    }

    // ── fetch ─────────────────────────────────────────────────────────────────
    async function _fetchAndRender() {
        const container = document.getElementById("mcp-manager-container");
        if (!container) return;
        container.innerHTML = `<div class="mcp-loading"><span class="material-icons-round spin">progress_activity</span> Loading…</div>`;
        try {
            const { data } = await _safeFetch("/api/mcp/servers");
            _servers = data.servers || [];
            _renderList(container);
        } catch (e) {
            container.innerHTML = `<div class="mcp-error"><span class="material-icons-round">error_outline</span> Failed to load MCP servers.</div>`;
        }
    }

    // ── list view ─────────────────────────────────────────────────────────────
    function _renderList(container) {
        const hasServers = _servers.length > 0;

        container.innerHTML = `
            <div class="mcp-toolbar">
                <span class="mcp-server-count">${_servers.length} server${_servers.length !== 1 ? "s" : ""} configured</span>
                <button class="btn-primary btn-sm" id="mcp-add-btn">
                    <span class="material-icons-round" style="font-size:15px;vertical-align:middle">add</span> Add Server
                </button>
            </div>
            <div class="mcp-list" id="mcp-list">
                ${hasServers
                    ? _servers.map(_buildServerRow).join("")
                    : `<div class="mcp-empty"><span class="material-icons-round">hub</span><p>No MCP servers configured yet.</p><p class="mcp-empty-hint">Click <b>Add Server</b> to connect your first MCP server.</p></div>`
                }
            </div>
            <div class="mcp-editor-overlay" id="mcp-editor-overlay" style="display:none">
                <div class="mcp-editor-card" id="mcp-editor-card"></div>
            </div>`;

        document.getElementById("mcp-add-btn").addEventListener("click", () => _openEditor(null));

        _servers.forEach(s => {
            const row = document.getElementById(`mcp-row-${_safeId(s._name)}`);
            if (!row) return;
            row.querySelector(".mcp-row-edit").addEventListener("click", () => _openEditor(s._name));
            row.querySelector(".mcp-row-delete").addEventListener("click", () => _confirmDelete(s._name));
            row.querySelector(".mcp-row-test").addEventListener("click", () => _testServer(s._name));
            const connectBtn = row.querySelector(".mcp-row-connect");
            if (connectBtn) connectBtn.addEventListener("click", () => _startAutoOAuth(s._name));
            const manualBtn = row.querySelector(".mcp-row-oauth-manual");
            if (manualBtn) manualBtn.addEventListener("click", () => _openOAuthManualModal(s._name));
        });
    }

    function _isHttpServer(s) {
        const t = s.type || "";
        return !!(s.url || t === "sse" || t === "streamableHttp");
    }

    function _hasOAuth(s) {
        return !!(s.oauth && s.oauth.access_token);
    }

    function _buildServerRow(s) {
        const sid = _safeId(s._name);
        const typeLabel = s.type || (s.url ? "sse" : "stdio");
        const typeCls = typeLabel === "stdio" ? "mcp-type-stdio" : "mcp-type-http";
        const endpoint = s.url
            ? `<span class="mcp-endpoint" title="${escapeHtml(s.url)}">${escapeHtml(_truncate(s.url, 48))}</span>`
            : (s.command
                ? `<span class="mcp-endpoint" title="${escapeHtml(s.command)}">${escapeHtml(_truncate(s.command, 48))}</span>`
                : `<span class="mcp-endpoint muted">—</span>`);
        const toolsCount = (s.enabled_tools || ["*"]).join(", ");
        const isHttp = _isHttpServer(s);
        const hasOAuth = _hasOAuth(s);

        const oauthBadge = isHttp
            ? (hasOAuth
                ? `<span class="mcp-oauth-badge active" title="OAuth token active">🔒 OAuth</span>`
                : `<span class="mcp-oauth-badge inactive" title="No OAuth token">🔓 No OAuth</span>`)
            : "";

        const connectBtn = (isHttp && !hasOAuth)
            ? `<button class="btn-icon mcp-row-connect mcp-oauth-connect" title="Connect with OAuth"><span class="material-icons-round">login</span></button>`
            : "";

        const manualBtn = isHttp
            ? `<button class="btn-icon mcp-row-oauth-manual" title="Manual token"><span class="material-icons-round">key</span></button>`
            : "";

        return `
        <div class="mcp-row" id="mcp-row-${sid}">
            <div class="mcp-row-icon"><span class="material-icons-round">hub</span></div>
            <div class="mcp-row-info">
                <div class="mcp-row-name">${escapeHtml(s._name)}</div>
                <div class="mcp-row-meta">
                    <span class="mcp-type-badge ${typeCls}">${typeLabel}</span>
                    ${endpoint}
                    ${oauthBadge}
                    <span class="mcp-tools-hint" title="Enabled tools: ${escapeHtml(toolsCount)}">tools: ${escapeHtml(_truncate(toolsCount, 30))}</span>
                </div>
            </div>
            <div class="mcp-row-status" id="mcp-status-${sid}"></div>
            <div class="mcp-row-actions">
                ${connectBtn}
                ${manualBtn}
                <button class="btn-icon mcp-row-test" title="Test connection"><span class="material-icons-round">bolt</span></button>
                <button class="btn-icon mcp-row-edit" title="Edit"><span class="material-icons-round">edit</span></button>
                <button class="btn-icon mcp-row-delete danger" title="Delete"><span class="material-icons-round">delete</span></button>
            </div>
        </div>`;
    }

    // ── OAuth auto-discovery flow ─────────────────────────────────────────────
    async function _startAutoOAuth(name) {
        const toast = _showOAuthToast(`🔄 Discovering OAuth for "${name}"…`);
        try {
            const { res, data } = await _safeFetch(
                `/api/mcp/servers/${encodeURIComponent(name)}/oauth/start`,
                { method: "POST" }
            );
            if (!res.ok) {
                _removeOAuthToast(toast);
                const useFallback = confirm(
                    `Auto-discovery failed: ${data.error || "unknown error"}\n\nWant to enter the token manually?`
                );
                if (useFallback) _openOAuthManualModal(name);
                return;
            }

            const { auth_url, state } = data;
            _updateOAuthToast(toast, `🔐 Opening login popup…`);

            const popupWidth = 600, popupHeight = 700;
            const left = Math.round(window.screenX + (window.outerWidth - popupWidth) / 2);
            const top = Math.round(window.screenY + (window.outerHeight - popupHeight) / 2);
            _oauthPopup = window.open(
                auth_url,
                "mcp_oauth_popup",
                `width=${popupWidth},height=${popupHeight},left=${left},top=${top},toolbar=no,menubar=no`
            );

            if (!_oauthPopup) {
                _removeOAuthToast(toast);
                alert("Popup blocked! Please allow popups for this page.");
                return;
            }

            _updateOAuthToast(toast, `⏳ Waiting for authorization…`);

            // Poll for completion
            if (_oauthPollInterval) clearInterval(_oauthPollInterval);
            _oauthPollInterval = setInterval(async () => {
                try {
                    const { data: statusData } = await _safeFetch(
                        `/api/mcp/oauth/status?state=${encodeURIComponent(state)}`
                    );
                    if (statusData.completed) {
                        clearInterval(_oauthPollInterval);
                        _oauthPollInterval = null;
                        if (_oauthPopup && !_oauthPopup.closed) _oauthPopup.close();
                        _oauthPopup = null;
                        _removeOAuthToast(toast);
                        _toastSuccess(`🔒 OAuth connected for "${name}"!`);
                        await _fetchAndRender();
                    }
                } catch (_) {
                    // ignore polling errors
                }
            }, 1500);

            // Timeout after 10 minutes
            setTimeout(() => {
                if (_oauthPollInterval) {
                    clearInterval(_oauthPollInterval);
                    _oauthPollInterval = null;
                }
                if (_oauthPopup && !_oauthPopup.closed) _oauthPopup.close();
                _removeOAuthToast(toast);
            }, 600000);

        } catch (e) {
            _removeOAuthToast(toast);
            _toastError(`Network error: ${e}`);
        }
    }

    // ── manual OAuth modal ────────────────────────────────────────────────────
    function _openOAuthManualModal(name) {
        const existing = document.getElementById("mcp-oauth-modal-overlay");
        if (existing) existing.remove();

        const overlay = document.createElement("div");
        overlay.id = "mcp-oauth-modal-overlay";
        overlay.className = "mcp-editor-overlay";
        overlay.style.display = "flex";
        overlay.innerHTML = `
            <div class="mcp-editor-card" style="max-width:420px">
                <div class="mcp-editor-header">
                    <span class="mcp-editor-title">🔑 Manual OAuth Token – ${escapeHtml(name)}</span>
                    <button class="btn-icon" id="mcp-oam-close"><span class="material-icons-round">close</span></button>
                </div>
                <div class="mcp-editor-body">
                    <div class="field-row">
                        <label>Access Token <span class="req">*</span></label>
                        <input id="mcp-oam-token" type="text" class="form-input" placeholder="eyJ…">
                    </div>
                    <div class="field-row">
                        <label>Refresh Token <span class="hint">(optional)</span></label>
                        <input id="mcp-oam-refresh" type="text" class="form-input" placeholder="">
                    </div>
                    <div class="field-row">
                        <label>Expires in <span class="hint">(seconds, optional)</span></label>
                        <input id="mcp-oam-expires" type="number" class="form-input" placeholder="3600">
                    </div>
                    <div class="field-row" style="flex-direction:row;align-items:center;gap:8px">
                        <input type="checkbox" id="mcp-oam-clear" style="width:auto">
                        <label for="mcp-oam-clear" style="margin:0">Clear existing token</label>
                    </div>
                </div>
                <div class="mcp-editor-footer">
                    <div id="mcp-oam-err" class="mcp-editor-err" style="display:none"></div>
                    <div class="mcp-editor-actions">
                        <button class="btn-secondary" id="mcp-oam-cancel">Cancel</button>
                        <button class="btn-primary" id="mcp-oam-save">Save Token</button>
                    </div>
                </div>
            </div>`;
        document.body.appendChild(overlay);

        const close = () => overlay.remove();
        document.getElementById("mcp-oam-close").addEventListener("click", close);
        document.getElementById("mcp-oam-cancel").addEventListener("click", close);
        document.getElementById("mcp-oam-save").addEventListener("click", async () => {
            const errEl = document.getElementById("mcp-oam-err");
            const clearChk = document.getElementById("mcp-oam-clear").checked;

            if (clearChk) {
                const { res } = await _safeFetch(
                    `/api/mcp/servers/${encodeURIComponent(name)}/oauth`,
                    { method: "DELETE" }
                );
                if (res.ok) {
                    close();
                    _toastSuccess(`Token cleared for "${name}".`);
                    await _fetchAndRender();
                } else {
                    _showEditorErr(errEl, "Failed to clear token.");
                }
                return;
            }

            const token = (document.getElementById("mcp-oam-token")?.value || "").trim();
            if (!token) {
                _showEditorErr(errEl, "Access token is required.");
                return;
            }
            const body = { access_token: token };
            const refresh = (document.getElementById("mcp-oam-refresh")?.value || "").trim();
            if (refresh) body.refresh_token = refresh;
            const expires = parseInt(document.getElementById("mcp-oam-expires")?.value);
            if (expires > 0) body.expires_in = expires;

            const { res, data } = await _safeFetch(
                `/api/mcp/servers/${encodeURIComponent(name)}/oauth`,
                { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }
            );
            if (res.ok) {
                close();
                _toastSuccess(`Token saved for "${name}".`);
                await _fetchAndRender();
            } else {
                _showEditorErr(errEl, data.error || "Save failed.");
            }
        });
    }

    // ── OAuth toast helpers ───────────────────────────────────────────────────
    function _showOAuthToast(msg) {
        const el = document.createElement("div");
        el.className = "mcp-oauth-toast";
        el.innerHTML = `<span class="material-icons-round spin" style="font-size:16px;vertical-align:middle">progress_activity</span> ${escapeHtml(msg)}`;
        document.body.appendChild(el);
        return el;
    }

    function _updateOAuthToast(el, msg) {
        if (!el) return;
        el.innerHTML = `<span class="material-icons-round spin" style="font-size:16px;vertical-align:middle">progress_activity</span> ${escapeHtml(msg)}`;
    }

    function _removeOAuthToast(el) {
        if (el && el.parentNode) el.parentNode.removeChild(el);
    }

    // ── editor ────────────────────────────────────────────────────────────────
    function _openEditor(name) {
        _editingName = name;
        _dirty = false;
        const s = name ? (_servers.find(x => x._name === name) || {}) : {};
        const overlay = document.getElementById("mcp-editor-overlay");
        const card = document.getElementById("mcp-editor-card");
        if (!overlay || !card) return;

        const isNew = !name;
        const title = isNew ? "Add MCP Server" : `Edit – ${escapeHtml(name)}`;

        const argsVal = Array.isArray(s.args) ? s.args.join(", ") : (s.args || "");
        const toolsVal = Array.isArray(s.enabled_tools) ? s.enabled_tools.join(", ") : (s.enabled_tools || "*");
        const headersVal = (s.headers && Object.keys(s.headers).length) ? JSON.stringify(s.headers, null, 2) : "";
        const envVal = (s.env && Object.keys(s.env).length) ? JSON.stringify(s.env, null, 2) : "";

        card.innerHTML = `
            <div class="mcp-editor-header">
                <span class="mcp-editor-title">${title}</span>
                <button class="btn-icon" id="mcp-editor-close"><span class="material-icons-round">close</span></button>
            </div>
            <div class="mcp-editor-body">
                <div class="field-row">
                    <label>Server Name <span class="req">*</span></label>
                    <input id="mcp-ed-name" type="text" class="form-input" placeholder="my-server" value="${escapeHtml(name || "")}" ${!isNew ? "" : ""}>
                </div>
                <div class="field-row">
                    <label>Transport Type</label>
                    <select id="mcp-ed-type" class="form-input">
                        <option value="" ${!s.type ? "selected" : ""}>Auto-detect</option>
                        <option value="stdio" ${s.type === "stdio" ? "selected" : ""}>stdio</option>
                        <option value="sse" ${s.type === "sse" ? "selected" : ""}>sse</option>
                        <option value="streamableHttp" ${s.type === "streamableHttp" ? "selected" : ""}>streamableHttp</option>
                    </select>
                </div>
                <div class="field-row">
                    <label>Command</label>
                    <input id="mcp-ed-command" type="text" class="form-input" placeholder="npx, node, python…" value="${escapeHtml(s.command || "")}">
                </div>
                <div class="field-row">
                    <label>Args <span class="hint">(comma-separated)</span></label>
                    <input id="mcp-ed-args" type="text" class="form-input" placeholder="-y, @modelcontextprotocol/server-filesystem, /path" value="${escapeHtml(argsVal)}">
                </div>
                <div class="field-row">
                    <label>URL <span class="hint">(SSE / HTTP)</span></label>
                    <input id="mcp-ed-url" type="text" class="form-input" placeholder="http://localhost:3000/sse" value="${escapeHtml(s.url || "")}">
                </div>
                <div class="field-row">
                    <label>Headers <span class="hint">(JSON)</span></label>
                    <textarea id="mcp-ed-headers" class="form-input mcp-ed-textarea" placeholder='{"Authorization": "Bearer …"}'>${escapeHtml(headersVal)}</textarea>
                </div>
                <div class="field-row">
                    <label>Env Vars <span class="hint">(JSON)</span></label>
                    <textarea id="mcp-ed-env" class="form-input mcp-ed-textarea" placeholder='{"API_KEY": "…"}'>${escapeHtml(envVal)}</textarea>
                </div>
                <div class="field-row">
                    <label>Tool Timeout <span class="hint">(seconds)</span></label>
                    <input id="mcp-ed-timeout" type="number" class="form-input" value="${s.tool_timeout ?? 30}" min="1" max="600">
                </div>
                <div class="field-row">
                    <label>Enabled Tools <span class="hint">(comma-sep, * = all)</span></label>
                    <input id="mcp-ed-tools" type="text" class="form-input" placeholder="*, tool_name, …" value="${escapeHtml(toolsVal)}">
                </div>
            </div>
            <div class="mcp-editor-footer">
                <div id="mcp-editor-err" class="mcp-editor-err" style="display:none"></div>
                <div class="mcp-editor-actions">
                    <button class="btn-secondary" id="mcp-ed-cancel">Cancel</button>
                    <button class="btn-primary" id="mcp-ed-save">
                        <span class="material-icons-round" style="font-size:15px;vertical-align:middle">save</span> Save
                    </button>
                </div>
            </div>`;

        overlay.style.display = "flex";
        document.getElementById("mcp-editor-close").addEventListener("click", _closeEditor);
        document.getElementById("mcp-ed-cancel").addEventListener("click", _closeEditor);
        document.getElementById("mcp-ed-save").addEventListener("click", _saveEditor);

        setTimeout(() => {
            const nameInput = document.getElementById("mcp-ed-name");
            if (nameInput) nameInput.focus();
        }, 60);
    }

    function _closeEditor() {
        const overlay = document.getElementById("mcp-editor-overlay");
        if (overlay) overlay.style.display = "none";
        _editingName = null;
        _dirty = false;
    }

    async function _saveEditor() {
        const nameInput = document.getElementById("mcp-ed-name");
        const name = (nameInput?.value || "").trim();
        const errEl = document.getElementById("mcp-editor-err");

        if (!name) {
            _showEditorErr(errEl, "Server name is required.");
            nameInput?.focus();
            return;
        }

        if (!_editingName && _servers.find(x => x._name === name)) {
            _showEditorErr(errEl, `A server named "${name}" already exists.`);
            nameInput?.focus();
            return;
        }

        const parseJsonField = (id) => {
            const val = (document.getElementById(id)?.value || "").trim();
            if (!val) return {};
            try { return JSON.parse(val); } catch {
                _showEditorErr(errEl, `Invalid JSON in ${id.replace("mcp-ed-", "")} field.`);
                return null;
            }
        };

        const headers = parseJsonField("mcp-ed-headers");
        if (headers === null) return;
        const env = parseJsonField("mcp-ed-env");
        if (env === null) return;

        const body = {
            type: document.getElementById("mcp-ed-type")?.value || null,
            command: document.getElementById("mcp-ed-command")?.value.trim() || null,
            args: (document.getElementById("mcp-ed-args")?.value || "")
                .split(",").map(s => s.trim()).filter(Boolean),
            url: document.getElementById("mcp-ed-url")?.value.trim() || null,
            headers: Object.keys(headers).length ? headers : null,
            env: Object.keys(env).length ? env : null,
            tool_timeout: parseInt(document.getElementById("mcp-ed-timeout")?.value) || 30,
            enabled_tools: (document.getElementById("mcp-ed-tools")?.value || "*")
                .split(",").map(s => s.trim()).filter(Boolean),
        };

        Object.keys(body).forEach(k => { if (body[k] === null) delete body[k]; });

        const saveBtn = document.getElementById("mcp-ed-save");
        if (saveBtn) { saveBtn.disabled = true; saveBtn.innerHTML = '<span class="material-icons-round spin" style="font-size:15px;vertical-align:middle">progress_activity</span> Saving…'; }

        try {
            if (_editingName && _editingName !== name) {
                const { res: renameRes, data: rd } = await _safeFetch(
                    `/api/mcp/servers/${encodeURIComponent(_editingName)}/rename`,
                    { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ new_name: name }) }
                );
                if (!renameRes.ok) {
                    _showEditorErr(errEl, rd.error || "Rename failed.");
                    if (saveBtn) { saveBtn.disabled = false; saveBtn.innerHTML = '<span class="material-icons-round" style="font-size:15px;vertical-align:middle">save</span> Save'; }
                    return;
                }
            }

            const { res, data } = await _safeFetch(
                `/api/mcp/servers/${encodeURIComponent(name)}`,
                { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }
            );
            if (!res.ok) {
                _showEditorErr(errEl, data.error || "Save failed.");
                if (saveBtn) { saveBtn.disabled = false; saveBtn.innerHTML = '<span class="material-icons-round" style="font-size:15px;vertical-align:middle">save</span> Save'; }
                return;
            }

            _closeEditor();
            _toastSuccess(`Server "${name}" saved.`);

            // Post-save: offer OAuth for HTTP servers without token
            await _fetchAndRender();
            const saved = _servers.find(x => x._name === name);
            if (saved && _isHttpServer(saved) && !_hasOAuth(saved)) {
                const doOAuth = confirm(`"${name}" is an HTTP server.\nConnect with OAuth now?`);
                if (doOAuth) _startAutoOAuth(name);
            }
        } catch (e) {
            _showEditorErr(errEl, "Network error: " + e);
            if (saveBtn) { saveBtn.disabled = false; saveBtn.innerHTML = '<span class="material-icons-round" style="font-size:15px;vertical-align:middle">save</span> Save'; }
        }
    }

    // ── delete ────────────────────────────────────────────────────────────────
    async function _confirmDelete(name) {
        const ok = await shibaDialog(
            "confirm",
            "Delete MCP Server",
            `Remove "${name}" from the config? This cannot be undone.`,
            { confirmText: "Delete", danger: true }
        );
        if (!ok) return;
        try {
            const { res, data } = await _safeFetch(
                `/api/mcp/servers/${encodeURIComponent(name)}`,
                { method: "DELETE" }
            );
            if (!res.ok) { _toastError(data.error || "Delete failed."); return; }
            _toastSuccess(`Server "${name}" deleted.`);
            await _fetchAndRender();
        } catch (e) {
            _toastError("Network error: " + e);
        }
    }

    // ── test connection ───────────────────────────────────────────────────────
    async function _testServer(name) {
        const sid = _safeId(name);
        const statusEl = document.getElementById(`mcp-status-${sid}`);
        if (!statusEl) return;

        if (_testTimers[name]) { clearTimeout(_testTimers[name]); delete _testTimers[name]; }

        statusEl.innerHTML = `<span class="mcp-test-spin"><span class="material-icons-round spin" style="font-size:15px">progress_activity</span></span>`;

        try {
            const { res, data } = await _safeFetch(
                `/api/mcp/servers/${encodeURIComponent(name)}/test`,
                { method: "POST" }
            );
            if (data.ok) {
                statusEl.innerHTML = `<span class="mcp-status-badge ok" title="${escapeHtml(data.detail || "OK")}"><span class="material-icons-round" style="font-size:13px">check_circle</span> OK</span>`;
            } else {
                statusEl.innerHTML = `<span class="mcp-status-badge err" title="${escapeHtml(data.error || "Error")}"><span class="material-icons-round" style="font-size:13px">error_outline</span> Fail</span>`;
            }
        } catch (e) {
            statusEl.innerHTML = `<span class="mcp-status-badge err" title="${escapeHtml(String(e))}"><span class="material-icons-round" style="font-size:13px">error_outline</span> Error</span>`;
        }

        _testTimers[name] = setTimeout(() => {
            if (statusEl) statusEl.innerHTML = "";
            delete _testTimers[name];
        }, 8000);
    }

    // ── helpers ───────────────────────────────────────────────────────────────
    function _safeId(name) {
        return (name || "").replace(/[^a-zA-Z0-9_-]/g, "_");
    }

    function _truncate(str, n) {
        if (!str) return "";
        return str.length > n ? str.slice(0, n - 1) + "…" : str;
    }

    function _showEditorErr(el, msg) {
        if (!el) return;
        el.textContent = msg;
        el.style.display = "block";
    }

    function _toastSuccess(msg) {
        _toast(msg, "check_circle", "toast-success");
    }

    function _toastError(msg) {
        _toast(msg, "error_outline", "toast-error");
    }

    function _toast(msg, icon, cls) {
        let container = document.getElementById("toast-container");
        if (!container) {
            container = document.createElement("div");
            container.id = "toast-container";
            document.body.appendChild(container);
        }
        const t = document.createElement("div");
        t.className = `toast ${cls}`;
        t.innerHTML = `<span class="toast-icon material-icons-round">${icon}</span> ${escapeHtml(msg)}`;
        container.appendChild(t);
        setTimeout(() => t.classList.add("visible"), 60);
        setTimeout(() => {
            t.classList.remove("visible"); t.classList.add("hiding");
            setTimeout(() => t.remove(), 300);
        }, 3200);
    }

    // ── export public API ─────────────────────────────────────────────────────
    window._mcpManager = { reload: _fetchAndRender };
})();
