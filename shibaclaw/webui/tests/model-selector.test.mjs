import assert from 'node:assert/strict';
import test from 'node:test';
import vm from 'node:vm';
import { browserFixture, readFrontend, settle } from './browser-fixture.mjs';

const sources = [
    { id: 'endpoint_one', name: 'Local', api_base: 'http://localhost:8001/v1', provider: 'custom' },
    { id: 'endpoint_two', name: 'Local', apiBase: 'http://localhost:8002/v1', provider: 'custom' },
];
const catalog = [{ id: 'endpoint_one/org/shared', raw_id: 'org/shared', name: 'Shared', provider: 'endpoint_one', supports_reasoning: true }];

function fixture(payload = { models: catalog, providers: sources }) {
    const browser = browserFixture();
    const { context, document } = browser;
    const requests = [];
    const alerts = [];
    context.debounce = fn => fn;
    context.alert = message => alerts.push(message);
    context.console = { error() {}, warn() {} };
    context.authFetch = async (url, options) => {
        requests.push({ url, options });
        const provider = new URL(url, 'http://localhost').searchParams.get('provider');
        const response = provider ? { ...payload, models: payload.models.filter(model => model.provider === provider) } : payload;
        return { ok: true, json: async () => response };
    };
    vm.runInContext(readFrontend('js/model_selector.js'), context);
    const add = id => {
        const element = document.createElement('div');
        element.id = id;
        element.value = '';
        document.body.appendChild(element);
        return element;
    };
    const run = code => vm.runInContext(code, context);
    const event = (node, type, extra = {}) => node.dispatchEvent({ type, stopPropagation() {}, preventDefault() {}, ...extra });
    return { ...browser, add, run, event, requests, alerts };
}

async function chatDefaultFixture() {
    const f = fixture();
    for (const id of ['btn-model-select', 'model-dropdown-menu', 'model-search-input', 'model-list-container', 'active-model-display']) f.add(id);
    await f.context.ensureAvailableModels();
    const originalFetch = f.context.authFetch;
    f.context.authFetch = async (url, options) => {
        if (url !== '/api/settings') return originalFetch(url, options);
        f.requests.push({ url, options });
        return { ok: true, json: async () => ({ agents: { defaults: { model: catalog[0].id } } }) };
    };
    f.context.openComposerMenu = (_, menu) => { menu.style.display = 'flex'; };
    f.context.positionComposerMenu = () => {};
    f.context.setupModelSelector();
    f.context.state.sessionId = 'session/1';
    const search = f.document.getElementById('model-search-input');
    const list = f.document.getElementById('model-list-container');
    const menu = f.document.getElementById('model-dropdown-menu');
    const display = f.document.getElementById('active-model-display');
    const button = f.document.getElementById('btn-model-select');
    const open = async () => {
        menu.style.display = 'none';
        f.event(button, 'click');
        await settle();
    };
    const defaultItem = () => list.querySelector('.model-picker-defaults')?.querySelector('.model-item');
    return { ...f, search, list, menu, display, button, open, defaultItem };
}

test('manual models preserve org/model and offer a choice for each active source without catalogs', async () => {
    const f = fixture({ models: [], providers: sources });
    await f.context.ensureAvailableModels();
    const choices = f.context.customModelChoices(' org/new-model ');
    assert.equal(choices.map(item => item.id).join(','), 'endpoint_one/org/new-model,endpoint_two/org/new-model');
    assert.equal(f.context.customModelChoices('endpoint_two/org/new-model')[0].id, 'endpoint_two/org/new-model');
    assert.equal(f.context.customModelChoices('endpoint_two/').length, 0);
    assert.equal(f.context.customModelChoices(' ').length, 0);
    assert.match(f.context.modelProviderDescription(choices[0]), /Local.*8001/);
    assert.match(f.context.modelProviderDescription(choices[1]), /Local.*8002/);
});

