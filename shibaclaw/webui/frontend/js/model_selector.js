let _availableModels = [];
let _fetchingModelsPromise = null;
let _hasFetchedModels = false;
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
    {
        valueId: "s-hb-model",
        buttonId: "s-hb-model-button",
        displayId: "s-hb-model-display",
        providerId: "s-hb-model-provider",
        menuId: "s-hb-model-menu",
        searchId: "s-hb-model-search",
        listId: "s-hb-model-list",
        emptyLabel: "Same as default model",
        emptyProvider: "Inherits",
        emptyChoiceLabel: "Same as default model",
        emptyChoiceProvider: "Inherits",
        allowEmpty: true,
    },
];
let _settingsModelPickersInitialized = false;

async function fetchModels() {
    try {
        const res = await authFetch("/api/models");
        const data = await res.json();
        if (!res.ok) {
            throw new Error(data.error || "Failed to fetch models");
        }
        if (Array.isArray(data.errors) && data.errors.length) {
            console.warn("Some providers failed to return models", data.errors);
        }
        return data.models || [];
    } catch (e) {
        console.error("Failed to fetch models", e);
        return [];
    }
}

async function ensureAvailableModels(listEl = null) {
    if (_availableModels.length || _hasFetchedModels) {
        return _availableModels;
    }
    if (_fetchingModelsPromise) {
        return _fetchingModelsPromise;
    }
    if (listEl) {
        listEl.innerHTML = '<div style="padding: 10px; text-align: center; color: var(--text-secondary); font-size: 0.85rem;">Loading models...</div>';
    }
    _fetchingModelsPromise = fetchModels().then(models => {
        _availableModels = models || [];
        _hasFetchedModels = true;
        _fetchingModelsPromise = null;
        return _availableModels;
    }).catch(err => {
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
    );
}

function findAvailableModel(modelId) {
    if (!modelId) {
        return null;
    }
    return _availableModels.find(m => m.id === modelId || m.raw_id === modelId) || null;
}

function createModelListItem(model, currentModelId, onSelect) {
    const item = document.createElement("div");
    item.className = "model-item" + (model.id === currentModelId ? " selected" : "");

    const nameEl = document.createElement("span");
    nameEl.className = "model-item-name";
    nameEl.textContent = model.name || model.raw_id || model.id || "";

    const providerEl = document.createElement("span");
    providerEl.className = "model-item-provider";
    providerEl.textContent = model.provider_label || model.provider || "";

    item.appendChild(nameEl);
    item.appendChild(providerEl);
    item.title = [model.raw_id || model.id || "", model.provider_label || model.provider || ""].filter(Boolean).join(" • ");
    item.addEventListener("click", (e) => {
        e.stopPropagation();
        onSelect(model);
    });
    return item;
}

function renderModelList(list, models, currentModelId, onSelect, extraItems = []) {
    list.innerHTML = "";
    const allItems = [...extraItems, ...models];
    if (!allItems.length) {
        list.innerHTML = '<div style="padding: 10px; text-align: center; color: var(--text-secondary); font-size: 0.85rem;">No models found</div>';
        return;
    }
    allItems.forEach(model => list.appendChild(createModelListItem(model, currentModelId, onSelect)));
}

async function updateModelSelectorDisplay(modelId) {
    const display = document.getElementById("active-model-display");
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

    await ensureAvailableModels();
    const match = findAvailableModel(resolvedModelId);
    display.textContent = match ? (match.name || match.raw_id || match.id) : (resolvedModelId || "Default");
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
    const match = findAvailableModel(value);
    display.textContent = match ? (match.name || match.raw_id || match.id) : value;
    provider.textContent = match ? (match.provider_label || match.provider || "") : "Custom";
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

    renderModelList(
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
        extraItems,
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
            search.value = "";
            renderSettingsModelPickerOptions(config);
            search.focus();
        });

        menu.addEventListener("click", (e) => e.stopPropagation());
        search.addEventListener("input", () => renderSettingsModelPickerOptions(config));
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

    btn.addEventListener("click", async (e) => {
        e.stopPropagation();
        const isHidden = menu.style.display === "none";
        if (isHidden) {
            menu.style.display = "flex";
            await ensureAvailableModels(list);
            renderModels(_availableModels);
            search.value = "";
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

    search.addEventListener("input", () => {
        const filtered = filterModelsByQuery(search.value);
        renderModels(filtered);
    });

    function renderModels(models) {
        const currentModelId = state.activeModelId || "";
        renderModelList(list, models, currentModelId, async (model) => {
            state.activeModelId = model.id;
            updateModelSelectorDisplay(model.id);
            menu.style.display = "none";
            if (state.sessionId) {
                await authFetch("/api/sessions/" + encodeURIComponent(state.sessionId), {
                    method: "PATCH",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ model: model.id })
                });
            }
        });
    }
}
document.addEventListener("DOMContentLoaded", () => {
    setupSettingsModelPickers();
    setTimeout(setupModelSelector, 500);
});
