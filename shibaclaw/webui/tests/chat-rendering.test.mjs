import test from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import { browserFixture, readFrontend } from './browser-fixture.mjs';

function setup() {
    const fixture = browserFixture();
    const { context: app, document } = fixture;
    const history = document.createElement('div');
    history.id = 'chat-history';
    document.body.appendChild(history);
    app.chatHistory = history;
    app.DEFAULT_AVATAR = '/static/shibaclaw_logo.webp';
    Object.assign(app.state, { sessionId: 'webui:chat', sessionLoadSeq: 1, messageCount: 0, processGroups: {}, _streamBuffers: {} });
    app.setInterval = () => 1;
    const handlers = new Map(), frames = new Map(), calls = [];
    app.realtime = { on: (name, fn) => handlers.set(name, fn), connect() {}, emit() {}, connected: true };
    app.getStoredToken = () => '';
    app.requestAnimationFrame = fn => { const id = frames.size + 1; frames.set(id, fn); return id; };
    app.cancelAnimationFrame = id => frames.delete(id);
    vm.runInContext(readFrontend('js/chat.js'), app);
    vm.runInContext(readFrontend('js/api_socket.js'), app);
    app.activateChat = app.addTimestamp = app.enhanceCodeBlocks = app.hideTypingBubble = app.hideThinking = app.collapseProcessGroup = () => {};
    app.scrollToBottom = app.setWorkingState = app.updateQueueIndicator = app.updateSendButton = app.autoTitleSession = app.loadHistory = app.refreshTokenBadge = () => {};
    app.showThinking = text => calls.push(['thinking', text]);
    app.addProcessStep = (...args) => calls.push(['step', ...args]);
    app.initSocket();
    return { ...fixture, history, handlers, frames, calls };
}

test('final response replaces partial chunks and cancels pending animation frames', () => {
    const { context: app, history, handlers, frames } = setup();
    handlers.get('agent_response_chunk')({ id: 'one', session_key: 'webui:chat', content: 'Partial' });
    assert.equal(frames.size, 1);
    handlers.get('agent_response')({ id: 'one', session_key: 'webui:chat', content: 'Complete authoritative answer' });
    const bubbles = history.querySelectorAll('.message-bubble');
    assert.equal(bubbles.length, 1);
    assert.equal(bubbles[0].getAttribute('data-raw-content'), 'Complete authoritative answer');
    assert.equal(frames.size, 0);
    assert.equal(app.state._streamBuffers.one, undefined);
});

test('attachment-only final responses clear streamed text while keeping the attachment', () => {
    const { history, handlers } = setup();
    handlers.get('agent_response_chunk')({ id: 'one', content: 'An internal draft' });
    handlers.get('agent_response')({ id: 'one', content: '', attachments: [{ type: 'image/png', url: '/image.png' }] });
    const bubble = history.querySelector('.message-bubble');
    assert.equal(bubble.getAttribute('data-raw-content'), '');
    assert.equal(bubble.children.length, 1);
    assert.equal(bubble.children[0].tagName, 'IMG');
});

test('fallback chunks are retained when the final payload omits its content', () => {
    const { history, handlers, context: app } = setup();
    const saved = [];
    app._historyWindowAppendLive = (_, message) => saved.push(message);
    handlers.get('agent_response_chunk')({ id: 'one', content: 'Available text' });
    handlers.get('agent_response')({ id: 'one', attachments: [] });
    assert.equal(history.querySelector('.message-bubble').getAttribute('data-raw-content'), 'Available text');
    assert.equal(saved[0].content, 'Available text');
    assert.deepEqual(Array.from(saved[0].metadata.attachments), []);
});

test('tool events accept normalized session ids and ignore events from another chat', () => {
    const { handlers, calls, context: app } = setup();
    handlers.get('agent_tool')({ id: 'one', session_key: 'chat', content: 'read_file' });
    assert.equal(calls.filter(call => call[0] === 'step').length, 1);
    handlers.get('agent_tool')({ id: 'two', session_key: 'webui:other', content: 'exec' });
    assert.equal(calls.filter(call => call[0] === 'step').length, 1);
    app.state.queueCount = 0;
    handlers.get('message_queued')({ session_key: 'webui:other', position: 3 });
    assert.equal(app.state.queueCount, 0);
});

test('repeated user questions remain distinct turns in restored history', () => {
    const { context: app } = setup();
    const messages = [
        { role: 'user', content: 'Any updates?' },
        { role: 'assistant', content: 'Working on it.' },
        { role: 'user', content: 'Any updates?' },
        { role: 'assistant', content: 'Done.' },
    ];
    const parsed = app._parseSessionMessages(messages, 1, 'webui:chat');
    assert.equal(parsed.parsedMessages.length, 4);
    assert.equal(parsed.parsedMessages[2].turnId, 2);
});

test('reconnect reloads the session to recover final responses missed while offline', () => {
    const { handlers, context: app } = setup();
    const loads = [];
    app.state._initialConnectDone = true;
    app.fetchStatus = () => {};
    app.loadSession = id => loads.push(id);
    handlers.get('connected')({ session_id: 'webui:chat' });
    assert.deepEqual(loads, ['webui:chat']);
});

test('code language captions remain plain text and repeated enhancement keeps one header', () => {
    const { context: app, document } = browserFixture();
    vm.runInContext(readFrontend('js/chat.js'), app);
    const container = document.createElement('div');
    const pre = document.createElement('pre');
    const code = document.createElement('code');
    code.className = 'language-<img/src=x/onerror=alert(1)>';
    code.textContent = 'print("hello")';
    pre.appendChild(code);
    container.appendChild(pre);
    app.enhanceCodeBlocks(container);
    app.enhanceCodeBlocks(container);
    assert.equal(container.querySelectorAll('.code-block-header').length, 1);
    assert.equal(container.querySelector('.code-block-header').querySelector('span').textContent, '<img/src=x/onerror=alert(1)>');
    assert.equal(container.querySelector('.code-block-header').querySelector('img'), null);
});
