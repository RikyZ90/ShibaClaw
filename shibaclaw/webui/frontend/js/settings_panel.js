window.openSettingsView = async function () {
    const chatArea = document.getElementById("chat-area");
    const settingsView = document.getElementById("settings-view");
    if (chatArea) chatArea.style.display = "none";
    if (settingsView) settingsView.style.display = "flex";

    if (typeof window.closeSidebarOnMobile === "function") {
        window.closeSidebarOnMobile();
    }

    const loader = document.getElementById("settings-loading");
    if (loader) loader.style.display = "flex";
    document.querySelectorAll(".settings-panel").forEach(p => p.style.display = "none");
    try {
        const res = await authFetch("/api/settings");
        const cfg = await res.json();
        if (cfg.error) throw cfg.error;
        window._shibaConfig = cfg;
        populateSettings(cfg);
        if (loader) loader.style.display = "none";
        
        let startTab = "agent";
        try { startTab = localStorage.getItem("shibaclaw_settings_tab") || "agent"; } catch (e) { }
        
        const isMobile = window.matchMedia("(max-width: 768px)").matches;
        if (isMobile) {
            document.getElementById("settings-mobile-dashboard").style.display = "block";
            document.getElementById("settings-body").style.display = "none";
            document.getElementById("settings-sidebar").style.display = "none";
            switchSettingsTab(startTab, { skipMobileDetailShow: true });
        } else {
            document.getElementById("settings-mobile-dashboard").style.display = "none";
            document.getElementById("settings-body").style.display = "block";
            document.getElementById("settings-sidebar").style.display = "flex";
            switchSettingsTab(startTab);
        }
    } catch (e) {
        if (loader) {
            loader.innerHTML = `<span class="material-icons-round" style="color:var(--accent-red)">error</span> Failed to load settings`;
        }
    }
};

window.closeSettingsView = function () {
    _clearOAuthPollsByPrefix("settings:");
    const settingsView = document.getElementById("settings-view");
    const chatArea = document.getElementById("chat-area");
    if (settingsView) settingsView.style.display = "none";
    if (chatArea) chatArea.style.display = "flex";
};

window.backToSettingsDashboard = function () {
    document.getElementById("settings-mobile-dashboard").style.display = "block";
    document.getElementById("settings-body").style.display = "none";
    const subtitleEl = document.getElementById("settings-current-tab-title");
    if (subtitleEl) subtitleEl.textContent = "Settings Dashboard";
};

window.openOnboardFromSettings = function () {
    window.closeSettingsView();
    openOnboardWizard();
};

window.switchSettingsTab = function (tab, options = {}) {
    document.querySelectorAll(".settings-sidebar-item").forEach(t => t.classList.remove("active"));
    const sidebarEl = document.querySelector(`.settings-sidebar-item[data-tab="${tab}"]`);
    if (sidebarEl) sidebarEl.classList.add("active");
    document.querySelectorAll(".settings-tab").forEach(t => t.classList.remove("active"));
    const tabEl = document.querySelector(`.settings-tab[data-tab="${tab}"]`);
    if (tabEl) tabEl.classList.add("active");
    document.querySelectorAll(".settings-panel").forEach(p => p.style.display = "none");
    const panel = $("panel-" + tab);
    if (panel) panel.style.display = "block";
    if (tab === "oauth") loadOAuthPanel();
    if (tab === "update") loadUpdatePanel();
    if (tab === "skills") loadSkillsPanel();
    if (tab === "plugins") loadPluginsPanel();
    if (tab === "heartbeat") loadHeartbeatSettingsPanel();
    if (tab === "mcp") { if (typeof loadMcpManagerPanel === "function") loadMcpManagerPanel(); }
    try { localStorage.setItem("shibaclaw_settings_tab", tab); } catch (e) { }

    const isMobile = window.matchMedia("(max-width: 768px)").matches;
    const subtitleEl = document.getElementById("settings-current-tab-title");
    if (subtitleEl) {
        const label = sidebarEl ? sidebarEl.querySelector("span:last-child")?.textContent || tab : tab;
        subtitleEl.textContent = label;
    }

    if (isMobile) {
        if (options.skipMobileDetailShow) {
            document.getElementById("settings-mobile-dashboard").style.display = "block";
            document.getElementById("settings-body").style.display = "none";
        } else {
            document.getElementById("settings-mobile-dashboard").style.display = "none";
            document.getElementById("settings-body").style.display = "block";
            document.getElementById("settings-body").scrollTop = 0;
        }
    } else {
        document.getElementById("settings-mobile-dashboard").style.display = "none";
        document.getElementById("settings-body").style.display = "block";
    }
};

/* ── Skills panel ── */
window._skillsData = [];
window._skillsPinnedList = [];
window._skillsMaxPinned = 5;

async function loadSkillsPanel() {
    const listEl = document.getElementById("skills-list");
    const selectEl = document.getElementById("skills-profile-select");
    
    // Ensure dropdown is populated
    if (selectEl && selectEl.options.length <= 1) {
        if (typeof fetchProfiles === "function") {
            try {
                const profiles = await fetchProfiles();
                let html = "";
                for (const p of profiles) {
                    html += '<option value="' + p.id + '">' + escHtml(p.label) + '</option>';
                }
                selectEl.innerHTML = html;
            } catch (e) {}
        }
    }
    
    // Sync the dropdown to the active profile if it's the first time opening
    if (selectEl && !selectEl.dataset.initialized) {
        const defaultPid = (typeof state !== 'undefined' && state.profileId) ? state.profileId : 'default';
        selectEl.value = defaultPid;
        selectEl.dataset.initialized = "true";
    }

    try {
        const pid = selectEl ? selectEl.value : ((typeof state !== 'undefined' && state.profileId) ? state.profileId : 'default');
        const res = await authFetch("/api/skills?profile_id=" + encodeURIComponent(pid));
        if (!res.ok) {
            if (listEl) listEl.innerHTML = '<div style="color:#e57373;font-size:13px;padding:12px">Failed to load skills (HTTP ' + res.status + ')</div>';
            return;
        }
        const data = await res.json();
        window._skillsData = data.skills || [];
        window._skillsPinnedList = data.pinned_skills || [];
        window._skillsMaxPinned = data.max_pinned_skills || 5;
        renderSkillsPanel();
    } catch (e) {
        console.error("loadSkillsPanel", e);
        if (listEl) listEl.innerHTML = '<div style="color:#e57373;font-size:13px;padding:12px">Error loading skills</div>';
    }
}

function renderSkillsPanel() {
    const skills = window._skillsData;
    const pinned = window._skillsPinnedList;
    var alwaysActive = skills.filter(function (s) { return s.always || pinned.includes(s.name); });
    var alwaysNames = alwaysActive.map(function (s) { return s.name; });

    var counter = document.getElementById("skills-pin-counter");
    if (counter) counter.textContent = alwaysActive.length + " / " + window._skillsMaxPinned;

    var pinnedList = document.getElementById("skills-pinned-list");
    if (pinnedList) {
        if (alwaysActive.length === 0) {
            pinnedList.innerHTML = '<span style="color:var(--text-secondary);font-size:12px">No always-active skills</span>';
        } else {
            pinnedList.innerHTML = alwaysActive.map(function (s) {
                var canUnpin = !s.always;
                var closeBtn = canUnpin
                    ? ' <span class="material-icons-round" style="font-size:14px;cursor:pointer;vertical-align:middle" onclick="toggleSkillPin(\'' + escHtml(s.name) + '\', false)">close</span>'
                    : ' <span class="material-icons-round" style="font-size:14px;vertical-align:middle;opacity:0.4" title="Set in SKILL.md">lock</span>';
                return '<span class="skills-pinned-chip">' + escHtml(s.name) + closeBtn + '</span>';
            }).join("");
        }
    }

    var listEl = document.getElementById("skills-list");
    if (!listEl) return;
    var q = ((document.getElementById("skills-search") || {}).value || "").toLowerCase();
    var filtered = q ? skills.filter(function (s) { return s.name.toLowerCase().includes(q) || (s.description || "").toLowerCase().includes(q); }) : skills;
    if (filtered.length === 0) {
        listEl.innerHTML = '<div style="color:var(--text-secondary);font-size:13px;padding:12px">No skills found.</div>';
        return;
    }
    listEl.innerHTML = filtered.map(function (s) { return renderSkillCard(s, alwaysNames); }).join("");
}

