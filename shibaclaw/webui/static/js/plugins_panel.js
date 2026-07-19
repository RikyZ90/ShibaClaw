window.loadPluginsPanel = async function () {
    const installedList = document.getElementById("installed-plugins-list");
    const availableList = document.getElementById("available-plugins-list");
    if (!installedList || !availableList) return;

    installedList.innerHTML = `<div class="settings-loader"><span class="material-icons-round spin">progress_activity</span> Loading plugins...</div>`;
    availableList.innerHTML = "";

    try {
        const res = await authFetch("/api/plugins");
        const data = await res.json();
        
        installedList.innerHTML = "";
        availableList.innerHTML = "";

        if (data.plugins && data.plugins.length > 0) {
            data.plugins.forEach(p => {
                const card = document.createElement("div");
                card.className = "skill-card";
                card.style.cssText = "display:flex; justify-content:space-between; align-items:center; padding:12px; border:1px solid var(--border-color); border-radius:8px; margin-bottom:8px; background:var(--bg-secondary)";
                card.innerHTML = `
                    <div style="display:flex; align-items:center; gap:10px">
                        <span class="material-icons-round" style="color:var(--shiba-gold)">${p.type === 'tts' ? 'volume_up' : 'forum'}</span>
                        <div>
                            <div style="font-weight:600; font-size:0.9rem">${escapeHtml(p.display_name)}</div>
                            <div style="font-size:0.75rem; color:var(--text-muted)">${escapeHtml(p.name)} (${escapeHtml(p.type)})</div>
                        </div>
                    </div>
                    <div style="display:flex; align-items:center; gap:8px">
                        <span class="acc-badge ${p.enabled ? 'on' : 'off'}">${p.enabled ? 'Enabled' : 'Disabled'}</span>
                        ${(() => {
                            let buttons = "";
                            if (p.name === 'shibaclaw-rag') {
                                buttons += `<button class="btn-icon" onclick="openModal('rag-settings-modal')" title="Settings" style="background:transparent; border:none; cursor:pointer">
                                    <span class="material-icons-round" style="color:var(--text-secondary); font-size:18px">settings</span>
                                </button>`;
                            }
                            const pkgName = p.type === 'tts' ? `shibaclaw-tts-${p.name}` : (p.type === 'channel' ? `shibaclaw-channel-${p.name}` : p.name);
                            buttons += `<button class="btn-icon" onclick="uninstallPlugin('${pkgName}')" title="Uninstall" style="background:transparent; border:none; cursor:pointer">
                                <span class="material-icons-round" style="color:var(--accent-red); font-size:18px">delete</span>
                            </button>`;
                            return buttons;
                        })()}
                    </div>
                `;
                installedList.appendChild(card);
            });
        } else {
            installedList.innerHTML = `<div style="color:var(--text-muted); font-size:0.85rem">No external plugins installed.</div>`;
        }

        if (data.available && data.available.length > 0) {
            data.available.forEach(p => {
                const card = document.createElement("div");
                card.className = "skill-card";
                card.style.cssText = "display:flex; justify-content:space-between; align-items:center; padding:12px; border:1px solid var(--border-color); border-radius:8px; margin-bottom:8px; background:var(--bg-secondary)";
                card.innerHTML = `
                    <div style="display:flex; align-items:center; gap:10px; flex:1; min-width:0">
                        <span class="material-icons-round" style="color:var(--text-muted)">cloud_download</span>
                        <div style="min-width:0; flex:1">
                            <div style="font-weight:600; font-size:0.9rem">${escapeHtml(p.display_name)}</div>
                            <div style="font-size:0.8rem; color:var(--text-secondary); white-space:nowrap; overflow:hidden; text-overflow:ellipsis">${escapeHtml(p.description)}</div>
                        </div>
                    </div>
                    <button class="btn-primary btn-sm" onclick="installPlugin('${escapeHtml(p.name)}')" style="white-space:nowrap; margin-left:12px">
                        <span class="material-icons-round" style="font-size:14px; vertical-align:middle">download</span> Install
                    </button>
                `;
                availableList.appendChild(card);
            });
        } else {
            availableList.innerHTML = `<div style="color:var(--text-muted); font-size:0.85rem">No available plugins to show.</div>`;
        }
    } catch (e) {
        installedList.innerHTML = `<div style="color:var(--accent-red); font-size:0.85rem">Error loading plugins list: ${escapeHtml(e.message || e)}</div>`;
    }
};

