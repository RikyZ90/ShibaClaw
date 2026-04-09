// ── File Handling ─────────────────────────────────────────────
function initFileHandlers() {
    const btnAttach = $("btn-attach");
    const fileInput = $("file-input");
    const dragOverlay = $("drag-overlay");

    console.debug("[SHIBA] Initializing file handlers", { btnAttach: !!btnAttach, fileInput: !!fileInput });
    if (btnAttach && fileInput) {
        btnAttach.onclick = () => fileInput.click();
        fileInput.onchange = (e) => {
            handleFileUpload(e.target.files);
            fileInput.value = "";
        };
    }

    window.addEventListener("dragover", (e) => {
        e.preventDefault();
        dragOverlay.classList.add("active");
    });

    window.addEventListener("dragleave", (e) => {
        if (e.relatedTarget === null || !dragOverlay.contains(e.relatedTarget)) {
            dragOverlay.classList.remove("active");
        }
    });

    window.addEventListener("drop", (e) => {
        e.preventDefault();
        dragOverlay.classList.remove("active");
        handleFileUpload(e.dataTransfer.files);
    });

    window.addEventListener("paste", (e) => {
        const items = e.clipboardData.items;
        const files = [];
        for (let item of items) {
            if (item.kind === "file") {
                files.push(item.getAsFile());
            }
        }
        console.debug("[SHIBA] Paste event", { count: files.length });
        if (files.length > 0) handleFileUpload(files);
    });
}

async function handleFileUpload(files) {
    console.debug("[SHIBA] handleFileUpload", files);
    if (!files || files.length === 0) return;

    for (const file of files) {
        const formData = new FormData();
        formData.append("file", file);

        try {
            const res = await authFetch("/api/upload", {
                method: "POST",
                body: formData
            });

            if (res.ok) {
                const data = await res.json();
                const uploadedFile = data.files[0];
                state.stagedFiles.push({
                    name: uploadedFile.filename,
                    url: uploadedFile.url,
                    type: file.type,
                    stagedAt: Date.now()
                });
                updateStagingUI();
            } else {
                const err = await res.json();
                shibaDialog("alert", "Upload Failed", `Could not upload ${file.name}: ${err.error}`, { danger: true });
            }
        } catch (e) {
            console.error("Upload error:", e);
        }
    }
}

function updateStagingUI() {
    const container = $("attachment-staging");
    if (!container) return;

    container.innerHTML = "";
    if (state.stagedFiles.length === 0) {
        container.style.display = "none";
        return;
    }

    container.style.display = "flex";
    state.stagedFiles.forEach((file, idx) => {
        const item = document.createElement("div");
        item.className = "staged-file";
        
        let thumb = `<span class="material-icons-round">insert_drive_file</span>`;
        if (file.type.startsWith("image/")) {
            thumb = `<img src="${file.url}" class="staged-file-thumb">`;
        }

        item.innerHTML = `
            ${thumb}
            <span class="staged-file-name" title="${file.name}">${file.name}</span>
            <button class="btn-remove-staged" onclick="removeStagedFile(${idx})">
                <span class="material-icons-round">close</span>
            </button>
        `;
        container.appendChild(item);
    });
}

window.removeStagedFile = function(idx) {
    state.stagedFiles.splice(idx, 1);
    updateStagingUI();
};


