let _providerDrafts = {};
let _savingProvider = false;

function setProviderSaving(saving) {
    _savingProvider = saving;
    document.getElementById("panel-providers")?.querySelectorAll("input, button").forEach(control => {
        control.disabled = saving;
    });
}

const PROVIDER_OAUTH_TYPES = new Set([
    "openai_codex", "github_copilot", "google_gemini_cli", "qwen_oauth", "minimax_portal", "z_ai",
]);

function providerType(name) {
    return name.replace(/[A-Z]/g, letter => "_" + letter.toLowerCase());
}

function providerLabel(name) {
    const labels = {
        custom: "Custom / OpenAI compatible", azure_openai: "Azure OpenAI", openai: "OpenAI",
        openrouter: "OpenRouter", aihubmix: "AiHubMix", siliconflow: "SiliconFlow", xai: "xAI",
        vllm: "vLLM", deepseek: "DeepSeek", dashscope: "DashScope", zhipu: "Zhipu",
        opencode_zen: "OpenCode Zen", opencode_go: "OpenCode Go",
    };
    return labels[name] || name.replaceAll("_", " ").replace(/\b\w/g, letter => letter.toUpperCase());
}

function providerSettingsPatch(ids = Object.keys(_providerDrafts)) {
    const providers = structuredClone(lastSettingsConfig.providers || {});
    const providerEndpoints = structuredClone(lastSettingsConfig.providerEndpoints || {});
    for (const id of ids) {
        if (!_providerDrafts[id]) continue;
        if (id.startsWith("endpoint_")) providerEndpoints[id] = structuredClone(_providerDrafts[id]);
        else providers[id] = structuredClone(_providerDrafts[id]);
    }
    return { providers, providerEndpoints };
}

function validateProviderDrafts(ids = Object.keys(_providerDrafts)) {
    for (const id of ids) {
        const pc = _providerDrafts[id];
        const form = document.getElementById("provider-form-" + id);
        if (form && !form.reportValidity()) return false;
        if (pc?.enabled !== false && !pc?.apiKey && !pc?.apiBase) {
            if (form) {
                const input = form.querySelector(".provider-endpoint-base");
                input.setCustomValidity(t("settings.provider.address_required"));
                input.reportValidity();
                input.setCustomValidity("");
            }
            return false;
        }
    }
    return true;
}

