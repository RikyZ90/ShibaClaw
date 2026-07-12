// ── Update Panel ──────────────────────────────────────────────
let _updateState = { manifestUrl: null, manifest: null, result: null, busy: false, commands: {} };

function _updateValue(data, key) {
    return (data && data[key]) ? data[key] : "-";
}

function _renderUpdateManifestSection(manifest, personalFiles) {
    let section = "";
    
    // Add the post-update troubleshooting alert at the top, in red
    section += `
        <div class="update-notes" style="border: 1px solid var(--accent-red); background: rgba(248, 113, 113, 0.05); margin-bottom: 12px;">
            <div class="update-notes-title" style="color: var(--accent-red);">
                <span class="material-icons-round" style="color: var(--accent-red);">warning</span>
                Login Troubleshooting
            </div>
            <div class="update-notes-body" style="color: var(--text-primary); font-size: 0.85rem;">
                If you experience login issues with the WebUI post-update, please run <code>shibaclaw reset-admin</code> in your terminal/console.
            </div>
        </div>`;

    if (manifest && manifest.release_notes) {
        section += `
            <div class="update-notes">
                <div class="update-notes-title"><span class="material-icons-round">article</span> What's new</div>
                <div class="update-notes-body">${escapeHtml(manifest.release_notes)}</div>
            </div>`;
    }

    if (personalFiles && personalFiles.length > 0) {
        const items = personalFiles.map(file => {
            const note = file.note ? ` <span class="update-file-note">- ${escapeHtml(file.note)}</span>` : "";
            return `<li><span class="material-icons-round" style="font-size:14px;vertical-align:middle;color:var(--accent-orange)">description</span> <code>${escapeHtml(file.path)}</code>${note}</li>`;
        }).join("");
        section += `
            <div class="update-personal">
                <div class="update-personal-title"><span class="material-icons-round">folder_open</span> Files changed by this release</div>
                <ul class="update-personal-list">${items}</ul>
                <div class="update-personal-note">If you customized any of these tracked files, back them up before updating. After the update, run <code>shibaclaw onboard</code> again to refresh them. If you keep personal information in these files, save a copy first so you can restore it afterward.</div>
            </div>`;
    }

    return section;
}

function _renderUpdateActionSection(data) {
    const actionCommand = (data.action_command || "").trim();
    const actionUrl = (data.action_url || data.release_url || "").trim();
    const actionLabel = escapeHtml(data.action_label || "Suggested action");
    const notes = Array.isArray(data.notes) ? data.notes : [];

    _updateState.commands = { action: actionCommand };

    const commandRow = actionCommand ? `
        <div style="margin-top:8px;font-size:13px;color:var(--text-muted)">Command</div>
        <div class="update-cmd-row">
            <code>${escapeHtml(actionCommand)}</code>
            <button class="btn-link" onclick="copyUpdateCommand('action')" title="Copy">
                <span class="material-icons-round" style="font-size:16px">content_copy</span>
            </button>
        </div>` : "";

    const notesHtml = notes.length ? `
        <ul class="update-personal-list" style="margin-top:12px">
            ${notes.map(note => `<li>${escapeHtml(note)}</li>`).join("")}
        </ul>` : "";

    const buttons = [];
    if (data.update_available && data.action_kind === "automatic") {
        buttons.push(`
            <button class="btn-primary" onclick="runUpdateAction()" ${_updateState.busy ? "disabled" : ""}>
                <span class="material-icons-round" style="font-size:14px;vertical-align:middle">system_update</span> Install update
            </button>`);
    }
    if (actionUrl) {
        buttons.push(`
            <a href="${escapeHtml(actionUrl)}" target="_blank" class="btn-secondary">
                <span class="material-icons-round" style="font-size:14px;vertical-align:middle">open_in_new</span> ${actionLabel}
            </a>`);
    }
    if (data.release_url && data.release_url !== actionUrl) {
        buttons.push(`
            <a href="${escapeHtml(data.release_url)}" target="_blank" class="btn-secondary">
                <span class="material-icons-round" style="font-size:14px;vertical-align:middle">article</span> Release notes
            </a>`);
    }

    if (!commandRow && buttons.length === 0 && !notesHtml) {
        return "";
    }

    return `
        <div class="update-notes" style="margin-top:16px">
            <div class="update-notes-title"><span class="material-icons-round">terminal</span> How to update</div>
            ${commandRow}
            ${notesHtml}
            ${buttons.length ? `<div class="update-actions" style="margin-top:16px">${buttons.join("")}</div>` : ""}
        </div>`;
}

