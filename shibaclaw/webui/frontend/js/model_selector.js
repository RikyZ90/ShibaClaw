let _availableModels = [];
let _modelProviders = [];
let _fetchingModelsPromise = null;
let _hasFetchedModels = false;
let _modelCacheVersion = 0;
const SETTINGS_MODEL_PICKERS = [
    {
        valueId: "s-agent-model",
        buttonId: "s-agent-model-button",
        displayId: "s-agent-model-display",
        providerId: "s-agent-model-provider",
        menuId: "s-agent-model-menu",
        searchId: "s-agent-model-search",
        listId: "s-agent-model-list",
        emptyLabel: "Select a default model",
        emptyProvider: "New sessions",
        emptyChoiceLabel: null,
        emptyChoiceProvider: null,
        allowEmpty: false,
    },
    {
        valueId: "s-agent-consolidationModel",
        buttonId: "s-agent-consolidationModel-button",
        displayId: "s-agent-consolidationModel-display",
        providerId: "s-agent-consolidationModel-provider",
        menuId: "s-agent-consolidationModel-menu",
        searchId: "s-agent-consolidationModel-search",
        listId: "s-agent-consolidationModel-list",
        emptyLabel: "Same as default session model",
        emptyProvider: "Inherits",
        emptyChoiceLabel: "Same as default session model",
        emptyChoiceProvider: "Inherits",
        allowEmpty: true,
    },
];
let _settingsModelPickersInitialized = false;

async function fetchModels(providerId = "") {
    try {
        const res = await authFetch("/api/models" + (providerId ? "?provider=" + encodeURIComponent(providerId) : ""));
        const data = await res.json();
        if (!res.ok) {
            throw new Error(data.error || "Failed to fetch models");
        }
        if (Array.isArray(data.errors) && data.errors.length) {
            console.warn("Some providers failed to return models", data.errors);
        }
        return data;
    } catch (e) {
        console.error("Failed to fetch models", e);
        return { models: [], providers: [] };
    }
}

function resetAvailableModelsCache() {
    _modelCacheVersion++;
    _availableModels = [];
    _modelProviders = [];
    _hasFetchedModels = false;
    _fetchingModelsPromise = null;
}
window.resetAvailableModelsCache = resetAvailableModelsCache;

async function ensureAvailableModels(listEl = null) {
    if (_availableModels.length || _hasFetchedModels) {
        return _availableModels;
    }
    if (_fetchingModelsPromise) {
        return _fetchingModelsPromise;
    }
    if (listEl) {
        listEl.innerHTML = `<div style="padding: 10px; text-align: center; color: var(--text-secondary); font-size: 0.85rem;">${escapeHtml(typeof t === "function" ? t("chat.loading_models") : "Loading models...")}</div>`;
    }
    const version = _modelCacheVersion;
    _fetchingModelsPromise = fetchModels().then(data => {
        if (version !== _modelCacheVersion) return _availableModels;
        _availableModels = data.models || [];
        _modelProviders = Array.isArray(data.providers) ? data.providers : [...new Map(_availableModels.map(model => [model.provider, {
            id: model.provider, name: model.provider_label || model.provider,
        }])).values()];
        _hasFetchedModels = true;
        _fetchingModelsPromise = null;
        return _availableModels;
    }).catch(err => {
        if (version !== _modelCacheVersion) return _availableModels;
        _hasFetchedModels = true;
        _fetchingModelsPromise = null;
        return [];
    });
    return _fetchingModelsPromise;
}

function filterModelsByQuery(query) {
    const q = (query || "").trim().toLowerCase();
    if (!q) {
        return _availableModels.slice();
    }
    return _availableModels.filter(m =>
        (m.name || "").toLowerCase().includes(q)
        || (m.raw_id || m.id || "").toLowerCase().includes(q)
        || (m.provider_label || "").toLowerCase().includes(q)
        || (m.provider || "").toLowerCase().includes(q)
        || modelProviderDescription(m).toLowerCase().includes(q)
    );
}

