function _setFsLoading(container) {
    container.replaceChildren();

    const wrapper = document.createElement("div");
    wrapper.style.padding = "2rem";
    wrapper.style.textAlign = "center";
    wrapper.style.color = "var(--text-muted)";
    wrapper.appendChild(createMaterialIcon("progress_activity", "material-icons-round spin"));
    container.appendChild(wrapper);
}

function _setFsMessage(
    container,
    message,
    { color = "var(--text-muted)", center = false, padding = "2rem" } = {}
) {
    container.replaceChildren();

    const wrapper = document.createElement("div");
    wrapper.style.padding = padding;
    wrapper.style.color = color;
    if (center) {
        wrapper.style.textAlign = "center";
    }
    wrapper.textContent = message;
    container.appendChild(wrapper);
}

function _appendFsBreadcrumbSeparator(breadcrumb) {
    const separator = createMaterialIcon("chevron_right");
    separator.style.fontSize = "12px";
    breadcrumb.appendChild(separator);
}

function _appendFsBreadcrumbItem(breadcrumb, label, onClick, { active = false } = {}) {
    const item = document.createElement("span");
    item.className = active ? "breadcrumb-item active" : "breadcrumb-item";
    item.textContent = label;
    if (typeof onClick === "function") {
        item.addEventListener("click", onClick);
    }
    breadcrumb.appendChild(item);
}

function _renderFsBreadcrumb(breadcrumb, path, activeLabel = null) {
    if (!breadcrumb) return;

    breadcrumb.replaceChildren();
    _appendFsBreadcrumbItem(breadcrumb, "root", () => window.loadFs("."));

    const parts = path.split(/[/\\]/).filter((part) => part && part !== ".");
    let currentPartPath = "";

    parts.forEach((part, index) => {
        currentPartPath += (index === 0 ? "" : "/") + part;
        _appendFsBreadcrumbSeparator(breadcrumb);
        _appendFsBreadcrumbItem(breadcrumb, part, () => window.loadFs(currentPartPath));
    });

    if (activeLabel !== null) {
        _appendFsBreadcrumbSeparator(breadcrumb);
        _appendFsBreadcrumbItem(breadcrumb, activeLabel, null, { active: true });
    }
}

function _createFsRow({ icon, name, size = "", mtime = "", isDir = false, onClick }) {
    const row = document.createElement("div");
    row.className = isDir ? "fs-item is-dir" : "fs-item";
    if (typeof onClick === "function") {
        row.addEventListener("click", onClick);
    }

    row.appendChild(createMaterialIcon(icon, "material-icons-round fs-item-icon"));

    const nameEl = document.createElement("span");
    nameEl.className = "fs-item-name";
    nameEl.title = name;
    nameEl.textContent = name;
    row.appendChild(nameEl);

    const sizeEl = document.createElement("span");
    sizeEl.className = "fs-item-size";
    sizeEl.textContent = size;
    row.appendChild(sizeEl);

    const mtimeEl = document.createElement("span");
    mtimeEl.className = "fs-item-mtime";
    mtimeEl.textContent = mtime;
    row.appendChild(mtimeEl);

    return row;
}

// ── File Handling ─────────────────────────────────────────────
function initFileHandlers() {
    if (state.fileHandlersInitialized) return;
    state.fileHandlersInitialized = true;

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

    container.replaceChildren();
    if (state.stagedFiles.length === 0) {
        container.style.display = "none";
        return;
    }

    container.style.display = "flex";
    state.stagedFiles.forEach((file, idx) => {
        const item = document.createElement("div");
        item.className = "staged-file";

        const isImage = typeof file.type === "string" && file.type.startsWith("image/");
        if (isImage) {
            const thumb = document.createElement("img");
            thumb.src = file.url;
            thumb.className = "staged-file-thumb";
            item.appendChild(thumb);
        } else {
            item.appendChild(createMaterialIcon("insert_drive_file"));
        }

        const nameEl = document.createElement("span");
        nameEl.className = "staged-file-name";
        nameEl.title = file.name;
        nameEl.textContent = file.name;
        item.appendChild(nameEl);

        const removeBtn = document.createElement("button");
        removeBtn.className = "btn-remove-staged";
        removeBtn.appendChild(createMaterialIcon("close"));
        removeBtn.addEventListener("click", () => window.removeStagedFile(idx));
        item.appendChild(removeBtn);

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
    _setFsLoading(list);
    _renderFsBreadcrumb(breadcrumb, path);

    const parts = path.split(/[/\\]/).filter(p => p && p !== ".");

    try {
        const res = await authFetch(`/api/fs/explore?path=${encodeURIComponent(path)}`);
        const data = await res.json();

        if (data.error) {
            _setFsMessage(list, data.error, { color: "var(--accent-red)" });
            return;
        }

        list.replaceChildren();
        
        if (path !== "." && path !== "/" && parts.length > 0) {
            const parentPath = parts.slice(0, -1).join("/") || ".";
            const row = _createFsRow({
                icon: "folder_open",
                name: "..",
                onClick: () => window.loadFs(parentPath),
            });
            list.appendChild(row);
        }

        data.items.forEach(f => {
            const icon = f.is_dir ? "folder" : "insert_drive_file";
            const size = f.is_dir ? "" : formatSize(f.size);
            const mtime = new Date(f.mtime * 1000).toLocaleString();

            const row = _createFsRow({
                icon,
                name: f.name,
                size,
                mtime,
                isDir: f.is_dir,
                onClick: () => {
                    if (f.is_dir) {
                        window.loadFs(f.path);
                    } else {
                        openFileEditor(f.path, f.name);
                    }
                },
            });
            list.appendChild(row);
        });

    } catch (e) {
        _setFsMessage(list, "Error loading files", { color: "var(--accent-red)" });
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

    _setFsLoading(content);
    _renderFsBreadcrumb(breadcrumb, state.currentFsPath, fileName);

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
            _setFsMessage(content, err.error || "Error loading file", { color: "var(--accent-red)" });
            return;
        }
        const text = await res.text();

        content.innerHTML = `
            <div class="file-editor-toolbar">
                <span class="file-editor-name" id="file-editor-name"></span>
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
        const fileNameEl = document.getElementById("file-editor-name");
        if (fileNameEl) fileNameEl.textContent = fileName;
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
        _setFsMessage(content, `Error: ${e.message}`, { color: "var(--accent-red)" });
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