// escHtml removed — use global escapeHtml() from utils.js
var escHtml = escapeHtml;

function renderSkillCard(skill, activeNames) {
    var isActive = activeNames.includes(skill.name);
    var isYamlAlways = skill.always;
    var badgeClass = skill.source === "builtin" ? "builtin" : "workspace";
    var availClass = skill.available ? "" : " unavailable";
    var pinBtn = isYamlAlways
        ? '<span class="material-icons-round" style="font-size:16px;color:var(--shiba-gold);opacity:0.6" title="Always active (SKILL.md)">lock</span>'
        : '<span class="material-icons-round" style="font-size:16px;cursor:pointer;color:' + (isActive ? 'var(--shiba-gold)' : 'var(--text-secondary)') + '" title="' + (isActive ? 'Unpin' : 'Pin as always active') + '" onclick="toggleSkillPin(\'' + escHtml(skill.name) + '\', ' + !isActive + ')">' + (isActive ? 'push_pin' : 'add_circle_outline') + '</span>';
    var deleteBtn = skill.source === "workspace"
        ? '<span class="material-icons-round" style="font-size:16px;cursor:pointer;color:var(--text-secondary)" title="Delete" onclick="deleteSkill(\'' + escHtml(skill.name) + '\')">delete</span>'
        : '';
    return '<div class="skill-card' + availClass + '">' +
        '<div class="skill-card-body">' +
        '<div class="skill-card-name">' + escHtml(skill.name) + ' <span class="skill-badge ' + badgeClass + '">' + escHtml(skill.source) + '</span></div>' +
        '<div class="skill-card-desc">' + escHtml(skill.description || 'No description') + '</div>' +
        (skill.missing_requirements ? '<div style="font-size:11px;color:#e57373;margin-top:2px">Missing: ' + escHtml(skill.missing_requirements) + '</div>' : '') +
        '</div>' +
        '<div class="skill-card-actions">' + pinBtn + deleteBtn + '</div>' +
        '</div>';
}

window.toggleSkillPin = async function (name, pin) {
    let list = [...window._skillsPinnedList];
    if (pin) {
        if (list.length >= window._skillsMaxPinned) { alert("Max pinned skills reached (" + window._skillsMaxPinned + ")"); return; }
        if (!list.includes(name)) list.push(name);
    } else {
        list = list.filter(n => n !== name);
    }
    try {
        const selectEl = document.getElementById("skills-profile-select");
        const pid = selectEl ? selectEl.value : ((typeof state !== 'undefined' && state.profileId) ? state.profileId : 'default');
        const res = await authFetch("/api/skills/pin", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ pinned_skills: list, profile_id: pid }) });
        if (!res.ok) { const d = await res.json().catch(() => ({})); alert(d.error || "Pin failed"); return; }
        window._skillsPinnedList = list;
        renderSkillsPanel();
    } catch (e) { console.error("toggleSkillPin", e); }
};

window.deleteSkill = async function (name) {
    if (!confirm("Delete skill '" + name + "'? This cannot be undone.")) return;
    try {
        const res = await authFetch("/api/skills/" + encodeURIComponent(name), { method: "DELETE" });
        const d = await res.json().catch(() => ({}));
        if (!res.ok) { alert(d.error || "Delete failed"); return; }
        loadSkillsPanel();
    } catch (e) { console.error("deleteSkill", e); }
};

window.handleSkillsFileSelect = function (event) {
    const fileInput = event.target;
    const nameEl = document.getElementById("skills-import-filename");
    const importBtn = document.getElementById("skills-import-btn");
    if (fileInput.files.length) {
        if (nameEl) nameEl.textContent = fileInput.files[0].name;
        if (importBtn) importBtn.disabled = false;
    } else {
        if (nameEl) nameEl.textContent = "No file selected";
        if (importBtn) importBtn.disabled = true;
    }
};

window.importSkills = async function () {
    const fileInput = document.getElementById("skills-import-file");
    if (!fileInput || !fileInput.files.length) return;
    const el = document.getElementById("skills-import-result");
    const form = new FormData();
    form.append("file", fileInput.files[0]);
    form.append("conflict", "overwrite");
    if (el) { el.style.display = "block"; el.innerHTML = '<span style="color:var(--text-secondary)">Importing...</span>'; }
    try {
        const res = await authFetch("/api/skills/import", { method: "POST", body: form });
        const d = await res.json();
        if (!res.ok) { if (el) el.innerHTML = '<span style="color:#e57373">' + escHtml(d.error || "Error") + '</span>'; return; }
        if (el) el.innerHTML = '<span style="color:#4ade80">Imported ' + (d.imported_count || 0) + ' skill(s)</span>';
        fileInput.value = "";
        var nameEl = document.getElementById("skills-import-filename");
        if (nameEl) nameEl.textContent = "No file selected";
        document.getElementById("skills-import-btn").disabled = true;
        loadSkillsPanel();
    } catch (e) {
        console.error("importSkills", e);
        if (el) { el.style.display = "block"; el.innerHTML = '<span style="color:#e57373">Network error</span>'; }
    }
};

document.addEventListener("DOMContentLoaded", function () {
    document.addEventListener("input", function (e) {
        if (e.target && e.target.id === "skills-search") renderSkillsPanel();
    });

    // Set up listener for memory compaction events
    if (typeof realtime !== 'undefined' && realtime) {
        realtime.on("memory_compacted", () => {
            if (state.contextModalOpen && state.sessionId) {
                _loadContextModalContent();
            }
        });
    }
});

/* ── end Skills panel ── */

