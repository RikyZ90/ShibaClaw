import test from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import { browserFixture, readFrontend } from './browser-fixture.mjs';

function setup() {
    const fixture = browserFixture();
    const { context: app, document } = fixture;
    for (const id of ['subagent-feedback-container', 'subagent-avatar-btn', 'subagent-drawer', 'chat-history']) {
        const node = document.createElement('div');
        node.setAttribute('id', id);
        document.body.appendChild(node);
    }
    app.setInterval = () => 1;
    vm.runInContext(readFrontend('js/subagent_ui.js'), app);
    app.subagentUI.init();
    app.subagentUI.selectSession('webui:a');
    return { ...fixture, ui: app.subagentUI };
}

function row(overrides = {}) {
    return { task_id: 'sub_123', session_key: 'webui:a', label: 'Research', task: 'Inspect the source',
        status: 'running', kind: 'spawn', revision: 1, started_at: Date.now() / 1000 - 5, ...overrides };
}

test('labels, task details and results stay plain text, including malicious markup', () => {
    const { ui, document } = setup();
    const payload = '<img src=x onerror=alert(1)>';
    ui.receive(row({ label: payload, task: payload, result: payload }));
    const card = document.getElementById('task-run-sub_123');
    assert.ok(card.textContent.includes(payload));
    assert.ok(document.getElementById('subagent-drawer').textContent.includes(payload));
    assert.equal(card.querySelector('.subagent-run-task').innerHTML, '&lt;img src=x onerror=alert(1)&gt;');
});

test('completion retains the card and removes the active task count', () => {
    const { ui, document } = setup();
    ui.receive(row());
    ui.receive(row({ status: 'succeeded', revision: 2, result: 'Done', finished_at: Date.now() / 1000 }));
    const card = document.getElementById('task-run-sub_123');
    assert.ok(card.textContent.includes('Done'));
    assert.equal(document.getElementById('subagent-feedback-container').style.display, 'none');
    assert.equal(card.querySelector('.subagent-run-cancel'), null);
    ui.receive(row({ revision: 1 }));
    assert.equal(card.getAttribute('data-status'), 'succeeded');
});

test('switching sessions isolates cards and updates received for a background session', () => {
    const { ui, document } = setup();
    ui.receive(row());
    ui.selectSession('webui:b');
    assert.equal(document.getElementById('task-run-sub_123'), null);
    assert.equal(document.getElementById('subagent-feedback-container').style.display, 'none');
    ui.receive(row({ status: 'cancelled', revision: 2 }));
    assert.equal(document.getElementById('task-run-sub_123'), null);
    ui.selectSession('a');
    assert.equal(document.getElementById('task-run-sub_123').getAttribute('data-status'), 'cancelled');
});

test('snapshot recovers cards after reload and ignores an older snapshot revision', () => {
    const { ui, document } = setup();
    ui.snapshot({ session_key: 'a', tasks: [row({ revision: 4, phase: 'auditing', kind: 'mea' })] });
    assert.ok(document.getElementById('task-run-sub_123').textContent.includes('Audit'));
    ui.snapshot({ session_key: 'a', tasks: [row({ revision: 2 })] });
    assert.equal(ui.rows()[0].revision, 4);
    ui.snapshot({ session_key: 'a', tasks: [], snapshot_at: Date.now() / 1000 });
    assert.equal(document.getElementById('task-run-sub_123'), null);
});

test('cancel targets the task id and a rejected cancellation restores the action', () => {
    const { ui, document, emissions } = setup();
    ui.receive(row());
    const card = document.getElementById('task-run-sub_123');
    card.querySelector('.subagent-run-cancel').click();
    assert.equal(emissions[0][0], 'subagent_cancel');
    assert.equal(emissions[0][1].task_id, 'sub_123');
    assert.equal(emissions[0][1].session_key, undefined);
    ui.cancelAck({ session_key: 'a', task_id: 'sub_123', cancelled: false });
    assert.equal(card.querySelector('.subagent-run-cancel').disabled, false);
});

test('offline state is explicit and disables cancellation until a snapshot is recovered', () => {
    const { ui, document } = setup();
    ui.receive(row());
    ui.setConnected(false);
    const card = document.getElementById('task-run-sub_123');
    assert.ok(card.textContent.includes('Connection lost'));
    assert.equal(card.querySelector('.subagent-run-cancel').disabled, true);
    ui.snapshot({ session_key: 'a', tasks: [row()] });
    assert.equal(card.querySelector('.subagent-run-cancel').disabled, false);
});

test('updates preserve expanded details and do not force scroll while reading history', () => {
    const { ui, document, context: app } = setup();
    let scrolls = 0;
    app.scrollToBottom = () => scrolls++;
    const history = document.getElementById('chat-history');
    Object.assign(history, { scrollHeight: 1500, clientHeight: 600, scrollTop: 0 });
    ui.receive(row());
    const card = document.getElementById('task-run-sub_123');
    card.querySelector('.subagent-run-details').open = true;
    ui.receive(row({ revision: 2, current_tool: 'read_file' }));
    assert.equal(card.querySelector('.subagent-run-details').open, true);
    assert.equal(scrolls, 0);
});

test('restored cards sit between the request and the later reply', () => {
    const { ui, document } = setup();
    const history = document.getElementById('chat-history');
    const request = document.createElement('div');
    request.setAttribute('data-message-at', '10');
    const reply = document.createElement('div');
    reply.setAttribute('data-message-at', '30');
    history.append(request, reply);
    ui.receive(row({ started_at: 20 }));
    assert.equal(history.children[0], request);
    assert.equal(history.children[1].getAttribute('data-task-id'), 'sub_123');
    assert.equal(history.children[2], reply);
});

test('pending work retries synchronization after a lost terminal event or gateway reconnect', () => {
    const { ui, context: app, emissions } = setup();
    ui.receive(row());
    app.realtime.connected = true;
    ui.lastSync = 0;
    ui.tick();
    assert.equal(emissions.at(-1)[0], 'subagent_sync');
    const count = emissions.length;
    ui.tick();
    assert.equal(emissions.length, count);
    ui.snapshot({ session_key: 'a', tasks: [row({ status: 'incomplete', revision: 3 })] });
    ui.lastSync = 0;
    ui.tick();
    assert.equal(emissions.length, count);
});
