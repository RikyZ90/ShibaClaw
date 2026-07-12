// ── Mentions System for Chat Input ─────────────────────────────────────────

let mentionData = {
    kb: [],
    mcp: [],
    app: [],
    loaded: false
};

let mentionState = {
    active: false,
    query: "",
    cursorPos: 0,
    selectedIndex: 0,
    matches: []
};

async function loadMentionData() {
    if (mentionData.loaded) return;
    try {
        const [kbRes, mcpRes] = await Promise.all([
            authFetch("/api/knowledge").then(res => res.ok ? res.json() : []),
            authFetch("/api/mcp/servers").then(res => res.ok ? res.json() : [])
        ]);
        
        mentionData.kb = (kbRes.collections || []).map(k => ({ type: "kb", id: k.id, name: k.name, label: "Knowledge Base", icon: "menu_book" }));
        mentionData.mcp = (mcpRes.servers || []).map(m => ({ type: "mcp", id: m._name || m.name, name: m._name || m.name, label: "App", icon: "apps" }));
        mentionData.app = []; // Kept empty for compatibility
        
        mentionData.loaded = true;
    } catch (e) {
        console.error("Failed to load mention data:", e);
    }
}

function renderMentionMenu() {
    let menu = document.getElementById("mention-menu");
    if (!menu) {
        menu = document.createElement("div");
        menu.id = "mention-menu";
        menu.className = "mention-dropdown";
        
        // Add basic styles directly or expect them in css
        menu.style.position = "absolute";
        menu.style.bottom = "100%";
        menu.style.left = "0";
        menu.style.marginBottom = "8px";
        menu.style.backgroundColor = "var(--bg-panel, #2a2b32)";
        menu.style.border = "1px solid var(--border-color, #3f414d)";
        menu.style.borderRadius = "8px";
        menu.style.boxShadow = "0 4px 12px rgba(0,0,0,0.5)";
        menu.style.zIndex = "1000";
        menu.style.maxHeight = "250px";
        menu.style.overflowY = "auto";
        menu.style.width = "300px";
        menu.style.display = "none";
        
        const wrapper = document.querySelector(".input-wrapper");
        if (wrapper) {
            wrapper.style.position = "relative";
            wrapper.appendChild(menu);
        }
    }

    if (!mentionState.active || mentionState.matches.length === 0) {
        menu.style.display = "none";
        return;
    }

    menu.innerHTML = "";
    mentionState.matches.forEach((match, idx) => {
        const item = document.createElement("div");
        item.className = "mention-item" + (idx === mentionState.selectedIndex ? " selected" : "");
        item.style.padding = "8px 12px";
        item.style.cursor = "pointer";
        item.style.display = "flex";
        item.style.alignItems = "center";
        item.style.gap = "8px";
        item.style.borderBottom = "1px solid var(--border-color, #3f414d)";
        if (idx === mentionState.selectedIndex) {
            item.style.backgroundColor = "var(--primary-color-alpha, rgba(99, 102, 241, 0.2))";
        }

        item.innerHTML = `
            <span class="material-icons-round" style="font-size:18px; color:var(--text-muted)">${match.icon}</span>
            <div style="flex:1; overflow:hidden;">
                <div style="font-weight:500; font-size:13px; white-space:nowrap; text-overflow:ellipsis; overflow:hidden;">${match.name}</div>
                <div style="font-size:11px; color:var(--text-muted)">${match.label}</div>
            </div>
        `;

        item.onmousedown = (e) => {
            e.preventDefault(); // Prevent blur for mouse users
            insertMention(match);
        };
        item.onclick = (e) => {
            e.preventDefault();
            insertMention(match);
        };
        item.onmouseenter = () => {
            mentionState.selectedIndex = idx;
            Array.from(menu.children).forEach((child, i) => {
                if (i === idx) {
                    child.classList.add("selected");
                    child.style.backgroundColor = "var(--primary-color-alpha, rgba(99, 102, 241, 0.2))";
                } else {
                    child.classList.remove("selected");
                    child.style.backgroundColor = "transparent";
                }
            });
        };

        menu.appendChild(item);
    });
    
    menu.style.display = "block";
    
    // Ensure selected item is visible
    const selectedEl = menu.querySelector(".mention-item.selected");
    if (selectedEl) {
        selectedEl.scrollIntoView({ block: "nearest" });
    }
}

