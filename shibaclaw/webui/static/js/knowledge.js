/**
 * Knowledge Base Manager Logic
 */

let allKnowledgeBases = [];
let activeSessionKBs = [];

function showKBFeedback(msg, isError = false) {
    const el = document.getElementById('kb-feedback-msg');
    if (!el) return;
    el.textContent = msg;
    el.style.display = 'block';
    el.style.backgroundColor = isError ? 'rgba(220, 53, 69, 0.1)' : 'rgba(40, 167, 69, 0.1)';
    el.style.color = isError ? 'var(--danger)' : 'var(--success)';
    el.style.border = `1px solid ${isError ? 'var(--danger)' : 'var(--success)'}`;
    
    setTimeout(() => { el.style.display = 'none'; }, isError ? 5000 : 3000);
}

async function loadKnowledgeBases() {
    try {
        const container = document.getElementById('kb-list-container');
        if (container && allKnowledgeBases.length === 0) {
            container.innerHTML = `
            <div style="text-align:center; padding: 40px 20px; color: var(--text-muted); display:flex; flex-direction:column; align-items:center; gap:12px;">
                <span class="material-icons-round spin" style="font-size:40px; color: var(--primary);">sync</span>
                <span style="font-size:14px;">Loading collections...</span>
            </div>`;
        }
        
        const res = await authFetch('/api/knowledge?t=' + Date.now());
        const data = await res.json();
        allKnowledgeBases = data.collections || [];
        
        const validIds = allKnowledgeBases.map(kb => kb.id);
        const originalLength = activeSessionKBs.length;
        activeSessionKBs = activeSessionKBs.filter(id => validIds.includes(id));
        
        if (activeSessionKBs.length !== originalLength && state.sessionId) {
            authFetch(`/api/sessions/${encodeURIComponent(state.sessionId)}`, {
                method: 'PATCH',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({knowledge_bases: activeSessionKBs})
            }).catch(e => console.error(e));
        }
        
        renderKBManagerList();
        renderKBSelectorDropdown();
    } catch (e) {
        console.error("Failed to load knowledge bases", e);
    }
}

function renderKBManagerList() {
    const container = document.getElementById('kb-list-container');
    if (!container) return;
    
    if (allKnowledgeBases.length === 0) {
        container.innerHTML = `
        <div style="text-align:center; padding: 40px 20px; color: var(--text-muted); display:flex; flex-direction:column; align-items:center; gap:12px; background: rgba(255,255,255,0.02); border-radius:12px; border: 1px dashed var(--border-light);">
            <span class="material-icons-round" style="font-size:48px; opacity: 0.5;">topic</span>
            <span style="font-size:15px;">No collections created yet.</span>
            <span style="font-size:13px; opacity:0.8;">Create a collection below to start dragging and dropping files.</span>
        </div>`;
        return;
    }
    
    container.innerHTML = allKnowledgeBases.map(kb => {
        const badges = (kb.files || []).map(f => `<div class="kb-file-badge"><span class="material-icons-round">description</span> ${f}</div>`).join('');
        return `
        <div class="kb-dropzone" id="dropzone-${kb.id}"
             ondragover="event.preventDefault(); this.classList.add('dragover');"
             ondragleave="event.preventDefault(); this.classList.remove('dragover');"
             ondrop="event.preventDefault(); this.classList.remove('dragover'); handleKBDrop(event, '${kb.id}')">
            
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <div>
                    <strong style="display:block; margin-bottom:4px; font-size: 15px;">${kb.name}</strong>
                    <span style="font-size: 13px; color: var(--text-muted);">${kb.files ? kb.files.length : 0} file(s) loaded</span>
                </div>
                <div style="display:flex; gap: 10px; align-items: center; position:relative; z-index:10;">
                    <input type="file" id="upload-${kb.id}" style="display:none" onchange="uploadToKB('${kb.id}', this)">
                    <button class="btn-secondary" id="btn-upload-${kb.id}" style="display:flex; align-items:center; gap:6px; padding:6px 12px; font-size: 13px;" onclick="document.getElementById('upload-${kb.id}').click()" title="Upload file">
                        <span class="material-icons-round" style="font-size: 16px;">upload_file</span> Upload Docs
                    </button>
                    <button class="btn-icon" id="del-btn-${kb.id}" onclick="deleteKB('${kb.id}')" title="Delete Collection">
                        <span class="material-icons-round" style="color: var(--danger);">delete</span>
                    </button>
                </div>
            </div>
            
            ${badges ? `<div class="kb-file-badges-container">${badges}</div>` : ''}
        </div>
        `;
    }).join('');
}

async function handleKBDrop(e, kbId) {
    if (!e.dataTransfer.files || e.dataTransfer.files.length === 0) return;
    const file = e.dataTransfer.files[0];
    await uploadToKB(kbId, null, file);
}

