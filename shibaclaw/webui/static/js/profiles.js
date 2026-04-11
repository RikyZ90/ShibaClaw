/**
 * ShibaClaw WebUI — Profile Selector
 * Handles agent profile switching per session.
 */

// ── Profile state ────────────────────────────────────────────
let _profilesCache = null;

const profileBtn = document.getElementById("btn-profile");
const profileDropdown = document.getElementById("profile-dropdown");
const profileLabel = document.getElementById("profile-label");

// ── API helpers ──────────────────────────────────────────────
async function fetchProfiles() {
    try {
        const res = await authFetch("/api/profiles");
        if (!res.ok) return [];
        const data = await res.json();
        _profilesCache = data.profiles || [];
        return _profilesCache;
    } catch {
        return _profilesCache || [];
    }
}

async function switchProfile(profileId) {
    if (!state.sessionId || profileId === state.profileId) return;
    try {
        await authFetch(`/api/sessions/${encodeURIComponent(state.sessionId)}`, {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ profile_id: profileId }),
        });
        state.profileId = profileId;
        _applyProfileAvatar(profileId);
        updateProfileLabel();
        closeProfileDropdown();
    } catch (e) {
        console.error("Failed to switch profile:", e);
    }
}

/** Update the avatar in state and refresh all visible agent avatars. */
function _applyProfileAvatar(profileId) {
    const profiles = _profilesCache || [];
    const current = profiles.find(p => p.id === profileId);
    const avatarUrl = (current && current.avatar) ? current.avatar : DEFAULT_AVATAR;
    state.profileAvatar = avatarUrl;
    // Update all existing agent avatars in the chat
    document.querySelectorAll(".agent-avatar-img").forEach(img => {
        img.src = avatarUrl;
    });
    // Update sidebar logo too
    const sidebarLogo = document.querySelector(".logo img");
    if (sidebarLogo) sidebarLogo.src = avatarUrl;
}

// ── UI helpers ───────────────────────────────────────────────
function updateProfileLabel() {
    if (!profileLabel) return;
    const profiles = _profilesCache || [];
    const current = profiles.find(p => p.id === state.profileId);
    profileLabel.textContent = current ? current.label : (state.profileId || "Default");
}

function closeProfileDropdown() {
    if (profileDropdown) profileDropdown.classList.remove("active");
}

async function renderProfileDropdown() {
    if (!profileDropdown) return;
    const profiles = await fetchProfiles();

    let html = "";
    for (const p of profiles) {
        const isActive = p.id === state.profileId;
        html += `
            <div class="profile-option ${isActive ? "active" : ""}"
                 data-profile-id="${p.id}" title="${p.description || ""}">
                <span class="material-icons-round profile-option-icon">
                    ${isActive ? "radio_button_checked" : "radio_button_unchecked"}
                </span>
                <div class="profile-option-info">
                    <div class="profile-option-name">${escapeHtml(p.label)}</div>
                    ${p.description ? `<div class="profile-option-desc">${escapeHtml(p.description)}</div>` : ""}
                </div>
                ${p.builtin ? '<span class="profile-option-badge">built-in</span>' : ""}
            </div>`;
    }
    html += '<div class="profile-divider"></div>';
    html += `
        <div class="profile-action" id="profile-action-create">
            <span class="material-icons-round">add_circle_outline</span>
            Create custom profile
        </div>`;

    profileDropdown.innerHTML = html;

    // Bind click handlers
    profileDropdown.querySelectorAll(".profile-option").forEach(el => {
        el.addEventListener("click", () => switchProfile(el.dataset.profileId));
    });

    const createBtn = profileDropdown.querySelector("#profile-action-create");
    if (createBtn) createBtn.addEventListener("click", () => startProfileCreationSession());
}

function escapeHtml(text) {
    const d = document.createElement("div");
    d.textContent = text;
    return d.innerHTML;
}