test('a catalog match on one endpoint leaves a manual choice on another, with no cross-endpoint lookup', async () => {
    const f = fixture();
    await f.context.ensureAvailableModels();
    assert.equal(f.context.customModelChoices('org/shared').map(item => item.id).join(','), 'endpoint_two/org/shared');
    assert.equal(f.context.findAvailableModel('endpoint_two/org/shared'), null);
    assert.equal(f.context.findAvailableModel('endpoint_deleted/org/shared'), null);
    assert.equal(f.context.findAvailableModel('shared'), null);
    assert.equal(f.context.findAvailableModel('org/shared').id, catalog[0].id);
    assert.equal(f.context.modelForDisplay('endpoint_two/org/shared').provider, 'endpoint_two');
    assert.equal(f.context.customModelChoices('org/shared-extra').length, 2);
});

test('ambiguous raw model IDs never pick whichever endpoint appears first', async () => {
    const f = fixture({ models: [...catalog, { ...catalog[0], id: 'endpoint_two/org/shared', provider: 'endpoint_two' }], providers: sources });
    await f.context.ensureAvailableModels();
    assert.equal(f.context.findAvailableModel('org/shared'), null);
    assert.equal(f.context.findAvailableModel('endpoint_two/org/shared').provider, 'endpoint_two');
});

test('both settings model pickers use endpoint-specific manual choices and keyboard selection', async () => {
    const f = fixture({ models: [], providers: sources });
    await f.context.ensureAvailableModels();
    for (const config of f.run('SETTINGS_MODEL_PICKERS')) {
        for (const key of ['valueId', 'displayId', 'providerId', 'menuId', 'searchId', 'listId']) f.add(config[key]);
        const search = f.document.getElementById(config.searchId);
        search.value = 'org/new-model';
        f.context.renderSettingsModelPickerOptions(config);
        const list = f.document.getElementById(config.listId);
        assert.equal(list.querySelectorAll('.model-custom-action').length, 1);
        assert.equal(list.querySelectorAll('.model-provider-choice').length, 0);
        f.event(list.querySelector('.model-custom-action'), 'click');
        assert.equal(f.document.getElementById(config.valueId).value, '');
        const choice = list.querySelectorAll('.model-provider-choice').find(item => item.title.includes('8002'));
        assert.equal(choice.tabIndex, 0);
        assert.equal(choice.getAttribute('role'), 'button');
        assert.match(choice.textContent, /Local.*8002/);
        f.event(choice, 'keydown', { key: 'Enter' });
        await settle();
        assert.equal(f.document.getElementById(config.valueId).value, 'endpoint_two/org/new-model');
        assert.equal(f.document.getElementById(config.displayId).textContent, 'org/new-model');
        assert.match(f.document.getElementById(config.providerId).textContent, /8002/);
        assert.equal(f.document.getElementById(config.menuId).style.display, 'none');
    }
});