window.copyUpdateCommand = async function (key) {
    const value = ((_updateState.commands || {})[key] || "").trim();
    if (!value) return;
    try {
        await navigator.clipboard.writeText(value);
    } catch (e) {
        console.error("copyUpdateCommand", e);
    }
};

window.runUpdateAction = async function () {
    const panel = $("update-status-container");
    const update = _updateState.result;
    if (!panel || !update || _updateState.busy) return;
    if (update.action_kind !== "automatic") return;

    const confirmed = await shibaDialog(
        "confirm",
        "Apply update?",
        "ShibaClaw will restart after a successful update.",
        { confirmText: "Update" }
    );
    if (!confirmed) return;

    _updateState.busy = true;
    const isPip = update.install_method === "pip";
    
    panel.innerHTML = `
        <div class="update-progress-card">
            <div class="update-progress-icon-wrap">
                <span class="material-icons-round update-icon-pulsing">system_update</span>
            </div>
            <div class="update-progress-container">
                <div class="update-progress-header">
                    <span class="update-progress-title">${isPip ? "Installing Update via pip" : "Downloading Update"}</span>
                    ${isPip ? "" : '<span class="update-progress-percent" id="update-progress-percent">0%</span>'}
                </div>
                <div class="update-progress-track ${isPip ? "indeterminate" : ""}">
                    <div id="update-progress-fill" class="update-progress-fill" style="${isPip ? "width: 100%;" : "width: 0%;"}"></div>
                </div>
                <div class="update-progress-status" id="update-progress-text">${isPip ? "Running pip upgrade in background, this may take a few minutes..." : "Preparing update..."}</div>
            </div>
        </div>`;

    try {
        const res = await authFetch("/api/update/apply", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ update, manifest: _updateState.manifest }),
        });
        const report = await res.json();
        if (!res.ok || report.error) {
            throw new Error(report.error || report.message || `HTTP ${res.status}`);
        }

        const ok = (report.pip && report.pip.ok) || (report.exe && report.exe.ok);
        const output = (report.pip && report.pip.output) || (report.exe && report.exe.output) || "";
        const installerOutput = (!ok && output) ? escapeHtml(output) : "";
        const message = escapeHtml(report.message || "Update complete.");
        const icon = ok ? "check_circle" : "error_outline";
        const color = ok ? "var(--accent-green)" : "var(--accent-red)";
        const footer = report.restarting
            ? '<div class="update-meta">Restarting ShibaClaw now...</div>'
            : '<div class="update-meta"><button class="btn-link" onclick="loadUpdatePanel(true)">Refresh status</button></div>';

        panel.innerHTML = `
            <div class="update-available">
                <span class="material-icons-round" style="font-size:48px;color:${color}">${icon}</span>
                <div class="update-ok-text">${message}</div>
                ${installerOutput ? `<div class="update-notes" style="margin-top:16px"><div class="update-notes-title"><span class="material-icons-round">terminal</span> Installer output</div><pre style="white-space:pre-wrap;margin:0;color:var(--text-secondary)">${installerOutput}</pre></div>` : ""}
                ${footer}
            </div>`;
    } catch (e) {
        const msg = e.message || "";
        const isNetworkOrTimeout = e.name === "TypeError" || msg.includes("HTTP 504") || msg.includes("HTTP 502") || msg.includes("Failed to fetch") || msg.includes("NetworkError");
        
        if (isNetworkOrTimeout) {
            panel.innerHTML = `
                <div class="update-progress-card">
                    <div class="update-progress-icon-wrap">
                        <span class="material-icons-round update-icon-pulsing" style="color:var(--accent-orange)">system_update</span>
                    </div>
                    <div class="update-progress-container">
                        <div class="update-progress-header">
                            <span class="update-progress-title">Update in Progress</span>
                        </div>
                        <div class="update-progress-status" style="white-space:normal;line-height:1.4">
                            The installation is taking a while or the server is restarting. The update is continuing in the background. Please wait a moment and then check the status.
                        </div>
                        <div class="update-meta" style="margin-top:12px">
                            <button class="btn-primary" onclick="loadUpdatePanel(true)">Refresh status</button>
                        </div>
                    </div>
                </div>`;
        } else {
            panel.innerHTML = `<div class="update-error"><span class="material-icons-round">error_outline</span> ${escapeHtml(msg || "Failed to apply the update.")}<br><button class="btn-secondary" style="margin-top:12px" onclick="loadUpdatePanel(true)">Retry</button></div>`;
        }
    } finally {
        _updateState.busy = false;
    }
};

