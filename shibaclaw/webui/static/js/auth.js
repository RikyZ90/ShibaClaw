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
        // Token expired/invalid — show login
        showLogin("Session expired. Please re-enter your token.");
        throw new Error("Unauthorized");
    }
    return res;
}


