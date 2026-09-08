// Memory Manager Panel Logic
(function () {
    let _memData = {
        memory: "",
        user: "",
        history: "",
        diary: "",
        tokens: 0,
        max_tokens: 1500,
        quarantined: []
    };
    let _activeTab = "memory"; // "memory", "user", "history", "diary"
    let _isEditMode = false;

    window.loadMemoryData = async function () {
        const contentEl = document.getElementById("memory-content-area");
        if (!contentEl) return;

        contentEl.innerHTML = `
            <div style="padding: 3rem; text-align: center; color: var(--text-muted);">
                <span class="material-icons-round spin" style="font-size: 24px;">progress_activity</span>
                <div style="margin-top: 8px;">Loading memory...</div>
            </div>`;

        try {
            const res = await authFetch("/api/memory");
            if (!res.ok) throw new Error(`Server returned ${res.status}`);
            _memData = await res.json();
            _updateTokenBadge();
            renderMemoryView();
        } catch (e) {
            contentEl.innerHTML = `
                <div style="padding: 2rem; color: var(--accent-red, #e06c75); text-align: center;">
                    <span class="material-icons-round" style="font-size: 32px;">error_outline</span>
                    <div style="margin-top: 8px;">Failed to load memory: ${escapeHtml(e.message)}</div>
                </div>`;
        }
    };

    function _updateTokenBadge() {
        const badge = document.getElementById("memory-token-badge");
        if (!badge) return;
        const current = _memData.tokens || 0;
        const max = _memData.max_tokens || 1500;
        const pct = Math.min(100, Math.round((current / max) * 100));
        
        let color = "var(--shiba-gold)";
        if (pct > 90) color = "var(--accent-red, #e06c75)";
        else if (pct > 75) color = "#e5c07b";

        badge.innerHTML = `
            <span class="material-icons-round" style="font-size: 14px; vertical-align: middle;">memory</span>
            <span>${current} / ${max} tokens (${pct}%)</span>
        `;
        badge.style.color = color;
    }

    window.switchMemoryTab = function (tab) {
        _activeTab = tab;
        _isEditMode = false;
        document.querySelectorAll(".memory-tab-btn").forEach(btn => {
            btn.classList.toggle("active", btn.dataset.tab === tab);
        });
        renderMemoryView();
    };

    window.toggleMemoryEdit = function () {
        _isEditMode = !_isEditMode;
        renderMemoryView();
    };

    function getTargetFilename() {
        if (_activeTab === "user") return "USER.md";
        if (_activeTab === "history") return "HISTORY.md";
        if (_activeTab === "diary") return "DREAM_DIARY.md";
        return "MEMORY.md";
    }

    function getCurrentContent() {
        if (_activeTab === "user") return _memData.user || "";
        if (_activeTab === "history") return _memData.history || "";
        if (_activeTab === "diary") return _memData.diary || "";
        return _memData.memory || "";
    }

    function renderMemoryView() {
        const contentEl = document.getElementById("memory-content-area");
        const editBtn = document.getElementById("btn-memory-edit-toggle");
        const saveBtn = document.getElementById("btn-memory-save");
        if (!contentEl) return;

        const content = getCurrentContent();
        const filename = getTargetFilename();

        if (editBtn) {
            editBtn.innerHTML = _isEditMode 
                ? '<span class="material-icons-round">visibility</span> View' 
                : '<span class="material-icons-round">edit</span> Edit';
        }
        if (saveBtn) {
            saveBtn.style.display = _isEditMode ? "inline-flex" : "none";
        }

        if (_isEditMode) {
            contentEl.innerHTML = `
                <div style="height: 100%; display: flex; flex-direction: column;">
                    <div style="font-size: 11px; color: var(--text-muted); margin-bottom: 6px;">Editing <strong>${filename}</strong></div>
                    <textarea id="memory-editor-textarea" class="form-input" style="flex: 1; min-height: 380px; font-family: var(--font-mono, monospace); font-size: 13px; line-height: 1.5; resize: none;">${escapeHtml(content)}</textarea>
                </div>`;
        } else {
            if (_activeTab === "diary" && !content && (!_memData.quarantined || _memData.quarantined.length === 0)) {
                contentEl.innerHTML = `
                    <div style="padding: 2.5rem; text-align: center; color: var(--text-muted);">
                        <span class="material-icons-round" style="font-size: 36px; opacity: 0.5;">bedtime</span>
                        <div style="margin-top: 8px;">No Dream Diary entries or quarantined items yet.</div>
                    </div>`;
                return;
            }

            if (!content && _activeTab !== "diary") {
                contentEl.innerHTML = `
                    <div style="padding: 2.5rem; text-align: center; color: var(--text-muted);">
                        <span class="material-icons-round" style="font-size: 36px; opacity: 0.5;">description</span>
                        <div style="margin-top: 8px;"><strong>${filename}</strong> is currently empty.</div>
                        <div style="margin-top: 6px; font-size: 12px;">Click Edit to populate it or interact with the agent to learn facts.</div>
                    </div>`;
                return;
            }

            let html = `<div class="markdown-body" style="padding: 1rem; line-height: 1.6;">${renderMarkdown(content)}</div>`;

            if (_activeTab === "diary" && _memData.quarantined && _memData.quarantined.length > 0) {
                html += `
                    <div style="margin-top: 2rem; border-top: 1px solid var(--border-color); padding-top: 1rem;">
                        <h4 style="display: flex; align-items: center; gap: 6px; color: var(--accent-red, #e06c75); font-size: 13px; margin-bottom: 8px;">
                            <span class="material-icons-round" style="font-size: 16px;">shield</span>
                            Quarantined Memories (${_memData.quarantined.length})
                        </h4>
                        <div style="display: flex; flex-direction: column; gap: 8px;">`;
                for (const q of _memData.quarantined) {
                    html += `
                        <div style="background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.06); border-radius: 6px; padding: 8px 12px; font-size: 12px;">
                            <div style="font-weight: 600; color: var(--text-primary);">${escapeHtml(q.name)}</div>
                            <pre style="margin-top: 4px; padding: 6px; background: rgba(0,0,0,0.2); border-radius: 4px; font-size: 11px; white-space: pre-wrap; color: var(--text-muted);">${escapeHtml(q.preview)}</pre>
                        </div>`;
                }
                html += `</div></div>`;
            }

            contentEl.innerHTML = html;
            if (typeof enhanceCodeBlocks === "function") enhanceCodeBlocks(contentEl);
        }
    }

    window.saveCurrentMemoryFile = async function () {
        const textarea = document.getElementById("memory-editor-textarea");
        const statusEl = document.getElementById("memory-save-status");
        if (!textarea) return;

        const filename = getTargetFilename();
        const content = textarea.value;

        if (statusEl) {
            statusEl.textContent = "Saving...";
            statusEl.style.color = "var(--shiba-gold)";
        }

        try {
            const res = await authFetch("/api/memory/save", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ file: filename, content: content })
            });
            const data = await res.json();
            if (!res.ok) throw new Error(data.error || "Save failed");

            if (_activeTab === "user") _memData.user = content;
            else if (_activeTab === "history") _memData.history = content;
            else if (_activeTab === "diary") _memData.diary = content;
            else _memData.memory = content;

            if (data.tokens !== undefined) _memData.tokens = data.tokens;
            _updateTokenBadge();

            if (statusEl) {
                statusEl.textContent = "Saved!";
                statusEl.style.color = "#98c379";
                setTimeout(() => { statusEl.textContent = ""; }, 3000);
            }
            _isEditMode = false;
            renderMemoryView();
        } catch (e) {
            if (statusEl) {
                statusEl.textContent = `Error: ${e.message}`;
                statusEl.style.color = "var(--accent-red, #e06c75)";
            }
        }
    };

    window.searchForgetMemory = async function () {
        const input = document.getElementById("memory-forget-input");
        const needle = (input ? input.value : "").trim();
        if (needle.length < 3) {
            alert("Please enter at least 3 characters to search/forget.");
            return;
        }

        try {
            const res = await authFetch("/api/memory/forget", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ needle: needle, confirm: false })
            });
            const data = await res.json();
            if (!res.ok) throw new Error(data.error || "Forget search failed");

            const memCount = data.counts ? data.counts["MEMORY.md"] || 0 : 0;
            const histCount = data.counts ? data.counts["HISTORY.md"] || 0 : 0;
            const total = memCount + histCount;

            if (total === 0) {
                alert(`No lines found matching "${needle}" in MEMORY.md or HISTORY.md.`);
                return;
            }

            const previewLines = [
                ...(data.matches?.["MEMORY.md"] || []).map(m => `[MEMORY] ${m}`),
                ...(data.matches?.["HISTORY.md"] || []).map(m => `[HISTORY] ${m}`)
            ].slice(0, 5).join("\n");

            const msg = `Found ${total} matching line(s) for "${needle}":\n\n${previewLines}\n\nDo you want to quarantine and permanently redact these entries?`;
            
            if (confirm(msg)) {
                const confRes = await authFetch("/api/memory/forget", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ needle: needle, confirm: true })
                });
                const confData = await confRes.json();
                if (!confRes.ok) throw new Error(confData.error || "Failed to redact lines");
                alert(`Successfully quarantined and removed matching lines.`);
                if (input) input.value = "";
                await loadMemoryData();
            }
        } catch (e) {
            alert(`Error: ${e.message}`);
        }
    };
})();