test('chat manual selection sends canonical ID and preserves the current model on a failed PATCH', async () => {
    const f = fixture({ models: [], providers: sources });
    for (const id of ['btn-model-select', 'model-dropdown-menu', 'model-search-input', 'model-list-container', 'active-model-display']) f.add(id);
    await f.context.ensureAvailableModels();
    f.context.state.sessionId = 'session/1';
    f.context.state.activeModelId = 'endpoint_one/old';
    const display = f.document.getElementById('active-model-display');
    display.textContent = 'old';
    const menu = f.document.getElementById('model-dropdown-menu');
    menu.style.display = 'flex';
    f.context.setupModelSelector();
    const search = f.document.getElementById('model-search-input');
    search.value = 'org/new-model';
    f.event(search, 'input');
    const list = f.document.getElementById('model-list-container');
    let succeed = false;
    f.context.authFetch = async (url, options) => {
        f.requests.push({ url, options });
        return { ok: succeed, json: async () => ({ error: 'Model unavailable' }) };
    };
    f.event(list.querySelector('.model-custom-action'), 'click');
    assert.equal(f.requests.filter(request => request.options?.method === 'PATCH').length, 0);
    assert.equal(f.context.state.activeModelId, 'endpoint_one/old');
    const choice = list.querySelectorAll('.model-provider-choice').find(item => item.title.includes('8002'));
    f.event(choice, 'keydown', { key: 'Enter' });
    await settle();
    assert.equal(f.context.state.activeModelId, 'endpoint_one/old');
    assert.equal(display.textContent, 'old');
    assert.equal(menu.style.display, 'flex');
    assert.equal(f.alerts[0], 'Model unavailable');
    const request = f.requests.at(-1);
    assert.equal(request.url, '/api/sessions/session%2F1');
    assert.equal(JSON.parse(request.options.body).model, 'endpoint_two/org/new-model');
    succeed = true;
    f.event(choice, 'click');
    await settle();
    assert.equal(f.context.state.activeModelId, 'endpoint_two/org/new-model');
    assert.equal(display.textContent, 'org/new-model');
    assert.equal(menu.style.display, 'none');
});

test('catalog results stay first with one custom action even when many providers offer a manual model', async () => {
    const manySources = [...sources, ...Array.from({ length: 25 }, (_, index) => ({
        id: `endpoint_extra_${index}`, name: 'Local', api_base: `http://localhost:${9000 + index}/v1`, provider: 'custom',
    }))];
    const f = fixture({ models: catalog, providers: manySources });
    await f.context.ensureAvailableModels();
    const list = f.add('picker-list');
    const selections = [];
    f.context.renderModelPicker(list, f.context.filterModelsByQuery('org/shared'), '', model => selections.push(model.id), 'org/shared');
    assert.equal(list.children[0].className, 'model-picker-results');
    assert.equal(list.children[0].children[0].querySelector('.model-item-name').textContent, 'Shared');
    assert.equal(list.children.length, 2);
    assert.equal(list.querySelectorAll('.model-custom-action').length, 1);
    assert.equal(list.querySelectorAll('.model-provider-choice').length, 0);
    f.event(list.querySelector('.model-custom-action'), 'click');
    assert.equal(selections.length, 0);
    assert.equal(list.querySelectorAll('.model-custom-action').length, 0);
    assert.equal(list.querySelectorAll('.model-provider-choice').length, manySources.length - 1);
    assert.equal(list.querySelector('.model-provider-choice').querySelector('.model-item-name').textContent, 'Local');
    assert.equal(list.querySelector('.model-provider-choice').querySelector('.model-item-provider').textContent, 'http://localhost:8002/v1');
    assert.equal(f.document.activeElement, list.querySelector('.model-provider-choice'));
    f.event(list.querySelector('.model-picker-back'), 'click');
    assert.equal(selections.length, 0);
    assert.equal(list.children[0].children[0].querySelector('.model-item-name').textContent, 'Shared');
    assert.equal(list.querySelectorAll('.model-custom-action').length, 1);
    assert.equal(f.document.activeElement, list.querySelector('.model-custom-action'));
    f.event(list.querySelector('.model-custom-action'), 'click');
    f.event(list.querySelector('.model-provider-choice'), 'keydown', { key: ' ' });
    assert.deepEqual(selections, ['endpoint_two/org/shared']);
});

test('a single candidate selects directly, including an explicit source prefix and org/model IDs', async () => {
    for (const [providers, query] of [
        [[sources[1]], 'org/new-model'],
        [sources, 'endpoint_two/org/new-model'],
    ]) {
        const f = fixture({ models: [], providers });
        await f.context.ensureAvailableModels();
        const list = f.add('picker-list');
        const selections = [];
        f.context.renderModelPicker(list, [], '', model => selections.push(model.id), query);
        assert.equal(list.querySelectorAll('.model-custom-action').length, 1);
        f.event(list.querySelector('.model-custom-action'), 'click');
        assert.deepEqual(selections, ['endpoint_two/org/new-model']);
        assert.equal(list.querySelectorAll('.model-picker-back').length, 0);
        assert.equal(list.querySelectorAll('.model-provider-choice').length, 0);
    }
});