async function saveProviderEndpoint(id) {
    if (_savingProvider || !validateProviderDrafts([id])) return;
    setProviderSaving(true);
    const patch = providerSettingsPatch([id]);
    const status = document.getElementById("provider-save-status");
    status.textContent = t("settings.provider.saving");
    try {
        const response = await authFetch("/api/settings", {
            method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(patch),
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || t("settings.provider.save_failed"));
        const saved = id.startsWith("endpoint_") ? patch.providerEndpoints[id] : patch.providers[id];
        if (saved.apiKey && saved.apiKey !== "***") saved.apiKey = "***";
        lastSettingsConfig.providers = patch.providers;
        lastSettingsConfig.providerEndpoints = patch.providerEndpoints;
        delete _providerDrafts[id];
        renderProviderSettings();
        status.textContent = t("settings.provider.saved");
        if (typeof resetAvailableModelsCache === "function") resetAvailableModelsCache();
        if (typeof refreshSettingsModelPickers === "function") void refreshSettingsModelPickers();
        if (typeof fetchStatus === "function") void fetchStatus();
    } catch (error) {
        status.textContent = t("settings.save_error", { err: error.message });
    } finally {
        setProviderSaving(false);
    }
}

function renderProviderSettings() {
    const catalog = document.getElementById("provider-catalog");
    const list = document.getElementById("providers-list");
    if (!catalog || !list) return;
    catalog.replaceChildren();
    list.replaceChildren();
    const saved = lastSettingsConfig;
    const entries = new Map();
    for (const [id, pc] of Object.entries(saved.providers || {})) {
        if (!PROVIDER_OAUTH_TYPES.has(providerType(id)) && (pc.apiKey || pc.apiBase || pc.name)) entries.set(id, pc);
    }
    for (const [id, pc] of Object.entries(saved.providerEndpoints || {})) entries.set(id, pc);
    for (const [id, pc] of Object.entries(_providerDrafts)) entries.set(id, pc);

    const search = document.getElementById("provider-search");
    const filterCatalog = () => {
        const query = search.value.trim().toLowerCase();
        for (const button of catalog.children) button.hidden = !button.textContent.toLowerCase().includes(query);
    };
    search.oninput = filterCatalog;
    for (const key of Object.keys(saved.providers || {})) {
        const type = providerType(key);
        if (PROVIDER_OAUTH_TYPES.has(type)) continue;
        const button = document.createElement("button");
        button.type = "button";
        button.className = "provider-catalog-item";
        const label = providerLabel(type);
        button.innerHTML = `<span>${escapeHtml(label)}</span><span class="material-icons-round" aria-hidden="true">add</span>`;
        button.setAttribute("aria-label", t("settings.provider.add_named", { name: label }));
        button.addEventListener("click", () => {
            const id = "endpoint_" + Array.from(crypto.getRandomValues(new Uint8Array(16)), byte => byte.toString(16).padStart(2, "0")).join("");
            const bases = { custom: "http://localhost:8000/v1", vllm: "http://localhost:8000/v1", ollama: "http://localhost:11434" };
            _providerDrafts[id] = { provider: type, name: label, enabled: true, apiBase: bases[type] || null };
            renderProviderSettings();
            const form = document.getElementById("provider-form-" + id);
            form?.querySelector(".provider-endpoint-name")?.focus();
            form?.scrollIntoView({ block: "nearest", behavior: "smooth" });
        });
        catalog.appendChild(button);
    }
    filterCatalog();

    for (const [id, pc] of entries) {
        const type = pc.provider || providerType(id);
        const label = providerLabel(type);
        const dirty = !!_providerDrafts[id];
        const card = document.createElement("details");
        card.className = "provider-endpoint-card";
        card.open = dirty;
        card.innerHTML = `
            <summary class="provider-endpoint-summary">
                <span class="provider-endpoint-heading"><strong>${escapeHtml(pc.name || label)}</strong>
                    <span class="provider-endpoint-address">${escapeHtml(pc.apiBase || label)}</span></span>
                <span class="provider-tile-badge ${pc.enabled !== false ? "on" : "off"}">${escapeHtml(dirty ? t("settings.provider.unsaved") : t(pc.enabled !== false ? "settings.provider.active" : "settings.provider.disabled"))}</span>
                <span class="material-icons-round" aria-hidden="true">expand_more</span>
            </summary>
            <form id="provider-form-${escapeHtml(id)}" class="provider-endpoint-form">
                <div class="field-row"><label for="provider-name-${escapeHtml(id)}">${escapeHtml(t("settings.provider.name"))}</label>
                    <input id="provider-name-${escapeHtml(id)}" class="form-input provider-endpoint-name" type="text" value="${escapeHtml(pc.name || label)}" required></div>
                <div class="field-row"><label for="provider-base-${escapeHtml(id)}">${escapeHtml(t("settings.provider.api_base"))}</label>
                    <input id="provider-base-${escapeHtml(id)}" class="form-input provider-endpoint-base" type="url" value="${escapeHtml(pc.apiBase || "")}" placeholder="${escapeHtml(t("settings.provider.api_base_ph"))}"></div>
                <div class="field-row"><label for="provider-key-${escapeHtml(id)}">${escapeHtml(t("settings.provider.key_optional"))}</label>
                    <input id="provider-key-${escapeHtml(id)}" class="form-input provider-endpoint-key" type="password" autocomplete="new-password" value="${escapeHtml(pc.apiKey || "")}" placeholder="${escapeHtml(providerKeyPlaceholder(type))}"></div>
                <div class="provider-endpoint-actions">
                    <label class="provider-enabled-label"><input class="provider-endpoint-enabled" type="checkbox" role="switch" ${pc.enabled !== false ? "checked" : ""}> ${escapeHtml(t("settings.provider.enabled"))}</label>
                    <button class="btn-secondary provider-cancel" type="button">${escapeHtml(t("common.cancel"))}</button>
                    <button class="btn-primary provider-save" type="submit">${escapeHtml(t("settings.provider.save"))}</button>
                </div>
            </form>`;
        const form = card.querySelector("form");
        const markDirty = () => {
            _providerDrafts[id] = {
                ...pc,
                name: form.querySelector(".provider-endpoint-name").value.trim(),
                apiBase: form.querySelector(".provider-endpoint-base").value.trim() || null,
                apiKey: form.querySelector(".provider-endpoint-key").value.trim(),
                enabled: form.querySelector(".provider-endpoint-enabled").checked,
            };
            card.querySelector(".provider-tile-badge").textContent = t("settings.provider.unsaved");
            document.getElementById("provider-save-status").textContent = "";
        };
        form.addEventListener("input", markDirty);
        form.addEventListener("submit", event => { event.preventDefault(); markDirty(); void saveProviderEndpoint(id); });
        form.querySelector(".provider-cancel").addEventListener("click", () => { delete _providerDrafts[id]; renderProviderSettings(); });
        list.appendChild(card);
    }
    if (!entries.size) {
        const empty = document.createElement("p");
        empty.className = "provider-help";
        empty.textContent = t("settings.provider.empty");
        list.appendChild(empty);
    }
    const active = [...entries].filter(([id]) => {
        const pc = id.startsWith("endpoint_") ? saved.providerEndpoints?.[id] : saved.providers?.[id];
        return pc && pc.enabled !== false;
    }).length;
    document.getElementById("provider-stats").textContent = t("settings.provider.active_count", { n: active });
}
