// ── Telegram Mini App bootstrap ──
// Mini App (Telegram.WebApp): full chat UI (+ optional sidebar).
// Browser / site (:8443): never touches this path → full WebUI.

function getTelegramWebApp() {
    try {
        return window.Telegram && Telegram.WebApp ? Telegram.WebApp : null;
    } catch (_) {
        return null;
    }
}

function hasTelegramLaunchParams() {
    // Real Mini App launch puts tgWebAppData / tgWebAppPlatform in hash or query.
    // Plain ?tgWebApp=1 (our menu URL marker) is NOT enough — browsers/iframes use that too.
    try {
        const raw = String(location.hash || "") + "&" + String(location.search || "");
        return /(?:^|[?#&])tgWebAppData=/.test(raw) || /(?:^|[?#&])tgWebAppPlatform=/.test(raw);
    } catch (_) {
        return false;
    }
}

function isTelegramMiniApp() {
    // telegram-web-app.js always creates a stub in normal browsers — do NOT trust
    // bare window.Telegram.WebApp. Require real initData or Telegram launch params.
    const wa = getTelegramWebApp();
    if (!wa) return false;
    if (typeof wa.initData === "string" && wa.initData.length > 0) return true;
    return hasTelegramLaunchParams();
}

function hasTelegramInitData() {
    const wa = getTelegramWebApp();
    return !!(wa && typeof wa.initData === "string" && wa.initData.length > 0);
}

function applyTelegramTheme() {
    const wa = getTelegramWebApp();
    if (!wa) return;
    const tp = wa.themeParams || {};
    const root = document.documentElement;
    const map = {
        bg_color: "--bg-primary",
        secondary_bg_color: "--bg-secondary",
        text_color: "--text-primary",
        hint_color: "--text-muted",
        button_color: "--accent",
        button_text_color: "--accent-contrast",
        link_color: "--accent",
    };
    for (const [tgKey, cssVar] of Object.entries(map)) {
        if (tp[tgKey]) root.style.setProperty(cssVar, tp[tgKey]);
    }
    if (tp.bg_color) {
        document.body.style.backgroundColor = tp.bg_color;
    }
}

function showTelegramAccessDenied(message) {
    const overlay = document.getElementById("login-overlay");
    const appContainer = document.getElementById("app-container");
    if (!overlay) {
        alert(message || "Access denied");
        return;
    }
    overlay.style.display = "flex";
    if (appContainer) appContainer.style.display = "none";

    const subtitle = document.getElementById("login-subtitle");
    if (subtitle) subtitle.textContent = message || "Telegram access denied";

    const userInput = document.getElementById("login-username");
    const passInput = document.getElementById("login-password");
    const loginBtn = document.getElementById("btn-login");
    if (userInput) userInput.style.display = "none";
    if (passInput) passInput.style.display = "none";
    if (loginBtn) loginBtn.style.display = "none";

    const err = document.getElementById("login-error");
    if (err) {
        err.textContent = message || "Access denied";
        err.style.display = "block";
    }
    const hint = document.getElementById("login-hint");
    if (hint) {
        hint.style.display = "block";
        hint.textContent = "Open via the bot menu button «ShibaClaw» (not a regular browser link).";
    }
}

function ensureTelegramMiniChrome() {
    // Optional sidebar / settings access for Mini App chat mode
    const headerLeft =
        document.querySelector("#chat-header .header-left") ||
        document.querySelector(".chat-header .header-left") ||
        document.querySelector("#settings-view .settings-header-left");
    if (headerLeft && !document.getElementById("tg-mini-menu-btn")) {
        const btn = document.createElement("button");
        btn.type = "button";
        btn.id = "tg-mini-menu-btn";
        btn.title = "Menu";
        btn.setAttribute("aria-label", "Open menu");
        btn.innerHTML = '<span class="material-icons-round">menu</span>';
        btn.addEventListener("click", () => {
            const sidebar = document.getElementById("sidebar");
            if (sidebar) sidebar.classList.toggle("open");
        });
        headerLeft.insertBefore(btn, headerLeft.firstChild);
    }
}

function hideTelegramBrokenControls() {
    // Only when actually inside Telegram Mini App
    if (!isTelegramMiniApp()) return;
    document.body.classList.add("tg-mini");
    const restart = document.getElementById("btn-restart");
    if (restart) restart.style.display = "none";
    document.querySelectorAll(
        "[data-settings-tab='update'], .settings-sidebar-item[data-tab='update'], #btn-apply-update, .update-apply-btn"
    ).forEach((el) => {
        el.style.display = "none";
    });
    ensureTelegramMiniChrome();
}

function enterTelegramMiniChatMode() {
    if (!isTelegramMiniApp()) return;
    hideTelegramBrokenControls();
    // Full chat UI — do not force-open settings
}

function safeSetStoredToken(token) {
    try {
        setStoredToken(token);
        return true;
    } catch (e) {
        console.warn("localStorage set failed", e);
        try {
            sessionStorage.setItem("shibaclaw_token", token);
            window.getStoredToken = () => sessionStorage.getItem("shibaclaw_token") || "";
            return true;
        } catch (e2) {
            console.warn("sessionStorage set failed", e2);
            return false;
        }
    }
}

function waitForInitData(timeoutMs) {
    return new Promise((resolve) => {
        if (hasTelegramInitData()) {
            resolve(true);
            return;
        }
        const started = Date.now();
        const t = setInterval(() => {
            if (hasTelegramInitData()) {
                clearInterval(t);
                resolve(true);
                return;
            }
            if (Date.now() - started >= timeoutMs) {
                clearInterval(t);
                resolve(false);
            }
        }, 50);
    });
}

async function loginWithTelegramInitData(initData) {
    const res = await fetch("/api/auth/telegram", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ initData }),
    });
    const data = await res.json().catch(() => ({}));
    if (res.ok && data.status === "ok" && data.session_token) {
        if (typeof state !== "undefined") state.authRequired = true;
        safeSetStoredToken(data.session_token);
        if (typeof hideLogin === "function") hideLogin();
        try {
            if (typeof startApp === "function") startApp();
        } catch (e) {
            console.error("startApp after telegram auth failed", e);
        }
        enterTelegramMiniChatMode();
        return { ok: true };
    }
    return { ok: false, error: data.error || ("HTTP " + res.status) };
}