test('empty-catalog endpoint is discoverable by display name or URL and back restores the source query', async () => {
    const strata = { ...sources[1], name: 'strata' };
    for (const query of ['strata', 'localhost:8002']) {
        const f = fixture({ models: catalog, providers: [sources[0], strata] });
        await f.context.ensureAvailableModels();
        const list = f.add('picker-list');
        const search = f.add('picker-search');
        const selections = [];
        const onSelect = model => selections.push(model.id);
        search.value = query;
        f.context.renderModelPicker(list, f.context.filterModelsByQuery(query), '', onSelect, query, [], search);
        const source = list.querySelector('.model-source-choice');
        assert.ok(source, `missing source for query ${query}`);
        assert.match(source.textContent, /strata/);
        assert.match(source.textContent, /8002/);
        if (query === 'strata') assert.ok(!list.querySelector('.model-custom-action'));
        f.event(source, 'keydown', { key: 'Enter' });
        assert.equal(list.dataset.providerId, strata.id);
        assert.equal(search.value, '');
        assert.match(search.placeholder || search.getAttribute('placeholder'), /strata/);
        assert.equal(selections.length, 0);
        assert.equal(list.querySelectorAll('.model-item').length, 0);
        search.value = 'org/new-model';
        f.context.renderModelPicker(list, f.context.filterModelsByQuery(search.value), '', onSelect, search.value, [], search);
        assert.equal(list.querySelectorAll('.model-custom-action').length, 1);
        f.event(list.querySelector('.model-picker-back'), 'click');
        assert.equal(search.value, query);
        assert.ok(!list.dataset.providerId);
        assert.ok(list.querySelector('.model-source-choice'));
        assert.equal(selections.length, 0);
        f.event(list.querySelector('.model-source-choice'), 'click');
        search.value = 'org/new-model';
        f.context.renderModelPicker(list, f.context.filterModelsByQuery(search.value), '', onSelect, search.value, [], search);
        f.event(list.querySelector('.model-custom-action'), 'click');
        assert.deepEqual(selections, ['endpoint_two/org/new-model']);
        assert.equal(list.querySelectorAll('.model-provider-choice').length, 0);
    }
});

test('chat source discovery scopes manual IDs without selecting a model or sending a PATCH', async () => {
    const f = fixture({ models: catalog, providers: [sources[0], { ...sources[1], name: 'strata' }] });
    for (const id of ['btn-model-select', 'model-dropdown-menu', 'model-search-input', 'model-list-container', 'active-model-display']) f.add(id);
    await f.context.ensureAvailableModels();
    f.context.state.sessionId = 'session/1';
    f.context.state.activeModelId = catalog[0].id;
    f.document.getElementById('active-model-display').textContent = 'Shared';
    f.context.openComposerMenu = (_, menu) => { menu.style.display = 'flex'; };
    f.context.positionComposerMenu = () => {};
    f.context.setupModelSelector();
    const search = f.document.getElementById('model-search-input');
    const list = f.document.getElementById('model-list-container');
    search.value = 'strata';
    f.event(search, 'input');
    f.event(list.querySelector('.model-source-choice'), 'click');
    assert.equal(f.context.state.activeModelId, catalog[0].id);
    assert.equal(f.document.getElementById('active-model-display').textContent, 'Shared');
    assert.equal(f.requests.filter(request => request.options?.method === 'PATCH').length, 0);
    const button = f.document.getElementById('btn-model-select');
    f.document.getElementById('model-dropdown-menu').style.display = 'none';
    f.event(button, 'click');
    await settle();
    assert.ok(!list.dataset.providerId);
    assert.equal(search.value, '');
    search.value = 'strata';
    f.event(search, 'input');
    f.event(list.querySelector('.model-source-choice'), 'click');
    search.value = 'org/new-model';
    f.event(search, 'input');
    assert.equal(list.querySelectorAll('.model-custom-action').length, 1);
    assert.ok(!list.querySelector('.model-provider-choice'));
    f.event(list.querySelector('.model-custom-action'), 'click');
    await settle();
    const patch = f.requests.find(request => request.options?.method === 'PATCH');
    assert.ok(patch);
    assert.equal(JSON.parse(patch.options.body).model, 'endpoint_two/org/new-model');
    assert.equal(f.context.state.activeModelId, 'endpoint_two/org/new-model');
});

