// ── Login/Logout UI ───────────────────────────────────────────
function syncFooterActions() {
    const logoutBtn = document.getElementById("btn-logout");
    if (logoutBtn) logoutBtn.hidden = !state.authRequired;
}

function showLogin(errorMsg = "", isSetup = false) {
    const overlay = document.getElementById("login-overlay");
    const appContainer = document.getElementById("app-container");
    const errorEl = document.getElementById("login-error");
    const usernameInput = document.getElementById("login-username");

    // Update UI text based on mode
    document.getElementById("login-subtitle").textContent = isSetup
        ? "Create an admin account to secure your keys"
        : "Enter your credentials to continue";
    document.getElementById("btn-login-text").textContent = isSetup ? "Setup Account" : "Connect";
    document.getElementById("btn-login-icon").textContent = isSetup ? "person_add" : "login";

    const hint = document.getElementById("login-hint");
    if (isSetup) {
        hint.style.display = "block";
        hint.innerHTML = "Your API keys will be migrated to an encrypted vault.";
    } else {
        hint.style.display = "none";
    }

    // Set a data attribute on the button to know what action to perform
    document.getElementById("btn-login").dataset.mode = isSetup ? "setup" : "login";

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

    setTimeout(() => {
        if (usernameInput) usernameInput.focus();
    }, 100);
}

function hideLogin() {
    const overlay = document.getElementById("login-overlay");
    const appContainer = document.getElementById("app-container");
    overlay.style.display = "none";
    appContainer.style.display = "";
}

async function attemptLogin(username, password, mode) {
    try {
        const endpoint = mode === "setup" ? "/api/auth/setup" : "/api/auth/login";
        const res = await fetch(endpoint, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ username, password }),
        });
        const data = await res.json();

        if (res.ok && data.status === "ok") {
            setStoredToken(data.session_token);
            hideLogin();
            startApp();
            return true;
        } else {
            showLogin(data.error || "Authentication failed.", mode === "setup");
            return false;
        }
    } catch (e) {
        showLogin("Connection error. Is the server running?", mode === "setup");
        return false;
    }
}

window.openChangePasswordModal = function() {
    document.getElementById("cp-old").value = "";
    document.getElementById("cp-new").value = "";
    document.getElementById("cp-confirm").value = "";
    document.getElementById("cp-error").style.display = "none";
    document.getElementById("change-password-modal").classList.add("active");
};

window.submitChangePassword = async function() {
    const oldPassword = document.getElementById("cp-old").value.trim();
    const newPassword = document.getElementById("cp-new").value.trim();
    const confirmPassword = document.getElementById("cp-confirm").value.trim();
    const errorEl = document.getElementById("cp-error");

    if (!oldPassword || !newPassword || !confirmPassword) {
        errorEl.textContent = "All fields are required.";
        errorEl.style.display = "block";
        return;
    }

    if (newPassword !== confirmPassword) {
        errorEl.textContent = "New passwords do not match.";
        errorEl.style.display = "block";
        return;
    }

    if (newPassword.length < 6) {
        errorEl.textContent = "New password must be at least 6 characters.";
        errorEl.style.display = "block";
        return;
    }

    try {
        const res = await authFetch("/api/auth/change-password", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ old_password: oldPassword, new_password: newPassword }),
        });

        const data = await res.json();

        if (res.ok && data.status === "ok") {
            closeModal("change-password-modal");
            if (typeof toast !== "undefined") { // assuming toast is globally available
                shibaDialog("alert", "Success", "Password changed successfully.", { confirmText: "Close" });
            } else {
                alert("Password changed successfully.");
            }
        } else {
            errorEl.textContent = data.error || "Failed to change password.";
            errorEl.style.display = "block";
        }
    } catch (e) {
        errorEl.textContent = "Connection error. Is the server running?";
        errorEl.style.display = "block";
    }
};

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