function findAvailableModel(modelId) {
    if (!modelId) {
        return null;
    }
    const cleanId = String(modelId).trim();
    const exactId = _availableModels.find(m => m.id === cleanId);
    if (exactId) return exactId;
    const prefix = cleanId.split("/")[0];
    if (prefix.startsWith("endpoint_") || _modelProviders.some(provider => provider.id === prefix)) return null;
    const rawMatches = _availableModels.filter(m => m.raw_id === cleanId);
    return rawMatches.length === 1 ? rawMatches[0] : null;
}

function modelProviderDescription(model) {
    const source = _modelProviders.find(provider => provider.id === model.provider);
    return source ? [source.name || source.id, source.api_base || source.apiBase].filter(Boolean).join(" • ")
        : model.provider_label || model.provider || "";
}

function customModelChoices(query) {
    const typedId = (query || "").trim();
    if (!typedId) return [];
    const explicitSource = _modelProviders.find(provider => typedId.startsWith(provider.id + "/"));
    const rawId = explicitSource ? typedId.slice(explicitSource.id.length + 1) : typedId;
    if (!rawId) return [];
    const sources = explicitSource ? [explicitSource] : _modelProviders;
    return sources.filter(source => !_availableModels.some(model => model.id === `${source.id}/${rawId}`)).map(source => ({
        id: `${source.id}/${rawId}`,
        raw_id: rawId,
        name: typeof t === "function" ? t("chat.use_custom_model", { model: rawId }) : `Use “${rawId}”`,
        provider: source.id,
        provider_label: source.name || source.id,
    }));
}

function modelForDisplay(modelId) {
    const match = findAvailableModel(modelId);
    if (match) return match;
    const source = _modelProviders.find(provider => String(modelId || "").startsWith(provider.id + "/"));
    return source ? { id: modelId, raw_id: modelId.slice(source.id.length + 1), provider: source.id } : null;
}

function createModelListItem(model, currentModelId, onSelect) {
    const item = document.createElement("div");
    item.className = "model-item" + (model.id === currentModelId ? " selected" : "");
    item.tabIndex = 0;
    item.setAttribute("role", "button");

    const nameEl = document.createElement("span");
    nameEl.className = "model-item-name";
    nameEl.textContent = model.name || model.raw_id || model.id || "";

    const providerEl = document.createElement("span");
    providerEl.className = "model-item-provider";
    providerEl.textContent = modelProviderDescription(model);

    item.appendChild(nameEl);
    item.appendChild(providerEl);
    item.title = [model.raw_id || model.id || "", modelProviderDescription(model)].filter(Boolean).join(" • ");
    item.addEventListener("click", (e) => {
        e.stopPropagation();
        onSelect(model);
    });
    item.addEventListener("keydown", (e) => {
        if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            e.stopPropagation();
            onSelect(model);
        }
    });
    return item;
}

function renderModelList(list, models, currentModelId, onSelect, extraItems = []) {
    list.innerHTML = "";
    const allItems = [...extraItems, ...models];
    if (!allItems.length) {
        list.innerHTML = `<div style="padding: 10px; text-align: center; color: var(--text-secondary); font-size: 0.85rem;">${escapeHtml(typeof t === "function" ? t("chat.no_models") : "No models found")}</div>`;
        return;
    }
    allItems.forEach(model => list.appendChild(createModelListItem(model, currentModelId, onSelect)));
}