async function loadOAuthPanel() {
    const list = document.getElementById("oauth-list");
    if (!list) return;
    _clearOAuthPollsByPrefix("settings:");
    const providers = [
        { name: "openrouter", label: "OpenRouter", icon: "route", desc: "Authenticate in the browser and store the returned OpenRouter API key directly in provider settings.", mode: "browser_redirect", cta: "Open OpenRouter" },
        { name: "github_copilot", label: "GitHub Copilot", icon: "code", desc: "Authenticate via GitHub device flow. Uses native OAuth orchestration." },
        { name: "openai_codex", label: "OpenAI Codex", icon: "psychology", desc: "Authenticate via OAuth CLI kit. Requires oauth-cli-kit package." },
        { name: "xai", label: "xAI / Grok", icon: "public", desc: "xAI Subscription Sync OAuth flow." },
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
                    <button class="btn-secondary btn-sm" id="btn-oauth-disconnect-${p.name}" style="display:none; color: #ef4444; border-color: rgba(239, 68, 68, 0.3)">
                        <span class="material-icons-round" style="font-size:14px;vertical-align:middle">logout</span> Disconnect
                    </button>
                </div>
                <div class="oauth-logs" id="oauth-logs-${p.name}" style="display:none;height:260px;overflow-y:scroll;overflow-x:hidden;background:var(--bg-primary);border-radius:6px;padding:12px;font-size:12px;font-family:'JetBrains Mono',monospace;color:var(--text-secondary);margin-top:4px;border:1px solid var(--border-color);white-space:pre-wrap;line-height:1.6"></div>
            </div>`;
        list.appendChild(card);

        document.getElementById("btn-oauth-login-" + p.name).addEventListener("click", async () => {
            const btn = document.getElementById("btn-oauth-login-" + p.name);
            const badge = document.getElementById("oauth-badge-" + p.name);
            const logsEl = document.getElementById("oauth-logs-" + p.name);
            btn.disabled = true; btn.innerHTML = '<span class="material-icons-round spin" style="font-size:14px;vertical-align:middle">progress_activity</span> Contacting...';
            logsEl.style.display = "block"; logsEl.innerHTML = p.name === "openrouter" ? "Preparing OpenRouter login...\n" : "Requesting device code...\n";
            const loginBtnHtml = '<span class="material-icons-round" style="font-size:14px;vertical-align:middle">login</span> Login';
            try {
                const resp = await authFetch("/api/oauth/login", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ provider: p.name }) });
                const jd = await resp.json();
                if (jd.error) {
                    logsEl.textContent = "Error: " + jd.error;
                    btn.disabled = false; btn.innerHTML = loginBtnHtml;
                    return;
                }

                if (jd.status === "awaiting_paste" && jd.console_url) {
                    try {
                        window.open(jd.console_url, "_blank", "noopener,noreferrer");
                    } catch { /* ignore popup blockers */ }
                }

                if (jd.user_code && jd.verification_uri) {
                    badge.textContent = "Awaiting auth..."; badge.className = "acc-badge off";
                    btn.innerHTML = '<span class="material-icons-round spin" style="display:inline-block;width:14px;height:14px;line-height:14px;font-size:14px;vertical-align:middle">progress_activity</span> Waiting...';
                    const codeId = "oauth-code-" + Date.now();
                    logsEl.innerHTML =
                        `<div class="device-auth-ui" style="text-align:center;padding:12px 0">` +
                        `<div style="font-size:13px;color:var(--text-secondary);margin-bottom:10px">Sign in on the official site and enter the code below:</div>` +
                        `<div style="display:flex;align-items:center;justify-content:center;gap:16px;flex-wrap:wrap">` +
                        `<a href="${jd.verification_uri}" target="_blank" style="display:inline-flex;align-items:center;gap:6px;color:var(--bg-primary);background:var(--shiba-gold);padding:8px 16px;border-radius:8px;font-size:13px;font-weight:600;text-decoration:none;transition:opacity .2s" onmouseover="this.style.opacity='0.85'" onmouseout="this.style.opacity='1'">` +
                        `<span class="material-icons-round" style="font-size:16px">open_in_new</span> Open ${p.label}` +
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
                    try {
                        window.open(jd.verification_uri, "_blank", "noopener,noreferrer");
                    } catch { /* ignore popup blockers */ }
                }

                if (jd.auth_url && p.mode === "browser_redirect") {
                    badge.textContent = "Awaiting auth..."; badge.className = "acc-badge off";
                    btn.innerHTML = '<span class="material-icons-round spin" style="display:inline-block;width:14px;height:14px;line-height:14px;font-size:14px;vertical-align:middle">progress_activity</span> Waiting...';
                    logsEl.innerHTML =
                        `<div class="oauth-browser-auth-ui" style="text-align:center;padding:12px 0">` +
                        `<div style="font-size:13px;color:var(--text-secondary);margin-bottom:10px">Signing in on the official website...</div>` +
                        `<a href="${jd.auth_url}" target="_blank" rel="noopener noreferrer" style="display:inline-flex;align-items:center;gap:6px;color:var(--bg-primary);background:var(--shiba-gold);padding:8px 16px;border-radius:8px;font-size:13px;font-weight:600;text-decoration:none;transition:opacity .2s" onmouseover="this.style.opacity='0.85'" onmouseout="this.style.opacity='1'">` +
                        `<span class="material-icons-round" style="font-size:16px">open_in_new</span> ${p.cta || 'Open login'}` +
                        `</a>` +
                        `<div style="margin-top:12px;font-size:11px;color:var(--text-muted)">If no tab opened automatically, use the button above.</div>` +
                        `<div style="margin-top:12px;display:flex;align-items:center;justify-content:center;gap:6px;font-size:11px;color:var(--text-muted)">` +
                        `<span class="material-icons-round spin" style="display:inline-block;width:14px;height:14px;line-height:14px;font-size:14px">progress_activity</span> Waiting for browser callback...` +
                        `</div>` +
                        `</div>`;
                    try {
                        window.open(jd.auth_url, "_blank", "noopener,noreferrer");
                    } catch { /* ignore popup blockers */ }
                }

                if (jd.job_id) {
                    const pollScope = "settings:" + p.name;
                    _startOAuthJobPoll(pollScope, jd.job_id, async (job) => {
                        if (job.status === "done") {
                            badge.textContent = "Configured"; badge.className = "acc-badge on";
                            btn.disabled = false; btn.innerHTML = loginBtnHtml;
                            logsEl.innerHTML = `<div style="color:#4ade80;font-weight:600;text-align:center;padding:12px">✅ Authentication successful!</div>`;
                            try {
                                const settingsView = document.getElementById("settings-view");
                                if (settingsView && settingsView.style.display !== "none") {
                                    const settingsRes = await authFetch("/api/settings");
                                    const settingsCfg = await settingsRes.json();
                                    if (!settingsCfg.error) {
                                        window._shibaConfig = settingsCfg;
                                        populateSettings(settingsCfg);
                                        _availableModels = []; // Clear model cache
                                        _hasFetchedModels = false;
                                        switchSettingsTab("oauth");
                                    }
                                }
                                switchSettingsTab("oauth");
                            } catch { /* silent */ }
                            return true;
                        }
                        if (job.status === "error") {
                            badge.textContent = "Error"; badge.className = "acc-badge off";
                            btn.disabled = false; btn.innerHTML = loginBtnHtml;
                            const logs = (job.logs || []).join("\n");
                            logsEl.innerHTML = `<div style="color:#f87171;padding:8px;white-space:pre-wrap">${logs}</div>`;
                            return true;
                        }
                        if (job.status === "awaiting_paste" && !logsEl.querySelector('.paste-auth-ui')) {
                            badge.textContent = "Awaiting paste..."; badge.className = "acc-badge off";
                            btn.innerHTML = '<span class="material-icons-round spin" style="display:inline-block;width:14px;height:14px;line-height:14px;font-size:14px;vertical-align:middle">progress_activity</span> Waiting...';
                            const inputId = "paste-input-" + jd.job_id;
                            const submitId = "paste-submit-" + jd.job_id;
                            logsEl.innerHTML =
                                `<div class="paste-auth-ui" style="text-align:center;padding:12px 0">` +
                                `<div style="font-size:13px;color:var(--text-secondary);margin-bottom:10px;line-height:1.5">${job.instruction || 'Paste the token below:'}</div>` +
                                `<a href="${job.console_url}" target="_blank" style="display:inline-flex;align-items:center;gap:6px;color:var(--bg-primary);background:var(--shiba-gold);padding:8px 16px;border-radius:8px;font-size:13px;font-weight:600;text-decoration:none;transition:opacity .2s;margin-bottom:14px" onmouseover="this.style.opacity='0.85'" onmouseout="this.style.opacity='1'">` +
                                `<span class="material-icons-round" style="font-size:16px">open_in_new</span> Open ${p.label}` +
                                `</a>` +
                                `<div style="display:flex;gap:8px;align-items:center;justify-content:center">` +
                                `<input id="${inputId}" type="password" class="form-input" placeholder="Paste key/token here..." style="flex:1;max-width:400px;font-size:12px;font-family:'JetBrains Mono',monospace">` +
                                `<button id="${submitId}" class="btn-primary btn-sm" style="white-space:nowrap">` +
                                `<span class="material-icons-round" style="font-size:14px;vertical-align:middle">send</span> Submit` +
                                `</button>` +
                                `</div>` +
                                `</div>`;
                            setTimeout(() => {
                                const submitBtn = document.getElementById(submitId);
                                const inputEl = document.getElementById(inputId);
                                if (submitBtn && inputEl) {
                                    const doSubmit = async () => {
                                        const code = inputEl.value.trim();
                                        if (!code) return;
                                        submitBtn.disabled = true; submitBtn.textContent = "Sending...";
                                        try {
                                            await authFetch("/api/oauth/code", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ job_id: jd.job_id, code }) });
                                        } catch { submitBtn.disabled = false; submitBtn.textContent = "Submit"; }
                                    };
                                    submitBtn.addEventListener("click", doSubmit);
                                    inputEl.addEventListener("keydown", e => { if (e.key === "Enter") doSubmit(); });
                                }
                            }, 50);
                        }
                        if (job.status === "awaiting_redirect" && job.auth_url && p.mode === "browser_redirect" && !logsEl.querySelector('.oauth-browser-auth-ui')) {
                            badge.textContent = "Awaiting auth..."; badge.className = "acc-badge off";
                            btn.innerHTML = '<span class="material-icons-round spin" style="display:inline-block;width:14px;height:14px;line-height:14px;font-size:14px;vertical-align:middle">progress_activity</span> Waiting for auth...';
                            logsEl.innerHTML =
                                `<div class="oauth-browser-auth-ui" style="text-align:center;padding:12px 0">` +
                                `<a href="${job.auth_url}" target="_blank" rel="noopener noreferrer" style="display:inline-flex;align-items:center;gap:6px;color:var(--bg-primary);background:var(--shiba-gold);padding:8px 16px;border-radius:8px;font-size:13px;font-weight:600;text-decoration:none;transition:opacity .2s" onmouseover="this.style.opacity='0.85'" onmouseout="this.style.opacity='1'">` +
                                `<span class="material-icons-round" style="font-size:16px">open_in_new</span> ${p.cta || 'Open login'}` +
                                `</a>` +
                                `<div style="margin-top:12px;display:flex;align-items:center;justify-content:center;gap:6px;font-size:11px;color:var(--text-muted)">` +
                                `<span class="material-icons-round spin" style="display:inline-block;width:14px;height:14px;line-height:14px;font-size:14px">progress_activity</span> Waiting for browser callback...` +
                                `</div>` +
                                `</div>`;
                        } else if (job.status === "awaiting_code" && job.auth_url && !logsEl.querySelector('.codex-auth-ui')) {
                            badge.textContent = "Awaiting auth..."; badge.className = "acc-badge off";
                            btn.innerHTML = '<span class="material-icons-round spin" style="display:inline-block;width:14px;height:14px;line-height:14px;font-size:14px;vertical-align:middle">progress_activity</span> Waiting...';
                            const inputId = "codex-input-" + jd.job_id;
                            const submitId = "codex-submit-" + jd.job_id;
                            logsEl.innerHTML =
                                `<div class="codex-auth-ui" style="text-align:center;padding:12px 0">` +
                                `<div style="font-size:13px;color:var(--text-secondary);margin-bottom:10px">Click the button below to sign in with OpenAI:</div>` +
                                `<a href="${job.auth_url}" target="_blank" style="display:inline-flex;align-items:center;gap:6px;color:var(--bg-primary);background:var(--shiba-gold);padding:8px 16px;border-radius:8px;font-size:13px;font-weight:600;text-decoration:none;transition:opacity .2s" onmouseover="this.style.opacity='0.85'" onmouseout="this.style.opacity='1'">` +
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
                            setTimeout(() => {
                                const submitBtn = document.getElementById(submitId);
                                const inputEl = document.getElementById(inputId);
                                if (submitBtn && inputEl) {
                                    const doSubmit = async () => {
                                        const code = inputEl.value.trim();
                                        if (!code) return;
                                        submitBtn.disabled = true; submitBtn.textContent = "Sending...";
                                        try {
                                            await authFetch("/api/oauth/code", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ job_id: jd.job_id, code }) });
                                            inputEl.value = ""; inputEl.placeholder = "Code submitted, waiting...";
                                        } catch { submitBtn.disabled = false; submitBtn.textContent = "Submit"; }
                                    };
                                    submitBtn.addEventListener("click", doSubmit);
                                    inputEl.addEventListener("keydown", e => { if (e.key === "Enter") doSubmit(); });
                                }
                            }, 50);
                        }
                        return false;
                    });
                } else if (!jd.user_code) {
                    logsEl.textContent = jd.error || "Unknown response";
                    btn.disabled = false; btn.innerHTML = loginBtnHtml;
                }
            } catch (e) {
                logsEl.textContent = "Error: " + e;
                btn.disabled = false; btn.innerHTML = loginBtnHtml;
            }
        });
        document.getElementById("btn-oauth-disconnect-" + p.name).addEventListener("click", async () => {
            const btn = document.getElementById("btn-oauth-disconnect-" + p.name);
            const logsEl = document.getElementById("oauth-logs-" + p.name);
            btn.disabled = true;
            btn.innerHTML = '<span class="material-icons-round spin" style="font-size:14px;vertical-align:middle">progress_activity</span> Disconnecting...';
            try {
                const resp = await authFetch("/api/oauth/disconnect", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ provider: p.name }) });
                const jd = await resp.json();
                if (jd.ok) {
                    logsEl.style.display = "block";
                    logsEl.innerHTML = `<div style="color:var(--text-primary);padding:8px">Disconnected successfully.</div>`;
                    _refreshOAuthStatus();
                } else {
                    logsEl.style.display = "block";
                    logsEl.textContent = "Error disconnecting: " + (jd.error || "Unknown");
                    btn.disabled = false;
                    btn.innerHTML = '<span class="material-icons-round" style="font-size:14px;vertical-align:middle">logout</span> Disconnect';
                }
            } catch (e) {
                logsEl.style.display = "block";
                logsEl.textContent = "Error: " + e;
                btn.disabled = false;
                btn.innerHTML = '<span class="material-icons-round" style="font-size:14px;vertical-align:middle">logout</span> Disconnect';
            }
        });
    }

    _refreshOAuthStatus();
}

async function _refreshOAuthStatus() {
    try {
        const r = await authFetch("/api/oauth/providers");
        const data = await r.json();
        for (const p of (data.providers || [])) {
            const badge = document.getElementById("oauth-badge-" + p.name);
            const btnLogin = document.getElementById("btn-oauth-login-" + p.name);
            const btnDisconnect = document.getElementById("btn-oauth-disconnect-" + p.name);
            
            if (!badge) continue;
            const ok = p.status === "configured";
            badge.textContent = ok ? "Configured" : (p.status === "missing_dependency" ? "Missing dep" : "Not configured");
            badge.className = "acc-badge " + (ok ? "on" : "off");
            
            if (btnLogin && btnDisconnect) {
                if (ok) {
                    btnLogin.style.display = "none";
                    btnDisconnect.style.display = "inline-flex";
                    btnDisconnect.disabled = false;
                    btnDisconnect.innerHTML = '<span class="material-icons-round" style="font-size:14px;vertical-align:middle">logout</span> Disconnect';
                } else {
                    btnLogin.style.display = "inline-flex";
                    btnDisconnect.style.display = "none";
                }
            }
        }
    } catch { /* silent */ }
}

function _addProviderOption(sel, value, label) {
    if (sel.querySelector(`option[value="${value}"]`)) return;
    const opt = document.createElement("option");
    opt.value = value;
    opt.textContent = label || value.charAt(0).toUpperCase() + value.slice(1);
    sel.appendChild(opt);
}

async function _populateOAuthProviders(sel, current) {
    try {
        const r = await authFetch("/api/oauth/providers");
        const data = await r.json();
        for (const p of (data.providers || [])) {
            if (p.status === "configured") _addProviderOption(sel, p.name, p.label);
        }
        if (current) sel.value = current;
    } catch { /* silent */ }
}

function providerKeyPlaceholder(name) {
    const placeholders = {
        anthropic: "sk-ant-...",
        nvidia: "nvapi-...",
        deepseek: "sk-...",
        gemini: "AIza...",
        groq: "gsk_...",
        openai: "sk-...",
        openrouter: "sk-or-...",
        opencodeZen: "zen-...",
        opencodeGo: "go-...",
    };
    return placeholders[name] || "Enter API key";
}

function populateSettings(cfg) {
    lastSettingsConfig = JSON.parse(JSON.stringify(cfg));
    const d = cfg.agents?.defaults || {};
    $("s-agent-model").value = d.model || "";
    $("s-agent-consolidationModel").value = d.consolidationModel || "";
    setupSettingsModelPickers();
    void refreshSettingsModelPickers();
    $("s-agent-temp").value = d.temperature ?? 0.1;
    $("s-agent-maxTokens").value = d.maxTokens ?? 8192;
    $("s-agent-ctxTokens").value = d.contextWindowTokens ?? 65536;
    $("s-agent-maxIter").value = d.maxToolIterations ?? 40;
    $("s-agent-toolTimeout").value = d.toolTimeout ?? 660;
    $("s-agent-loopWallTimeout").value = d.loopWallTimeout ?? 600;
    $("s-agent-subagentTimeout").value = d.subagentTimeout ?? 600;
    $("s-agent-workspace").value = d.workspace || "~/.shibaclaw/workspace";
    $("s-agent-reasoning").value = d.reasoningEffort || "";

    // Audio settings
    const au = cfg.audio || {};
    $("s-audio-providerUrl").value = au.providerUrl || "";
    $("s-audio-apiKey").value = au.apiKey || "";
    $("s-audio-model").value = au.model || "";

    const providerSelect = document.getElementById("s-audio-ttsProvider");
    const voiceSelect = document.getElementById("s-audio-ttsVoice");
    const langSelect = document.getElementById("s-audio-ttsLang");
    const speedInput = document.getElementById("s-audio-ttsSpeed");
    if (providerSelect) providerSelect.value = au.ttsProvider || "browser";
    if (voiceSelect) voiceSelect.value = au.ttsVoice || "F1";
    if (langSelect) langSelect.value = au.ttsLang || "en";
    if (speedInput) speedInput.value = au.ttsSpeed ?? 1.0;

    const ttsFromConfig = au.ttsEnabled !== undefined ? au.ttsEnabled : (localStorage.getItem("shibaclaw_tts_enabled") === "true");
    const toggleEl = $("tts-toggle");
    toggleEl.checked = ttsFromConfig;
    if (window.speechTTS) window.speechTTS.enabled = ttsFromConfig;

    toggleEl.onchange = (e) => {
        if (window.speechTTS) window.speechTTS.enabled = e.target.checked;
        localStorage.setItem("shibaclaw_tts_enabled", e.target.checked);
        if (!e.target.checked && window.speechTTS) window.speechTTS.stop();
        updateTtsSettingsVisibility();
    };
    if (providerSelect) providerSelect.onchange = updateTtsSettingsVisibility;
    setTimeout(() => { if (typeof updateTtsSettingsVisibility === "function") updateTtsSettingsVisibility(); }, 50);

    // UI toggles for thought blocks (per-user local overrides)
    try {
        const hide = localStorage.getItem("shibaclaw_hide_thoughts");
        if (hide !== null && document.getElementById("s-ui-hide-thoughts")) {
            document.getElementById("s-ui-hide-thoughts").checked = (hide === "true");
        } else if (document.getElementById("s-ui-hide-thoughts")) {
            document.getElementById("s-ui-hide-thoughts").checked = !!(cfg.ui && cfg.ui.hide_thoughts);
        }
    } catch (e) { }
    try {
        const coll = localStorage.getItem("shibaclaw_collapse_thoughts");
        if (coll !== null && document.getElementById("s-ui-collapse-thoughts")) {
            document.getElementById("s-ui-collapse-thoughts").checked = (coll === "true");
        } else if (document.getElementById("s-ui-collapse-thoughts")) {
            document.getElementById("s-ui-collapse-thoughts").checked = !!(cfg.ui && cfg.ui.collapse_thoughts);
        }
    } catch (e) { }

    // Mobile Enter behavior (per-user local override)
    try {
        const mobileEnter = localStorage.getItem("shibaclaw_mobile_enter_newline");
        if (mobileEnter !== null && document.getElementById("s-ui-mobile-enter-newline")) {
            document.getElementById("s-ui-mobile-enter-newline").checked = (mobileEnter === "true");
        } else if (document.getElementById("s-ui-mobile-enter-newline")) {
            document.getElementById("s-ui-mobile-enter-newline").checked = !!(cfg.ui && cfg.ui.mobile_enter_newline);
        }
    } catch (e) { }

    const prov = cfg.providers || {};
    const list = $("providers-list");
    list.innerHTML = "";

    const PROV_ICONS = {
        custom: "tune", azureOpenai: "cloud", anthropic: "psychology", openai: "auto_awesome",
        openrouter: "route", nvidia: "developer_board", deepseek: "explore", groq: "speed", zhipu: "translate",
        dashscope: "dashboard", vllm: "memory", ollama: "dns", gemini: "diamond",
        moonshot: "dark_mode", minimax: "compress", aihubmix: "hub", siliconflow: "waves",
        volcengine: "volcano", volcentineCodingPlan: "code", byteplus: "add_box",
        byteplusCodingPlan: "code", openaiCodex: "terminal", githubCopilot: "code",
        opencodeZen: "spa", opencodeGo: "rocket_launch",
    };

    const provEntries = Object.entries(prov);
    let configuredCount = 0;
    let expandedProv = null;

    const provTiles = new Map();

    for (const [name, pc] of provEntries) {
        const hasKey = !!(pc.apiKey);
        if (hasKey) configuredCount++;
        const displayName = name.replace(/([A-Z])/g, " $1").replace(/^./, s => s.toUpperCase());
        const icon = PROV_ICONS[name] || "key";

        const tile = document.createElement("div");
        tile.className = "provider-tile" + (hasKey ? " configured" : "");
        tile.dataset.provName = name;
        tile.dataset.displayName = displayName.toLowerCase();
        tile.innerHTML = `
            <div class="provider-tile-icon"><span class="material-icons-round">${icon}</span></div>
            <div class="provider-tile-name">${displayName}</div>
            <span class="provider-tile-badge ${hasKey ? 'on' : 'off'}">${hasKey ? '✓ Configured' : 'Not set'}</span>`;

        tile.addEventListener("click", () => {
            const wasExpanded = tile.classList.contains("expanded");

            list.querySelectorAll(".provider-tile").forEach(t => t.classList.remove("expanded"));
            const oldExpand = list.querySelector(".provider-tile-expand");
            if (oldExpand) oldExpand.remove();

            if (wasExpanded) { expandedProv = null; return; }

            tile.classList.add("expanded");
            expandedProv = name;

            const expandPanel = document.createElement("div");
            expandPanel.className = "provider-tile-expand";
            expandPanel.innerHTML = `
                <div class="provider-expand-header">
                    <div class="provider-expand-title">
                        <span class="material-icons-round" style="font-size:18px">${icon}</span>
                        ${displayName}
                    </div>
                    <button class="provider-expand-close" title="Close">
                        <span class="material-icons-round" style="font-size:18px">close</span>
                    </button>
                </div>
                <div class="field-row">
                    <label>API Key</label>
                    <input type="password" class="form-input prov-key" data-prov="${name}" value="${pc.apiKey || ""}" placeholder="${providerKeyPlaceholder(name)}">
                </div>
                <div class="field-row">
                    <label>API Base URL</label>
                    <input type="text" class="form-input prov-base" data-prov="${name}" value="${pc.apiBase || ""}" placeholder="(default)">
                </div>`;

            const keyInput = expandPanel.querySelector(".prov-key");
            if (keyInput) {
                keyInput.addEventListener("input", (e) => {
                    pc.apiKey = e.target.value.trim();
                    if (typeof lastSettingsConfig !== "undefined" && lastSettingsConfig.providers && lastSettingsConfig.providers[name]) {
                        lastSettingsConfig.providers[name].apiKey = e.target.value.trim();
                    }
                });
            }

            const baseInput = expandPanel.querySelector(".prov-base");
            if (baseInput) {
                baseInput.addEventListener("input", (e) => {
                    pc.apiBase = e.target.value.trim() || null;
                    if (typeof lastSettingsConfig !== "undefined" && lastSettingsConfig.providers && lastSettingsConfig.providers[name]) {
                        lastSettingsConfig.providers[name].apiBase = e.target.value.trim() || null;
                    }
                });
            }

            expandPanel.querySelector(".provider-expand-close").addEventListener("click", (e) => {
                e.stopPropagation();
                tile.classList.remove("expanded");
                expandPanel.remove();
                expandedProv = null;
            });

            expandPanel.addEventListener("click", (e) => e.stopPropagation());

            tile.after(expandPanel);
        });

        list.appendChild(tile);
        provTiles.set(name, tile);
    }

    const statsEl = $("provider-stats");
    if (statsEl) {
        statsEl.innerHTML = `<span class="stat-configured">${configuredCount} Configured</span><span class="stat-dot"></span><span>${provEntries.length} Total</span>`;
    }

    const searchInput = document.getElementById("provider-search");
    if (searchInput) {
        searchInput.addEventListener("input", () => {
            const q = searchInput.value.toLowerCase().trim();
            for (const [name, tile] of provTiles) {
                const matches = !q || name.toLowerCase().includes(q) || tile.dataset.displayName.includes(q);
                tile.style.display = matches ? "" : "none";
            }
            const expandPanel = list.querySelector(".provider-tile-expand");
            if (expandPanel && expandedProv) {
                const parentTile = provTiles.get(expandedProv);
                if (parentTile && parentTile.style.display === "none") {
                    expandPanel.remove();
                    parentTile.classList.remove("expanded");
                    expandedProv = null;
                }
            }
        });
    }

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


    const gw = cfg.gateway || {};
    $("s-gw-host").value = gw.host || "127.0.0.1";
    $("s-gw-port").value = gw.port ?? 19999;

    const hb = gw.heartbeat || {};
    $("s-hb-enabled").checked = hb.enabled !== false;
    $("s-hb-interval").value = hb.intervalMin ?? 30;
    $("s-hb-profile").value = hb.profileId || "";

    const ch = cfg.channels || {};

    const targetChanSelect = $("s-hb-target-channel");
    if (targetChanSelect) {
        let html = '<option value="">Auto-detect</option>';
        html += '<option value="webui">Web UI</option>';

        for (const [name, cc] of Object.entries(ch)) {
            if (["sendProgress", "sendToolHints"].includes(name) || typeof cc !== "object") continue;
            if (cc.enabled === true) {
                const displayName = name.charAt(0).toUpperCase() + name.slice(1);
                html += `<option value="${name}">${displayName}</option>`;
            }
        }
        targetChanSelect.innerHTML = html;
    }

    const targets = Object.keys(hb.targets || {});
    if (targets.length > 0) {
        const firstChan = targets[0];
        if (targetChanSelect && targetChanSelect.querySelector(`option[value="${firstChan}"]`)) {
            targetChanSelect.value = firstChan;
        } else if (targetChanSelect) {
            // Add it if it's currently selected but disabled, so it doesn't just disappear
            targetChanSelect.innerHTML += `<option value="${firstChan}">${firstChan.charAt(0).toUpperCase() + firstChan.slice(1)} (disabled)</option>`;
            targetChanSelect.value = firstChan;
        }
        $("s-hb-target-id").value = hb.targets[firstChan] || "";
    } else {
        if (targetChanSelect) targetChanSelect.value = "";
        $("s-hb-target-id").value = "";
    }


    $("s-ch-sendProgress").checked = ch.sendProgress !== false;
    $("s-ch-sendToolHints").checked = !!ch.sendToolHints;

    const detail = $("channels-detail");
    detail.innerHTML = "";
    const skip = ["sendProgress", "sendToolHints"];

    const CH_ICON_MAP = {
        telegram: "send", discord: "forum", slack: "tag", whatsapp: "chat",
        webui: "language", cli: "terminal", email: "email", dingtalk: "notifications",
        feishu: "chat_bubble", matrix: "grid_view", mochat: "sms", qq: "forum",
        wecom: "business",
    };

    const EMAIL_FIELD_CONFIG = {
        imapHost: { label: "IMAP Server", section: "inbound", type: "text", placeholder: "imap.gmail.com" },
        imapPort: { label: "IMAP Port", section: "inbound", type: "number", placeholder: "993" },
        imapUsername: { label: "IMAP Username", section: "inbound", type: "text", placeholder: "email@gmail.com" },
        imapPassword: { label: "IMAP Password", section: "inbound", type: "password", placeholder: "App password" },
        imapUseSsl: { label: "IMAP SSL", section: "inbound", type: "boolean" },
        imapMailbox: { label: "IMAP Mailbox", section: "inbound", type: "text", placeholder: "INBOX" },
        smtpHost: { label: "SMTP Server", section: "outbound", type: "text", placeholder: "smtp.gmail.com" },
        smtpPort: { label: "SMTP Port", section: "outbound", type: "number", placeholder: "587" },
        smtpUsername: { label: "SMTP Username", section: "outbound", type: "text", placeholder: "email@gmail.com" },
        smtpPassword: { label: "SMTP Password", section: "outbound", type: "password", placeholder: "App password" },
        smtpUseTls: { label: "SMTP STARTTLS", section: "outbound", type: "boolean" },
        smtpUseSsl: { label: "SMTP SSL", section: "outbound", type: "boolean" },
        fromAddress: { label: "From Address", section: "outbound", type: "text", placeholder: "shibaclaw@gmail.com" },
        autoReplyEnabled: { label: "Auto Reply", section: "general", type: "boolean" },
        pollIntervalSeconds: { label: "Poll Interval (sec)", section: "general", type: "number", placeholder: "30" },
        markSeen: { label: "Mark as Read", section: "general", type: "boolean" },
        maxBodyChars: { label: "Max Body Length", section: "general", type: "number", placeholder: "12000" },
        subjectPrefix: { label: "Reply Prefix", section: "general", type: "text", placeholder: "Re: " },
        allowFrom: { label: "Allowed Senders", section: "general", type: "array", placeholder: "email1@test.com, email2@test.com" },
    };

    const channelEntries = [];
    for (const [name, cc] of Object.entries(ch)) {
        if (skip.includes(name) || typeof cc !== "object") continue;
        channelEntries.push([name, cc]);
    }

    const channelListEl = document.getElementById("channel-list");
    const channelDetailPane = document.getElementById("channel-detail-pane");
    if (channelListEl) channelListEl.innerHTML = "";

    let activeCount = 0;
    let selectedChannel = null;

    function buildChannelFields(name, cc) {
        const enabled = cc.enabled === true;
        let fieldsHtml = `
            <div class="field-row">
                <label>Enabled</label>
                <label class="toggle"><input type="checkbox" class="ch-enabled" data-ch="${name}" ${enabled ? "checked" : ""}><span class="toggle-slider"></span></label>
            </div>
        `;

        if (name === "email") {
            fieldsHtml += `
            <div class="field-row">
                <label>Authorize IMAP/SMTP access</label>
                <label class="toggle"><input type="checkbox" class="ch-field" data-ch="${name}" data-key="consentGranted" data-type="boolean" ${(cc.consentGranted || cc.consent_granted) ? "checked" : ""}><span class="toggle-slider"></span></label>
            </div>
            `;
        }

        if (name === "email" && EMAIL_FIELD_CONFIG) {
            const sections = { inbound: [], outbound: [], general: [] };
            for (const [key, val] of Object.entries(cc)) {
                if (key === "enabled" || key === "consentGranted" || key === "consent_granted") continue;
                const fieldConfig = EMAIL_FIELD_CONFIG[key] || null;
                const section = fieldConfig?.section || "general";
                const label = fieldConfig?.label || key;
                const placeholder = fieldConfig?.placeholder || "";

                let valStr = "";
                let originalType = typeof val;
                if (Array.isArray(val)) { originalType = "array"; valStr = val.join(", "); }
                else if (val !== null && originalType === "object") { originalType = "object"; valStr = JSON.stringify(val); }
                else { if (val === null) originalType = "string"; valStr = val === null ? "" : String(val); }

                let inputHtml = "";
                if (originalType === "boolean" || fieldConfig?.type === "boolean") {
                    inputHtml = `<div class="field-row"><label>${label}</label><label class="toggle"><input type="checkbox" class="ch-field" data-ch="${name}" data-key="${key}" data-type="boolean" ${valStr === "true" || val === true ? "checked" : ""}><span class="toggle-slider"></span></label></div>`;
                } else {
                    const isPassword = fieldConfig?.type === "password" || key.toLowerCase().includes("password") || key.toLowerCase().includes("secret");
                    const safeVal = String(valStr).replace(/"/g, '&quot;');
                    inputHtml = `<div class="field-row"><label>${label}</label><input type="${isPassword ? "password" : (fieldConfig?.type || "text")}" class="form-input ch-field" data-ch="${name}" data-key="${key}" data-type="${originalType}" value="${safeVal}" placeholder="${placeholder}"></div>`;
                }
                if (!sections[section]) sections[section] = [];
                sections[section].push(inputHtml);
            }

            const sectionLabels = { inbound: '📥 Email IN (IMAP)', outbound: '📤 Email OUT (SMTP)', general: '⚙️ General' };
            for (const [sectionKey, sectionFields] of Object.entries(sections)) {
                if (sectionFields.length > 0) {
                    fieldsHtml += `<div class="channel-detail-section-label">${sectionLabels[sectionKey] || sectionKey}</div>`;
                    fieldsHtml += sectionFields.join("");
                }
            }
        } else {
            const compareConfigKeys = (a, b) => {
                const getWeight = (key) => {
                    const lower = key.toLowerCase();
                    if (lower.includes("token") || lower.includes("secret") || lower.includes("password") || lower.includes("key")) {
                        if (lower.includes("proxy")) return 90;
                        return 10;
                    }
                    if (["mode", "webhookpath", "replyinthread", "replytomessage", "grouppolicy"].includes(lower)) {
                        return 20;
                    }
                    if (lower.includes("allow")) {
                        return 30;
                    }
                    if (lower === "dm" || lower === "mention") {
                        return 40;
                    }
                    if (lower.includes("proxy")) {
                        return 90;
                    }
                    return 50;
                };

                const wA = getWeight(a);
                const wB = getWeight(b);
                if (wA !== wB) return wA - wB;
                return a.localeCompare(b);
            };

            const formatLabel = (keyPath) => {
                const ABBR_MAP = {
                    dm: "DM", imap: "IMAP", smtp: "SMTP", url: "URL", ip: "IP", api: "API", ssl: "SSL", tls: "TLS", id: "ID", tts: "TTS", stt: "STT"
                };
                return keyPath.split('.').map(part => {
                    const words = part.replace(/([A-Z])/g, ' $1').replace(/_/g, ' ').split(/\s+/);
                    return words.map(w => {
                        const lower = w.toLowerCase();
                        if (ABBR_MAP[lower]) return ABBR_MAP[lower];
                        return w.charAt(0).toUpperCase() + w.slice(1).toLowerCase();
                    }).join(' ').trim();
                }).join(' › ');
            };

            const buildFieldHtml = (keyPath, val) => {
                let inputType = "text";
                let valStr = "";
                let originalType = typeof val;

                if (val === null) {
                    originalType = "string";
                    valStr = "";
                } else if (Array.isArray(val)) {
                    originalType = "array";
                    valStr = val.join(", ");
                } else if (originalType === "object") {
                    if (keyPath === "groups" || keyPath.startsWith("groups.")) {
                        originalType = "object";
                        valStr = JSON.stringify(val);
                    } else {
                        let html = "";
                        const subEntries = Object.entries(val).sort((a, b) => compareConfigKeys(a[0], b[0]));
                        for (const [childKey, childVal] of subEntries) {
                            html += buildFieldHtml(keyPath ? `${keyPath}.${childKey}` : childKey, childVal);
                        }
                        return html;
                    }
                } else {
                    valStr = String(val);
                }

                if (originalType === "boolean") {
                    const label = formatLabel(keyPath);
                    return `<div class="field-row"><label>${label}</label><label class="toggle"><input type="checkbox" class="ch-field" data-ch="${name}" data-key="${keyPath}" data-type="boolean" ${val ? "checked" : ""}><span class="toggle-slider"></span></label></div>`;
                }

                const lowerKey = keyPath.toLowerCase();
                if (lowerKey.includes("token") || lowerKey.includes("secret") || lowerKey.includes("password")) {
                    inputType = "password";
                }

                const safeVal = String(valStr).replace(/"/g, '&quot;');
                const label = formatLabel(keyPath);
                return `<div class="field-row"><label>${label}</label><input type="${inputType}" class="form-input ch-field" data-ch="${name}" data-key="${keyPath}" data-type="${originalType}" value="${safeVal}"></div>`;
            };

            const entries = Object.entries(cc).filter(([key]) => key !== "enabled" && key !== "consentGranted" && key !== "consent_granted");
            entries.sort((a, b) => compareConfigKeys(a[0], b[0]));
            for (const [key, val] of entries) {
                fieldsHtml += buildFieldHtml(key, val);
            }
        }
        return fieldsHtml;
    }

    function selectChannel(name, cc) {
        if (!channelDetailPane || !channelListEl) return;
        selectedChannel = name;

        channelListEl.querySelectorAll(".channel-list-item").forEach(el => {
            el.classList.toggle("active", el.dataset.ch === name);
        });

        const displayName = name.charAt(0).toUpperCase() + name.slice(1);
        const iconName = CH_ICON_MAP[name] || "chat";
        const fieldsHtml = buildChannelFields(name, cc);

        channelDetailPane.innerHTML = `
            <div class="channel-detail-header">
                <div class="channel-detail-icon"><span class="material-icons-round">${iconName}</span></div>
                <div class="channel-detail-title">${displayName}</div>
            </div>
            ${fieldsHtml}`;

        const hiddenInputs = detail.querySelectorAll(`input[data-ch="${name}"]`);
        const hiddenInputMap = new Map();
        hiddenInputs.forEach(el => {
            const k = el.classList.contains("ch-enabled") ? "__enabled__" : el.dataset.key;
            hiddenInputMap.set(k, el);
        });

        const paneInputs = channelDetailPane.querySelectorAll(`input[data-ch="${name}"]`);
        paneInputs.forEach(paneEl => {
            const k = paneEl.classList.contains("ch-enabled") ? "__enabled__" : paneEl.dataset.key;
            const hiddenEl = hiddenInputMap.get(k);
            if (!hiddenEl) return;

            if (hiddenEl.type === "checkbox") {
                paneEl.checked = hiddenEl.checked;
            } else {
                paneEl.value = hiddenEl.value;
            }

            if (paneEl.type === "checkbox") {
                paneEl.addEventListener("change", () => { hiddenEl.checked = paneEl.checked; });
            } else {
                paneEl.addEventListener("input", () => { hiddenEl.value = paneEl.value; });
            }
        });

        const enabledToggle = channelDetailPane.querySelector(`input.ch-enabled[data-ch="${name}"]`);
        if (enabledToggle) {
            enabledToggle.addEventListener("change", () => {
                const item = channelListEl.querySelector(`.channel-list-item[data-ch="${name}"]`);
                const dot = item?.querySelector(".channel-list-status");
                if (item) item.classList.toggle("enabled", enabledToggle.checked);
                if (dot) {
                    dot.className = "channel-list-status " + (enabledToggle.checked ? "on" : "off");
                }
                updateChannelStats();
            });
        }
    }

    function updateChannelStats() {
        const statsEl = document.getElementById("channel-stats");
        if (!statsEl) return;
        let active = 0;
        channelListEl.querySelectorAll(".channel-list-item").forEach(el => {
            if (el.classList.contains("enabled")) active++;
        });
        statsEl.innerHTML = `<span class="stat-active">${active} Active</span><span class="stat-dot"></span><span>${channelEntries.length} Total</span>`;
    }

    for (const [name, cc] of channelEntries) {
        const enabled = cc.enabled === true;
        if (enabled) activeCount++;

        const fieldsHtml = buildChannelFields(name, cc);
        const hiddenBlock = document.createElement("div");
        hiddenBlock.innerHTML = fieldsHtml;
        detail.appendChild(hiddenBlock);
    }

    let firstActive = null;
    for (const [name, cc] of channelEntries) {
        const enabled = cc.enabled === true;
        const displayName = name.charAt(0).toUpperCase() + name.slice(1);
        const iconName = CH_ICON_MAP[name] || "chat";

        if (channelListEl) {
            const item = document.createElement("div");
            item.className = "channel-list-item" + (enabled ? " enabled" : "");
            item.dataset.ch = name;
            item.innerHTML = `
                <span class="material-icons-round channel-list-icon">${iconName}</span>
                <span class="channel-list-name">${displayName}</span>
                <span class="channel-list-status ${enabled ? 'on' : 'off'}"></span>`;
            item.addEventListener("click", () => selectChannel(name, cc));
            channelListEl.appendChild(item);

            if (!firstActive && enabled) firstActive = [name, cc];
        }
    }

    const chStatsEl = document.getElementById("channel-stats");
    if (chStatsEl) {
        chStatsEl.innerHTML = `<span class="stat-active">${activeCount} Active</span><span class="stat-dot"></span><span>${channelEntries.length} Total</span>`;
    }

    if (firstActive) {
        selectChannel(firstActive[0], firstActive[1]);
    } else if (channelEntries.length > 0) {
        selectChannel(channelEntries[0][0], channelEntries[0][1]);
    }
}

/* Legacy MCP accordion card functions removed in favor of MCP Server Manager panel */

window.saveSettings = async function () {
    const patch = {
        agents: {
            defaults: {
                provider: "auto",
                model: $("s-agent-model").value,
                consolidationModel: $("s-agent-consolidationModel").value || null,
                temperature: parseFloat($("s-agent-temp").value),
                maxTokens: parseInt($("s-agent-maxTokens").value),
                contextWindowTokens: parseInt($("s-agent-ctxTokens").value),
                maxToolIterations: parseInt($("s-agent-maxIter").value),
                toolTimeout: parseInt($("s-agent-toolTimeout").value),
                loopWallTimeout: parseInt($("s-agent-loopWallTimeout").value),
                subagentTimeout: parseInt($("s-agent-subagentTimeout").value),
                workspace: $("s-agent-workspace").value,
                reasoningEffort: $("s-agent-reasoning").value || null,
                pinnedSkills: window._skillsPinnedList || [],
                maxPinnedSkills: window._skillsMaxPinned || 5,
            }
        },
        providers: (typeof lastSettingsConfig !== "undefined" && lastSettingsConfig.providers) ? JSON.parse(JSON.stringify(lastSettingsConfig.providers)) : {},
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
                enabled: $("s-hb-enabled").checked,
                intervalMin: parseInt($("s-hb-interval").value),
                model: $("s-hb-model").value || null,
                profileId: $("s-hb-profile").value || null,
                targets: (() => {
                    const chan = $("s-hb-target-channel").value;
                    const tid = $("s-hb-target-id").value;
                    if (chan) {
                        return { [chan]: tid };
                    }
                    return {};
                })()
            }
        },
        channels: {
            sendProgress: $("s-ch-sendProgress").checked,
            sendToolHints: $("s-ch-sendToolHints").checked,
        },
        audio: {
            providerUrl: $("s-audio-providerUrl").value || null,
            apiKey: $("s-audio-apiKey").value || null,
            model: $("s-audio-model").value || "whisper-large-v3-turbo",
            ttsEnabled: $("tts-toggle").checked,
            ttsProvider: $("s-audio-ttsProvider").value || "browser",
            ttsVoice: $("s-audio-ttsVoice").value || "F1",
            ttsLang: $("s-audio-ttsLang").value || "en",
            ttsSpeed: parseFloat($("s-audio-ttsSpeed").value) || 1.0,
        }
    };

    document.querySelectorAll(".prov-key").forEach(el => {
        const name = el.dataset.prov;
        if (!patch.providers[name]) patch.providers[name] = {};
        patch.providers[name].apiKey = el.value.trim();
    });
    document.querySelectorAll(".prov-base").forEach(el => {
        const name = el.dataset.prov;
        if (!patch.providers[name]) patch.providers[name] = {};
        const value = el.value.trim();
        patch.providers[name].apiBase = value || null;
    });

    const chDetailRoot = document.getElementById("channels-detail") || document;
    chDetailRoot.querySelectorAll(".ch-enabled").forEach(el => {
        const name = el.dataset.ch;
        if (!patch.channels[name]) patch.channels[name] = {};
        patch.channels[name].enabled = el.checked;
    });
    chDetailRoot.querySelectorAll(".ch-field").forEach(el => {
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
            try { val = JSON.parse(el.value); } catch (e) { val = {}; }
        } else if (type === "number") {
            val = Number(el.value);
        } else {
            val = el.value;
        }

        const parts = key.split(".");
        let current = patch.channels[name];
        for (let i = 0; i < parts.length - 1; i++) {
            if (!current[parts[i]]) current[parts[i]] = {};
            current = current[parts[i]];
        }
        current[parts[parts.length - 1]] = val;
    });

    // Persist UI-only preferences locally so changes are immediate
    try {
        if (document.getElementById("s-ui-hide-thoughts")) localStorage.setItem("shibaclaw_hide_thoughts", document.getElementById("s-ui-hide-thoughts").checked ? "true" : "false");
        if (document.getElementById("s-ui-collapse-thoughts")) localStorage.setItem("shibaclaw_collapse_thoughts", document.getElementById("s-ui-collapse-thoughts").checked ? "true" : "false");
        if (document.getElementById("s-ui-mobile-enter-newline")) localStorage.setItem("shibaclaw_mobile_enter_newline", document.getElementById("s-ui-mobile-enter-newline").checked ? "true" : "false");
    } catch (e) { }

    try {
        const res = await authFetch("/api/settings", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(patch)
        });
        const data = await res.json();
        if (typeof closeSettingsView === "function") closeSettingsView();
        _availableModels = []; // Clear model cache to force refresh
        _hasFetchedModels = false;
        fetchStatus();

        if (data.restarted) {
            shibaDialog("alert", "Restart Required", "Gateway is restarting to apply network changes.", { confirmText: "OK" });
        } else {
            // Hot-reloaded successfully without restarting
            let container = document.getElementById("toast-container");
            if (!container) {
                container = document.createElement("div");
                container.id = "toast-container";
                document.body.appendChild(container);
            }
            const toast = document.createElement("div");
            toast.className = "toast toast-success";
            toast.innerHTML = `<span class="toast-icon material-icons-round">check_circle</span> Settings saved & hot-reloaded successfully!`;
            container.appendChild(toast);
            setTimeout(() => { toast.classList.add("visible"); }, 100);
            setTimeout(() => {
                toast.classList.remove("visible");
                toast.classList.add("hiding");
                setTimeout(() => toast.remove(), 300);
            }, 3000);
        }
    } catch (e) {
        shibaDialog("alert", "Error", "Error saving settings: " + e, { confirmText: "Close", danger: true });
    }
};