test('both settings pickers route an empty-catalog source search to that endpoint only', async () => {
    const f = fixture({ models: catalog, providers: [sources[0], { ...sources[1], name: 'strata' }] });
    await f.context.ensureAvailableModels();
    const configs = f.run('SETTINGS_MODEL_PICKERS');
    for (const config of configs) {
        for (const key of ['valueId', 'buttonId', 'displayId', 'providerId', 'menuId', 'searchId', 'listId']) f.add(config[key]);
    }
    f.context.setupSettingsModelPickers();
    for (const config of configs) {
        const search = f.document.getElementById(config.searchId);
        const value = f.document.getElementById(config.valueId);
        value.value = catalog[0].id;
        search.value = 'strata';
        f.context.renderSettingsModelPickerOptions(config);
        const list = f.document.getElementById(config.listId);
        f.event(list.querySelector('.model-source-choice'), 'click');
        assert.equal(value.value, catalog[0].id);
        assert.equal(list.dataset.providerId, 'endpoint_two');
        f.document.getElementById(config.menuId).style.display = 'none';
        f.event(f.document.getElementById(config.buttonId), 'click');
        await settle();
        assert.ok(!list.dataset.providerId);
        assert.equal(search.value, '');
        search.value = 'strata';
        f.event(search, 'input');
        f.event(list.querySelector('.model-source-choice'), 'click');
        search.value = 'org/new-model';
        f.context.renderSettingsModelPickerOptions(config);
        f.event(list.querySelector('.model-custom-action'), 'click');
        await settle();
        assert.equal(value.value, 'endpoint_two/org/new-model');
        assert.match(f.document.getElementById(config.providerId).textContent, /strata/);
    }
    assert.equal(f.requests.filter(request => request.options?.method === 'PATCH').length, 0);
});

test('source selection fetches its fresh catalog and preserves the typed query and other sources', async () => {
    const strata = { ...sources[1], name: 'strata' };
    const loaded = { id: 'endpoint_two/org/loaded-model', raw_id: 'org/loaded-model', name: 'Loaded Model', provider: strata.id, provider_label: strata.name };
    const f = fixture({ models: catalog, providers: [sources[0], strata] });
    await f.context.ensureAvailableModels();
    let finish;
    f.context.authFetch = (url, options) => {
        f.requests.push({ url, options });
        return new Promise(resolve => { finish = resolve; });
    };
    const list = f.add('picker-list');
    const search = f.add('picker-search');
    const selections = [];
    const onSelect = model => selections.push(model.id);
    search.value = 'strata';
    f.context.renderModelPicker(list, [], '', onSelect, search.value, [], search);
    f.event(list.querySelector('.model-source-choice'), 'click');
    assert.equal(f.requests.at(-1).url, '/api/models?provider=endpoint_two');
    assert.equal(list.dataset.providerId, strata.id);
    assert.equal(search.value, '');
    assert.equal(f.context.findAvailableModel(loaded.id), null);
    search.value = 'org/loaded';
    f.context.renderModelPicker(list, f.context.filterModelsByQuery(search.value), '', onSelect, search.value, [], search);
    finish({ ok: true, json: async () => ({ models: [loaded], providers: [strata] }) });
    await settle();
    assert.equal(search.value, 'org/loaded');
    assert.equal(list.querySelector('.model-item-name').textContent, 'Loaded Model');
    assert.equal(f.context.findAvailableModel(loaded.id).provider, strata.id);
    assert.equal(f.context.findAvailableModel(catalog[0].id).provider, sources[0].id);
    assert.equal(selections.length, 0);
    f.event(list.querySelector('.model-source-back'), 'click');
    assert.equal(search.value, 'strata');
    assert.ok(list.querySelector('.model-source-choice'));
    assert.ok(list.querySelectorAll('.model-item-name').some(item => item.textContent === 'Loaded Model'));
    assert.equal(selections.length, 0);
    assert.equal(f.requests.filter(request => request.options?.method === 'PATCH').length, 0);
});

