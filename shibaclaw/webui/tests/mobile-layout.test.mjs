import test from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import { readFrontend } from './browser-fixture.mjs';

function fixture(width = 375) {
    let document;
    const events = () => ({ listeners: {}, addEventListener(type, fn) { (this.listeners[type] ||= []).push(fn); } });
    const element = () => {
        const node = { ...events(), attributes: {}, classes: new Set(), style: {},
            setAttribute(name, value) { this.attributes[name] = value; },
            focus() { if (!this.inert && !this.parentNode?.inert) document.activeElement = this; },
            contains(target) { return target === this || target.parentNode === this; }, closest() { return null; } };
        node.classList = {
            toggle: (name, enabled) => enabled ? node.classes.add(name) : node.classes.delete(name),
            remove: name => node.classes.delete(name),
            contains: name => node.classes.has(name),
        };
        return node;
    };
    const nodes = Object.fromEntries(['sidebar', 'sidebar-backdrop', 'notification-center', 'mobile-menu-btn', 'sidebar-toggle',
        'btn-new-session', 'btn-send', 'chat-input', 'btn-stop'].map(id => [id, element()]));
    const sidebarButton = element();
    sidebarButton.parentNode = nodes.sidebar;
    const controls = [nodes['mobile-menu-btn'], nodes['sidebar-toggle'], element()];
    const properties = new Map();
    const rootStyle = { setProperty: (name, value) => properties.set(name, value), removeProperty: name => properties.delete(name) };
    document = { ...events(), documentElement: { style: rootStyle }, activeElement: nodes['chat-input'],
        getElementById: id => nodes[id] || null,
        querySelectorAll: selector => selector === '.mobile-menu-btn, .workspace-mobile-menu, .sidebar-toggle' ? controls : [] };
    const mediaQueries = new Map();
    const matchMedia = query => {
        if (!mediaQueries.has(query)) {
            const maxWidth = /^\(max-width: (\d+)px\)$/.exec(query);
            assert.ok(maxWidth, `Unsupported media query: ${query}`);
            mediaQueries.set(query, { ...events(), media: query, maxWidth: Number(maxWidth[1]), matches: width <= Number(maxWidth[1]) });
        }
        return mediaQueries.get(query);
    };
    const viewport = { ...events(), height: 667, offsetTop: 0, scale: 1 };
    nodes['chat-input'].scrollHeight = 600;
    const app = vm.createContext({ ...events(), document, visualViewport: viewport, matchMedia, innerWidth: width,
        $: id => nodes[id] || null, state: {}, chatInput: nodes['chat-input'], btnSend: nodes['btn-send'],
        getComputedStyle: () => ({ maxHeight: '84px' }), setTimeout: () => 1, clearTimeout() {}, clockTimer: null,
        console, navigator: {}, localStorage: { getItem: () => null } });
    app.window = app;
    vm.runInContext(readFrontend('js/chat.js'), app);
    vm.runInContext(readFrontend('js/main.js'), app);
    const resize = nextWidth => {
        width = app.innerWidth = nextWidth;
        const changed = [];
        for (const media of mediaQueries.values()) {
            const matches = width <= media.maxWidth;
            if (media.matches !== matches) {
                media.matches = matches;
                changed.push(media);
            }
        }
        app.listeners.resize?.forEach(fn => fn());
        changed.forEach(media => media.listeners.change?.forEach(fn => fn({ matches: media.matches, media: media.media })));
    };
    return { app, nodes, viewport, properties, controls, resize, matchMedia, document, sidebarButton };
}

test('keyboard viewport changes resize the visible mobile shell and cap multiline input', () => {
    const { app, viewport, properties, nodes } = fixture();
    app.initListeners();
    assert.equal(properties.get('--mobile-viewport-height'), '667px');
    assert.equal(nodes['chat-input'].style.height, '84px');
    viewport.height = 360;
    viewport.offsetTop = 12;
    viewport.listeners.resize.forEach(fn => fn());
    assert.equal(properties.get('--mobile-viewport-height'), '360px');
    assert.equal(properties.get('--mobile-viewport-top'), '12px');
    assert.equal(viewport.listeners.scroll.length, 1);
    app.initListeners();
    assert.equal(viewport.listeners.resize.length, 1, 'initialization must not duplicate viewport handlers');
});

test('pinch zoom and desktop resizing release the mobile viewport override', () => {
    const { app, viewport, resize, properties } = fixture();
    app.syncMobileViewport();
    viewport.scale = 2;
    app.syncMobileViewport();
    assert.equal(properties.has('--mobile-viewport-height'), false);
    viewport.scale = 1;
    app.syncMobileViewport();
    resize(1280);
    app.syncMobileViewport();
    assert.equal(properties.has('--mobile-viewport-height'), false);
    assert.equal(properties.has('--mobile-viewport-top'), false);
});

test('closed mobile navigation leaves the focus order and desktop navigation remains accessible', () => {
    const { app, nodes, resize, controls } = fixture();
    app.setSidebarOpen(false);
    assert.equal(nodes.sidebar.inert, true);
    assert.equal(nodes.sidebar.attributes['aria-hidden'], 'true');
    app.setSidebarOpen(true);
    assert.equal(nodes.sidebar.inert, false);
    assert.ok(controls.every(button => button.attributes['aria-expanded'] === 'true'));
    app.closeSidebarOnMobile();
    assert.equal(nodes.sidebar.inert, true);
    assert.ok(controls.every(button => button.attributes['aria-expanded'] === 'false'));
    resize(1280);
    app.setSidebarOpen(false);
    assert.equal(nodes.sidebar.inert, false);
    assert.equal(nodes.sidebar.attributes['aria-hidden'], 'false');
});

test('tablet and desktop resize updates sidebar accessibility and focus in both directions', () => {
    const { app, nodes, controls, resize, matchMedia, document, sidebarButton } = fixture(850);
    app.initListeners();
    const assertSidebar = mobile => {
        assert.equal(app.isMobileSidebar(), mobile);
        assert.equal(nodes.sidebar.inert, mobile);
        assert.equal(nodes.sidebar.attributes['aria-hidden'], String(mobile));
        assert.equal(nodes.sidebar.classList.contains('open'), false);
        assert.equal(nodes['sidebar-backdrop'].classList.contains('active'), false);
        assert.ok(controls.every(button => button.attributes['aria-expanded'] === 'false'));
        nodes['chat-input'].focus();
        sidebarButton.focus();
        assert.equal(document.activeElement === sidebarButton, !mobile);
    };
    assert.equal(matchMedia('(max-width: 768px)').matches, false);
    assertSidebar(true);
    resize(1280);
    assertSidebar(false);
    resize(850);
    assertSidebar(true);
    app.setSidebarOpen(true);
    assert.equal(nodes['sidebar-backdrop'].classList.contains('active'), true);
    sidebarButton.focus();
    assert.equal(document.activeElement, sidebarButton);
    resize(901);
    assertSidebar(false);
    resize(900);
    assertSidebar(true);
});