function renderModelPicker(list, models, currentModelId, onSelect, query, extraItems = [], searchInput = null) {
    const scopedSource = _modelProviders.find(source => source.id === list.dataset.providerId);
    const q = (query || "").trim().toLowerCase();
    const matchingSources = !scopedSource && searchInput ? _modelProviders.filter(source => {
        const custom = source.provider === "custom" || source.id.startsWith("endpoint_");
        const matches = q ? [source.name, source.id, source.api_base, source.apiBase, source.provider].some(value => (value || "").toLowerCase().includes(q)) : custom;
        return matches && (custom || !models.some(model => model.provider === source.id));
    }) : [];
    const sourceNameQuery = !scopedSource && _modelProviders.some(source => [source.name, source.id].some(value => (value || "").toLowerCase() === q));
    const choices = sourceNameQuery ? [] : customModelChoices(query).filter(choice => !scopedSource || choice.provider === scopedSource.id);
    if (scopedSource) models = models.filter(model => model.provider === scopedSource.id);
    list.classList.add("model-picker-list");
    list.replaceChildren();
    if (extraItems.length) {
        const defaults = document.createElement("div");
        defaults.className = "model-picker-defaults";
        extraItems.forEach(model => defaults.appendChild(createModelListItem(model, currentModelId, onSelect)));
        list.appendChild(defaults);
    }
    if (scopedSource && searchInput) {
        const back = document.createElement("button");
        back.type = "button";
        back.className = "model-picker-back model-source-back";
        back.textContent = typeof t === "function" ? t("chat.back_to_models") : "Back to models";
        back.addEventListener("click", event => {
            event.stopPropagation();
            const previousQuery = list.dataset.providerQuery || "";
            delete list.dataset.providerId;
            delete list.dataset.providerQuery;
            searchInput.value = previousQuery;
            searchInput.placeholder = typeof t === "function" ? t("common.search_models") : "Search models...";
            renderModelPicker(list, filterModelsByQuery(previousQuery), currentModelId, onSelect, previousQuery, extraItems, searchInput);
            searchInput.focus();
        });
        const heading = document.createElement("div");
        heading.className = "model-custom-heading";
        heading.textContent = modelProviderDescription({ provider: scopedSource.id });
        list.append(back, heading);
    }
    const results = document.createElement("div");
    results.className = "model-picker-results";
    results.tabIndex = 0;
    results.setAttribute("role", "region");
    results.setAttribute("aria-label", typeof t === "function" ? t("chat.model_results") : "Model results");
    if (matchingSources.length) {
        const heading = document.createElement("div");
        heading.className = "model-custom-heading";
        heading.textContent = typeof t === "function" ? t("chat.model_endpoints") : "Endpoints";
        results.appendChild(heading);
    }
    for (const source of matchingSources) {
        const item = createModelListItem({ id: source.id, name: source.name || source.id, provider: source.id }, "", async () => {
            list.dataset.providerId = source.id;
            list.dataset.providerQuery = query;
            searchInput.value = "";
            searchInput.placeholder = typeof t === "function" ? t("chat.model_id_for", { provider: source.name || source.id }) : `Model ID for ${source.name || source.id}`;
            renderModelPicker(list, _availableModels, currentModelId, onSelect, "", extraItems, searchInput);
            searchInput.focus();
            const version = _modelCacheVersion;
            const request = Symbol();
            list._providerRequest = request;
            const data = await fetchModels(source.id);
            if (version !== _modelCacheVersion || list.dataset.providerId !== source.id || list._providerRequest !== request) return;
            _availableModels = _availableModels.filter(model => model.provider !== source.id).concat(data.models || []);
            renderModelPicker(list, filterModelsByQuery(searchInput.value), currentModelId, onSelect, searchInput.value, extraItems, searchInput);
        });
        item.classList.add("model-source-choice");
        item.querySelector(".model-item-provider").textContent = source.api_base || source.apiBase || source.provider || source.id;
        results.appendChild(item);
    }
    if (scopedSource && !q && !models.length) {
        const hint = document.createElement("div");
        hint.className = "model-custom-heading";
        hint.textContent = typeof t === "function" ? t("chat.enter_model_id") : "No models loaded. Enter a model ID to use this endpoint.";
        results.appendChild(hint);
    } else if (!matchingSources.length && (models.length || !choices.length)) {
        renderModelList(results, models, currentModelId, onSelect);
    } else {
        if (models.length) {
            const heading = document.createElement("div");
            heading.className = "model-custom-heading";
            heading.textContent = typeof t === "function" ? t("chat.model_results") : "Model results";
            results.appendChild(heading);
        }
        models.forEach(model => results.appendChild(createModelListItem(model, currentModelId, onSelect)));
    }
    list.appendChild(results);
    if (!choices.length) return;

    const action = document.createElement("button");
    action.type = "button";
    action.className = "model-custom-action";
    action.textContent = typeof t === "function" ? t("chat.use_custom_model", { model: choices[0].raw_id }) : `Use “${choices[0].raw_id}”`;
    action.title = typeof t === "function" ? t("chat.choose_model_provider") : "Choose a provider";
    action.addEventListener("click", event => {
        event.stopPropagation();
        if (choices.length === 1) {
            onSelect(choices[0]);
            return;
        }
        const back = document.createElement("button");
        back.type = "button";
        back.className = "model-picker-back";
        back.textContent = typeof t === "function" ? t("chat.back_to_models") : "Back to models";
        back.addEventListener("click", event => {
            event.stopPropagation();
            renderModelPicker(list, models, currentModelId, onSelect, query, extraItems, searchInput);
            list.querySelector(".model-custom-action").focus();
        });
        const heading = document.createElement("div");
        heading.className = "model-custom-heading";
        heading.textContent = typeof t === "function" ? t("chat.choose_model_provider") : "Choose a provider";
        results.replaceChildren();
        results.setAttribute("aria-label", heading.textContent);
        for (const choice of choices) {
            const item = createModelListItem(choice, currentModelId, onSelect);
            item.classList.add("model-provider-choice");
            item.querySelector(".model-item-name").textContent = choice.provider_label;
            const source = _modelProviders.find(provider => provider.id === choice.provider);
            const detail = item.querySelector(".model-item-provider");
            const duplicateName = _modelProviders.some(other => other.id !== source.id && other.name === source.name);
            detail.textContent = source.api_base || source.apiBase || (duplicateName ? source.id : "");
            detail.hidden = !detail.textContent;
            results.appendChild(item);
        }
        const defaults = list.querySelector(".model-picker-defaults");
        list.replaceChildren(...[defaults, back, heading, results].filter(Boolean));
        results.querySelector(".model-item")?.focus();
    });
    list.appendChild(action);
}

