// ── Login/Logout UI ───────────────────────────────────────────
function syncFooterActions() {
    const logoutBtn = document.getElementById("btn-logout");
    if (logoutBtn) logoutBtn.hidden = !state.authRequired;
}

function showLogin(errorMsg = "") {
    const overlay = document.getElementById("login-overlay");
    const appContainer = document.getElementById("app-container");
    const errorEl = document.getElementById("login-error");
    const tokenInput = document.getElementById("login-token");

    overlay.style.display = "flex";
    appContainer.style.display = "none";

    if (errorMsg) {
        errorEl.textContent = errorMsg;
        errorEl.style.display = "block";
        // Shake animation
        const card = overlay.querySelector(".login-card");
        card.classList.remove("shake");
        void card.offsetWidth; // force reflow
        card.classList.add("shake");
    } else {
        errorEl.style.display = "none";
    }

    setTimeout(() => tokenInput.focus(), 100);
}

function hideLogin() {
    const overlay = document.getElementById("login-overlay");
    const appContainer = document.getElementById("app-container");
    overlay.style.display = "none";
    appContainer.style.display = "";
}

async function attemptLogin(token) {
    try {
        const res = await fetch("/api/auth/verify", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ token }),
        });
        const data = await res.json();
        if (data.valid) {
            setStoredToken(token);
            hideLogin();
            startApp();
            return true;
        } else {
            showLogin("Invalid token. Check the terminal output.");
            return false;
        }
    } catch (e) {
        showLogin("Connection error. Is the server running?");
        return false;
    }
}

function logout() {
    clearStoredToken();
    _clearAllOAuthPolls();
    if (state.socket) {
        state.socket.disconnect({ clearToken: true });
        state.socket = null;
    }
    if (state.healthTimer) {
        clearInterval(state.healthTimer);
        state.healthTimer = null;
    }
    if (state.historyTimer) {
        clearInterval(state.historyTimer);
        state.historyTimer = null;
    }
    if (state.autoTimer) {
        clearInterval(state.autoTimer);
        state.autoTimer = null;
    }
    state._initialConnectDone = false;
    state.contextModalOpen = false;
    state.processing = false;
    state.sessionId = null;
    state.sessionLoadSeq++;
    if (typeof resetNotificationCenter === "function") {
        resetNotificationCenter();
    }
    setStatusIndicator("disconnected");
    const logoutBtn = document.getElementById("btn-logout");
    if (logoutBtn) logoutBtn.hidden = true;
    showLogin();
}

function startApp() {
    initSocket();
    initListeners();
    fetchStatus();
    loadHistory();
    initAutomationSections();
    refreshTokenBadge();
    initFileHandlers();
    initOnboardWizard();
    if (typeof initNotificationCenter === "function") {
        void initNotificationCenter();
    }
    if (typeof loadKnowledgeBases === "function") {
        void loadKnowledgeBases();
    }
    if (typeof initMentions === "function") {
        initMentions();
    }
    chatInput.focus();

    syncFooterActions();

    // Gateway health check every 5s
    checkGatewayHealth();
    if (state.healthTimer) clearInterval(state.healthTimer);
    state.healthTimer = setInterval(checkGatewayHealth, 5000);

    // Auto-refresh history every 30s
    if (state.historyTimer) clearInterval(state.historyTimer);
    state.historyTimer = setInterval(loadHistory, 30000);

    // Auto-refresh automation every 30s
    if (state.autoTimer) clearInterval(state.autoTimer);
    state.autoTimer = setInterval(() => { loadCronSection(); loadHeartbeatSection(); }, 30000);
}
