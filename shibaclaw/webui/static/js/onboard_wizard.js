const _ob = { step: 1, provider: null, providers: [], templates: { existing: [] } };

function initOnboardWizard() {
    if (state.onboardInitialized) return;
    state.onboardInitialized = true;

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

window.openOnboardWizard = async function () {
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
    } catch (e) {
        grid.innerHTML = '<p style="color:var(--accent-red)">Failed to load providers</p>';
    }
}

async function _obLoadTemplates() {
    try {
        const res = await authFetch("/api/onboard/templates");
        const data = await res.json();
        _ob.templates = { existing: data.existing_files || [], new_files: data.new_files || [] };
    } catch (e) { _ob.templates = { existing: [], new_files: [] }; }
}

function _obRenderGrid() {
    const grid = document.getElementById("ob-provider-grid");
    grid.innerHTML = "";
    const ICONS = {
        openrouter: "route", anthropic: "psychology", openai: "auto_awesome", gemini: "diamond",
        nvidia: "developer_board", deepseek: "explore", groq: "speed", ollama: "dns", github_copilot: "code"
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
        // Remove the default OAuth badge that was shown even when not authenticated
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

function _obNormalizeModelValue(providerName, modelId) {
    const raw = (modelId || "").trim();
    if (!raw || !providerName) return raw;
    const prefix = `${providerName}/`;
    return raw.startsWith(prefix) ? raw.slice(prefix.length) : raw;
}

function _obSetupStep2() {
    const p = _ob.provider;
    _clearOAuthPollsByPrefix("onboard:");
    if (!p) return;
    const keySection = document.getElementById("ob-key-section");
    const oauthSection = document.getElementById("ob-oauth-section");
    const localSection = document.getElementById("ob-local-section");
    keySection.style.display = "none";
    oauthSection.style.display = "none";
    localSection.style.display = "none";

    if (p.is_local) {
        localSection.style.display = "";
    } else if (p.is_oauth || p.name === "openrouter") {
        oauthSection.style.display = "";
        if (p.name === "openrouter") {
            keySection.style.display = "";
            document.getElementById("ob-key-title").textContent = p.label + " \u2014 API Key or OAuth";
            document.getElementById("ob-key-hint").textContent = "You can enter your API key below, or use the browser OAuth login.";
            if (p.status === "env_detected" || p.status === "configured") {
                document.getElementById("ob-api-key").placeholder = "Leave blank to keep current key";
            } else {
                document.getElementById("ob-api-key").value = "";
                document.getElementById("ob-api-key").placeholder = providerKeyPlaceholder(p.name);
            }
        } else {
            document.getElementById("ob-key-title").textContent = p.label + " \u2014 OAuth";
        }

        const btn = document.getElementById("ob-oauth-btn");
        const statusEl = document.getElementById("ob-oauth-status");
        if (p.status === "oauth_ok") {
            statusEl.innerHTML = '<span style="color:#4ade80"><span class="material-icons-round" style="font-size:16px;vertical-align:middle">check_circle</span> Already authenticated</span>';
        } else {
            statusEl.innerHTML = "";
            btn.style.width = "";
            btn.innerHTML = p.name === "openrouter" ? '<span class="material-icons-round" style="font-size:16px;vertical-align:middle">route</span> Login with OpenRouter' : '<span class="material-icons-round" style="font-size:16px;vertical-align:middle">lock_open</span> Start OAuth Setup';
            btn.onclick = async () => {
                btn.style.width = btn.offsetWidth + "px";
                btn.disabled = true;
                btn.innerHTML = '<span class="material-icons-round spin" style="font-size:16px;vertical-align:middle">progress_activity</span> Starting...';
                try {
                    const resp = await authFetch("/api/oauth/login", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ provider: p.name }) });
                    const jd = await resp.json();
                    if (jd.auth_url) {
                        try {
                            const newWindow = window.open(jd.auth_url, '_blank', 'width=600,height=800');
                            if (!newWindow) throw new Error("Popup blocked");
                            statusEl.innerHTML = '<div style="text-align:center;margin-top:1rem">' +
                                '<div style="font-size:13px;color:var(--text-secondary);margin-bottom:10px">OpenRouter will return here automatically when the authorization is complete.</div>' +
                                '<span class="material-icons-round spin" style="font-size:14px;vertical-align:middle">progress_activity</span> Waiting for auth...</div>';
                        } catch (ex) {
                            statusEl.innerHTML = `<div style="text-align:center;margin-top:1rem">` +
                                `<a href="${jd.auth_url}" target="_blank" class="btn-primary" style="display:inline-flex;align-items:center;gap:6px;text-decoration:none">` +
                                `<span class="material-icons-round" style="font-size:16px">open_in_new</span> Click here if popup is blocked</a>` +
                                `<div style="margin-top:8px;font-size:11px;color:var(--text-muted)">` +
                                `<span class="material-icons-round spin" style="font-size:14px;vertical-align:middle">progress_activity</span> Waiting for auth...</div></div>`;
                        }
                    } else if (jd.user_code && jd.verification_uri) {
                        statusEl.innerHTML = '<div style="text-align:center;margin-top:1rem">' +
                            '<a href="' + jd.verification_uri + '" target="_blank" class="btn-primary" style="display:inline-flex;align-items:center;gap:6px;text-decoration:none">' +
                            '<span class="material-icons-round" style="font-size:16px">open_in_new</span> Open GitHub</a>' +
                            '<div style="margin-top:10px;font-size:22px;letter-spacing:3px;font-weight:700;color:var(--shiba-gold);font-family:monospace;cursor:pointer" ' +
                            'onclick="navigator.clipboard.writeText(\'' + jd.user_code + '\')" title="Click to copy">' + jd.user_code + '</div>' +
                            '<div style="margin-top:8px;font-size:11px;color:var(--text-muted)">' +
                            '<span class="material-icons-round spin" style="font-size:14px;vertical-align:middle">progress_activity</span> Waiting for auth...</div></div>';
                    }
                    if (jd.job_id) {
                        const pollScope = "onboard:" + p.name;
                        _startOAuthJobPoll(pollScope, jd.job_id, async (job) => {
                            if (job.status === "done") {
                                statusEl.innerHTML = '<span style="color:#4ade80"><span class="material-icons-round" style="font-size:16px;vertical-align:middle">check_circle</span> Authenticated!</span>';
                                btn.disabled = false;
                                btn.innerHTML = '<span class="material-icons-round" style="font-size:16px;vertical-align:middle">check</span> Done';
                                if (p.name === "openrouter") {
                                    document.getElementById("ob-api-key").value = "";
                                    document.getElementById("ob-api-key").placeholder = "Authenticated via OAuth";
                                }
                                return true;
                            }
                            if (job.status === "error") {
                                statusEl.innerHTML = '<span style="color:#f87171">Authentication failed</span>';
                                btn.disabled = false;
                                btn.innerHTML = p.name === "openrouter" ? '<span class="material-icons-round" style="font-size:16px;vertical-align:middle">lock_open</span> Retry' : '<span class="material-icons-round" style="font-size:16px;vertical-align:middle">lock_open</span> Retry';
                                return true;
                            }
                            return false;
                        });
                    }
                } catch (e) {
                    statusEl.innerHTML = '<span style="color:#f87171">Error: ' + escapeHtml(String(e)) + '</span>';
                    btn.disabled = false;
                    btn.innerHTML = p.name === "openrouter" ? '<span class="material-icons-round" style="font-size:16px;vertical-align:middle">lock_open</span> Retry' : '<span class="material-icons-round" style="font-size:16px;vertical-align:middle">lock_open</span> Retry';
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
            document.getElementById("ob-api-key").placeholder = providerKeyPlaceholder(p.name);
        }
    }
}

function _obSetupStep3() {
    const p = _ob.provider;
    if (!p) return;
    document.getElementById("ob-model-hint").textContent = "Provider: " + p.label + ". Check the provider docs for available models.";
    const modelInput = document.getElementById("ob-model-input");
    const currentModel = (_ob.currentProvider === p.name) ? _obNormalizeModelValue(p.name, _ob.currentModel) : "";
    const defaultModel = p.name === "openrouter"
        ? "google/gemma-4-31b-it:free"
        : _obNormalizeModelValue(p.name, p.default_model);
    if (!modelInput.value || _ob._lastModelProvider !== p.name) {
        _ob._lastModelProvider = p.name;
        modelInput.value = currentModel || defaultModel;
    }

    const wrapper = document.getElementById("ob-model-selector-wrapper");
    const menu = document.getElementById("ob-model-dropdown-menu");
    const list = document.getElementById("ob-model-list-container");

    // Load models
    ensureAvailableModels(list).then(() => {
        _obRenderModelDropdown(modelInput.value);
    });

    if (wrapper._closeDropdownListener) {
        document.removeEventListener("click", wrapper._closeDropdownListener);
    }
    const closeDropdown = (e) => {
        if (!wrapper.contains(e.target)) {
            menu.style.display = "none";
        }
    };
    wrapper._closeDropdownListener = closeDropdown;
    document.addEventListener("click", closeDropdown);

    modelInput.onfocus = () => {
        _obRenderModelDropdown(modelInput.value);
        menu.style.display = "block";
    };

    modelInput.oninput = () => {
        _obRenderModelDropdown(modelInput.value);
        menu.style.display = "block";
    };
}

function _obRenderModelDropdown(query) {
    const p = _ob.provider;
    if (!p) return;
    const list = document.getElementById("ob-model-list-container");
    if (!list) return;

    let filtered = filterModelsByQuery(query);
    filtered = filtered.filter(m => m.provider === p.name);

    const currentModelId = _obNormalizeModelValue(p.name, document.getElementById("ob-model-input").value);
    const onboardModels = filtered.map(m => ({
        ...m,
        id: _obNormalizeModelValue(p.name, m.raw_id || m.id),
    }));

    renderModelList(list, onboardModels, currentModelId, (m) => {
        document.getElementById("ob-model-input").value = m.id;
        document.getElementById("ob-model-dropdown-menu").style.display = "none";
    });
}

function _obSetupStep4() {
    const p = _ob.provider;
    const modelValue = p
        ? _obNormalizeModelValue(p.name, document.getElementById("ob-model-input").value)
        : document.getElementById("ob-model-input").value;
    document.getElementById("ob-sum-provider").textContent = p ? p.label : "\u2014";
    document.getElementById("ob-sum-model").textContent = modelValue || "\u2014";

    const tplSection = document.getElementById("ob-tpl-section");
    const tplList = document.getElementById("ob-tpl-list");
    if (_ob.templates.existing.length > 0) {
        tplSection.style.display = "";
        tplList.innerHTML = "";
        for (const f of _ob.templates.existing) {
            const item = document.createElement("label");
            item.className = "ob-tpl-item";
            const icon = f === "Tasks.md" ? "schedule_send" : "description";
            item.innerHTML = '<input type="checkbox" value="' + f + '"> <span class="material-icons-round" style="font-size:16px;color:var(--text-muted)">' + icon + '</span> ' + f;
            tplList.appendChild(item);
        }
    } else {
        tplSection.style.display = "none";
    }
}

window.obGoStep = function (dir) {
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

window.obSubmit = async function () {
    const btn = document.getElementById("ob-btn-finish");
    btn.style.width = btn.offsetWidth + "px";
    btn.disabled = true;
    btn.innerHTML = '<span class="material-icons-round spin" style="font-size:16px;vertical-align:middle">progress_activity</span> Saving...';
    const modelValue = _ob.provider
        ? _obNormalizeModelValue(_ob.provider.name, document.getElementById("ob-model-input").value)
        : document.getElementById("ob-model-input").value.trim();

    const overwrite = [];
    document.querySelectorAll("#ob-tpl-list input:checked").forEach(cb => overwrite.push(cb.value));

    try {
        const res = await authFetch("/api/onboard/submit", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                provider: _ob.provider.name,
                api_key: document.getElementById("ob-api-key").value.trim(),
                model: modelValue,
                overwrite_templates: overwrite,
            })
        });
        const data = await res.json();
        if (!res.ok) throw data.error || "Setup failed";

        btn.style.width = "";
        closeModal("onboard-modal");
        state.onboardModalShown = false;
        _availableModels = []; // Clear model cache to force refresh
        _hasFetchedModels = false;
        fetchStatus();
        loadHistory();
    } catch (e) {
        btn.style.width = "";
        btn.disabled = false;
        btn.innerHTML = '<span class="material-icons-round" style="font-size:16px;vertical-align:middle">check</span> Finish Setup';
        await shibaDialog("alert", "Error", "Setup failed: " + e, { danger: true });
    }
};
