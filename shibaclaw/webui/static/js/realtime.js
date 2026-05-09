/**
 * realtime.js — Native WebSocket adapter for ShibaClaw WebUI.
 *
 * Drop-in replacement for the Socket.IO client.  Exposes a thin
 * event-emitter API identical to the one previously consumed by
 * chat.js, main.js, profiles.js, ui_panels.js and speech.js:
 *
 *   realtime.on(event, handler)
 *   realtime.off(event, handler)
 *   realtime.emit(type, payload)
 *   realtime.request(type, payload)      → Promise<response>
 *   realtime.connected                   → boolean
 *   realtime.sessionId / profileId       → current values
 */

const realtime = (() => {
    let ws = null;
    let connected = false;
    let sessionId = "";
    let profileId = "default";
    let authToken = "";
    let reconnectEnabled = true;
    const listeners = {};          // event → Set<fn>
    const pendingRequests = {};    // id → {resolve, reject, timer}
    let reconnectDelay = 1000;
    let reconnectTimer = null;
    let pingTimer = null;
    let idCounter = 0;

    function nextId() { return "r" + (++idCounter) + "_" + Date.now().toString(36); }

    // ── Event emitter ───────────────────────────────────────

    function on(event, fn)  { (listeners[event] ??= new Set()).add(fn); }
    function off(event, fn) { listeners[event]?.delete(fn); }
    function fire(event, data) {
        for (const fn of (listeners[event] ?? [])) {
            try { fn(data); } catch(e) { console.error("[realtime] handler error (", event, "):", e); }
        }
    }

    function _rejectPendingRequests(message) {
        for (const [id, pending] of Object.entries(pendingRequests)) {
            clearTimeout(pending.timer);
            pending.reject(new Error(message));
            delete pendingRequests[id];
        }
    }

    // ── Connection ──────────────────────────────────────────

    function connect(token) {
        if (typeof token === "string") {
            authToken = token;
        }
        reconnectEnabled = true;

        if (ws && (ws.readyState === WebSocket.CONNECTING || ws.readyState === WebSocket.OPEN)) return;

        const proto = location.protocol === "https:" ? "wss:" : "ws:";
        const url = `${proto}//${location.host}/ws`;

        ws = new WebSocket(url);

        ws.onopen = () => {
            const savedSessionId = localStorage.getItem("shiba_session_id");
            ws.send(JSON.stringify({ type: "auth", token: authToken || "", session_id: savedSessionId || "" }));
        };

        ws.onmessage = (ev) => {
            let msg;
            try { msg = JSON.parse(ev.data); } catch { return; }
            _dispatch(msg);
        };

        ws.onclose = (ev) => {
            const wasConnected = connected;
            connected = false;
            ws = null;
            _stopPing();
            _rejectPendingRequests(ev.reason || "connection closed");
            if (wasConnected) fire("disconnect", { code: ev.code, reason: ev.reason });
            _scheduleReconnect();
        };

        ws.onerror = () => {}; // onclose will fire after
    }

    function disconnect(options = {}) {
        const { clearToken = false } = options;
        reconnectEnabled = false;
        if (clearToken) {
            authToken = "";
        }
        if (reconnectTimer) { clearTimeout(reconnectTimer); reconnectTimer = null; }
        _stopPing();
        _rejectPendingRequests("disconnected");
        if (ws) { ws.close(1000); ws = null; }
        connected = false;
    }

    function _scheduleReconnect() {
        if (!reconnectEnabled || reconnectTimer) return;
        if (reconnectTimer) return;
        reconnectTimer = setTimeout(() => {
            reconnectTimer = null;
            connect();
        }, reconnectDelay);
        reconnectDelay = Math.min(reconnectDelay * 1.5, 15000);
    }

    function _startPing() {
        _stopPing();
        pingTimer = setInterval(() => {
            if (ws?.readyState === WebSocket.OPEN) ws.send(JSON.stringify({ type: "ping" }));
        }, 25000);
    }
    function _stopPing() { if (pingTimer) { clearInterval(pingTimer); pingTimer = null; } }

    // ── Dispatch incoming messages ──────────────────────────

    function _dispatch(msg) {
        const t = msg.type;

        if (t === "connected") {
            connected = true;
            reconnectDelay = 1000;
            sessionId = msg.session_id || sessionId;
            profileId = msg.profile_id || profileId;
            _startPing();
            fire("connected", msg);
            return;
        }

        if (t === "pong") return;

        if (t === "error") {
            fire("error", msg);
            return;
        }

        // Request/response pattern (for transcribe etc.)
        if (msg.id && pendingRequests[msg.id]) {
            const p = pendingRequests[msg.id];
            delete pendingRequests[msg.id];
            clearTimeout(p.timer);
            if (msg.error) p.reject(new Error(msg.error));
            else p.resolve(msg);
            // Also fire as event so listeners can react
        }

        // Map server message types to events
        if (t === "message_ack")      fire("message_ack", msg);
        else if (t === "message_queued") fire("message_queued", msg);
        else if (t === "thinking")    fire("agent_thinking", msg);
        else if (t === "tool")        fire("agent_tool", msg);
        else if (t === "response_chunk") fire("agent_response_chunk", msg);
        else if (t === "response")    fire("agent_response", msg);
        else if (t === "session_reset")  {
            sessionId = msg.session_id || sessionId;
            profileId = msg.profile_id || profileId;
            fire("session_reset", msg);
        }
        else if (t === "session_status") fire("session_status", msg);
        else if (t === "transcribe_result") fire("transcribe_result", msg);
        else fire(t, msg);  // generic fallback
    }

    // ── Send helpers ────────────────────────────────────────

    function emit(type, payload) {
        if (!ws || ws.readyState !== WebSocket.OPEN) return false;
        const msg = { type, ...(payload || {}) };
        ws.send(JSON.stringify(msg));
        return true;
    }

    /**
     * Send a message and wait for a response with matching id.
     * Used for transcribe_audio (request/response pattern).
     */
    function request(type, payload, timeoutMs = 30000) {
        return new Promise((resolve, reject) => {
            const id = nextId();
            const msg = { type, id, ...(payload || {}) };
            const timer = setTimeout(() => {
                delete pendingRequests[id];
                reject(new Error("timeout"));
            }, timeoutMs);
            pendingRequests[id] = { resolve, reject, timer };
            if (ws?.readyState === WebSocket.OPEN) {
                ws.send(JSON.stringify(msg));
            } else {
                delete pendingRequests[id];
                clearTimeout(timer);
                reject(new Error("not connected"));
            }
        });
    }

    // ── Public API ──────────────────────────────────────────

    return {
        connect,
        disconnect,
        on,
        off,
        emit,
        request,
        fire,
        get connected() { return connected; },
        get sessionId() { return sessionId; },
        set sessionId(v) { sessionId = v; },
        get profileId() { return profileId; },
        set profileId(v) { profileId = v; },
    };
})();