let _activeSessionReasoningEffort = null;

function checkModelSupportsReasoning(modelId) {
    if (!modelId) return false;
    const model = findAvailableModel(modelId);
    if (model && typeof model.supports_reasoning === "boolean") {
        return model.supports_reasoning;
    }
    const mid = String(modelId).toLowerCase().trim();
    const raw = mid.split("/").pop();
    const base = raw.split(":")[0];

    // 1. OpenAI o-series & Azure/OpenRouter o-deployments (o1, o3, o4)
    if (base.startsWith("o1") || base.startsWith("o3") || base.startsWith("o4") || base.includes("-o1") || base.includes("o1-") || base.includes("-o3") || base.includes("o3-") || base.includes("-o4") || base.includes("o4-")) {
        return true;
    }
    // 2. Anthropic Claude 3.7+
    if (base.includes("claude-3-7") || base.includes("claude-3.7") || base.includes("claude-4")) {
        return true;
    }
    // 3. Gemini thinking models
    if (base.includes("thinking") || base.includes("gemini-2.5") || base.includes("gemini-3")) {
        return true;
    }
    // 4. DeepSeek R1 / Reasoner models
    if (base.includes("deepseek-r1") || base.includes("reasoner") || base.includes("-r1") || base.includes("r1-") || raw.includes("r1:") || base === "r1") {
        return true;
    }
    // 5. Qwen QwQ / QvQ
    if (base.includes("qwq") || base.includes("qvq")) {
        return true;
    }
    // 6. Grok 3 / xAI
    if (base.includes("grok-3") || base.includes("grok-beta")) {
        return true;
    }
    // 7. Kimi / Moonshot
    if (base.includes("kimi-k1.5") || base.includes("kimi-k2") || (base.includes("kimi") && (base.includes("1.5") || base.includes("2")))) {
        return true;
    }
    // 8. GLM zero
    if (base.includes("glm-4-zero") || base.includes("glm-zero")) {
        return true;
    }
    // 9. Generic open reasoning models & keywords
    if (base.includes("marco-o1") || base.includes("sky-t1") || base.includes("smallthinker") || base.includes("reasoning") || base.includes("think") || base.includes("thought")) {
        return true;
    }

    return false;
}

