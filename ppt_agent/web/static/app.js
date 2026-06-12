const state = {
  sessionId: localStorage.getItem("growing_agent_session_id") || "",
  selectedFiles: [],
  chatFiles: [],
  busy: false,
  _downloadShown: false,  // 防止重复显示下载按钮
};

const els = {
  messages: document.querySelector("#messages"),
  chatForm: document.querySelector("#chatForm"),
  messageInput: document.querySelector("#messageInput"),
  sendButton: document.querySelector("#sendButton"),
  fileInput: document.querySelector("#fileInput"),
  uploadButton: document.querySelector("#uploadButton"),
  fileList: document.querySelector("#fileList"),
  dropzone: document.querySelector("#dropzone"),
  statusPill: document.querySelector("#statusPill"),
  materialCount: document.querySelector("#materialCount"),
  requirementComplete: document.querySelector("#requirementComplete"),
  projectStatus: document.querySelector("#projectStatus"),
  pptxDownload: document.querySelector("#pptxDownload"),
  outlineList: document.querySelector("#outlineList"),
  toast: document.querySelector("#toast"),
  chatFileInput: document.querySelector("#chatFileInput"),
  chatFilePreview: document.querySelector("#chatFilePreview"),
};

// ── 聊天框发送 ──
els.chatForm.addEventListener("submit", async (event) => {
  event.preventDefault();

  if (state.busy) return;

  const message = els.messageInput.value.trim();
  const hasFiles = state.chatFiles.length > 0;

  if (!message && !hasFiles) return;

  setBusy(true);

  // 如果有文件，先上传
  if (hasFiles) {
    await uploadChatFiles();
    // 如果没有文本消息，上传后自动发一条触发消息
    if (!message) {
      // 上传后 graph 已有资料，collect_material_node 会自动继续
      await sendChatMessage("__files_uploaded__");
      clearChatFiles();
      setBusy(false);
      return;
    }
  }

  // 有文本消息
  if (message) {
    addMessage("user", message);
    els.messageInput.value = "";
    await sendChatMessage(message);
  }

  setBusy(false);
});

// ── 聊天框文件选择 ──
els.chatFileInput.addEventListener("change", () => {
  state.chatFiles = Array.from(els.chatFileInput.files || []);
  renderChatFilePreview();
});

// ── 侧栏文件上传 ──
els.fileInput.addEventListener("change", () => {
  state.selectedFiles = Array.from(els.fileInput.files || []);
  renderSelectedFiles();
});

els.uploadButton.addEventListener("click", uploadSelectedFiles);

["dragenter", "dragover"].forEach((name) => {
  els.dropzone.addEventListener(name, (event) => {
    event.preventDefault();
    els.dropzone.classList.add("dragover");
  });
});

["dragleave", "drop"].forEach((name) => {
  els.dropzone.addEventListener(name, (event) => {
    event.preventDefault();
    els.dropzone.classList.remove("dragover");
  });
});

els.dropzone.addEventListener("drop", (event) => {
  state.selectedFiles = Array.from(event.dataTransfer.files || []);
  renderSelectedFiles();
});

// ── API 调用 ──

async function sendChatMessage(message, showInChat = true) {
  try {
    const payload = await postJson("/api/chat", {
      session_id: state.sessionId || null,
      message,
    });
    saveSession(payload.session_id);
    if (payload.assistant_reply) {
      addMessage("agent", payload.assistant_reply);
    }
    renderState(payload.state);
    if (payload.state?.pptx_ready && payload.state?.pptx_download_url && !state._downloadShown) {
      state._downloadShown = true;
      addDownloadMessage(payload.state.pptx_download_url);
    }
  } catch (error) {
    showToast(error.message, true);
    if (showInChat) {
      addMessage("agent", `请求失败：${error.message}`);
    }
  }
}

async function uploadChatFiles() {
  const files = state.chatFiles;
  if (!files.length) return;

  const formData = new FormData();
  if (state.sessionId) {
    formData.append("session_id", state.sessionId);
  }
  files.forEach((file) => formData.append("files", file));

  try {
    const payload = await postForm("/api/materials", formData);
    saveSession(payload.session_id);
    renderState(payload.state);

    const fileNames = files.map((f) => f.name).join("、");
    addMessage("agent", `📎 已上传资料：${fileNames}`);
    showToast(`已上传 ${files.length} 个资料文件。`);
  } catch (error) {
    showToast(error.message, true);
    addMessage("agent", `📎 上传失败：${error.message}`);
  }
}

async function uploadSelectedFiles() {
  if (!state.selectedFiles.length || state.busy) {
    showToast("请先选择资料文件。", true);
    return;
  }

  const formData = new FormData();
  if (state.sessionId) {
    formData.append("session_id", state.sessionId);
  }
  state.selectedFiles.forEach((file) => formData.append("files", file));

  setBusy(true);
  try {
    const payload = await postForm("/api/materials", formData);
    saveSession(payload.session_id);
    renderState(payload.state);
    showToast(`已上传 ${state.selectedFiles.length} 个资料文件。`);
    addMessage("agent", `资料已上传：${payload.material.file_paths.join("、")}`);
    state.selectedFiles = [];
    els.fileInput.value = "";
    renderSelectedFiles();

    // 如果 Agent 正在等待资料，自动触发继续
    if (payload.state?.status === "waiting_material") {
      addMessage("agent", "资料已就绪，继续处理...");
      await sendChatMessage("__files_uploaded__");
    }
  } catch (error) {
    showToast(error.message, true);
  } finally {
    setBusy(false);
  }
}