// ── File Explorer ─────────────────────────────────────────────
window.loadFs = async function(path = ".") {
    const list = $("fs-content");
    const breadcrumb = $("fs-breadcrumb");
    if (!list) return;

    state.currentFsPath = path;
    list.innerHTML = `<div style="padding:2rem;text-align:center;color:var(--text-muted)">
        <span class="material-icons-round spin">progress_activity</span>
    </div>`;

    const parts = path.split(/[/\\]/).filter(p => p && p !== ".");
    let bcHtml = `<span class="breadcrumb-item" onclick="loadFs('.')">root</span>`;
    let currentPartPath = "";
    parts.forEach((p, i) => {
        currentPartPath += (i === 0 ? "" : "/") + p;
        bcHtml += ` <span class="material-icons-round" style="font-size:12px">chevron_right</span> `;
        bcHtml += `<span class="breadcrumb-item" onclick="loadFs('${currentPartPath.replace(/'/g, "\\'")}')">${p}</span>`;
    });
    breadcrumb.innerHTML = bcHtml;

    try {
        const res = await authFetch(`/api/fs/explore?path=${encodeURIComponent(path)}`);
        const data = await res.json();

        if (data.error) {
            list.innerHTML = `<div style="padding:2rem;color:var(--accent-red)">${data.error}</div>`;
            return;
        }

        list.innerHTML = "";
        
        if (path !== "." && path !== "/" && parts.length > 0) {
            const parentPath = parts.slice(0, -1).join("/") || ".";
            const row = document.createElement("div");
            row.className = "fs-item";
            row.onclick = () => loadFs(parentPath);
            row.innerHTML = `
                <span class="material-icons-round fs-item-icon">folder_open</span>
                <span class="fs-item-name">..</span>
                <span></span><span></span>
            `;
            list.appendChild(row);
        }

        data.items.forEach(f => {
            const row = document.createElement("div");
            row.className = `fs-item ${f.is_dir ? "is-dir" : ""}`;
            
            const icon = f.is_dir ? "folder" : "insert_drive_file";
            const size = f.is_dir ? "" : formatSize(f.size);
            const mtime = new Date(f.mtime * 1000).toLocaleString();

            row.onclick = () => {
                if (f.is_dir) {
                    loadFs(f.path);
                } else {
                    openFileEditor(f.path, f.name);
                }
            };

            row.innerHTML = `
                <span class="material-icons-round fs-item-icon">${icon}</span>
                <span class="fs-item-name" title="${f.name}">${f.name}</span>
                <span class="fs-item-size">${size}</span>
                <span class="fs-item-mtime">${mtime}</span>
            `;
            list.appendChild(row);
        });

    } catch (e) {
        list.innerHTML = `<div style="padding:2rem;color:var(--accent-red)">Error loading files</div>`;
    }
};