// ── Toggle dropdown ──────────────────────────────────────────
if (profileBtn) {
    profileBtn.addEventListener("click", async (e) => {
        e.stopPropagation();
        const isOpen = profileDropdown.classList.contains("active");
        if (isOpen) {
            closeProfileDropdown();
        } else {
            await renderProfileDropdown();
            profileDropdown.classList.add("active");
        }
    });
}

// Close dropdown on outside click
document.addEventListener("click", (e) => {
    if (profileDropdown && !profileDropdown.contains(e.target) && e.target !== profileBtn) {
        closeProfileDropdown();
    }
});

// ── Create Profile via Agent Session ─────────────────────────
function startProfileCreationSession() {
    closeProfileDropdown();

    // Create a new session and send a preset prompt asking the agent
    // to build a custom profile SOUL.md interactively.
    if (!state.socket) return;

    const prompt = [
        "I want to create a new custom agent profile for ShibaClaw.",
        "Walk me through defining it step by step:",
        "1. Ask me what kind of assistant I need (role, specialty, tone).",
        "2. Based on my answers, generate a complete SOUL.md file.",
        "3. Once I'm happy with it, save it as a new profile using write_file to `profiles/<profile-id>/SOUL.md` in the workspace.",
        "4. Also update `profiles/manifest.json` to register the new profile with id, label, description, and `\"builtin\": false`.",
        "",
        "Start by asking me what kind of agent I'd like to create."
    ].join("\n");

    // Emit a new session event, then once reset, send the prompt
    const onReset = (data) => {
        state.socket.off("session_reset", onReset);
        // Small delay to let the UI settle
        setTimeout(() => {
            // Set the prompt in the input and send it
            const chatInput = document.getElementById("chat-input");
            if (chatInput) {
                chatInput.value = prompt;
                chatInput.dispatchEvent(new Event("input", { bubbles: true }));
            }
            const btnSend = document.getElementById("btn-send");
            if (btnSend) btnSend.click();
        }, 300);
    };

    state.socket.on("session_reset", onReset);
    state.socket.emit("new_session");
}

// ── Socket.IO integration ────────────────────────────────────
// Listen for profile_id in socket events to keep state in sync.
function initProfileSocket() {
    if (!state.socket) return;

    const origConnected = state.socket._callbacks && state.socket._callbacks["$connected"];
    state.socket.on("connected", (data) => {
        if (data.profile_id) {
            state.profileId = data.profile_id;
            _applyProfileAvatar(data.profile_id);
            updateProfileLabel();
        }
    });

    state.socket.on("session_reset", (data) => {
        if (data.profile_id) {
            state.profileId = data.profile_id;
            _applyProfileAvatar(data.profile_id);
            updateProfileLabel();
        }
    });
}

// Initialize after socket is ready
if (state.socket) {
    initProfileSocket();
} else {
    // Wait for socket to be set up by api_socket.js
    const _checkSocket = setInterval(() => {
        if (state.socket) {
            clearInterval(_checkSocket);
            initProfileSocket();
        }
    }, 200);
}

// Update label on session switch — hook into loadSession
const _origLoadSession = window.loadSession || (typeof loadSession !== "undefined" ? loadSession : null);

function _hookLoadSession() {
    // loadSession is a global from ui_panels.js;
    // we wrap it so profile state stays in sync after switching sessions.
    if (typeof loadSession !== "function") return;

    const orig = loadSession;
    window.loadSession = async function(sessionId, ...rest) {
        const result = await orig.call(this, sessionId, ...rest);
        // After session is loaded, fetch its profile_id
        try {
            const res = await authFetch(`/api/sessions/${encodeURIComponent(sessionId)}`);
            if (res.ok) {
                const data = await res.json();
                state.profileId = data.profile_id || "default";
                _applyProfileAvatar(state.profileId);
                updateProfileLabel();
            }
        } catch {}
        return result;
    };
}

_hookLoadSession();

// ── Auth header helper — delegate to auth.js ─────────────────
// authHeaders() is already defined in auth.js which loads before us.