function insertMention(match) {
    const input = document.getElementById("chat-input");
    if (!input) return;

    const text = input.value;
    const beforeAt = text.substring(0, mentionState.cursorPos - mentionState.query.length - 1); // -1 for the @
    const afterCursor = text.substring(mentionState.cursorPos);
    
    // Build the tag text, e.g. @kb:"My Docs"
    const hasSpace = match.name.includes(" ");
    const nameStr = hasSpace ? `"${match.name}"` : match.name;
    const tag = `@${match.type}:${nameStr} `;
    
    input.value = beforeAt + tag + afterCursor;
    
    // Move cursor
    const newCursor = beforeAt.length + tag.length;
    input.setSelectionRange(newCursor, newCursor);
    input.focus();
    
    // Dispatch input event to notify autoResize and other listeners
    input.dispatchEvent(new Event('input', { bubbles: true }));
    
    // Auto-toggle KB if it's a KB
    if (match.type === "kb") {
        if (typeof activeSessionKBs !== "undefined" && typeof toggleSessionKB === "function") {
            if (!activeSessionKBs.includes(match.id)) {
                // Pass a dummy event to toggleSessionKB since it expects one for stopPropagation
                toggleSessionKB(match.id, { stopPropagation: () => {} });
            }
        }
    }
    
    mentionState.active = false;
    renderMentionMenu();
    updateSendButton();
}

function handleMentionInput(e) {
    const input = e.target;
    const val = input.value;
    const pos = input.selectionStart;
    
    // Find if we are typing after an @
    const textBeforeCursor = val.substring(0, pos);
    const lastAtIdx = textBeforeCursor.lastIndexOf("@");
    
    if (lastAtIdx >= 0) {
        const textAfterAt = textBeforeCursor.substring(lastAtIdx + 1);
        // If there's a space, it's not a valid mention query anymore
        if (!/\s/.test(textAfterAt)) {
            mentionState.active = true;
            mentionState.query = textAfterAt.toLowerCase();
            mentionState.cursorPos = pos;
            
            // Filter
            const allItems = [...mentionData.kb, ...mentionData.mcp, ...mentionData.app];
            mentionState.matches = allItems.filter(item => 
                item.name.toLowerCase().includes(mentionState.query) || 
                item.type.toLowerCase().includes(mentionState.query)
            ).slice(0, 10); // Max 10 items
            
            mentionState.selectedIndex = 0;
            renderMentionMenu();
            
            // Lazy load data if not loaded
            if (!mentionData.loaded) {
                loadMentionData().then(() => handleMentionInput(e));
            }
            return;
        }
    }
    
    mentionState.active = false;
    renderMentionMenu();
}

function handleMentionKeydown(e) {
    if (!mentionState.active || mentionState.matches.length === 0) return;
    
    if (e.key === "ArrowDown") {
        e.preventDefault();
        e.stopImmediatePropagation();
        mentionState.selectedIndex = (mentionState.selectedIndex + 1) % mentionState.matches.length;
        renderMentionMenu();
    } else if (e.key === "ArrowUp") {
        e.preventDefault();
        e.stopImmediatePropagation();
        mentionState.selectedIndex = (mentionState.selectedIndex - 1 + mentionState.matches.length) % mentionState.matches.length;
        renderMentionMenu();
    } else if (e.key === "Enter") {
        e.preventDefault();
        e.stopImmediatePropagation();
        insertMention(mentionState.matches[mentionState.selectedIndex]);
    } else if (e.key === "Escape") {
        e.preventDefault();
        e.stopImmediatePropagation();
        mentionState.active = false;
        renderMentionMenu();
    }
}

// Initialization hook
function initMentions() {
    const chatInput = document.getElementById("chat-input");
    if (chatInput) {
        chatInput.addEventListener("input", handleMentionInput);
        chatInput.addEventListener("keydown", handleMentionKeydown, true); // Capture phase to prevent default Enter behavior
        chatInput.addEventListener("blur", () => {
            // Delay closing to allow clicks on menu
            setTimeout(() => {
                mentionState.active = false;
                renderMentionMenu();
            }, 200);
        });
        
        // Optional: Preload data when hovering over chat input to make it instantly available
        chatInput.addEventListener("mouseenter", loadMentionData, { once: true });
    }
}

// Export for app.js or main.js
window.initMentions = initMentions;
