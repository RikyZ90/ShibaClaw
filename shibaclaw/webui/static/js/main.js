// ── Event Listeners ───────────────────────────────────────────
function initListeners() {
    btnSend.addEventListener("click", sendMessage);

    chatInput.addEventListener("input", () => {
        updateSendButton();
        autoResizeInput();
    });

    chatInput.addEventListener("keydown", (e) => {
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });

    $("btn-new-session").addEventListener("click", () => {
        realtime.emit("new_session");
    });

    document.querySelectorAll(".btn-command[data-command]").forEach((btn) => {
        btn.addEventListener("click", () => {
            const cmd = btn.dataset.command;
            chatInput.value = cmd;
            sendMessage();
        });
    });

    $("btn-stop").addEventListener("click", () => {
        if (state.processing) {
            realtime.emit("stop");
            state.processing = false;
            setWorkingState(false);
            clearTimeout(state._typingBubbleTimeout);
            hideTypingBubble();
            hideThinking();
            updateSendButton();
            if (window.speechTTS) window.speechTTS.stop();
        }
    });

    document.querySelectorAll(".hint-card").forEach((card) => {
        card.addEventListener("click", () => {
            chatInput.value = card.dataset.hint;
            sendMessage();
        });
    });

    $("mobile-menu-btn").addEventListener("click", () => {
        $("sidebar").classList.toggle("open");
    });

    $("sidebar-toggle").addEventListener("click", () => {
        $("sidebar").classList.toggle("open");
    });

    document.querySelectorAll(".modal-backdrop").forEach(bg => {
        bg.addEventListener("click", (e) => {
            if (e.target === bg && bg.dataset.backdropClose !== "false") {
                bg.classList.remove("active");
            }
        });
    });

    // Clock
    function updateClock() {
        const clockEl = $("clock");
        if (!clockEl) return;
        const now = new Date();
        clockEl.textContent = now.toLocaleTimeString([], {
            hour: "2-digit",
            minute: "2-digit",
        });
    }

    function startClock() {
        if (clockTimer) {
            clearTimeout(clockTimer);
        }

        const tick = () => {
            updateClock();
            const now = new Date();
            const elapsedMs = now.getSeconds() * 1000 + now.getMilliseconds();
            const delay = Math.max(1000, 60000 - elapsedMs);
            clockTimer = window.setTimeout(tick, delay + 50);
        };

        tick();
    }

    startClock();
}


// ── Initialize ────────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", async () => {
    // Wire up login form
    const loginBtn = document.getElementById("btn-login");
    const loginInput = document.getElementById("login-token");
    const logoutBtn = document.getElementById("btn-logout");

    if (loginBtn) {
        loginBtn.addEventListener("click", () => {
            const token = loginInput.value.trim();
            if (token) attemptLogin(token);
        });
    }
    if (loginInput) {
        loginInput.addEventListener("keydown", (e) => {
            if (e.key === "Enter") {
                const token = loginInput.value.trim();
                if (token) attemptLogin(token);
            }
        });
    }
    if (logoutBtn) {
        logoutBtn.addEventListener("click", logout);
    }

    // Check if auth is required
    try {
        const res = await fetch("/api/auth/status");
        const data = await res.json();
        state.authRequired = data.auth_required;

        if (!data.auth_required) {
            // Auth disabled — start directly
            startApp();
            return;
        }

        // Check stored token
        const storedToken = getStoredToken();
        if (storedToken) {
            const verifyRes = await fetch("/api/auth/verify", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ token: storedToken }),
            });
            const verifyData = await verifyRes.json();
            if (verifyData.valid) {
                hideLogin();
                startApp();
                return;
            }
        }

        // No valid token — show login
        showLogin();
    } catch (e) {
        // Can't reach server — start anyway (will show errors naturally)
        startApp();
    }
});


