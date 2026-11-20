import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';

for (const category of ['ready', 'connection refused', 'timeout', 'auth failure', 'MCP initialization failure', 'tool discovery failure']) {
    test(`MCP test shows transport and ${category}`, async () => {
        let click;
        const status = { innerHTML: '' };
        const row = { querySelector: selector => ({ addEventListener: (event, callback) => {
            if (selector === '.mcp-row-test') click = callback;
        } }) };
        const elements = {
            'mcp-manager-container': { innerHTML: '' },
            'mcp-add-btn': { addEventListener() {} },
            'mcp-row-example': row,
            'mcp-status-example': status,
        };
        const context = {
            document: { getElementById: id => elements[id] },
            escapeHtml: value => String(value),
            setTimeout() {}, clearTimeout() {},
            authFetch: async url => ({ json: async () => url.endsWith('/test')
                ? { ok: category === 'ready', transport: 'streamableHttp', category, detail: 'Tools discovered.', error: 'Test failed.' }
                : { servers: [{ _name: 'example', type: 'streamableHttp' }] } }),
        };
        context.window = context;
        vm.runInNewContext(fs.readFileSync(new URL('../frontend/js/mcp_manager.js', import.meta.url), 'utf8'), context);
        await context.loadMcpManagerPanel();
        await click();
        assert.ok(status.innerHTML.includes(`streamableHttp: ${category}`), status.innerHTML);
        assert.ok(status.innerHTML.includes(category === 'ready' ? 'badge ok' : 'badge err'));
    });
}