function reasoningEffortLabel(effort) {
    const normalized = String(effort || "").toLowerCase();
    if (normalized === "low") return typeof t === "function" ? t("chat.effort_low") : "Low";
    if (normalized === "medium") return typeof t === "function" ? t("chat.effort_medium") : "Medium";
    if (normalized === "high") return typeof t === "function" ? t("chat.effort_high") : "High";
    if (normalized === "xhigh") return "Extra High";
    return normalized.replace(/[_-]+/g, " ").replace(/\b\w/g, char => char.toUpperCase());
}

function updateReasoningSelectorDisplay(reasoningEffort = undefined, modelId = null) {
    if (typeof reasoningEffort !== "undefined") {
        _activeSessionReasoningEffort = reasoningEffort;
    }
    const currentModel = modelId || state.activeModelId || "";
    const btn = document.getElementById("btn-reasoning-select");
    const display = document.getElementById("active-reasoning-display");
    const menu = document.getElementById("reasoning-dropdown-menu");
    const list = document.getElementById("reasoning-dropdown-list");
    if (!display || !btn) return;

    const supports = checkModelSupportsReasoning(currentModel);
    if (!supports) {
        display.textContent = typeof t === "function" ? t("chat.effort_na") : "Effort: N/A";
        btn.title = typeof t === "function" ? t("chat.effort_unsupported") : "Reasoning effort not supported for current model";
        btn.classList.add("disabled");
        btn.style.opacity = "0.5";
        btn.style.cursor = "not-allowed";
        if (menu) menu.style.display = "none";
        return;
    }

    btn.classList.remove("disabled");
    btn.style.opacity = "";
    btn.style.cursor = "";
    btn.title = typeof t === "function" ? t("chat.reasoning_title") : "Change reasoning effort for active session";

    let effortStr = _activeSessionReasoningEffort ? String(_activeSessionReasoningEffort).toLowerCase() : "";
    const currentModelEntry = findAvailableModel(currentModel);
    const supportedEfforts = currentModelEntry && currentModelEntry.reasoning_efforts;
    if (effortStr && Array.isArray(supportedEfforts) && !supportedEfforts.includes(effortStr)) {
        effortStr = "";
    }
    let label = typeof t === "function" ? t("chat.effort_default") : "Default";
    if (effortStr) label = reasoningEffortLabel(effortStr);

    display.textContent = (typeof t === "function" ? t("chat.effort_prefix") : "Effort: ") + label;

    if (list) {
        renderReasoningDropdownList(list, effortStr, currentModel);
    }
}