window.installPlugin = async function (explicitName) {
    const input = document.getElementById("plugin-install-name");
    const name = (explicitName || (input ? input.value : "")).trim();
    if (!name) return;

    const logEl = document.getElementById("plugin-action-log");
    const container = input ? input.parentElement : null;
    if (logEl) {
        logEl.style.display = "block";
        logEl.innerHTML = `<div style="display:flex; align-items:center; gap:8px"><span class="material-icons-round spin" style="color:var(--primary)">autorenew</span> <span>Installing <b>${escapeHtml(name)}</b>...</span></div><div style="font-size:0.8rem; margin-top:4px; color:var(--text-muted)">This runs pip install and will automatically restart the server.</div>`;
        logEl.classList.add("loading-pulse");
    }
    if (container) container.style.opacity = "0.5";

    try {
        const res = await authFetch("/api/plugins/install", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ package: name })
        });
        const data = await res.json();
        
        if (!res.ok) {
            if (logEl) {
                logEl.classList.remove("loading-pulse");
                logEl.innerHTML = `<div style="color:var(--danger)"><span class="material-icons-round">error</span> <b>Error:</b> ${escapeHtml(data.error || "Installation failed")}</div><pre style="margin-top:8px; font-size:0.75rem; background:rgba(0,0,0,0.2); padding:8px; border-radius:4px">${escapeHtml(data.stdout || "")}</pre>`;
            }
            if (container) container.style.opacity = "1";
            return;
        }

        if (logEl) {
            logEl.classList.remove("loading-pulse");
            logEl.innerHTML = `<div style="color:var(--success)"><span class="material-icons-round">check_circle</span> <b>Success!</b> Plugin installed.</div><div style="font-size:0.8rem; margin-top:4px">Restarting server to apply changes...</div>`;
        }
        if (input) input.value = "";
        
        await pollForServerRestart();
    } catch (e) {
        if (logEl) {
            logEl.classList.remove("loading-pulse");
            logEl.innerHTML = `<div style="color:var(--danger)"><span class="material-icons-round">error</span> <b>Network Error:</b> ${escapeHtml(e.message || e)}</div>`;
        }
        if (container) container.style.opacity = "1";
    }
};

window.uninstallPlugin = async function (name) {
    const confirmed = await shibaDialog("confirm", "Uninstall Plugin", `Are you sure you want to uninstall ${name}?`, { confirmText: "Uninstall", danger: true });
    if (!confirmed) return;

    const logEl = document.getElementById("plugin-action-log");
    if (logEl) {
        logEl.style.display = "block";
        logEl.innerHTML = `<div style="display:flex; align-items:center; gap:8px"><span class="material-icons-round spin" style="color:var(--accent-red)">autorenew</span> <span>Uninstalling <b>${escapeHtml(name)}</b>...</span></div><div style="font-size:0.8rem; margin-top:4px; color:var(--text-muted)">This will automatically restart the server.</div>`;
        logEl.classList.add("loading-pulse");
    }

    try {
        const res = await authFetch("/api/plugins/uninstall", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ package: name })
        });
        const data = await res.json();

        if (!res.ok) {
            if (logEl) {
                logEl.classList.remove("loading-pulse");
                logEl.innerHTML = `<div style="color:var(--danger)"><span class="material-icons-round">error</span> <b>Error:</b> ${escapeHtml(data.error || "Uninstallation failed")}</div><pre style="margin-top:8px; font-size:0.75rem; background:rgba(0,0,0,0.2); padding:8px; border-radius:4px">${escapeHtml(data.stdout || "")}</pre>`;
            }
            return;
        }

        if (logEl) {
            logEl.classList.remove("loading-pulse");
            logEl.innerHTML = `<div style="color:var(--success)"><span class="material-icons-round">check_circle</span> <b>Success!</b> Plugin uninstalled.</div><div style="font-size:0.8rem; margin-top:4px">Restarting server to apply changes...</div>`;
        }
        
        await pollForServerRestart();
    } catch (e) {
        if (logEl) {
            logEl.classList.remove("loading-pulse");
            logEl.innerHTML = `<div style="color:var(--danger)"><span class="material-icons-round">error</span> <b>Network Error:</b> ${escapeHtml(e.message || e)}</div>`;
        }
    }
};

async function pollForServerRestart() {
    let tries = 0;
    const interval = setInterval(async () => {
        tries++;
        try {
            const h = await authFetch("/api/status?_t=" + Date.now());
            if (h.ok) {
                const data = await h.json();
                if (data.status === "ok") {
                    clearInterval(interval);
                    window.location.reload();
                    return;
                }
            }
        } catch (e) { }
        if (tries > 20) {
            clearInterval(interval);
            alert("Server took too long to restart. Please reload manually.");
        }
    }, 2000);
}

window.updateTtsSettingsVisibility = function () {
    const toggle = document.getElementById("tts-toggle");
    const provSelect = document.getElementById("s-audio-ttsProvider");
    const voiceRow = document.getElementById("tts-voice-row");
    const langRow = document.getElementById("tts-lang-row");
    const speedRow = document.getElementById("tts-speed-row");
    const provRow = document.getElementById("tts-provider-row");

    if (!toggle || !provSelect) return;
    const checked = toggle.checked;
    const provider = provSelect.value;

    const showSupertonic = (checked && provider === "supertonic");
    if (provRow) provRow.style.display = checked ? "flex" : "none";
    if (voiceRow) voiceRow.style.display = showSupertonic ? "flex" : "none";
    if (langRow) langRow.style.display = showSupertonic ? "flex" : "none";
    if (speedRow) speedRow.style.display = showSupertonic ? "flex" : "none";
};