async function attemptTelegramMiniAuth() {
    const wa = getTelegramWebApp();
    // CDN stub is always present in browser — refuse unless this is a real Mini App launch
    if (!wa || !isTelegramMiniApp()) return false;

    try {
        if (typeof wa.ready === "function") wa.ready();
        if (typeof wa.expand === "function") wa.expand();
        if (typeof wa.disableVerticalSwipes === "function") wa.disableVerticalSwipes();
    } catch (_) { /* older clients */ }

    applyTelegramTheme();
    hideTelegramBrokenControls();

    const overlay = document.getElementById("login-overlay");
    const subtitle = document.getElementById("login-subtitle");
    if (overlay) overlay.style.display = "flex";
    if (subtitle) subtitle.textContent = "Signing in with Telegram…";
    const userInput = document.getElementById("login-username");
    const passInput = document.getElementById("login-password");
    const loginBtn = document.getElementById("btn-login");
    if (userInput) userInput.style.display = "none";
    if (passInput) passInput.style.display = "none";
    if (loginBtn) loginBtn.style.display = "none";

    let storedToken = "";
    try {
        storedToken = typeof getStoredToken === "function" ? getStoredToken() : "";
    } catch (_) { storedToken = ""; }
    if (storedToken) {
        try {
            const verifyRes = await fetch("/api/auth/verify", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ token: storedToken }),
            });
            const verifyData = await verifyRes.json();
            if (verifyData.valid) {
                if (typeof state !== "undefined") state.authRequired = true;
                if (typeof hideLogin === "function") hideLogin();
                try {
                    if (typeof startApp === "function") startApp();
                } catch (e) {
                    console.error("startApp after token verify failed", e);
                }
                enterTelegramMiniChatMode();
                return true;
            }
        } catch (_) { /* fall through */ }
    }

    const got = await waitForInitData(2500);
    if (!got) {
        showTelegramAccessDenied(
            "No Telegram initData. Open from the bot menu button «ShibaClaw», not a browser tab."
        );
        return true;
    }

    try {
        const result = await loginWithTelegramInitData(wa.initData);
        if (result.ok) return true;
        showTelegramAccessDenied(result.error || "Telegram authentication failed.");
        return true;
    } catch (e) {
        showTelegramAccessDenied("Error: " + (e && e.message ? e.message : e));
        return true;
    }
}

(function patchUnauthorizedForMini() {
    const orig = typeof handleUnauthorized === "function" ? handleUnauthorized : null;
    if (!orig) return;
    window.handleUnauthorized = function (message) {
        // Only re-auth via Telegram inside a real Mini App — never in browser/iframe stub
        if (isTelegramMiniApp()) {
            try { clearStoredToken(); } catch (_) { /* ignore */ }
            void attemptTelegramMiniAuth();
            return;
        }
        return orig(message);
    };
    handleUnauthorized = window.handleUnauthorized;
})();