async function createKB() {
    const input = document.getElementById('kb-new-name');
    const btn = document.getElementById('kb-btn-create');
    const name = input.value.trim();
    if (!name) {
        showKBFeedback("Please enter a collection name.", true);
        return;
    }
    
    const id = name.toLowerCase().replace(/[^a-z0-9]/g, '-');
    const oldHtml = btn.innerHTML;
    btn.innerHTML = `<span class="material-icons-round spin">sync</span>`;
    btn.disabled = true;
    
    try {
        const res = await authFetch('/api/knowledge', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({id, name})
        });
        if (res.ok) {
            input.value = '';
            showKBFeedback("Collection created successfully!");
            await loadKnowledgeBases();
        } else {
            const err = await res.json();
            showKBFeedback(err.error || "Failed to create KB", true);
        }
    } catch(e) {
        showKBFeedback("Error creating Knowledge Base", true);
    } finally {
        btn.innerHTML = oldHtml;
        btn.disabled = false;
    }
}

async function deleteKB(id) {
    const confirmed = await shibaDialog("confirm", "Delete Collection", `Are you sure you want to delete collection ${id}?`, { confirmText: "Delete", danger: true });
    if (!confirmed) return;
    
    const btn = document.getElementById(`del-btn-${id}`);
    if (btn) btn.innerHTML = `<span class="material-icons-round spin" style="color: var(--danger);">sync</span>`;
    try {
        await authFetch(`/api/knowledge/${id}`, { method: 'DELETE' });
        showKBFeedback("Collection deleted.");
        
        if (activeSessionKBs.includes(id)) {
            activeSessionKBs = activeSessionKBs.filter(x => x !== id);
            if (state.sessionId) {
                try {
                    await authFetch(`/api/sessions/${encodeURIComponent(state.sessionId)}`, {
                        method: 'PATCH',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({knowledge_bases: activeSessionKBs})
                    });
                } catch(e) {}
            }
        }
        
        await loadKnowledgeBases();
    } catch(e) {
        showKBFeedback("Delete failed", true);
        if (btn) btn.innerHTML = `<span class="material-icons-round" style="color: var(--danger);">delete</span>`;
    }
}

async function uploadToKB(id, inputElem, droppedFile = null) {
    const file = droppedFile || (inputElem && inputElem.files ? inputElem.files[0] : null);
    if (!file) return;
    
    const formData = new FormData();
    formData.append('file', file);
    
    const btn = document.getElementById(`btn-upload-${id}`);
    const oldHtml = btn ? btn.innerHTML : '';
    if (btn) {
        btn.innerHTML = `<span class="material-icons-round spin" style="font-size: 16px;">sync</span> Uploading...`;
        btn.style.pointerEvents = "none";
    }
    
    try {
        const res = await authFetch(`/api/knowledge/${id}/upload`, {
            method: 'POST',
            body: formData
        });
        if (res.ok) {
            await loadKnowledgeBases();
            if (btn) {
                btn.innerHTML = `<span class="material-icons-round" style="color:var(--success); font-size: 16px;">check_circle</span> Success!`;
                btn.style.borderColor = "var(--success)";
                setTimeout(() => {
                    btn.innerHTML = oldHtml;
                    btn.style.pointerEvents = "auto";
                    btn.style.borderColor = "";
                }, 2500);
            }
        } else {
            const err = await res.json();
            showKBFeedback("Upload failed: " + (err.error || ""), true);
            if (btn) {
                btn.innerHTML = oldHtml;
                btn.style.pointerEvents = "auto";
            }
        }
    } catch(e) {
        showKBFeedback("Upload error", true);
        if (btn) {
            btn.innerHTML = oldHtml;
            btn.style.pointerEvents = "auto";
        }
    } finally {
        if (inputElem) inputElem.value = "";
    }
}

function renderKBSelectorDropdown() {
    const list = document.getElementById('kb-dropdown-list');
    if (!list) return;
    
    list.innerHTML = allKnowledgeBases.map(kb => {
        const isActive = activeSessionKBs.includes(kb.id);
        return `
        <div class="model-item" onclick="toggleSessionKB('${kb.id}')" style="display:flex; justify-content:space-between; cursor:pointer;">
            <span>${kb.name}</span>
            ${isActive ? '<span class="material-icons-round" style="font-size:16px;">check</span>' : ''}
        </div>
        `;
    }).join('');
    
    const display = document.getElementById('active-kb-display');
    if (display) {
        display.innerText = `KBs (${activeSessionKBs.length})`;
    }
}

async function toggleSessionKB(id) {
    if (activeSessionKBs.includes(id)) {
        activeSessionKBs = activeSessionKBs.filter(x => x !== id);
    } else {
        activeSessionKBs.push(id);
    }
    renderKBSelectorDropdown();
    
    if (state.sessionId) {
        try {
            await authFetch(`/api/sessions/${encodeURIComponent(state.sessionId)}`, {
                method: 'PATCH',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({knowledge_bases: activeSessionKBs})
            });
        } catch(e) {
            console.error("Failed to update session KBs", e);
        }
    }
}

document.addEventListener('DOMContentLoaded', () => {
    
    const btn = document.getElementById('btn-kb-select');
    const menu = document.getElementById('kb-dropdown-menu');
    if (btn && menu) {
        btn.addEventListener('click', (e) => {
            e.stopPropagation();
            menu.style.display = menu.style.display === 'none' ? 'block' : 'none';
        });
        
        document.addEventListener('click', (e) => {
            if (!menu.contains(e.target) && !btn.contains(e.target)) {
                menu.style.display = 'none';
            }
        });
    }
});

window.setActiveKBs = function(kbs) {
    activeSessionKBs = Array.isArray(kbs) ? kbs : [];
    renderKBSelectorDropdown();
}