function formatSize(bytes) {
    if (bytes === 0) return "0 B";
    const k = 1024;
    const sizes = ["B", "KB", "MB", "GB", "TB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + " " + sizes[i];
}


// ── File Editor ───────────────────────────────────────────────
const TEXT_EXTENSIONS = /\.(txt|md|py|js|ts|jsx|tsx|json|yaml|yml|toml|sh|bash|zsh|env|cfg|conf|ini|html|css|scss|xml|csv|log|rst|Dockerfile|gitignore|editorconfig|lock|sql|go|rs|rb|java|c|cpp|h|php)$/i;

window.openFileEditor = async function(filePath, fileName) {
    const content = $("fs-content");
    const breadcrumb = $("fs-breadcrumb");
    if (!content) return;

    content.innerHTML = `<div style="padding:2rem;text-align:center;color:var(--text-muted)">
        <span class="material-icons-round spin">progress_activity</span>
    </div>`;

    const parts = state.currentFsPath.split(/[\/\\]/).filter(p => p && p !== ".");
    let bcHtml = `<span class="breadcrumb-item" onclick="loadFs('.')">root</span>`;
    let cur = "";
    parts.forEach((p, i) => {
        cur += (i === 0 ? "" : "/") + p;
        const cp = cur;
        bcHtml += ` <span class="material-icons-round" style="font-size:12px">chevron_right</span> `;
        bcHtml += `<span class="breadcrumb-item" onclick="loadFs('${cp.replace(/'/g, "\\'")}')">${p}</span>`;
    });
    bcHtml += ` <span class="material-icons-round" style="font-size:12px">chevron_right</span> <span class="breadcrumb-item active">${fileName}</span>`;
    breadcrumb.innerHTML = bcHtml;

    const isText = TEXT_EXTENSIONS.test(fileName);
    if (!isText) {
        content.innerHTML = `<div style="padding:3rem;text-align:center;color:var(--text-muted)">
            <span class="material-icons-round" style="font-size:48px;display:block;margin-bottom:8px">insert_drive_file</span>
            <p>Binary file — preview not available</p>
        </div>`;
        return;
    }

    try {
        const res = await authFetch(`/api/file-get?path=${encodeURIComponent(filePath)}&_t=${Date.now()}`);
        if (!res.ok) {
            const err = await res.json().catch(() => ({ error: res.statusText }));
            content.innerHTML = `<div style="padding:2rem;color:var(--accent-red)">${err.error || "Error loading file"}</div>`;
            return;
        }
        const text = await res.text();

        content.innerHTML = `
            <div class="file-editor-toolbar">
                <span class="file-editor-name">${fileName}</span>
                <span id="save-status" class="file-editor-status"></span>
                <button class="btn-edit-mode" id="btn-refresh-file" title="Reload file from disk">
                    <span class="material-icons-round" style="font-size:15px">refresh</span>
                </button>
                <button class="btn-edit-mode" id="btn-download-file" title="Download file">
                    <span class="material-icons-round" style="font-size:15px">download</span>
                </button>
                <button class="btn-edit-mode" id="btn-edit-mode" title="Enter edit mode">
                    <span class="material-icons-round" style="font-size:15px">edit</span> Edit
                </button>
                <button class="btn-primary btn-sm" id="btn-save-file" style="display:none">
                    <span class="material-icons-round" style="font-size:14px">save</span> Save
                </button>
            </div>
            <textarea class="file-editor-area" id="file-editor-textarea" spellcheck="false" readonly></textarea>
        `;
        const ta = document.getElementById("file-editor-textarea");
        const btnEdit = document.getElementById("btn-edit-mode");
        const btnSave = document.getElementById("btn-save-file");
        const btnRefresh = document.getElementById("btn-refresh-file");
        const btnDownload = document.getElementById("btn-download-file");
        btnDownload.onclick = () => {
            const blob = new Blob([ta.value], { type: "text/plain;charset=utf-8" });
            const a = document.createElement("a");
            a.href = URL.createObjectURL(blob);
            a.download = fileName;
            a.click();
            URL.revokeObjectURL(a.href);
        };
        ta.value = text;
        btnRefresh.onclick = async () => {
            btnRefresh.disabled = true;
            ta.setAttribute("readonly", "");
            btnEdit.classList.remove("active");
            btnEdit.innerHTML = `<span class="material-icons-round" style="font-size:15px">edit</span> Edit`;
            btnSave.style.display = "none";
            const ss = document.getElementById("save-status");
            if (ss) ss.textContent = "";
            try {
                const r = await authFetch(`/api/file-get?path=${encodeURIComponent(filePath)}&_t=${Date.now()}`);
                if (r.ok) ta.value = await r.text();
            } finally {
                btnRefresh.disabled = false;
            }
        };
        btnEdit.onclick = () => {
            const isEditing = !ta.hasAttribute("readonly");
            if (isEditing) {
                ta.setAttribute("readonly", "");
                btnEdit.classList.remove("active");
                btnEdit.innerHTML = `<span class="material-icons-round" style="font-size:15px">edit</span> Edit`;
                btnSave.style.display = "none";
            } else {
                ta.removeAttribute("readonly");
                ta.focus();
                btnEdit.classList.add("active");
                btnEdit.innerHTML = `<span class="material-icons-round" style="font-size:15px">visibility</span> View`;
                btnSave.style.display = "";
            }
        };
        btnSave.onclick = () => saveFile(filePath);
    } catch (e) {
        content.innerHTML = `<div style="padding:2rem;color:var(--accent-red)">Error: ${e.message}</div>`;
    }
};

window.saveFile = async function(filePath) {
    const textarea = document.getElementById("file-editor-textarea");
    const status = $("save-status");
    if (!textarea || !status) return;
    const btn = $("btn-save-file");
    if (btn) btn.disabled = true;
    status.textContent = "Saving\u2026";
    status.style.color = "";

    const body = { path: filePath, content: textarea.value };

    try {
        const res = await authFetch("/api/file-save", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body)
        });
        const data = await res.json().catch(() => ({}));
        if (!res.ok) {
            throw new Error(data.error || `Server error ${res.status}`);
        }
        if (data.error) throw new Error(data.error);
        status.style.color = "";
        status.textContent = `Saved! (${data.bytes ?? "?"} bytes \u2192 ${data.path ?? filePath})`;
        setTimeout(() => { status.textContent = ""; }, 4000);
    } catch (e) {
        console.error("[file-save] error", e);
        status.style.color = "var(--accent-red, #f38ba8)";
        status.textContent = "\u274c " + e.message;
    } finally {
        if (btn) btn.disabled = false;
    }
};

(function initChatWidth() {
    const STORAGE_KEY = "shibaclaw_chat_width";
    const DEFAULT = 860;
    const root = document.documentElement;

    const saved = parseInt(localStorage.getItem(STORAGE_KEY)) || DEFAULT;
    root.style.setProperty("--chat-width", saved + "px");

    function applyWidth(px) {
        root.style.setProperty("--chat-width", px + "px");
        document.querySelectorAll(".width-preset").forEach(btn => {
            btn.classList.toggle("active", parseInt(btn.dataset.width) === px);
        });
        localStorage.setItem(STORAGE_KEY, px);
    }

    document.addEventListener("DOMContentLoaded", () => {
        const toggleBtn = document.getElementById("btn-width-toggle");
        const popover   = document.getElementById("width-popover");

        applyWidth(saved);

        toggleBtn.addEventListener("click", (e) => {
            e.stopPropagation();
            popover.classList.toggle("open");
        });
        document.addEventListener("click", (e) => {
            if (!toggleBtn.contains(e.target) && !popover.contains(e.target)) {
                popover.classList.remove("open");
            }
        });
        document.querySelectorAll(".width-preset").forEach(btn => {
            btn.addEventListener("click", () => {
                applyWidth(parseInt(btn.dataset.width));
            });
        });
    });
})();


