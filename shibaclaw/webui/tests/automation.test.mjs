import assert from 'node:assert/strict';
import test from 'node:test';
import vm from 'node:vm';
import { browserFixture, readFrontend } from './browser-fixture.mjs';

function fixture(jobs = []) {
    const browser = browserFixture();
    const { context, document } = browser;
    document.readyState = 'loading';
    const html = readFrontend('index.html');
    const ids = [...new Set([...html.matchAll(/id="(ajf-[^"]+|automation-job-form|automation-job-list|automation-form-title)"/g)].map(match => match[1]))];
    for (const id of ids) {
        const select = html.match(new RegExp(`<select\\b[^>]*id="${id}"[^>]*>([\\s\\S]*?)</select>`));
        const element = document.createElement(select ? 'select' : 'div');
        element.id = id;
        element.value = '';
        element.checked = false;
        if (['ajf-enabled', 'ajf-deliver', 'ajf-delete-after'].includes(id)) element.type = 'checkbox';
        if (select) {
            for (const match of select[1].matchAll(/<option\b[^>]*value="([^"]*)"/g)) {
                const option = document.createElement('option');
                option.value = match[1];
                element.appendChild(option);
            }
            Object.defineProperty(element, 'options', { get: () => element.children });
            let value = element.options[0]?.value || '';
            Object.defineProperty(element, 'value', {
                get: () => value,
                set: next => { value = element.options.some(option => option.value === next) ? next : ''; },
            });
        }
        document.body.appendChild(element);
    }
    for (const name of ['automation-modal-toolbar', 'automation-tabs']) {
        const element = document.createElement('div');
        element.className = name;
        document.body.appendChild(element);
    }
    const dialogs = [];
    context.shibaDialog = async (...args) => { dialogs.push(args); return true; };
    const requests = [];
    context.authFetch = async (url, options = {}) => {
        requests.push({ url, options });
        return { ok: true, json: async () => url === '/api/profiles' ? { profiles: [{ id: 'special' }] } : {} };
    };
    vm.runInContext(readFrontend('js/automation.js'), context, { filename: 'automation.js' });
    // The list refresh is outside these form and document mutation checks.
    vm.runInContext('loadAutomationPanel = async () => {}', context);
    context.testJobs = jobs;
    vm.runInContext('_autoJobs = testJobs', context);
    return { ...browser, dialogs, requests, field: id => document.getElementById(id) };
}

const job = (id, name, extra = {}) => ({
    id, name, enabled: false, schedule: { kind: 'every', everyMs: 60000 }, payload: {}, ...extra,
});

test('editing a heartbeat preserves its type, file, model and delivery targets', async () => {
    const original = job('monitor', 'Monitor', {
        enabled: true,
        payload: {
            kind: 'heartbeat', heartbeatFile: 'monitor.md', model: 'provider/model',
            profileId: 'special', targets: { telegram: '123', discord: '456' },
        },
    });
    const f = fixture([original]);
    await f.context.openJobForm(original.id);
    f.field('ajf-name').value = 'Renamed monitor';
    await f.context.saveJobForm();
    const request = f.requests.at(-1);
    const body = JSON.parse(request.options.body);
    assert.equal(request.options.method, 'PATCH');
    assert.equal(body.name, 'Renamed monitor');
    assert.equal(body.payload.kind, 'heartbeat');
    assert.equal(body.payload.heartbeatFile, 'monitor.md');
    assert.equal(body.payload.model, 'provider/model');
    assert.deepEqual(body.payload.targets, original.payload.targets);
    assert.equal(body.payload.profileId, 'special');
});

test('a new disabled job resets the previous profile and sends its selected destination', async () => {
    const f = fixture([job('old', 'Old', { payload: { kind: 'scheduled', profileId: 'special' } })]);
    await f.context.openJobForm('old');
    assert.equal(f.field('ajf-profile').value, 'special');
    await f.context.openJobForm();
    assert.equal(f.field('ajf-profile').value, '');
    f.field('ajf-name').value = 'Reminder';
    f.field('ajf-message').value = 'Send a reminder';
    f.field('ajf-enabled').checked = false;
    f.field('ajf-deliver').checked = true;
    f.field('ajf-channel').value = 'telegram';
    f.field('ajf-target-id').value = '123456';
    await f.context.saveJobForm();
    const request = f.requests.at(-1);
    const body = JSON.parse(request.options.body);
    assert.equal(request.options.method, 'POST');
    assert.equal(body.enabled, false);
    assert.equal(body.payload.kind, 'scheduled');
    assert.equal(body.payload.profileId, null);
    assert.equal(body.payload.to, '123456');
    assert.deepEqual(body.payload.targets, { telegram: '123456' });
});

test('unchanged legacy delivery fields survive editing and use the selected channel target', async () => {
    const payload = { kind: 'scheduled', message: 'Report', deliver: true, channel: 'telegram', to: null, targets: { discord: '456', telegram: '123' } };
    const f = fixture([job('report', 'Report', { payload })]);
    await f.context.openJobForm('report');
    assert.equal(f.field('ajf-target-id').value, '123');
    await f.context.saveJobForm();
    const saved = JSON.parse(f.requests.at(-1).options.body).payload;
    assert.deepEqual(saved.targets, payload.targets);
    assert.equal(saved.to, null);
});

test('a saved plugin channel remains selectable and survives an unrelated edit', async () => {
    const payload = { kind: 'scheduled', message: 'Report', deliver: true, channel: 'matrix', to: '!room:server', targets: { matrix: '!room:server' } };
    const f = fixture([job('report', 'Report', { payload })]);
    await f.context.openJobForm('report');
    assert.equal(f.field('ajf-channel').value, 'matrix');
    f.field('ajf-name').value = 'Renamed';
    await f.context.saveJobForm();
    const saved = JSON.parse(f.requests.at(-1).options.body).payload;
    assert.equal(saved.channel, 'matrix');
    assert.equal(saved.to, payload.to);
    assert.deepEqual(saved.targets, payload.targets);
});

function taskFixture(jobs, { failedDelete, readStatus = 200, saveStatus = 200 } = {}) {
    const f = fixture(jobs);
    let markdown = '# Tasks\n\n## Task: Alpha\nDo alpha\n\n## Task: Beta\nDo beta\n\n## Task: Keep\nKeep these instructions\n';
    f.context.authFetch = async (url, options = {}) => {
        f.requests.push({ url, options });
        if (url.startsWith('/api/file-get')) {
            const snapshot = markdown;
            return { ok: readStatus === 200, status: readStatus, text: async () => snapshot };
        }
        if (url === '/api/file-save') {
            if (saveStatus === 200) markdown = JSON.parse(options.body).content;
            return { ok: saveStatus === 200, status: saveStatus };
        }
        return { ok: !url.endsWith(`/${failedDelete}`), status: url.endsWith(`/${failedDelete}`) ? 503 : 200 };
    };
    return { ...f, markdown: () => markdown };
}

test('clear removes persisted and virtual tasks with one document write and keeps other sections', async () => {
    const f = taskFixture([job('a', 'Alpha'), job('v-beta', 'Beta', { isVirtual: true })]);
    await f.context.clearCompletedJobs();
    const deletes = f.requests.filter(request => request.options.method === 'DELETE');
    assert.deepEqual(deletes.map(request => request.url), ['/api/automation/jobs/a']);
    assert.equal(f.requests.filter(request => request.url.startsWith('/api/file-get')).length, 1);
    assert.equal(f.requests.filter(request => request.url === '/api/file-save').length, 1);
    assert.doesNotMatch(f.markdown(), /Task: Alpha|Task: Beta/);
    assert.match(f.markdown(), /Task: Keep\nKeep these instructions/);
});

test('clear retains instructions for failed deletes, cleans successful ones and reports the error', async () => {
    const f = taskFixture([job('a', 'Alpha'), job('b', 'Beta')], { failedDelete: 'a' });
    await f.context.clearCompletedJobs();
    assert.match(f.markdown(), /Task: Alpha\nDo alpha/);
    assert.doesNotMatch(f.markdown(), /Task: Beta/);
    assert.match(f.markdown(), /Task: Keep/);
    assert.equal(f.dialogs.at(-1)[0], 'alert');
    assert.match(f.dialogs.at(-1)[2], /Alpha: HTTP 503/);
});

test('clear does not touch TASK.md when every delete fails', async () => {
    const f = taskFixture([job('a', 'Alpha')], { failedDelete: 'a' });
    await f.context.clearCompletedJobs();
    assert.equal(f.requests.length, 1);
    assert.match(f.markdown(), /Task: Alpha/);
    assert.equal(f.dialogs.at(-1)[0], 'alert');
});

test('clear retains shared task instructions while a same-named job remains', async () => {
    for (const retained of [job('b', 'alpha'), job('active', 'alpha', { enabled: true })]) {
        const f = taskFixture([job('a', 'Alpha'), retained], { failedDelete: retained.id });
        await f.context.clearCompletedJobs();
        assert.match(f.markdown(), /Task: Alpha\nDo alpha/);
        assert.equal(f.requests.filter(request => request.url === '/api/file-save').length, 0);
    }
});

test('concurrent task removals preserve both edits', async () => {
    const f = taskFixture([]);
    await Promise.all([
        f.context._removeFromTaskMd(['Alpha']),
        f.context._removeFromTaskMd(['Beta']),
    ]);
    assert.doesNotMatch(f.markdown(), /Task: Alpha|Task: Beta/);
    assert.match(f.markdown(), /Task: Keep/);
});

test('a failed task update does not prevent later task removals', async () => {
    const f = taskFixture([]);
    const originalFetch = f.context.authFetch;
    f.context.authFetch = async () => ({ ok: false, status: 503 });
    await assert.rejects(f.context._removeFromTaskMd(['Alpha']), /TASK.md: HTTP 503/);
    f.context.authFetch = originalFetch;
    await f.context._removeFromTaskMd(['Beta']);
    assert.match(f.markdown(), /Task: Alpha/);
    assert.doesNotMatch(f.markdown(), /Task: Beta/);
});

test('a failed document read never overwrites TASK.md and a failed save is reported', async () => {
    for (const options of [{ readStatus: 503 }, { saveStatus: 503 }]) {
        const f = taskFixture([job('a', 'Alpha')], options);
        await f.context.clearCompletedJobs();
        assert.match(f.markdown(), /Task: Alpha/);
        assert.equal(f.dialogs.at(-1)[0], 'alert');
        assert.match(f.dialogs.at(-1)[2], /TASK.md: HTTP 503/);
        if (options.readStatus) assert.equal(f.requests.filter(request => request.url === '/api/file-save').length, 0);
    }
});

test('canceling clear leaves jobs and task instructions untouched', async () => {
    const f = taskFixture([job('a', 'Alpha')]);
    f.context.shibaDialog = async () => false;
    await f.context.clearCompletedJobs();
    assert.equal(f.requests.length, 0);
    assert.match(f.markdown(), /Task: Alpha/);
});
