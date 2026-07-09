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
    
    let html = '';
    
    // Add banner if RAG is not available
    if (state.ragAvailable === false) {
        html += `
        <div style="background: rgba(255, 193, 7, 0.1); color: #ffc107; border: 1px solid rgba(255, 193, 7, 0.2); border-radius: 8px; padding: 12px; margin-bottom: 16px; font-size: 13px; display: flex; align-items: flex-start; gap: 8px;">
            <span class="material-icons-round" style="font-size: 18px; margin-top: 1px;">warning</span>
            <div>
                <strong>Local RAG is disabled.</strong> Document uploading and semantic search are unavailable. 
                <a href="#" onclick="closeModal('knowledge-modal'); openModal('settings-modal'); switchSettingsTab('plugins'); return false;" style="color: var(--primary); font-weight: bold; text-decoration: underline;">Install the Local RAG plugin from Settings</a> to enable them.
            </div>
        </div>`;
    }
    
    if (allKnowledgeBases.length === 0) {
        container.innerHTML = html + `
        <div style="text-align:center; padding: 40px 20px; color: var(--text-muted); display:flex; flex-direction:column; align-items:center; gap:12px; background: rgba(255,255,255,0.02); border-radius:12px; border: 1px dashed var(--border-light);">
            <span class="material-icons-round" style="font-size:48px; opacity: 0.5;">topic</span>
            <span style="font-size:15px;">No collections created yet.</span>
            <span style="font-size:13px; opacity:0.8;">Create a collection below to start dragging and dropping files.</span>
        </div>`;
        return;
    }
    
    container.innerHTML = html + allKnowledgeBases.map(kb => {
        const badges = (kb.files || []).map(f => `<div class="kb-file-badge"><span class="material-icons-round">description</span> ${f}</div>`).join('');
        
        // Hide/disable button if RAG not available
        const uploadBtn = (state.ragAvailable === false) ? `
            <button class="btn-secondary" id="btn-upload-${kb.id}" style="display:flex; align-items:center; gap:6px; padding:6px 12px; font-size: 13px; opacity: 0.5; cursor: not-allowed;" onclick="showKBFeedback('Please install the Local RAG plugin from settings.', true)" title="Upload file (Disabled)">
                <span class="material-icons-round" style="font-size: 16px;">upload_file</span> Upload Docs
            </button>
        ` : `
            <input type="file" id="upload-${kb.id}" multiple style="display:none" onchange="uploadToKB('${kb.id}', this)">
            <button class="btn-secondary" id="btn-upload-${kb.id}" style="display:flex; align-items:center; gap:6px; padding:6px 12px; font-size: 13px;" onclick="document.getElementById('upload-${kb.id}').click()" title="Upload file">
                <span class="material-icons-round" style="font-size: 16px;">upload_file</span> Upload Docs
            </button>
        `;
        
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
                    ${uploadBtn}
                    <button class="btn-icon" id="edit-btn-${kb.id}" onclick="renameKB('${kb.id}', '${kb.name.replace(/\\/g, '\\\\').replace(/'/g, "\\'")}')" title="Rename Collection">
                        <span class="material-icons-round" style="color: var(--text-primary);">edit</span>
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
    if (state.ragAvailable === false) {
        showKBFeedback("Local RAG is disabled. Please install the Local RAG plugin from settings.", true);
        return;
    }
    if (!e.dataTransfer.files || e.dataTransfer.files.length === 0) return;
    await uploadToKB(kbId, null, e.dataTransfer.files);
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

async function renameKB(id, currentName) {
    const newName = await shibaDialog("prompt", "Rename Collection", "Enter new name for collection:", { defaultValue: currentName, confirmText: "Rename" });
    if (!newName || newName.trim() === "" || newName === currentName) return;
    
    const btn = document.getElementById(`edit-btn-${id}`);
    const oldHtml = btn ? btn.innerHTML : '';
    if (btn) btn.innerHTML = `<span class="material-icons-round spin" style="color: var(--text-primary);">sync</span>`;
    
    try {
        const res = await authFetch(`/api/knowledge/${id}`, {
            method: 'PATCH',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({name: newName.trim()})
        });
        if (res.ok) {
            showKBFeedback("Collection renamed successfully.");
            await loadKnowledgeBases();
        } else {
            const err = await res.json();
            showKBFeedback(err.error || "Failed to rename collection", true);
            if (btn) btn.innerHTML = oldHtml;
        }
    } catch(e) {
        showKBFeedback("Error renaming collection", true);
        if (btn) btn.innerHTML = oldHtml;
    }
}

async function uploadToKB(id, inputElem, droppedFiles = null) {
    if (state.ragAvailable === false) {
        showKBFeedback("Local RAG is disabled. Please install the Local RAG plugin from settings.", true);
        return;
    }
    const files = droppedFiles ? Array.from(droppedFiles) : (inputElem && inputElem.files ? Array.from(inputElem.files) : []);
    if (files.length === 0) return;
    
    const btn = document.getElementById(`btn-upload-${id}`);
    const oldHtml = btn ? btn.innerHTML : '';
    if (btn) {
        btn.innerHTML = `<span class="material-icons-round spin" style="font-size: 16px;">sync</span> Uploading ${files.length} file(s)...`;
        btn.style.pointerEvents = "none";
    }
    
    let successCount = 0;
    for (const file of files) {
        const formData = new FormData();
        formData.append('file', file);
        
        try {
            const res = await authFetch(`/api/knowledge/${id}/upload`, {
                method: 'POST',
                body: formData
            });
            if (res.ok) {
                successCount++;
            } else {
                const err = await res.json();
                showKBFeedback(`Upload failed for ${file.name}: ` + (err.error || ""), true);
            }
        } catch(e) {
            showKBFeedback(`Upload error for ${file.name}`, true);
        }
    }

    await loadKnowledgeBases();
    if (btn) {
        if (successCount === files.length) {
            btn.innerHTML = `<span class="material-icons-round" style="color:var(--success); font-size: 16px;">check_circle</span> Success!`;
            btn.style.borderColor = "var(--success)";
        } else {
            btn.innerHTML = `<span class="material-icons-round" style="color:var(--danger); font-size: 16px;">error</span> Partial/Failed`;
            btn.style.borderColor = "var(--danger)";
        }
        setTimeout(() => {
            btn.innerHTML = oldHtml;
            btn.style.pointerEvents = "auto";
            btn.style.borderColor = "";
        }, 2500);
    }
    
    if (inputElem) inputElem.value = "";
}

function renderKBSelectorDropdown() {
    const list = document.getElementById('kb-dropdown-list');
    if (!list) return;
    
    if (state.ragAvailable === false) {
        list.innerHTML = `
        <div style="padding: 12px; font-size: 12px; color: var(--text-muted); text-align: center; line-height: 1.4;">
            Local RAG is disabled.<br>
            <span style="font-size: 11px; opacity: 0.8;"><a href="#" onclick="openModal('settings-modal'); switchSettingsTab('plugins'); return false;" style="color: var(--primary); font-weight: bold; text-decoration: underline;">Install it from Settings</a> to enable.</span>
        </div>`;
        const display = document.getElementById('active-kb-display');
        if (display) {
            display.innerText = `KBs (Disabled)`;
        }
        return;
    }
    
    list.innerHTML = allKnowledgeBases.map(kb => {
        const isActive = activeSessionKBs.includes(kb.id);
        return `
        <div class="model-item ${isActive ? 'selected' : ''}" onclick="toggleSessionKB('${kb.id}', event)">
            <span class="model-item-name">${kb.name}</span>
            ${isActive ? '<span class="material-icons-round" style="font-size:18px; color: var(--shiba-gold);">check_circle</span>' : '<span class="material-icons-round" style="font-size:18px; color: var(--text-muted); opacity: 0.3;">radio_button_unchecked</span>'}
        </div>
        `;
    }).join('');
    
    const display = document.getElementById('active-kb-display');
    if (display) {
        display.innerText = `KBs (${activeSessionKBs.length})`;
    }
}

async function toggleSessionKB(id, event) {
    if (event) {
        event.stopPropagation();
    }
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
