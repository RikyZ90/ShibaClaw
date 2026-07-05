/**
 * Connected Apps — real service grid with Klavis as invisible backend gateway.
 * Settings > Connected Apps
 */

(function () {
  'use strict';

  /* ── auth helper ────────────────────────────────────────────── */
  function _h(extra) {
    return typeof authHeaders === 'function' ? authHeaders(extra || {}) : (extra || {});
  }

  /* ── icon map ─────────────────────────────────────────────────────── */
  const ICON_EMOJI = {
    email:            '\u2709\uFE0F',
    folder:           '\uD83D\uDCC1',
    table_chart:      '\uD83D\uDCCA',
    description:      '\uD83D\uDCC4',
    calendar_today:   '\uD83D\uDCC5',
    mail:             '\uD83D\uDCE7',
    cloud:            '\u2601\uFE0F',
    event:            '\uD83D\uDDD3\uFE0F',
    chat:             '\uD83D\uDCAC',
    notes:            '\uD83D\uDCDD',
    code:             '\uD83D\uDCBB',
    merge_type:       '\uD83D\uDD00',
    bug_report:       '\uD83D\uDC1B',
    article:          '\uD83D\uDCCB',
    inventory_2:      '\uD83D\uDCE6',
    archive:          '\uD83D\uDDC3\uFE0F',
    palette:          '\uD83C\uDFA8',
    contacts:         '\uD83D\uDC65',
    business_center:  '\uD83D\uDCBC',
    payment:          '\uD83D\uDCB3',
  };

  /* ── category accent colours ────────────────────────────────────── */
  const CAT_COLOR = {
    google:       '#4285F4',
    microsoft:    '#00A4EF',
    productivity: '#6B21A8',
    dev:          '#E36209',
    storage:      '#0F766E',
    design:       '#A855F7',
    crm:          '#16A34A',
  };

  /* ── state ──────────────────────────────────────────────────────────────── */
  let _apps = [];
  let _backendConfigured = false;  let _pendingOauthUrl = null;
  let _pendingOauthAppId = null;
  // Prevent double-connect and double-poll
  const _connecting = new Set();
  const _polling    = new Set();

  const CATEGORY_LABELS = {
    google:       'Google Services',
    microsoft:    'Microsoft 365',
    productivity: 'Productivity',
    dev:          'Development',
    storage:      'Storage',
    design:       'Design',
    crm:          'CRM / Finance',
  };

  /* ── public entry point ─────────────────────────────────────────────── */
  window.loadConnectedAppsPanel = async function () {
    const container = document.getElementById('connected-apps-container');
    if (!container) return;
    container.innerHTML = '<div class="ca-loading">Loading\u2026</div>';
    await Promise.all([_loadApps(), _loadBackend()]);
    _renderPanel(container);
  };

  /* ── auto-hook switchSettingsTab ──────────────────────────────────────── */
  (function _hookSwitchSettingsTab() {
    function _patch(original) {
      return function (tab, options) {
        const result = original ? original.call(this, tab, options) : undefined;
        if (tab === 'connected-apps') {
          if (typeof window.loadConnectedAppsPanel === 'function') {
            window.loadConnectedAppsPanel();
          }
        }
        return result;
      };
    }
    if (typeof window.switchSettingsTab === 'function') {
      window.switchSettingsTab = _patch(window.switchSettingsTab);
    } else {
      document.addEventListener('DOMContentLoaded', function () {
        if (typeof window.switchSettingsTab === 'function') {
          window.switchSettingsTab = _patch(window.switchSettingsTab);
        }
      }, { once: true });
    }
  })();

  /* ── data fetching ───────────────────────────────────────────────────── */
  async function _loadApps() {
    try {
      const res = await fetch('/api/apps', { headers: _h() });
      if (!res.ok) throw new Error('HTTP ' + res.status);
      const data = await res.json();
      _apps = data.apps || [];
    } catch (e) {
      _apps = [];
    }
  }

  async function _loadBackend() {
    try {
      const res = await fetch('/api/apps/backend', { headers: _h() });
      if (!res.ok) throw new Error('HTTP ' + res.status);
      const data = await res.json();
      _backendConfigured = !!data.configured;
    } catch (e) {
      _backendConfigured = false;
    }
  }

  /* ── render ───────────────────────────────────────────────────────────────── */
  function _renderPanel(container) {
    const grouped = _groupByCategory(_apps);

    const groupsHtml = Object.entries(grouped).map(([cat, apps]) => {
      const label = CATEGORY_LABELS[cat] || cat;
      const color = CAT_COLOR[cat] || '#888';
      const cardsHtml = apps.map(a => _renderAppCard(a, color)).join('');
      return `
        <div class="ca-group">
          <h3 class="ca-group__title" style="border-left:3px solid ${color};padding-left:8px">${_esc(label)}</h3>
          <div class="ca-cards">${cardsHtml}</div>
        </div>
      `;
    }).join('');

    const toggleClass = _backendConfigured ? 'ca-backend-toggle ca-backend-toggle--ok' : 'ca-backend-toggle';
    const toggleLabel = _backendConfigured
      ? '\u2699\uFE0F\u00a0Configured \u2713'
      : '\u2699\uFE0F\u00a0Configure backend';

    container.innerHTML = `
      <div class="ca-header">
        <div class="ca-header__top">
          <div>
            <h2 class="ca-title">Connected Apps</h2>
            <p class="ca-subtitle">Connect Gmail, Drive, Outlook, Slack, GitHub and more to ShibaClaw.</p>
          </div>
          <button class="${toggleClass}" id="ca-backend-toggle">${toggleLabel}</button>
        </div>
        ${!_backendConfigured ? '<div class="ca-warning-box">Configure the Klavis backend to enable app connections.</div>' : ''}
      </div>

      <div id="ca-backend-section" class="ca-backend-section" style="display:none">
        ${_renderBackendForm()}
      </div>

      <div class="ca-groups">${groupsHtml}</div>

      ${_renderConnectModal()}
    `;

    _bindEvents();
  }

  function _groupByCategory(apps) {
    const result = {};
    for (const app of apps) {
      if (!result[app.category]) result[app.category] = [];
      result[app.category].push(app);
    }
    return result;
  }

  function _renderAppCard(app, accentColor) {
    let badgeClass = 'ca-badge--disconnected';
    let badgeLabel = 'Not connected';
    let btnLabel   = 'Connect';
    let btnCls     = 'ca-card__btn ca-card__btn--connect';
    let btnAction  = `data-action="connect" data-app-id="${_esc(app.id)}"`;
    let cardMod    = '';

    if (app.connected && app.enabled) {
      badgeClass = 'ca-badge--connected';
      badgeLabel = 'Connected';
      btnLabel   = 'Disconnect';
      btnCls     = 'ca-card__btn ca-card__btn--disconnect';
      btnAction  = `data-action="disconnect" data-app-id="${_esc(app.id)}"`;
      cardMod    = ' ca-card--connected';
    } else if (app.connected && !app.enabled) {
      badgeClass = 'ca-badge--disabled';
      badgeLabel = 'Disabled';
      btnLabel   = 'Reconnect';
      btnCls     = 'ca-card__btn ca-card__btn--reconnect';
      btnAction  = `data-action="connect" data-app-id="${_esc(app.id)}"`;
    }

    const emoji  = ICON_EMOJI[app.icon] || '\uD83D\uDD17';
    const accent = accentColor || '#888';

    return `
      <div class="ca-card${cardMod}" id="ca-card-${_esc(app.id)}" style="--ca-accent:${accent}">
        <div class="ca-card__icon-wrap">
          <span class="ca-card__emoji" aria-hidden="true">${emoji}</span>
        </div>
        <div class="ca-card__body">
          <div class="ca-card__header">
            <span class="ca-card__name">${_esc(app.name)}</span>
            <span class="ca-badge ${badgeClass}">${badgeLabel}</span>
          </div>
          <p class="ca-card__desc">${_esc(app.description)}</p>
          <div class="ca-card__actions">
            <button class="${btnCls}" ${btnAction}>${btnLabel}</button>
          </div>
        </div>
      </div>
    `;
  }

  function _renderBackendForm() {
    return `
      <div class="ca-backend-form">
        <h4>Backend settings <small>(Klavis gateway)</small></h4>
        <p class="ca-hint">ShibaClaw uses Klavis to manage MCP connections for the apps above. Your API key is stored locally and never shared.</p>
        <div class="ca-form-group">
          <label for="ca-backend-token">Klavis API key</label>
          <input type="password" id="ca-backend-token" placeholder="Enter your Klavis API key" autocomplete="new-password">
          <small>Get your key at <a href="https://klavis.ai" target="_blank" rel="noopener">klavis.ai</a></small>
        </div>
        <div id="ca-backend-result" class="ca-test-result" style="display:none"></div>
        <button class="btn btn-primary" id="ca-backend-save-btn">Save</button>
      </div>
    `;
  }

  function _renderConnectModal() {
    return `
      <div class="ca-modal-overlay" id="ca-app-modal-overlay" style="display:none">
        <div class="ca-modal" role="dialog" aria-modal="true" aria-labelledby="ca-modal-title">
          <div class="ca-modal__header">
            <h3 id="ca-modal-title">Connecting\u2026</h3>
            <button class="ca-modal__close" id="ca-modal-close" aria-label="Close">&times;</button>
          </div>
          <div class="ca-modal__body" id="ca-modal-body">
            <div id="ca-modal-status" class="ca-test-result" style="display:none"></div>
          </div>
        </div>
      </div>
    `;
  }

  /* ── events ─────────────────────────────────────────────────────────────── */
  function _bindEvents() {
    const toggleBtn = document.getElementById('ca-backend-toggle');
    if (toggleBtn) {
      toggleBtn.addEventListener('click', () => {
        const section = document.getElementById('ca-backend-section');
        if (section) section.style.display = section.style.display === 'none' ? 'block' : 'none';
      });
    }

    const backendSave = document.getElementById('ca-backend-save-btn');
    if (backendSave) backendSave.addEventListener('click', _saveBackend);

    const modalClose = document.getElementById('ca-modal-close');
    if (modalClose) modalClose.addEventListener('click', _closeModal);
    const overlay = document.getElementById('ca-app-modal-overlay');
    if (overlay) overlay.addEventListener('click', (e) => { if (e.target === overlay) _closeModal(); });

    const container = document.getElementById('connected-apps-container');
    if (container) {
      container.addEventListener('click', async (e) => {
        const btn = e.target.closest('[data-action]');
        if (!btn) return;
        const action = btn.dataset.action;
        const appId  = btn.dataset.appId;
        if (action === 'connect')         await _connectApp(appId);
        else if (action === 'disconnect') await _disconnectApp(appId);
        else if (action === 'reopen-oauth') _reopenOauth();
      });
    }
  }

  async function _closeModal() {
    const overlay = document.getElementById('ca-app-modal-overlay');
    if (overlay) overlay.style.display = 'none';
    _pendingOauthUrl = null;

    if (_pendingOauthAppId) {
      try {
        await fetch(`/api/apps/${encodeURIComponent(_pendingOauthAppId)}/cancel`, {
          method: 'POST',
          headers: _h()
        });
        _refreshCard(_pendingOauthAppId);
      } catch (e) {
        console.error('Failed to cancel OAuth flow:', e);
      }
      _pendingOauthAppId = null;
    }

  }

  function _openModal(title) {
    const overlay = document.getElementById('ca-app-modal-overlay');
    const titleEl = document.getElementById('ca-modal-title');
    if (titleEl) titleEl.textContent = title;
    const statusEl = document.getElementById('ca-modal-status');
    if (statusEl) statusEl.style.display = 'none';
    if (overlay) overlay.style.display = 'flex';
  }

  function _showModalStatus(type, msg) {
    const waitEl = document.getElementById('ca-modal-waiting');
    if (waitEl) waitEl.remove();
    const el = document.getElementById('ca-modal-status');
    if (!el) return;
    el.className = 'ca-test-result ca-test-result--' + type;
    el.textContent = msg;
    el.style.display = 'block';
  }

  function _showWaitingForLogin(appId, appName, oauthUrl) {
    _pendingOauthAppId = appId;
    _pendingOauthUrl = oauthUrl;
    const body = document.getElementById('ca-modal-body');
    if (!body) return;
    const statusEl = document.getElementById('ca-modal-status');
    if (statusEl) statusEl.style.display = 'none';
    const old = document.getElementById('ca-modal-waiting');
    if (old) old.remove();

    const div = document.createElement('div');
    div.id = 'ca-modal-waiting';
    div.className = 'ca-modal-waiting';
    div.innerHTML = `
      <div class="ca-spinner" role="status" aria-label="Waiting"></div>
      <div class="ca-modal-waiting__text">
        Waiting for ${_esc(appName)} login\u2026<br>
        <span style="font-size:0.78rem;opacity:.7">Complete the authorisation in the browser tab, then return here.</span>
      </div>
      <button class="ca-modal-waiting__open-link" data-action="reopen-oauth">
        \uD83D\uDD17 Re-open login page
      </button>
    `;
    body.appendChild(div);
  }

  function _reopenOauth() {
    if (_pendingOauthUrl) window.open(_pendingOauthUrl, '_blank', 'noopener');
  }

  /* ── connect / disconnect ──────────────────────────────────────────────── */
  async function _connectApp(appId) {
    // Debounce: ignore if already connecting this app
    if (_connecting.has(appId)) return;
    _connecting.add(appId);

    const appDef = _apps.find(a => a.id === appId);
    const name = appDef ? appDef.name : appId;
    _openModal(`Connecting ${name}\u2026`);
    try {
      const res = await fetch(`/api/apps/${encodeURIComponent(appId)}/connect`, {
        method: 'POST',
        headers: _h(),
      });
      const data = await res.json();
      if (!res.ok || data.error) {
        _showModalStatus('error', `Failed: ${data.error || 'Unknown error'}`);
        return;
      }
      if (data.oauth_url) {
        window.open(data.oauth_url, '_blank', 'noopener');
        _showWaitingForLogin(appId, name, data.oauth_url);
        _pollStatus(appId, name).catch(() => {});
        return;
      }
      _showModalStatus('success', `\u2713 ${name} connected successfully.`);
      await _loadApps();
      _refreshCard(appId);
    } catch (e) {
      _showModalStatus('error', `Network error: ${e.message}`);
    } finally {
      _connecting.delete(appId);
    }
  }

  /**
   * Poll /api/apps/{appId}/status every 5 s until connected or timed-out.
   * Only one loop per appId runs at a time (_polling Set guard).
   */
  async function _pollStatus(appId, name) {
    if (_polling.has(appId)) return;
    _polling.add(appId);
    const MAX_ATTEMPTS = 24;
    try {
      for (let attempt = 0; attempt < MAX_ATTEMPTS; attempt++) {
        await new Promise(r => setTimeout(r, 5000));

        // Stop if modal was closed
        const overlay = document.getElementById('ca-app-modal-overlay');
        if (!overlay || overlay.style.display === 'none') return;

        try {
          const res = await fetch(
            `/api/apps/${encodeURIComponent(appId)}/status`,
            { headers: _h() }
          );
          if (!res.ok) continue;
          const data = await res.json();
          if (data.connected) {
            _showModalStatus('success', `\u2713 ${name} connected successfully.`);
            await _loadApps();
            _refreshCard(appId);
            return;
          }
        } catch (_) { /* transient error, keep trying */ }
      }
      _showModalStatus('error', 'Timed out waiting for authorisation. Please try again.');
    } finally {
      _polling.delete(appId);
    }
  }

  async function _disconnectApp(appId) {
    const appDef = _apps.find(a => a.id === appId);
    const name = appDef ? appDef.name : appId;
    if (!confirm(`Disconnect ${name}? This will remove the MCP server entry.`)) return;
    try {
      const res = await fetch(`/api/apps/${encodeURIComponent(appId)}/connect`, {
        method: 'DELETE',
        headers: _h(),
      });
      const data = await res.json();
      if (!res.ok || data.error) {
        alert(`Disconnect failed: ${data.error || 'Unknown error'}`);
        return;
      }
    } catch (e) {
      alert(`Network error: ${e.message}`);
      return;
    }
    await _loadApps();
    _refreshCard(appId);
  }

  function _refreshCard(appId) {
    const cardEl = document.getElementById(`ca-card-${appId}`);
    if (!cardEl) return;
    const app = _apps.find(a => a.id === appId);
    if (!app) return;
    const color = CAT_COLOR[app.category] || '#888';
    cardEl.outerHTML = _renderAppCard(app, color);
  }

  /* ── backend save ────────────────────────────────────────────────────────── */
  async function _saveBackend() {
    const token = (document.getElementById('ca-backend-token')?.value || '').trim();
    const resultEl = document.getElementById('ca-backend-result');
    const _show = (type, msg) => {
      if (!resultEl) return;
      resultEl.className = 'ca-test-result ca-test-result--' + type;
      resultEl.textContent = msg;
      resultEl.style.display = 'block';
    };
    if (!token) { _show('error', 'API key is required.'); return; }
    try {
      const res = await fetch('/api/apps/backend', {
        method: 'PUT',
        headers: _h({ 'Content-Type': 'application/json' }),
        body: JSON.stringify({ bearer_token: token }),
      });
      const data = await res.json();
      if (!res.ok || data.error) { _show('error', data.error || 'Save failed'); return; }
      _show('success', '\u2713 Backend settings saved.');
      await _loadBackend();
      const toggleBtn = document.getElementById('ca-backend-toggle');
      if (toggleBtn) {
        if (_backendConfigured) {
          toggleBtn.className = 'ca-backend-toggle ca-backend-toggle--ok';
          toggleBtn.textContent = '\u2699\uFE0F\u00a0Configured \u2713';
        } else {
          toggleBtn.className = 'ca-backend-toggle';
          toggleBtn.textContent = '\u2699\uFE0F\u00a0Configure backend';
        }
      }
      const warn = document.querySelector('.ca-warning-box');
      if (warn && _backendConfigured) warn.style.display = 'none';
    } catch (e) {
      _show('error', `Network error: ${e.message}`);
    }
  }

  /* ── utils ───────────────────────────────────────────────────────────────── */
  function _esc(str) {
    return String(str || '')
      .replace(/&/g, '&amp;')
      .replace(/"/g, '&quot;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');
  }
})();