function renderReasoningDropdownList(container, currentEffort, modelId = null) {
    container.innerHTML = "";
    const model = findAvailableModel(modelId || state.activeModelId);
    const modelEfforts = model && Array.isArray(model.reasoning_efforts) && model.reasoning_efforts.length
        ? model.reasoning_efforts
        : ["low", "medium", "high"];
    const options = [
        { value: "", label: typeof t === "function" ? t("chat.effort_default") : "Default", desc: typeof t === "function" ? t("chat.effort_default_desc") : "Use provider default effort" },
        ...modelEfforts.map(effort => ({
            value: String(effort).toLowerCase(),
            label: reasoningEffortLabel(effort),
            desc: `Reasoning effort: ${reasoningEffortLabel(effort)}`
        }))
    ];

    options.forEach(opt => {
        const item = document.createElement("div");
        const isSelected = (opt.value === currentEffort) || (!opt.value && !currentEffort);
        item.className = "model-item" + (isSelected ? " selected" : "");
        item.title = opt.desc;
        
        const nameEl = document.createElement("span");
        nameEl.className = "model-item-name";
        nameEl.textContent = opt.label;

        item.appendChild(nameEl);

        if (isSelected) {
            const checkEl = document.createElement("span");
            checkEl.className = "material-icons-round composer-menu-check";
            checkEl.textContent = "check";
            item.appendChild(checkEl);
        }

        item.addEventListener("click", async (e) => {
            e.stopPropagation();
            const val = opt.value || null;
            _activeSessionReasoningEffort = val;
            updateReasoningSelectorDisplay(val, state.activeModelId);
            const menu = document.getElementById("reasoning-dropdown-menu");
            if (menu) menu.style.display = "none";

            if (state.sessionId) {
                try {
                    await authFetch("/api/sessions/" + encodeURIComponent(state.sessionId), {
                        method: "PATCH",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ reasoning_effort: val })
                    });
                } catch (err) {
                    console.error("Failed to update session reasoning effort", err);
                }
            }
        });

        container.appendChild(item);
    });
}

function positionComposerMenu(button, menu, preferredWidth = 420) {
    if (window.matchMedia("(max-width: 768px)").matches) {
        ["left", "width", "max-height"].forEach(name => menu.style.removeProperty(name));
        return;
    }
    const anchor = button.getBoundingClientRect();
    const wrapper = menu.parentElement.getBoundingClientRect();
    const width = Math.min(preferredWidth, window.innerWidth - 24);
    const left = Math.max(12, Math.min(anchor.left, window.innerWidth - width - 12));
    menu.style.left = `${left - wrapper.left}px`;
    menu.style.width = `${width}px`;
    menu.style.maxHeight = `${Math.max(80, anchor.top - 20)}px`;
}

function openComposerMenu(button, menu, preferredWidth) {
    document.querySelectorAll(".input-actions .model-dropdown-menu").forEach(other => {
        if (other !== menu) other.style.display = "none";
    });
    if (typeof closeProfileDropdown === "function") closeProfileDropdown();
    menu.style.display = "flex";
    positionComposerMenu(button, menu, preferredWidth);
}

function setupReasoningSelector() {
    const btn = document.getElementById("btn-reasoning-select");
    const menu = document.getElementById("reasoning-dropdown-menu");
    if (!btn || !menu) return;

    btn.addEventListener("click", (e) => {
        e.stopPropagation();
        if (btn.classList.contains("disabled")) return;
        const isHidden = menu.style.display === "none";
        if (isHidden) {
            openComposerMenu(btn, menu, 220);
            updateReasoningSelectorDisplay(_activeSessionReasoningEffort, state.activeModelId);
        } else {
            menu.style.display = "none";
        }
    });

    document.addEventListener("click", (e) => {
        if (!menu.contains(e.target) && e.target !== btn && !btn.contains(e.target)) {
            menu.style.display = "none";
        }
    });
}

window.checkModelSupportsReasoning = checkModelSupportsReasoning;
window.updateReasoningSelectorDisplay = updateReasoningSelectorDisplay;