test('all custom endpoints stay visible on an empty search with or without catalog models', async () => {
    const endpoints = [
        { ...sources[0], name: 'First local' },
        { ...sources[1], name: 'Remote server' },
        { id: 'custom', name: 'Legacy custom', provider: 'custom', api_base: 'http://localhost:8003/v1' },
        { id: 'endpoint_native', name: 'Alternate OpenAI', provider: 'openai', api_base: 'https://example.test/v1' },
    ];
    const builtin = { id: 'openai', name: 'OpenAI', provider: 'openai' };
    const models = [...catalog,
        { id: 'openai/gpt-test', raw_id: 'gpt-test', provider: builtin.id, name: 'Built-in model' },
        { id: 'endpoint_native/known-model', raw_id: 'known-model', provider: 'endpoint_native', name: 'Other endpoint model' },
    ];
    const f = fixture({ models, providers: [...endpoints, builtin] });
    await f.context.ensureAvailableModels();
    const list = f.add('picker-list');
    const search = f.add('picker-search');
    const selections = [];
    const onSelect = model => selections.push(model.id);
    for (const endpoint of endpoints) {
        delete list.dataset.providerId;
        delete list.dataset.providerQuery;
        search.value = '';
        f.context.renderModelPicker(list, f.context.filterModelsByQuery(''), '', onSelect, '', [], search);
        const sourceRows = list.querySelectorAll('.model-source-choice');
        assert.equal(sourceRows.length, endpoints.length);
        assert.ok(!sourceRows.some(row => row.querySelector('.model-item-name').textContent === builtin.name));
        const sourceRow = sourceRows.find(row => row.querySelector('.model-item-name').textContent === endpoint.name);
        assert.ok(sourceRow, `missing endpoint ${endpoint.id}`);
        assert.ok(list.querySelectorAll('.model-item-name').some(item => item.textContent === 'Built-in model'));
        const previousSelections = selections.length;
        f.event(sourceRow, 'click');
        await settle();
        assert.equal(list.dataset.providerId, endpoint.id);
        assert.equal(selections.length, previousSelections);
        search.value = 'org/new-model';
        f.context.renderModelPicker(list, f.context.filterModelsByQuery(search.value), '', onSelect, search.value, [], search);
        assert.equal(list.querySelectorAll('.model-custom-action').length, 1);
        f.event(list.querySelector('.model-custom-action'), 'click');
        assert.equal(selections.at(-1), `${endpoint.id}/org/new-model`);
    }
    assert.equal(f.requests.filter(request => request.options?.method === 'PATCH').length, 0);
});

