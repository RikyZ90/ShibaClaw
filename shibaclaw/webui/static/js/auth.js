// ── Auth ─────────────────────────────────────────────────────
const AUTH_KEY = "shibaclaw_token";

function getStoredToken() {
    return localStorage.getItem(AUTH_KEY) || "";
}

function setStoredToken(token) {
    localStorage.setItem(AUTH_KEY, token);
}

function clearStoredToken() {
    localStorage.removeItem(AUTH_KEY);
}

function handleUnauthorized(message = "Session expired. Please re-enter your token.") {
    clearStoredToken();

    if (typeof realtime !== "undefined") {
        realtime.disconnect({ clearToken: true });
    }

    if (typeof window.clearAllOAuthPolls === "function") {
        window.clearAllOAuthPolls();
    }

    if (typeof state !== "undefined") {
        state.socket = null;
        state._initialConnectDone = false;
        state.contextModalOpen = false;
        ["healthTimer", "historyTimer", "autoTimer"].forEach((timerKey) => {
            if (state[timerKey]) {
                clearInterval(state[timerKey]);
                state[timerKey] = null;
            }
        });
    }

    if (typeof showLogin === "function") {
        showLogin(message);
    }
}

/** Add auth header to all fetch calls. */
function authHeaders(extra = {}) {
    const token = getStoredToken();
    const headers = { ...extra };
    if (token) headers["Authorization"] = "Bearer " + token;
    return headers;
}

/** Wrapper around fetch that auto-adds auth headers. */
async function authFetch(url, opts = {}) {
    opts.headers = authHeaders(opts.headers || {});
    const res = await fetch(url, opts);
    if (res.status === 401) {
        handleUnauthorized();
        throw new Error("Unauthorized");
    }
    return res;
}


