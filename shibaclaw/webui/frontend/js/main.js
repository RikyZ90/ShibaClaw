// ── Event Listeners ───────────────────────────────────────────
const sidebarMediaQuery = window.matchMedia("(max-width: 900px)");

function isMobileSidebar() {
    return sidebarMediaQuery.matches;
}

function setSidebarOpen(open) {
    const sidebar = $("sidebar");
    const backdrop = $("sidebar-backdrop");
    if (!sidebar) return;

    if (open && isMobileSidebar()) {
        const nc = $("notification-center");
        if (nc) nc.classList.remove("is-open");
    }

    sidebar.classList.toggle("open", open);
    sidebar.inert = isMobileSidebar() && !open;
    sidebar.setAttribute("aria-hidden", String(sidebar.inert));
    document.querySelectorAll(".mobile-menu-btn, .workspace-mobile-menu, .sidebar-toggle").forEach(button => {
        button.setAttribute("aria-controls", "sidebar");
        button.setAttribute("aria-expanded", String(open && isMobileSidebar()));
    });
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

// Mobile browser toolbars and keyboards can shrink the visual viewport without
// changing 100dvh. Keep the composer inside the space the user can actually see.
function syncMobileViewport() {
    const viewport = window.visualViewport;
    const style = document.documentElement.style;
    if (isMobileSidebar() && viewport && viewport.scale === 1) {
        style.setProperty("--mobile-viewport-height", `${Math.round(viewport.height)}px`);
        style.setProperty("--mobile-viewport-top", `${Math.round(viewport.offsetTop)}px`);
    } else {
        style.removeProperty("--mobile-viewport-height");
        style.removeProperty("--mobile-viewport-top");
    }
    autoResizeInput();
}

function initListeners() {
    if (state.listenersInitialized) return;
    state.listenersInitialized = true;

    setSidebarOpen(false);
    syncMobileViewport();
    window.visualViewport?.addEventListener("resize", syncMobileViewport);
    window.visualViewport?.addEventListener("scroll", syncMobileViewport);
    window.addEventListener("resize", syncMobileViewport);
    sidebarMediaQuery.addEventListener("change", () => setSidebarOpen(false));

    btnSend.addEventListener("click", sendMessage);

    chatInput.addEventListener("input", () => {
        updateSendButton();
        autoResizeInput();
    });

    chatInput.addEventListener("keydown", (e) => {
        if (e.key === "Enter" && !e.shiftKey) {
            // Respect per-user mobile Enter->newline override (localStorage)
            try {
                const mobileEnter = localStorage.getItem("shibaclaw_mobile_enter_newline") === "true";
                const isTouch = ('ontouchstart' in window) || (navigator.maxTouchPoints && navigator.maxTouchPoints > 0);
                if (mobileEnter && isTouch) {
                    // allow default behavior (insert newline) on touch devices
                    return;
                }
            } catch (err) { }

            e.preventDefault();
            sendMessage();
        }
    });

    $("btn-new-session").addEventListener("click", () => {
        if (typeof closeSettingsView === "function") closeSettingsView();
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

    document.querySelectorAll(".hint-card[data-hint]").forEach((card) => {
        card.addEventListener("click", () => {
            chatInput.value = card.dataset.hintKey ? t(card.dataset.hintKey) : card.dataset.hint;
            autoResizeInput();
            updateSendButton();
            chatInput.focus();
            closeSidebarOnMobile();
        });
    });

    $("mobile-menu-btn").addEventListener("click", () => {
        setSidebarOpen(!$("sidebar").classList.contains("open"));
    });

    $("sidebar-toggle").addEventListener("click", () => {
        if (isMobileSidebar()) setSidebarOpen(!$("sidebar").classList.contains("open"));
        else if (typeof window.toggleWorkspaceSidebar === "function") window.toggleWorkspaceSidebar();
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
        if (sidebar.contains(e.target) || menuBtn?.contains(e.target) || toggleBtn?.contains(e.target) || e.target.closest(".workspace-mobile-menu")) return;
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
        const loc = (window.i18n && typeof window.i18n.clockLocale === "function")
            ? window.i18n.clockLocale()
            : undefined;
        clockEl.textContent = now.toLocaleTimeString(loc, {
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
    document.addEventListener("shibaclaw:localechange", updateClock);
}


// ── Initialize ────────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", async () => {
    if (window.i18n) {
        window.i18n.applyI18n();
        window.i18n.initLangSwitcher();
    }

    // Extract token from URL if present (desktop launcher)
    const urlParams = new URLSearchParams(window.location.search);
    const urlToken = urlParams.get("token");
    if (urlToken) {
        setStoredToken(urlToken);
        // Clean up URL to keep it pretty
        window.history.replaceState({}, document.title, window.location.pathname);
    }

    // Telegram Mini App only (real Telegram.WebApp — not browser CDN stub)
    if (typeof attemptTelegramMiniAuth === "function" && typeof isTelegramMiniApp === "function" && isTelegramMiniApp()) {
        const handled = await attemptTelegramMiniAuth();
        if (handled) {
            return;
        }
    }

    // Wire up login form
    const loginBtn = document.getElementById("btn-login");
    const loginUsernameInput = document.getElementById("login-username");
    const loginPasswordInput = document.getElementById("login-password");
    const logoutBtn = document.getElementById("btn-logout");

    const handleLoginSubmit = () => {
        const username = loginUsernameInput.value.trim();
        const password = loginPasswordInput.value.trim();
        const mode = loginBtn.dataset.mode;
        if (username && password) attemptLogin(username, password, mode);
    };

    if (loginBtn) {
        loginBtn.addEventListener("click", handleLoginSubmit);
    }
    if (loginUsernameInput) {
        loginUsernameInput.addEventListener("keydown", (e) => {
            if (e.key === "Enter") loginPasswordInput.focus();
        });
    }
    if (loginPasswordInput) {
        loginPasswordInput.addEventListener("keydown", (e) => {
            if (e.key === "Enter") handleLoginSubmit();
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

        // Password login disabled on telegram-mini surface (nginx header)
        if (data.telegram_mini && data.password_login === false) {
            showTelegramAccessDenied("Open this page from the Telegram Mini App menu.");
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

        // No valid token — show login (either setup or normal)
        showLogin("", data.needs_setup);
    } catch (e) {
        // Can't reach server — start anyway (will show errors naturally)
        startApp();
    }
    // Initialize Tally Feedback popup
    initFeedbackPopup();
});

// ── Tally Feedback Popup ──────────────────────────────────────
function initFeedbackPopup(force = false) {
    if (!force && localStorage.getItem('shibaclaw_feedback_v1_shown') === 'true') {
        return;
    }

    // Show popup 5 seconds after start
    setTimeout(() => {
        const popup = document.getElementById('feedback-popup');
        const dismissBtn = document.getElementById('feedback-dismiss');
        const feedbackLink = document.getElementById('feedback-link');

        if (popup && dismissBtn) {
            popup.classList.add('show');

            const dismissPopup = () => {
                popup.classList.remove('show');
                localStorage.setItem('shibaclaw_feedback_v1_shown', 'true');
            };

            dismissBtn.onclick = dismissPopup;
            if (feedbackLink) {
                feedbackLink.onclick = dismissPopup;
            }
        }
    }, force ? 100 : 5000); // 5 seconds delay (or immediate if forced)
}

window.initFeedbackPopup = initFeedbackPopup;





