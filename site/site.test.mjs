import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import { runInNewContext } from 'node:vm';

const source = readFileSync(new URL('./site.js', import.meta.url), 'utf8');

function demo() {
    const error = { hidden: true };
    const figure = { querySelector: () => error };
    const attributes = new Map([['aria-controls', 'desktop-demo'], ['aria-pressed', 'false']]);
    const button = Object.assign(new EventTarget(), {
        textContent: 'Play desktop demo',
        dataset: { demo: 'assets/shibdemo.webp', preview: 'desktop-preview.webp' },
        getAttribute: (name) => attributes.get(name),
        setAttribute: (name, value) => attributes.set(name, value),
        closest: () => figure,
    });
    const image = new EventTarget();
    const requests = [];
    let src = button.dataset.preview;
    Object.defineProperty(image, 'src', {
        get: () => src,
        set: (value) => { src = value; requests.push(value); },
    });
    const document = {
        querySelectorAll: (selector) => selector === '[data-demo]' ? [button] : [],
        getElementById: (id) => id === 'desktop-demo' ? image : null,
    };
    runInNewContext(source, { document });
    return { button, image, error, requests };
}

test('initialization keeps the static preview without requesting animation', () => {
    const { button, image, error, requests } = demo();
    assert.deepEqual(requests, []);
    assert.equal(image.src, button.dataset.preview);
    assert.equal(button.getAttribute('aria-pressed'), 'false');
    assert.equal(button.textContent, 'Play desktop demo');
    assert.equal(error.hidden, true);
});

test('play requests animation and stop restores the static preview and label', () => {
    const { button, image, requests } = demo();
    button.dispatchEvent(new Event('click'));
    assert.equal(image.src, button.dataset.demo);
    assert.equal(button.getAttribute('aria-pressed'), 'true');
    assert.equal(button.textContent, 'Stop demo');
    button.dispatchEvent(new Event('click'));
    assert.equal(image.src, button.dataset.preview);
    assert.equal(button.getAttribute('aria-pressed'), 'false');
    assert.equal(button.textContent, 'Play desktop demo');
    assert.deepEqual(requests, [button.dataset.demo, button.dataset.preview]);
});

test('animation errors restore the preview, expose fallback and allow a retry', () => {
    const { button, image, error, requests } = demo();
    image.dispatchEvent(new Event('error'));
    assert.deepEqual(requests, []);
    button.dispatchEvent(new Event('click'));
    image.dispatchEvent(new Event('error'));
    assert.equal(image.src, button.dataset.preview);
    assert.equal(button.getAttribute('aria-pressed'), 'false');
    assert.equal(button.textContent, 'Play desktop demo');
    assert.equal(error.hidden, false);
    button.dispatchEvent(new Event('click'));
    assert.equal(error.hidden, true);
    assert.equal(image.src, button.dataset.demo);
});

function copyCommand(clipboard) {
    const command = { textContent: 'curl example\ndocker compose up -d' };
    const status = { textContent: '' };
    const button = Object.assign(new EventTarget(), {
        hidden: true, textContent: 'Copy', dataset: { copy: 'install-docker' },
    });
    let selected;
    const selection = { removeAllRanges() {}, addRange: (range) => { selected = range.command; } };
    const document = {
        querySelectorAll: (selector) => selector === '[data-copy]' ? [button] : [],
        getElementById: (id) => id === 'copy-status' ? status : command,
        createRange: () => ({ selectNodeContents(value) { this.command = value; } }),
    };
    runInNewContext(source, { document, navigator: { clipboard }, window: { getSelection: () => selection } });
    return { button, command, status, selected: () => selected };
}

test('copy keeps the complete multiline command and confirms success', async () => {
    let copied;
    const { button, command, status } = copyCommand({ writeText: async (text) => { copied = text; } });
    assert.equal(button.hidden, false);
    button.dispatchEvent(new Event('click'));
    await new Promise(setImmediate);
    assert.equal(copied, command.textContent);
    assert.equal(button.textContent, 'Copied');
    assert.match(status.textContent, /copied/);
});

for (const [name, clipboard] of [
    ['unavailable', undefined],
    ['denied', { writeText: async () => { throw new Error('Clipboard denied'); } }],
]) {
    test(`clipboard ${name} selects the command for manual copying`, async () => {
        const { button, command, status, selected } = copyCommand(clipboard);
        button.dispatchEvent(new Event('click'));
        await new Promise(setImmediate);
        assert.equal(selected(), command);
        assert.equal(button.textContent, 'Copy');
        assert.match(status.textContent, /Ctrl\+C or ⌘C/);
    });
}