async function updateModelSelectorDisplay(modelId) {
    const display = document.getElementById("active-model-display");
    const btn = document.getElementById("btn-model-select");
    if (!display) return;
    let resolvedModelId = modelId;
    if (!resolvedModelId) {
        try {
            const cfgRes = await authFetch("/api/settings");
            const cfg = await cfgRes.json();
            resolvedModelId = cfg.agents?.defaults?.model || "";
        } catch (e) { }
    }

    state.activeModelId = resolvedModelId || "";
    state.modelOverrideId = modelId || "";

    await ensureAvailableModels();
    const match = modelForDisplay(resolvedModelId);
    const fullName = match ? (match.name || match.raw_id || match.id) : (resolvedModelId || "Default");
    display.textContent = modelId ? fullName : (typeof t === "function" ? t("common.default") : "Default");

    if (btn) {
        const providerText = match ? ` (${modelProviderDescription(match)})` : "";
        const rawIdText = match && match.raw_id && match.raw_id !== fullName ? ` • ${match.raw_id}` : "";
        btn.title = typeof t === "function" ? t("chat.active_model", { name: `${fullName}${providerText}${rawIdText}` }) : `Active Model: ${fullName}${providerText}${rawIdText}`;
    }

    updateReasoningSelectorDisplay(_activeSessionReasoningEffort, resolvedModelId);
    if (typeof refreshTokenBadge === "function") {
        refreshTokenBadge();
    }
}


function closeSettingsModelMenus(exceptMenu = null) {
    SETTINGS_MODEL_PICKERS.forEach(cfg => {
        const menu = document.getElementById(cfg.menuId);
        if (menu && menu !== exceptMenu) {
            menu.style.display = "none";
        }
    });
}

async function updateSettingsModelPickerDisplay(config) {
    const input = document.getElementById(config.valueId);
    const display = document.getElementById(config.displayId);
    const provider = document.getElementById(config.providerId);
    if (!input || !display || !provider) {
        return;
    }

    const value = input.value.trim();
    if (!value && config.allowEmpty) {
        display.textContent = config.emptyLabel;
        provider.textContent = config.emptyProvider;
        provider.classList.add("settings-model-button-provider-placeholder");
        return;
    }
    if (!value) {
        display.textContent = config.emptyLabel;
        provider.textContent = config.emptyProvider;
        provider.classList.add("settings-model-button-provider-placeholder");
        return;
    }

    await ensureAvailableModels();
    const match = modelForDisplay(value);
    display.textContent = match ? (match.name || match.raw_id || match.id) : value;
    provider.textContent = match ? modelProviderDescription(match) : "Custom";
    provider.classList.toggle("settings-model-button-provider-placeholder", !match);
}

async function refreshSettingsModelPickers() {
    for (const config of SETTINGS_MODEL_PICKERS) {
        await updateSettingsModelPickerDisplay(config);
    }
}

function renderSettingsModelPickerOptions(config) {
    const list = document.getElementById(config.listId);
    const search = document.getElementById(config.searchId);
    const input = document.getElementById(config.valueId);
    if (!list || !search || !input) {
        return;
    }

    const models = filterModelsByQuery(search.value);
    const extraItems = [];
    if (config.allowEmpty) {
        extraItems.push({
            id: "",
            raw_id: "",
            name: config.emptyChoiceLabel,
            provider_label: config.emptyChoiceProvider,
            provider: "",
        });
    }

    renderModelPicker(
        list,
        models,
        input.value.trim(),
        (model) => {
            input.value = model.id || "";
            void updateSettingsModelPickerDisplay(config);
            const menu = document.getElementById(config.menuId);
            if (menu) {
                menu.style.display = "none";
            }
        },
        search.value,
        extraItems,
        search,
    );
}

