import { readFileSync } from 'node:fs';
import vm from 'node:vm';

const frontend = new URL('../frontend/', import.meta.url);
export const readFrontend = path => readFileSync(new URL(path, frontend), 'utf8');

// Only the DOM operations used by the real scripts under test are implemented.
// This is a behavioral fixture, not a browser/layout or HTML parsing substitute.
class EventTarget {
    listeners = new Map();
    addEventListener(type, listener) {
        const listeners = this.listeners.get(type) || [];
        listeners.push(listener);
        this.listeners.set(type, listeners);
    }
    dispatchEvent(event) {
        event.target ||= this;
        for (const listener of this.listeners.get(event.type) || []) listener(event);
        return true;
    }
}

class Element extends EventTarget {
    constructor(tag = 'div', attrs = {}) {
        super();
        this.tagName = tag.toUpperCase();
        this.attributes = new Map();
        this.dataset = {};
        this.children = [];
        this.parentNode = null;
        this.style = { removeProperty(property) { delete this[property]; } };
        this.hidden = false;
        this._text = '';
        for (const [key, value] of Object.entries(attrs)) this.setAttribute(key, value);
        this.classList = {
            [Symbol.iterator]: () => this.className.split(/\s+/).filter(Boolean)[Symbol.iterator](),
            contains: name => this.className.split(/\s+/).includes(name),
            add: (...names) => { this.className = [...new Set([...this.className.split(/\s+/).filter(Boolean), ...names])].join(' '); },
            remove: (...names) => { this.className = this.className.split(/\s+/).filter(name => !names.includes(name)).join(' '); },
            toggle: (name, force) => {
                const enabled = force ?? !this.classList.contains(name);
                if (enabled) this.classList.add(name);
                else this.classList.remove(name);
                return enabled;
            },
        };
    }
    get id() { return this.getAttribute('id'); }
    set id(value) { this.setAttribute('id', value); }
    get className() { return this.getAttribute('class') || ''; }
    set className(value) { this.setAttribute('class', value); }
    setAttribute(name, value) {
        this.attributes.set(name, String(value));
        if (name.startsWith('data-')) this.dataset[name.slice(5).replace(/-([a-z])/g, (_, letter) => letter.toUpperCase())] = String(value);
    }
    getAttribute(name) { return this.attributes.get(name) ?? null; }
    removeAttribute(name) { this.attributes.delete(name); }
    appendChild(child) {
        if (child.parentNode) child.parentNode.children.splice(child.parentNode.children.indexOf(child), 1);
        child.parentNode = this;
        this.children.push(child);
        return child;
    }
    insertBefore(child, anchor) {
        if (child.parentNode) child.parentNode.children.splice(child.parentNode.children.indexOf(child), 1);
        child.parentNode = this;
        this.children.splice(this.children.indexOf(anchor), 0, child);
        return child;
    }
    remove() { if (this.parentNode) { this.parentNode.children.splice(this.parentNode.children.indexOf(this), 1); this.parentNode = null; } }
    toggleAttribute(name, force) {
        const on = force ?? !this.attributes.has(name);
        if (on) this.setAttribute(name, ''); else this.removeAttribute(name);
        if (name === 'hidden') this.hidden = on;
        return on;
    }
    append(...children) { children.forEach(child => this.appendChild(child)); }
    prepend(child) { this.appendChild(child); this.children.unshift(this.children.pop()); }
    replaceChildren(...children) {
        this.children.forEach(child => { child.parentNode = null; });
        this.children = [];
        this._text = '';
        this.append(...children);
    }
    get textContent() { return this._text + this.children.map(child => child.textContent).join(''); }
    set textContent(value) { this.replaceChildren(); this._text = String(value ?? ''); this._html = null; }
    get innerHTML() {
        return this._html ?? this.textContent.replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;');
    }
    set innerHTML(value) { this.replaceChildren(); this._html = String(value); }
    contains(other) {
        for (let node = other; node; node = node.parentNode) if (node === this) return true;
        return false;
    }
    focus() { this.focused = true; if (this._document) this._document.activeElement = this; }
    click() { this.dispatchEvent({ type: "click" }); }
    matches(selector) {
        if (selector === 'body') return this.tagName === 'BODY';
        if (selector.startsWith('#')) return this.id === selector.slice(1);
        if (selector.startsWith('[')) {
            const [key, value] = selector.slice(1, -1).split('=');
            const actual = this.getAttribute(key) ?? (key.startsWith('data-') ? this.dataset[key.slice(5)] ?? null : null);
            return value === undefined ? actual !== null : actual === value.replaceAll('"', '').replaceAll("'", '');
        }
        if (selector.startsWith('.')) return selector.slice(1).split('.').every(name => this.classList.contains(name));
        if (/^[a-z][a-z0-9-]*$/i.test(selector)) return this.tagName === selector.toUpperCase();
        throw new Error(`Unsupported fixture selector: ${selector}`);
    }
    querySelectorAll(selector) {
        if (selector.startsWith(':scope > ')) return this.children.filter(child => child.matches(selector.slice(9)));
        if (selector.startsWith('body > ')) {
            const body = this.querySelector('body');
            return body ? body.children.filter(child => child.matches(selector.slice(7))) : [];
        }
        const alternatives = selector.split(',').map(part => part.trim());
        const found = [];
        const visit = node => node.children.forEach(child => {
            if (alternatives.some(part => child.matches(part))) found.push(child);
            visit(child);
        });
        visit(this);
        return found;
    }
    querySelector(selector) { return this.querySelectorAll(selector)[0] || null; }
    closest(selector) {
        for (let node = this; node; node = node.parentNode) {
            if (selector.split(',').some(part => node.matches(part.trim()))) return node;
        }
        return null;
    }
}