async function postJson(url, body) {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return readResponse(response);
}

async function postForm(url, body) {
  const response = await fetch(url, {
    method: "POST",
    body,
  });
  return readResponse(response);
}

async function readResponse(response) {
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(payload.detail || "请求失败");
  }
  return payload;
}

function saveSession(sessionId) {
  if (!sessionId) return;
  state.sessionId = sessionId;
  localStorage.setItem("growing_agent_session_id", sessionId);
}

// ── UI 渲染 ──

function addMessage(role, text) {
  const article = document.createElement("article");
  article.className = `message ${role}`;
  article.innerHTML = `
    <div class="avatar">${role === "user" ? "你" : "简"}</div>
    <div class="bubble"></div>
  `;
  article.querySelector(".bubble").textContent = text;
  els.messages.appendChild(article);
  els.messages.scrollTop = els.messages.scrollHeight;
}

function addDownloadMessage(url) {
  const article = document.createElement("article");
  article.className = "message agent";
  article.innerHTML = `
    <div class="avatar">简</div>
    <div class="bubble download-bubble">
      <span>演示文稿已经准备好。</span>
      <a class="download-link" href="${escapeHtml(url)}">下载 PPT</a>
    </div>
  `;
  els.messages.appendChild(article);
  els.messages.scrollTop = els.messages.scrollHeight;
}

function renderSelectedFiles() {
  if (!state.selectedFiles.length) {
    els.fileList.innerHTML = "<li>尚未选择文件</li>";
    return;
  }

  els.fileList.innerHTML = state.selectedFiles
    .map((file) => `<li>${escapeHtml(file.name)} · ${formatBytes(file.size)}</li>`)
    .join("");
}

function renderChatFilePreview() {
  const files = state.chatFiles;
  if (!files.length) {
    els.chatFilePreview.style.display = "none";
    els.chatFilePreview.innerHTML = "";
    return;
  }

  els.chatFilePreview.style.display = "block";
  els.chatFilePreview.innerHTML = `
    <div class="chat-file-list">
      ${files.map((f) => `
        <span class="chat-file-tag">${escapeHtml(f.name)} (${formatBytes(f.size)})</span>
      `).join("")}
      <button type="button" class="chat-file-clear" id="clearChatFiles">✕</button>
    </div>
  `;

  document.querySelector("#clearChatFiles")?.addEventListener("click", clearChatFiles);
}

function clearChatFiles() {
  state.chatFiles = [];
  els.chatFileInput.value = "";
  els.chatFilePreview.style.display = "none";
  els.chatFilePreview.innerHTML = "";
}

function renderState(nextState = {}) {
  const material = nextState.material || {};
  const outline = nextState.deck_outline || [];

  els.statusPill.textContent = translateStatus(nextState.status);
  els.materialCount.textContent = String(material.raw_text_count || 0);
  els.requirementComplete.textContent = nextState.requirement_complete ? "是" : "否";
  els.projectStatus.textContent = nextState.project_ready ? "已创建" : "暂无";
  if (nextState.pptx_ready && nextState.pptx_download_url) {
    els.pptxDownload.innerHTML = `<a class="download-link" href="${escapeHtml(nextState.pptx_download_url)}">下载 PPT</a>`;
  } else {
    els.pptxDownload.textContent = "暂无";
  }

  if (!outline.length) {
    els.outlineList.innerHTML = "<li>暂无大纲</li>";
    return;
  }

  els.outlineList.innerHTML = outline
    .map((slide) => {
      const page = escapeHtml(String(slide.page || ""));
      const title = escapeHtml(slide.title || "未命名页面");
      const purpose = escapeHtml(slide.purpose || "");
      return `<li>P${page} ${title}${purpose ? `：${purpose}` : ""}</li>`;
    })
    .join("");
}

function setBusy(value) {
  state.busy = value;
  els.sendButton.disabled = value;
  els.uploadButton.disabled = value;
}

function showToast(message, isError = false) {
  els.toast.textContent = message;
  els.toast.classList.toggle("error", isError);
  els.toast.classList.add("show");
  window.clearTimeout(showToast.timer);
  showToast.timer = window.setTimeout(() => {
    els.toast.classList.remove("show");
  }, 2600);
}

function formatBytes(bytes) {
  if (bytes < 1024) return `${bytes} 字节`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} 千字节`;
  return `${(bytes / 1024 / 1024).toFixed(1)} 兆字节`;
}

function escapeHtml(value) {
  return value.replace(/[&<>"']/g, (char) => {
    const map = {
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#39;",
    };
    return map[char];
  });
}

function translateStatus(status) {
  const statusMap = {
    collecting: "收集中",
    waiting_user: "等待补充",
    brief_ready: "任务单已就绪",
    outline_ready: "大纲已就绪",
    project_created: "项目已创建",
    failed: "运行失败",
    waiting_material: "等待资料",
    material_ready: "资料已就绪",
    waiting_confirm: "等待确认",
    confirmed: "已确认",
    materials_written: "资料已写入",
    design_spec_created: "设计规格已生成",
    spec_lock_created: "执行规格已生成",
    svg_created: "页面已生成",
    ppt_exported: "PPT 已生成",
  };

  return statusMap[status] || "收集中";
}

renderSelectedFiles();
