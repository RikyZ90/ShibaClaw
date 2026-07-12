// Helper to select a session with immediate UI feedback
window.selectSession = function (sessionId, el) {
    console.debug('[SHIBA] selectSession clicked:', sessionId);
    // show loading spinner on the clicked session-info
    try {
        const info = el && el.closest('.history-item');
        if (info) {
            info.classList.add('loading');
            // add small spinner element
            let s = info.querySelector('.session-spinner');
            if (!s) {
                s = document.createElement('span');
                s.className = 'session-spinner';
                s.style.cssText = 'display:inline-block;width:14px;height:14px;border:2px solid rgba(0,0,0,0.1);border-left-color:var(--accent);border-radius:50%;margin-left:8px;animation:shiba-spin 0.9s linear infinite;vertical-align:middle';
                const nameEl = info.querySelector('.session-name');
                if (nameEl) nameEl.appendChild(s);
            }
        }
    } catch (e) { console.debug('[SHIBA] spinner add failed', e); }

    // Immediately mark session as active in sidebar for quick feedback
    document.querySelectorAll('.history-item').forEach(i => i.classList.remove('active'));
    const parent = el && el.closest('.history-item');
    if (parent) parent.classList.add('active');

    // Load the selected session; loadSession refreshes the token badge itself.
    (async () => {
        try {
            await loadSession(sessionId);
        } catch (e) { console.debug('[SHIBA] loadSession failed', e); }

        if (typeof window.closeSidebarOnMobile === 'function') {
            window.closeSidebarOnMobile();
        }

        // remove loading spinner
        try {
            if (parent) {
                const s = parent.querySelector('.session-spinner');
                if (s) s.remove();
                parent.classList.remove('loading');
            }
        } catch (e) { }

        console.debug('[SHIBA] selectSession complete:', sessionId);
    })();
};

// CSS for spinner
const style = document.createElement('style');
style.textContent = '@keyframes shiba-spin { from { transform: rotate(0deg);} to { transform: rotate(360deg);} } .history-item.loading { opacity: 0.8; } .history-item.loading .session-name { opacity: 0.9; }';
document.head.appendChild(style);
