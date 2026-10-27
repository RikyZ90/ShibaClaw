import assert from 'node:assert/strict';
import test from 'node:test';
import vm from 'node:vm';
import { browserFixture, readFrontend } from './browser-fixture.mjs';

function fixture(saved = {}) {
    const browser = browserFixture();
    const { context, document } = browser;
    const requests = [];
    let uuid = 0;
    let refreshes = 0;
    context.structuredClone = structuredClone;
    context.crypto = { getRandomValues: bytes => bytes.fill(++uuid) };
    context.lastSettingsConfig = { providers: { custom: {} }, providerEndpoints: {}, ...structuredClone(saved) };
    context.providerKeyPlaceholder = () => 'API key';
    context.resetAvailableModelsCache = () => { refreshes++; };
    context.refreshSettingsModelPickers = async () => {};
    context.fetchStatus = async () => {};
    context.authFetch = async (url, options) => {
        requests.push({ url, patch: JSON.parse(options.body) });
        return { ok: true, json: async () => ({}) };
    };
    const add = (id, tag = 'div') => {
        const node = document.createElement(tag);
        node.id = id;
        node.value = '';
        document.body.appendChild(node);
        return node;
    };
    const panel = add('panel-providers');
    for (const id of ['provider-catalog', 'providers-list', 'provider-search', 'provider-stats', 'provider-save-status']) {
        panel.appendChild(add(id, id === 'provider-search' ? 'input' : 'div'));
    }
    const save = add('test-provider-save', 'button');
    save.className = 'provider-save';
    panel.appendChild(save);
    vm.runInContext(readFrontend('js/provider_settings.js'), context);
    const run = code => vm.runInContext(code, context);
    const drafts = () => JSON.parse(run('JSON.stringify(_providerDrafts)'));
    const setDrafts = values => run(`_providerDrafts = ${JSON.stringify(values)};`);
    const event = (node, type) => node.dispatchEvent({ type, stopPropagation() {}, preventDefault() {} });
    return { ...browser, requests, add, run, drafts, setDrafts, event, refreshes: () => refreshes };
}

function loadSettingsSave(f) {
    const panelSource = readFrontend('js/settings_panel.js');
    vm.runInContext(panelSource, f.context);
    const saveSource = panelSource.slice(panelSource.indexOf('window.saveSettings ='));
    for (const [, id] of saveSource.matchAll(/\$\("([^"]+)"\)/g)) {
        if (!f.document.getElementById(id)) f.add(id).value = '1';
    }
    f.context.closeSettingsView = () => {};
    f.context.shibaDialog = async () => {};
    f.context.setTimeout = () => 0;
}

test('adding the same provider twice creates isolated endpoint drafts and snapshots', () => {
    const f = fixture();
    f.context.renderProviderSettings();
    const addCustom = f.document.getElementById('provider-catalog').children[0];
    // The fixture has no HTML parser; keep the real catalog click handler and
    // isolate draft creation from the subsequent card rendering.
    f.context.renderProviderSettings = () => {};
    f.event(addCustom, 'click');
    f.event(addCustom, 'click');
    const [first, second] = Object.keys(f.drafts());
    assert.notEqual(first, second);
    assert.match(first, /^endpoint_[a-f0-9]+$/);
    f.run(`_providerDrafts[${JSON.stringify(first)}].apiKey = 'first-key'; _providerDrafts[${JSON.stringify(first)}].apiBase = 'http://localhost:8001/v1';`);
    f.run(`_providerDrafts[${JSON.stringify(second)}].apiKey = 'second-key'; _providerDrafts[${JSON.stringify(second)}].apiBase = 'http://localhost:8002/v1';`);
    const patch = f.context.providerSettingsPatch();
    assert.equal(patch.providerEndpoints[first].apiKey, 'first-key');
    assert.equal(patch.providerEndpoints[second].apiKey, 'second-key');
    assert.match(patch.providerEndpoints[first].apiBase, /8001/);
    assert.match(patch.providerEndpoints[second].apiBase, /8002/);
    patch.providerEndpoints[first].apiKey = 'snapshot-edited';
    assert.equal(f.drafts()[first].apiKey, 'first-key');
    assert.equal(f.context.lastSettingsConfig.providerEndpoints[first], undefined);
});