window.updateDownloadProgress = function (percent) {
    const textEl = document.getElementById("update-progress-text");
    const barEl = document.getElementById("update-progress-fill");
    const percentEl = document.getElementById("update-progress-percent");
    if (textEl) textEl.textContent = `Downloading update package...`;
    if (percentEl) percentEl.textContent = `${percent}%`;
    if (barEl) barEl.style.width = percent + "%";
};

async function loadUpdatePanel(force = false) {
    const panel = $("update-status-container");
    if (!panel) return;

    if (_updateState.busy) {
        return;
    }

    _updateState.manifestUrl = null;
    _updateState.manifest = null;
    _updateState.result = null;
    _updateState.commands = {};

    panel.innerHTML = `<div class="update-checking"><span class="material-icons-round spin">progress_activity</span> Checking for updates...</div>`;

    try {
        const url = "/api/update/check" + (force ? "?force=1" : "");
        const res = await authFetch(url);
        const data = await res.json();

        if (data.error && !data.current) {
            panel.innerHTML = `<div class="update-error"><span class="material-icons-round">error_outline</span> ${escapeHtml(data.error)}<br><button class="btn-secondary" style="margin-top:12px" onclick="loadUpdatePanel(true)">Retry</button></div>`;
            return;
        }

        _updateState.result = data;

        const checkedAt = data.checked_at ? new Date(data.checked_at * 1000).toLocaleString() : "-";
        const displayCurrent = escapeHtml(_updateValue(data, "display_current") || _updateValue(data, "current"));
        const displayLatest = escapeHtml(_updateValue(data, "display_latest") || _updateValue(data, "latest"));
        const summary = escapeHtml(data.summary || (data.update_available ? "Update available." : "You're up to date."));

        let manifestSection = "";
        if (data.manifest_url && data.update_available) {
            _updateState.manifestUrl = data.manifest_url;
            try {
                const mRes = await authFetch("/api/update/manifest?url=" + encodeURIComponent(data.manifest_url));
                const mData = await mRes.json();
                _updateState.manifest = mData.manifest || null;
                manifestSection = _renderUpdateManifestSection(_updateState.manifest, mData.personal_files || []);
            } catch (e) {
                manifestSection = `<div class="update-notes" style="color:var(--text-muted);font-size:12px">Could not load update details.</div>`;
            }
        }

        const actionSection = _renderUpdateActionSection(data);
        const warningSection = data.error ? `
            <div class="update-notes" style="margin-top:16px">
                <div class="update-notes-title"><span class="material-icons-round">warning</span> Check warning</div>
                <div class="update-notes-body">${escapeHtml(data.error)}</div>
            </div>` : "";

        const headline = data.update_available ? "Update available" : "Status checked";
        const icon = data.update_available ? "system_update" : "check_circle";
        const iconColor = data.update_available ? "var(--accent-orange)" : "var(--accent-green)";
        const versionRow = data.update_available ? `
            <div class="update-version-row">
                <span class="update-badge current">${displayCurrent}</span>
                <span class="material-icons-round" style="color:var(--text-muted)">arrow_forward</span>
                <span class="update-badge latest">${displayLatest}</span>
            </div>` : `
            <div class="update-version-row">
                <span class="update-badge current">${displayCurrent}</span>
            </div>`;

        panel.innerHTML = `
            <div class="update-${data.update_available ? "available" : "ok"}">
                <span class="material-icons-round" style="font-size:48px;color:${iconColor}">${icon}</span>
                <div class="update-ok-text">${headline}</div>
                <div class="update-meta" style="margin-bottom:8px">${summary}</div>
                ${versionRow}
                ${manifestSection}
                ${warningSection}
                ${actionSection}
                <div class="update-meta">Last checked: ${checkedAt}${data.stale ? " (cached)" : ""} · <button class="btn-link" onclick="loadUpdatePanel(true)">Check again</button></div>
            </div>`;
    } catch (e) {
        panel.innerHTML = `<div class="update-error"><span class="material-icons-round">error_outline</span> Failed to check for updates.<br><button class="btn-secondary" style="margin-top:12px" onclick="loadUpdatePanel(true)">Retry</button></div>`;
    }
}