test('fresh provider response is ignored after leaving scope or invalidating the model cache', async () => {
    const strata = { ...sources[1], name: 'strata' };
    const loaded = { id: 'endpoint_two/org/loaded-model', raw_id: 'org/loaded-model', name: 'Loaded Model', provider: strata.id, provider_label: strata.name };
    for (const leave of ['back', 'invalidate']) {
        const f = fixture({ models: [], providers: [strata] });
        await f.context.ensureAvailableModels();
        let finish;
        f.context.authFetch = () => new Promise(resolve => { finish = resolve; });
        const list = f.add('picker-list');
        const search = f.add('picker-search');
        search.value = 'strata';
        f.context.renderModelPicker(list, [], '', () => assert.fail('source refresh must not select a model'), search.value, [], search);
        f.event(list.querySelector('.model-source-choice'), 'click');
        if (leave === 'back') f.event(list.querySelector('.model-source-back'), 'click');
        else f.context.resetAvailableModelsCache();
        const previousChildren = [...list.children];
        const previousQuery = search.value;
        finish({ ok: true, json: async () => ({ models: [loaded], providers: [strata] }) });
        await settle();
        assert.equal(list.children.length, previousChildren.length);
        assert.ok(list.children.every((child, index) => child === previousChildren[index]));
        assert.equal(search.value, previousQuery);
        assert.equal(f.context.findAvailableModel(loaded.id), null);
        if (leave === 'back') {
            assert.ok(!list.dataset.providerId);
            assert.equal(search.value, 'strata');
            assert.ok(list.querySelector('.model-source-choice'));
        }
    }
});

test('reopening the same source keeps its newest catalog when refreshes finish out of order', async () => {
    const strata = { ...sources[1], name: 'strata' };
    const loaded = { id: 'endpoint_two/org/loaded-model', raw_id: 'org/loaded-model', name: 'Loaded Model', provider: strata.id, provider_label: strata.name };
    const f = fixture({ models: [], providers: [strata] });
    await f.context.ensureAvailableModels();
    const responses = [];
    f.context.authFetch = () => new Promise(resolve => responses.push(resolve));
    const list = f.add('picker-list');
    const search = f.add('picker-search');
    search.value = 'strata';
    f.context.renderModelPicker(list, [], '', () => assert.fail('source refresh must not select a model'), search.value, [], search);
    f.event(list.querySelector('.model-source-choice'), 'click');
    f.event(list.querySelector('.model-source-back'), 'click');
    f.event(list.querySelector('.model-source-choice'), 'click');
    assert.equal(responses.length, 2);
    responses[1]({ ok: true, json: async () => ({ models: [loaded], providers: [strata] }) });
    await settle();
    assert.equal(list.querySelector('.model-item-name').textContent, 'Loaded Model');
    responses[0]({ ok: true, json: async () => ({ models: [], providers: [strata] }) });
    await settle();
    assert.equal(f.context.findAvailableModel(loaded.id)?.provider, strata.id);
    assert.equal(list.querySelector('.model-item-name')?.textContent, 'Loaded Model');
});

test('cache invalidation refreshes provider metadata and ignores earlier in-flight catalogs', async () => {
    const f = fixture();
    let resolveOld;
    f.context.authFetch = () => new Promise(resolve => { resolveOld = resolve; });
    const pending = f.context.ensureAvailableModels();
    f.context.resetAvailableModelsCache();
    f.context.authFetch = async () => ({ ok: true, json: async () => ({ models: [], providers: [sources[1]] }) });
    await f.context.ensureAvailableModels();
    resolveOld({ ok: true, json: async () => ({ models: catalog, providers: sources }) });
    await pending;
    assert.equal(f.context.customModelChoices('new').map(item => item.id).join(','), 'endpoint_two/new');
    assert.equal(f.context.findAvailableModel(catalog[0].id), null);
});