test('per-card save persists only its draft, masks its saved key and retains other drafts', async () => {
    const f = fixture({ providerEndpoints: { endpoint_saved: { provider: 'custom', name: 'Saved', apiKey: '***', apiBase: 'http://old/v1' } } });
    f.context.renderProviderSettings = () => {};
    f.setDrafts({
        endpoint_one: { provider: 'custom', name: 'Local', apiKey: 'first-key', apiBase: 'http://localhost:8001/v1', enabled: true },
        endpoint_two: { provider: 'custom', name: 'Local', apiKey: 'second-key', apiBase: 'http://localhost:8002/v1', enabled: true },
    });
    await f.context.saveProviderEndpoint('endpoint_one');
    assert.equal(f.requests.length, 1);
    assert.equal(f.requests[0].url, '/api/settings');
    assert.equal(f.requests[0].patch.providerEndpoints.endpoint_one.apiKey, 'first-key');
    assert.equal(f.requests[0].patch.providerEndpoints.endpoint_saved.apiKey, '***');
    assert.equal(f.requests[0].patch.providerEndpoints.endpoint_two, undefined);
    assert.equal(f.context.lastSettingsConfig.providerEndpoints.endpoint_one.apiKey, '***');
    assert.equal(f.drafts().endpoint_one, undefined);
    assert.equal(f.drafts().endpoint_two.apiKey, 'second-key');
    assert.equal(f.refreshes(), 1);
});

test('editing an existing provider sends its masked key unchanged', async () => {
    const f = fixture({ providers: { custom: { name: 'Existing', apiKey: '***', apiBase: 'http://localhost:8001/v1' } } });
    f.context.renderProviderSettings = () => {};
    f.setDrafts({ custom: { name: 'Renamed', apiKey: '***', apiBase: 'http://localhost:8001/v1', enabled: true } });
    await f.context.saveProviderEndpoint('custom');
    assert.equal(f.requests[0].patch.providers.custom.apiKey, '***');
    assert.equal(f.requests[0].patch.providers.custom.name, 'Renamed');
    assert.equal(f.context.lastSettingsConfig.providers.custom.apiKey, '***');
});

test('failed endpoint save retains the exact draft and leaves saved configuration untouched', async () => {
    const f = fixture();
    f.context.renderProviderSettings = () => { throw new Error('failed saves must not render'); };
    const draft = { provider: 'custom', name: 'Local', apiKey: 'draft-key', apiBase: 'http://localhost:8001/v1', enabled: true };
    f.setDrafts({ endpoint_one: draft });
    f.context.authFetch = async () => ({ ok: false, json: async () => ({ error: 'Cannot persist settings' }) });
    await f.context.saveProviderEndpoint('endpoint_one');
    assert.deepEqual(f.drafts().endpoint_one, draft);
    assert.equal(f.context.lastSettingsConfig.providerEndpoints.endpoint_one, undefined);
    assert.match(f.document.getElementById('provider-save-status').textContent, /Cannot persist settings/);
    assert.equal(f.run('_savingProvider'), false);
    assert.equal(f.document.getElementById('test-provider-save').disabled, false);
    assert.equal(f.refreshes(), 0);
});

test('disabled endpoint saves with no key or base while an enabled empty endpoint is rejected', async () => {
    const f = fixture();
    f.context.renderProviderSettings = () => {};
    f.setDrafts({ endpoint_one: { provider: 'custom', name: 'Inactive', enabled: false, apiKey: '', apiBase: null } });
    assert.equal(f.context.validateProviderDrafts(), true);
    await f.context.saveProviderEndpoint('endpoint_one');
    assert.equal(f.requests.length, 1);
    assert.equal(f.requests[0].patch.providerEndpoints.endpoint_one.enabled, false);
    f.setDrafts({ endpoint_two: { provider: 'custom', name: 'Missing address', enabled: true, apiKey: '', apiBase: null } });
    await f.context.saveProviderEndpoint('endpoint_two');
    assert.equal(f.requests.length, 1);
    assert.ok(f.drafts().endpoint_two);
});