export function browserFixture({ stored = {}, dark = false } = {}) {
    const document = new Element('document');
    document.readyState = 'complete';
    document.documentElement = document.appendChild(new Element('html'));
    document.body = document.documentElement.appendChild(new Element('body'));
    document.createElement = tag => { const node = new Element(tag); node._document = document; return node; };
    document.createElementNS = (_, tag) => new Element(tag);
    document.getElementById = id => document.querySelector(`#${id}`);
    const html = readFrontend('index.html');
    const ids = ['workspace-nav-tooltip', 'chat-area', 'workspace-view', 'workspace-agents', 'workspace-agent-grid', 'workspace-library-tabs', 'workspace-library-select', 'workspace-evolve-actions',
        'library-tab-graph', 'library-tab-you', 'library-tab-people', 'workspace-agent-graph', 'agent-graph-nodes', 'agent-graph-svg', 'agent-graph-detail', 'workspace-library-book', 'library-sheet', 'library-you-title', 'library-you', 'library-people-title', 'library-people-search', 'library-people',
        'workspace-view-title', 'workspace-page-heading', 'workspace-page-description', 'workspace-stage',
        'workspace-context-toggle', 'workspace-theme', 'workspace-chat-title', 'chat-input', 'history-list', 'btn-new-session',
        'profile-selector', 'context-content', 'token-badge', 'token-badge-text', 'token-badge-fill',
        'fs-modal', 'knowledge-modal', 'memory-modal', 'automation-modal', 'connected-apps-modal', 'context-modal', 'evolve-modal', 'evolve-content'];
    const nodes = Object.fromEntries(ids.map(id => {
        if (!html.includes(`id="${id}"`)) throw new Error(`Fixture id is absent from real HTML: ${id}`);
        return [id, document.body.appendChild(new Element('div', { id }))];
    }));
    for (const id of ids.filter(id => id.endsWith('-modal'))) nodes[id].appendChild(new Element('div', { class: 'modal' }));
    for (const match of html.matchAll(/<button\b[^>]*\bdata-workspace-(?:page|modal)="[^"]+"[^>]*>/g)) {
        const attrs = Object.fromEntries([...match[0].matchAll(/([\w-]+)="([^"]*)"/g)].map(attr => [attr[1], attr[2]]));
        document.body.appendChild(new Element('button', attrs));
    }
    nodes['workspace-library-book'].appendChild(new Element('aside', { class: 'library-rail' }));
    nodes['workspace-agent-graph'].appendChild(new Element('div', { class: 'agent-graph-stage' }));
    document.body.appendChild(new Element('div', { class: 'input-actions' }));
    nodes['chat-area'].style.display = 'flex';
    nodes['workspace-view'].style.display = 'none';
    nodes['workspace-context-toggle'].setAttribute('aria-expanded', 'false');
    const storage = new Map(Object.entries(stored));
    const systemTheme = new EventTarget();
    systemTheme.matches = dark;
    const requests = [];
    const emissions = [];
    const context = vm.createContext({
        document,
        localStorage: { getItem: key => storage.get(key) ?? null, setItem: (key, value) => storage.set(key, String(value)) },
        navigator: { language: 'en', languages: ['en'] },
        matchMedia: () => systemTheme,
        CustomEvent: class { constructor(type, options = {}) { this.type = type; Object.assign(this, options); } },
        state: { contextModalOpen: false, profileId: 'default', sessionId: null },
        _profilesCache: [],
        $: id => document.getElementById(id),
        authFetch: (url, options) => new Promise((resolve, reject) => requests.push({ url, options, resolve, reject })),
        addEventListener: () => {},
        realtime: { emit: (...args) => emissions.push(args) },
        loadFs: async () => {},
        closeSettingsView: () => {},
        console, setTimeout, clearTimeout, setInterval, clearInterval,
    });
    context.window = context;
    const load = path => vm.runInContext(readFrontend(`js/${path}`), context, { filename: path });
    load('i18n_catalogs.js');
    load('i18n.js');
    load('utils.js');
    load('ui_panels.js');
    load('workspace.js');
    return { context, document, nodes, requests, emissions, storage, systemTheme };
}

export const settle = () => new Promise(resolve => setImmediate(resolve));
export const profileResponse = profiles => ({ ok: true, json: async () => ({ profiles }) });
