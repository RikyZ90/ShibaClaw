/**
 * Subagent Feedback UI Controller
 * Manages the pulsing icons, task drawer, and skeleton loaders in chat.
 */

window.subagentUI = {
    activeSubagents: new Map(), // agentId -> { name, status }
    
    init() {
        this.container = document.getElementById('subagent-feedback-container');
        this.avatarBtn = document.getElementById('subagent-avatar-btn');
        this.drawer = document.getElementById('subagent-drawer');
        
        if (this.avatarBtn) {
            this.avatarBtn.addEventListener('click', () => {
                this.drawer.classList.toggle('open');
            });
        }
        
        // Close drawer when clicking outside
        document.addEventListener('click', (e) => {
            if (this.drawer && this.drawer.classList.contains('open') && 
                !this.container.contains(e.target)) {
                this.drawer.classList.remove('open');
            }
        });
    },

    /**
     * Start a subagent task
     */
    startSubagent(agentId, agentName, initialStatus) {
        this.activeSubagents.set(agentId, { name: agentName, status: initialStatus });
        this.updateDrawer();
        this.container.style.display = 'flex';
        this.injectSkeleton(agentId, agentName, initialStatus);
        if (typeof scrollToBottom === 'function') scrollToBottom();
    },

    /**
     * Update an active subagent's status
     */
    updateStatus(agentId, status) {
        const agent = this.activeSubagents.get(agentId);
        if (agent) {
            agent.status = status;
            this.updateDrawer();

            // Also update the inline terminal skeleton if it exists
            const statusEl = document.getElementById(`skeleton-status-${agentId}`);
            if (statusEl) {
                statusEl.textContent = status || 'is processing';
            }
        }
    },

    /**
     * Complete a subagent task and remove skeleton
     */
    finishSubagent(agentId) {
        this.activeSubagents.delete(agentId);
        this.updateDrawer();
        this.removeSkeleton(agentId);
        
        if (this.activeSubagents.size === 0) {
            this.container.style.display = 'none';
            if (this.drawer) this.drawer.classList.remove('open');
        }
    },

    /**
     * Re-renders the drawer contents
     */
    updateDrawer() {
        if (!this.drawer) return;
        
        this.drawer.innerHTML = '';
        this.activeSubagents.forEach((info, id) => {
            const taskEl = document.createElement('div');
            taskEl.className = 'subagent-task';
            taskEl.innerHTML = `
                <div class="subagent-task-header">
                    <span class="material-icons-round" style="font-size: 14px; color: #8A2BE2;">psychology</span>
                    ${info.name}
                </div>
                <div class="subagent-task-status">
                    <div class="spinner-mini"></div>
                    ${info.status}
                </div>
            `;
            this.drawer.appendChild(taskEl);
        });
    },

    /**
     * Injects a terminal-style loader into the chat
     */
    injectSkeleton(agentId, agentName, initialStatus) {
        const chatHistory = document.getElementById('chat-history');
        if (!chatHistory) return;
        
        // Remove if already exists
        this.removeSkeleton(agentId);
        
        const skeleton = document.createElement('div');
        skeleton.className = 'terminal-skeleton-container';
        skeleton.id = `skeleton-${agentId}`;
        
        const displayStatus = initialStatus || 'is processing';

        skeleton.innerHTML = `
            <div class="terminal-prompt">
                <span class="terminal-carret">&gt;</span>
                <span class="terminal-agent">[${agentName}]</span>
                <span class="terminal-action" id="skeleton-status-${agentId}">${displayStatus}</span>
                <span class="terminal-spinner"></span>
                <span class="terminal-cursor">_</span>
            </div>
        `;
        
        // Find the typing bubble to insert before it
        const typingBubble = document.getElementById('typing-indicator-wrapper');
        if (typingBubble && typingBubble.style.display !== 'none') {
            chatHistory.insertBefore(skeleton, typingBubble);
        } else {
            chatHistory.appendChild(skeleton);
        }
    },

    /**
     * Removes the terminal-style loader
     */
    removeSkeleton(agentId) {
        const el = document.getElementById(`skeleton-${agentId}`);
        if (el) el.remove();
    }
};

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    subagentUI.init();
});