function setupSettingsModelPickers() {
    if (_settingsModelPickersInitialized) {
        return;
    }

    SETTINGS_MODEL_PICKERS.forEach(config => {
        const button = document.getElementById(config.buttonId);
        const menu = document.getElementById(config.menuId);
        const search = document.getElementById(config.searchId);
        const list = document.getElementById(config.listId);
        if (!button || !menu || !search || !list) {
            return;
        }

        button.addEventListener("click", async (e) => {
            e.stopPropagation();
            const isOpen = menu.style.display === "flex";
            if (isOpen) {
                menu.style.display = "none";
                return;
            }

            closeSettingsModelMenus(menu);
            menu.style.display = "flex";
            await ensureAvailableModels(list);
            delete list.dataset.providerId;
            delete list.dataset.providerQuery;
            search.placeholder = typeof t === "function" ? t("common.search_models") : "Search models...";
            search.value = "";
            renderSettingsModelPickerOptions(config);
            search.focus();
        });

        menu.addEventListener("click", (e) => e.stopPropagation());
        search.addEventListener("input", debounce(() => renderSettingsModelPickerOptions(config), 250));
    });

    document.addEventListener("click", () => closeSettingsModelMenus());
    _settingsModelPickersInitialized = true;
}

function setupModelSelector() {
    const btn = document.getElementById("btn-model-select");
    const menu = document.getElementById("model-dropdown-menu");
    const search = document.getElementById("model-search-input");
    const list = document.getElementById("model-list-container");
    if (!btn || !menu) return;

    function repositionOpenMenu() {
        for (const [buttonId, menuId, width] of [
            ["btn-model-select", "model-dropdown-menu", 420],
            ["btn-reasoning-select", "reasoning-dropdown-menu", 220],
            ["btn-kb-select", "kb-dropdown-menu", 280],
        ]) {
            const button = document.getElementById(buttonId);
            const dropdown = document.getElementById(menuId);
            if (button && dropdown && dropdown.style.display !== "none") positionComposerMenu(button, dropdown, width);
        }
    }
    window.addEventListener("resize", repositionOpenMenu);
    window.visualViewport?.addEventListener("resize", repositionOpenMenu);

    btn.addEventListener("click", async (e) => {
        e.stopPropagation();
        const isHidden = menu.style.display === "none";
        if (isHidden) {
            openComposerMenu(btn, menu, 420);
            await ensureAvailableModels(list);
            delete list.dataset.providerId;
            delete list.dataset.providerQuery;
            search.placeholder = typeof t === "function" ? t("common.search_models") : "Search models...";
            search.value = "";
            renderModels(_availableModels);
            positionComposerMenu(btn, menu, 420);
            search.focus();
        } else {
            menu.style.display = "none";
        }
    });

    document.addEventListener("click", (e) => {
        if (!menu.contains(e.target) && e.target !== btn && !btn.contains(e.target)) {
            menu.style.display = "none";
        }
    });

    search.addEventListener("input", debounce(() => {
        const filtered = filterModelsByQuery(search.value);
        renderModels(filtered);
    }, 250));

    function renderModels(models) {
        const currentModelId = state.modelOverrideId || "";
        const defaultChoice = {
            id: "", name: typeof t === "function" ? t("common.default") : "Default",
            provider_label: typeof t === "function" ? t("chat.default_model_desc") : "Use Settings → Agent model",
        };
        renderModelPicker(list, models, currentModelId, async (model) => {
            try {
                if (state.sessionId) {
                    const response = await authFetch("/api/sessions/" + encodeURIComponent(state.sessionId), {
                        method: "PATCH",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ model: model.id || null })
                    });
                    if (!response.ok) {
                        const data = await response.json().catch(() => ({}));
                        throw new Error(data.error || (typeof t === "function" ? t("chat.model_update_failed") : "Failed to update session model"));
                    }
                }
                await updateModelSelectorDisplay(model.id);
                menu.style.display = "none";
            } catch (error) {
                console.error("Failed to update session model", error);
                alert(error.message || String(error));
            }
        }, search.value, [defaultChoice], search);
    }
}
document.addEventListener("DOMContentLoaded", () => {
    setupSettingsModelPickers();
    setTimeout(() => {
        setupModelSelector();
        setupReasoningSelector();
    }, 500);
});


window.updateReasoningSelectorDisplay = updateReasoningSelectorDisplay;
