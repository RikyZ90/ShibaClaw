// ── Event Listeners ───────────────────────────────────────────
function isMobileSidebar() {
    return window.matchMedia("(max-width: 768px)").matches;
}

function setSidebarOpen(open) {
    const sidebar = $("sidebar");
    const backdrop = $("sidebar-backdrop");
    if (!sidebar) return;

    sidebar.classList.toggle("open", open);
    if (backdrop) {
        backdrop.classList.toggle("active", open && isMobileSidebar());
    }
}

function closeSidebarOnMobile() {
    if (isMobileSidebar()) {
        setSidebarOpen(false);
    }
}

window.closeSidebarOnMobile = closeSidebarOnMobile;

function initListeners() {
    if (state.listenersInitialized) return;
    state.listenersInitialized = true;

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
        closeSidebarOnMobile();
    });

    document.querySelectorAll(".btn-command[data-command]").forEach((btn) => {
        btn.addEventListener("click", () => {
            const cmd = btn.dataset.command;
            chatInput.value = cmd;
            sendMessage();
            closeSidebarOnMobile();
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
            closeSidebarOnMobile();
        });
    });

    $("mobile-menu-btn").addEventListener("click", () => {
        setSidebarOpen(!$("sidebar").classList.contains("open"));
    });

    $("sidebar-toggle").addEventListener("click", () => {
        setSidebarOpen(!$("sidebar").classList.contains("open"));
    });

    $("sidebar-backdrop")?.addEventListener("click", closeSidebarOnMobile);

    document.addEventListener("keydown", (e) => {
        if (e.key === "Escape") {
            closeSidebarOnMobile();
        }
    });

    document.addEventListener("click", (e) => {
        const sidebar = $("sidebar");
        const menuBtn = $("mobile-menu-btn");
        const toggleBtn = $("sidebar-toggle");
        if (!sidebar || !isMobileSidebar() || !sidebar.classList.contains("open")) return;
        if (sidebar.contains(e.target) || menuBtn?.contains(e.target) || toggleBtn?.contains(e.target)) return;
        closeSidebarOnMobile();
    });

    document.querySelectorAll(".modal-backdrop").forEach(bg => {
        bg.addEventListener("click", (e) => {
            if (e.target === bg && bg.dataset.backdropClose !== "false") {
                if (typeof window.closeModal === "function" && bg.id) {
                    window.closeModal(bg.id);
                } else {
                    bg.classList.remove("active");
                }
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
    // Extract token from URL if present (desktop launcher)
    const urlParams = new URLSearchParams(window.location.search);
    const urlToken = urlParams.get("token");
    if (urlToken) {
        setStoredToken(urlToken);
        // Clean up URL to keep it pretty
        window.history.replaceState({}, document.title, window.location.pathname);
    }

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