test('chat Default tracks the inherited effective model and stays pinned through search and source scope', async () => {
    const f = await chatDefaultFixture();
    await f.context.updateModelSelectorDisplay('');
    assert.equal(f.context.state.modelOverrideId, '');
    assert.equal(f.context.state.activeModelId, catalog[0].id);
    assert.equal(f.display.textContent, 'Default');
    assert.match(f.button.title, /Shared/);
    await f.open();
    assert.ok(f.defaultItem().classList.contains('selected'));
    assert.equal(f.list.children[0].className, 'model-picker-defaults');
    assert.ok(!f.list.querySelector('.model-picker-results').contains(f.defaultItem()));
    f.search.value = 'endpoint_two';
    f.event(f.search, 'input');
    assert.ok(f.defaultItem().classList.contains('selected'));
    f.event(f.list.querySelector('.model-source-choice'), 'click');
    await settle();
    assert.equal(f.list.dataset.providerId, 'endpoint_two');
    assert.ok(f.defaultItem().classList.contains('selected'));
    f.search.value = 'org/new-model';
    f.event(f.search, 'input');
    assert.ok(f.defaultItem().classList.contains('selected'));
    assert.equal(f.requests.filter(request => request.options?.method === 'PATCH').length, 0);
});

test('successful chat Default reset PATCHes null and failed reset preserves the explicit override', async () => {
    const f = await chatDefaultFixture();
    await f.context.updateModelSelectorDisplay('endpoint_two/org/manual-model');
    await f.open();
    assert.ok(!f.defaultItem().classList.contains('selected'));
    const originalFetch = f.context.authFetch;
    let succeeds = false;
    f.context.authFetch = async (url, options) => {
        if (options?.method !== 'PATCH') return originalFetch(url, options);
        f.requests.push({ url, options });
        return { ok: succeeds, json: async () => ({ error: 'Reset rejected' }) };
    };
    f.event(f.defaultItem(), 'keydown', { key: 'Enter' });
    await settle();
    assert.equal(f.context.state.modelOverrideId, 'endpoint_two/org/manual-model');
    assert.equal(f.context.state.activeModelId, 'endpoint_two/org/manual-model');
    assert.equal(f.display.textContent, 'org/manual-model');
    assert.equal(f.menu.style.display, 'flex');
    assert.equal(f.alerts.at(-1), 'Reset rejected');
    assert.equal(JSON.parse(f.requests.at(-1).options.body).model, null);
    succeeds = true;
    f.event(f.defaultItem(), 'click');
    await settle();
    assert.equal(f.context.state.modelOverrideId, '');
    assert.equal(f.context.state.activeModelId, catalog[0].id);
    assert.equal(f.display.textContent, 'Default');
    assert.equal(f.menu.style.display, 'none');
    const patches = f.requests.filter(request => request.options?.method === 'PATCH');
    assert.equal(patches.length, 2);
    assert.ok(patches.every(request => JSON.parse(request.options.body).model === null));
    await f.open();
    assert.ok(f.defaultItem().classList.contains('selected'));
});

test('switching session model displays restores explicit overrides or inherited Default independently', async () => {
    const f = await chatDefaultFixture();
    for (const [override, effective, label, selected] of [
        ['', catalog[0].id, 'Default', true],
        [catalog[0].id, catalog[0].id, 'Shared', false],
        [null, catalog[0].id, 'Default', true],
        ['endpoint_two/org/manual-model', 'endpoint_two/org/manual-model', 'org/manual-model', false],
        ['', catalog[0].id, 'Default', true],
    ]) {
        await f.context.updateModelSelectorDisplay(override);
        await f.open();
        assert.equal(f.context.state.modelOverrideId, override || '');
        assert.equal(f.context.state.activeModelId, effective);
        assert.equal(f.display.textContent, label);
        assert.equal(f.defaultItem().classList.contains('selected'), selected);
    }
    assert.equal(f.requests.filter(request => request.options?.method === 'PATCH').length, 0);
});

test('Default remains available while choosing a provider for a manual model', async () => {
    const f = await chatDefaultFixture();
    await f.context.updateModelSelectorDisplay('');
    await f.open();
    f.search.value = 'org/new-model';
    f.event(f.search, 'input');
    f.event(f.list.querySelector('.model-custom-action'), 'click');
    assert.ok(f.list.querySelector('.model-provider-choice'));
    assert.ok(f.defaultItem(), 'Default must stay pinned during provider selection');
    assert.ok(f.defaultItem().classList.contains('selected'));
});