test('whole-settings save includes all pending endpoint and legacy provider drafts', async () => {
    const f = fixture({ providers: { custom: { apiKey: '***', apiBase: 'http://saved/v1' } } });
    loadSettingsSave(f);
    f.setDrafts({
        custom: { name: 'Legacy edited', apiKey: '***', apiBase: 'http://saved/v2' },
        endpoint_one: { provider: 'custom', name: 'Local', apiKey: 'first-key', apiBase: 'http://localhost:8001/v1', enabled: true },
        endpoint_two: { provider: 'custom', name: 'Local', apiKey: 'second-key', apiBase: 'http://localhost:8002/v1', enabled: true },
    });
    await f.context.saveSettings();
    assert.equal(f.requests.length, 1);
    assert.equal(f.requests[0].patch.providers.custom.name, 'Legacy edited');
    assert.equal(f.requests[0].patch.providers.custom.apiKey, '***');
    assert.equal(f.requests[0].patch.providerEndpoints.endpoint_one.apiKey, 'first-key');
    assert.equal(f.requests[0].patch.providerEndpoints.endpoint_two.apiKey, 'second-key');
    assert.equal(f.requests[0].patch.agents.defaults.provider, 'auto');
});

test('Settings Agent manual endpoint selection survives the whole-settings save payload', async () => {
    const endpoint = { provider: 'custom', name: 'Local server', apiKey: '***', apiBase: 'http://localhost:8002/v1', enabled: true };
    const f = fixture({ providerEndpoints: { endpoint_two: endpoint } });
    vm.runInContext(readFrontend('js/model_selector.js'), f.context);
    const config = f.run('SETTINGS_MODEL_PICKERS[0]');
    for (const key of ['valueId', 'displayId', 'providerId', 'menuId', 'searchId', 'listId']) f.add(config[key]);
    const originalFetch = f.context.authFetch;
    f.context.authFetch = async (url, options) => {
        if (!url.startsWith('/api/models')) return originalFetch(url, options);
        return { ok: true, json: async () => ({ models: [], providers: [{ id: 'endpoint_two', provider: 'custom', name: endpoint.name, api_base: endpoint.apiBase }] }) };
    };
    await f.context.ensureAvailableModels();
    const search = f.document.getElementById(config.searchId);
    search.value = 'org/manual-model';
    f.context.renderSettingsModelPickerOptions(config);
    const list = f.document.getElementById(config.listId);
    f.event(list.querySelector('.model-custom-action'), 'click');
    assert.equal(f.document.getElementById(config.valueId).value, 'endpoint_two/org/manual-model');
    loadSettingsSave(f);
    await f.context.saveSettings();
    assert.equal(f.requests.length, 1);
    const patch = f.requests[0].patch;
    assert.equal(patch.agents.defaults.provider, 'auto');
    assert.equal(patch.agents.defaults.model, 'endpoint_two/org/manual-model');
    assert.equal(patch.providerEndpoints.endpoint_two.apiKey, '***');
    assert.equal(patch.providerEndpoints.endpoint_two.apiBase, endpoint.apiBase);
});

test('per-card and whole-settings saves disable endpoint inputs and block overlapping saves', async () => {
    for (const wholeSettings of [false, true]) {
        const f = fixture();
        loadSettingsSave(f);
        f.context.renderProviderSettings = () => {};
        f.setDrafts({ endpoint_one: { provider: 'custom', name: 'Local', apiKey: 'draft-key', apiBase: 'http://localhost:8001/v1', enabled: true } });
        let finish;
        f.context.authFetch = (url, options) => {
            f.requests.push({ url, patch: JSON.parse(options.body) });
            return new Promise(resolve => { finish = resolve; });
        };
        const pending = wholeSettings ? f.context.saveSettings() : f.context.saveProviderEndpoint('endpoint_one');
        assert.equal(f.run('_savingProvider'), true);
        assert.equal(f.document.getElementById('provider-search').disabled, true);
        assert.equal(f.document.getElementById('test-provider-save').disabled, true);
        await f.context.saveProviderEndpoint('endpoint_one');
        await f.context.saveSettings();
        assert.equal(f.requests.length, 1);
        finish({ ok: true, json: async () => ({}) });
        await pending;
        assert.equal(f.run('_savingProvider'), false);
        assert.equal(f.document.getElementById('provider-search').disabled, false);
        assert.equal(f.document.getElementById('test-provider-save').disabled, false);
    }
});
