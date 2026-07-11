// ANA — Workspace client
(() => {
  const $ = (id) => document.getElementById(id);
  const messagesEl = $("messages");
  const composer = $("composer");
  const input = $("input");
  const newChatBtn = $("newChatBtn");
  const historyList = $("historyList");
  const uploadInput = $("uploadInput");
  const shareBtnNav = $("shareBtn");

  if (!composer) return;

  let conversationId = null;
  let attachedDocumentId = null;
  let attachedDocumentName = null;
  let activeAbortController = null;
  let activeUserRow = null;

  const ICON_COPY = `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1"/></svg>`;
  const ICON_CHECK = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="20 6 9 17 4 12"/></svg>`;
  const ICON_EDIT = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>`;
  const ICON_SHARE = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 12v8a2 2 0 002 2h12a2 2 0 002-2v-8"/><polyline points="16 6 12 2 8 6"/><line x1="12" y1="2" x2="12" y2="15"/></svg> Share`;

  const addMsg = (role, content, docName = null, messageId = null) => {
    const welcome = messagesEl.querySelector(".welcome");
    if (welcome) welcome.remove();

    const row = document.createElement("div");
    row.className = `msg-row msg-row--${role === "user" ? "user" : "bot"}`;
    if (messageId) row.dataset.messageId = messageId;

    if (role !== "user") {
      const logo = document.createElement("div");
      logo.className = "msg-logo";
      row.appendChild(logo);
    }

    const bubble = document.createElement("div");
    bubble.className = `msg msg--${role === "user" ? "user" : "bot"}`;

    if (role === "user") {
      let html = content.replace(/</g, "&lt;").replace(/>/g, "&gt;");
      if (docName) {
        html = `<div style="display:inline-flex;align-items:center;gap:6px;background:rgba(255,255,255,0.08);border:1px solid rgba(255,255,255,0.15);border-radius:8px;padding:6px 10px;margin-bottom:6px;font-size:13px;">📄 ${docName}</div><br>${html}`;
      }
      bubble.innerHTML = html;
    } else {
      bubble.innerHTML = marked.parse(content);
    }

    row.appendChild(bubble);

    const actions = document.createElement("div");
    if (role === "user") {
      actions.className = "msg-actions msg-actions--user";
      const copyBtn = document.createElement("button");
      copyBtn.className = "msg-action-btn";
      copyBtn.title = "Copy";
      copyBtn.innerHTML = ICON_COPY;
      copyBtn.addEventListener("click", () => {
        navigator.clipboard.writeText(content);
        copyBtn.innerHTML = ICON_CHECK;
        setTimeout(() => copyBtn.innerHTML = ICON_COPY, 2000);
      });
      const editBtn = document.createElement("button");
      editBtn.className = "msg-action-btn";
      editBtn.title = "Edit";
      editBtn.innerHTML = ICON_EDIT;
      editBtn.addEventListener("click", () => {
        startEdit(row, content);
      });
      actions.appendChild(copyBtn);
      actions.appendChild(editBtn);
    } else {
      actions.className = "msg-actions msg-actions--bot";
      const copyBtn = document.createElement("button");
      copyBtn.className = "msg-action-btn";
      copyBtn.title = "Copy response";
      copyBtn.innerHTML = ICON_COPY;
      copyBtn.addEventListener("click", () => {
        navigator.clipboard.writeText(bubble.innerText);
        copyBtn.innerHTML = ICON_CHECK;
        setTimeout(() => copyBtn.innerHTML = ICON_COPY, 2000);
      });
      actions.appendChild(copyBtn);

      bubble.querySelectorAll("pre").forEach((pre) => {
        const btn = document.createElement("button");
        btn.className = "copy-btn";
        btn.textContent = "Copy";
        btn.addEventListener("click", () => {
          navigator.clipboard.writeText(pre.innerText).then(() => {
            btn.textContent = "Copied!";
            setTimeout(() => btn.textContent = "Copy", 2000);
          });
        });
        pre.style.position = "relative";
        pre.appendChild(btn);
      });
    }

    row.appendChild(actions);
    messagesEl.appendChild(row);
    messagesEl.scrollTop = messagesEl.scrollHeight;
    return { bubble, row };
  };

  // ── EDIT MODE — turns a user bubble into an inline editable textarea ──
  const startEdit = (row, currentText) => {
    const bubble = row.querySelector(".msg");
    const messageId = row.dataset.messageId;
    const isCurrentlyGenerating = (row === activeUserRow);

    if (!messageId && !isCurrentlyGenerating) {
      alert("This message can't be edited yet — please wait for it to finish saving.");
      return;
    }

    const originalHTML = bubble.innerHTML;

    const textarea = document.createElement("textarea");
    textarea.value = currentText;
    textarea.style.cssText = "width:100%;min-height:60px;background:transparent;color:inherit;border:1px solid var(--border);border-radius:8px;padding:8px;font-family:inherit;font-size:inherit;resize:vertical;";
    bubble.innerHTML = "";
    bubble.appendChild(textarea);

    const btnRow = document.createElement("div");
    btnRow.style.cssText = "display:flex;gap:8px;margin-top:8px;";

    const saveBtn = document.createElement("button");
    saveBtn.textContent = "Save & Submit";
    saveBtn.className = "btn btn--primary";
    saveBtn.style.cssText = "padding:6px 14px;font-size:0.85rem;";

    const cancelBtn = document.createElement("button");
    cancelBtn.textContent = "Cancel";
    cancelBtn.className = "btn btn--ghost";
    cancelBtn.style.cssText = "padding:6px 14px;font-size:0.85rem;";
    cancelBtn.addEventListener("click", () => {
      bubble.innerHTML = originalHTML;
    });

    saveBtn.addEventListener("click", () => {
      const newText = textarea.value.trim();
      if (!newText) return;

      if (isCurrentlyGenerating) {
        // Cancel the in-flight response, then send this as a fresh message
        if (activeAbortController) {
          activeAbortController.abort();
          activeAbortController = null;
        }
        const nextEl = row.nextElementSibling;
        if (nextEl) nextEl.remove(); // remove the unfinished bot bubble
        row.remove();
        sendMessage(newText, null, null);
      } else {
        submitEdit(row, messageId, newText);
      }
    });

    btnRow.appendChild(saveBtn);
    btnRow.appendChild(cancelBtn);
    bubble.appendChild(btnRow);
    textarea.focus();
  };

  const submitEdit = async (editedRow, messageId, newText) => {
    // Remove the edited message AND everything visually below it
    let node = editedRow;
    const toRemove = [];
    while (node) {
      toRemove.push(node);
      node = node.nextElementSibling;
    }
    toRemove.forEach((n) => n.remove());

    const newUserRow = addMsg("user", newText).row;
    if (shareBtnNav) shareBtnNav.style.display = "flex";

    const { update, finish, row } = addStreamingMsg();

    activeUserRow = newUserRow;
    const controller = new AbortController();
    activeAbortController = controller;

    try {
      const res = await fetch("/chat/edit", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "same-origin",
        body: JSON.stringify({
          conversation_id: conversationId,
          message_id: messageId,
          message: newText,
          document_id: null,
        }),
        signal: controller.signal,
      });
      await consumeStream(res, update, finish, row, newUserRow);
    } catch (err) {
      if (err.name === "AbortError") return;
      row.remove();
      addMsg("bot", "⚠️ Network error: " + err.message);
    } finally {
      activeAbortController = null;
      activeUserRow = null;
    }
  };

  // ── STREAMING BOT MESSAGE ──
  const addStreamingMsg = () => {
    const welcome = messagesEl.querySelector(".welcome");
    if (welcome) welcome.remove();

    const row = document.createElement("div");
    row.className = "msg-row msg-row--bot";
    const logo = document.createElement("div");
    logo.className = "msg-logo";
    row.appendChild(logo);

    const bubble = document.createElement("div");
    bubble.className = "msg msg--bot";
    bubble.innerHTML = `<div class="dots"><span></span><span></span><span></span></div>`;
    row.appendChild(bubble);
    messagesEl.appendChild(row);
    messagesEl.scrollTop = messagesEl.scrollHeight;

    let fullText = "";
    let started = false;

    const update = (token) => {
      if (!started) {
        bubble.innerHTML = "";
        started = true;
      }
      fullText += token;
      bubble.innerHTML = marked.parse(fullText);
      messagesEl.scrollTop = messagesEl.scrollHeight;
    };

    const finish = () => {
      bubble.innerHTML = marked.parse(fullText);
      const actions = document.createElement("div");
      actions.className = "msg-actions msg-actions--bot";
      const copyBtn = document.createElement("button");
      copyBtn.className = "msg-action-btn";
      copyBtn.innerHTML = ICON_COPY;
      copyBtn.addEventListener("click", () => {
        navigator.clipboard.writeText(bubble.innerText);
        copyBtn.innerHTML = ICON_CHECK;
        setTimeout(() => copyBtn.innerHTML = ICON_COPY, 2000);
      });
      actions.appendChild(copyBtn);
      row.appendChild(actions);

      bubble.querySelectorAll("pre").forEach((pre) => {
        const btn = document.createElement("button");
        btn.className = "copy-btn";
        btn.textContent = "Copy";
        btn.addEventListener("click", () => {
          navigator.clipboard.writeText(pre.innerText).then(() => {
            btn.textContent = "Copied!";
            setTimeout(() => btn.textContent = "Copy", 2000);
          });
        });
        pre.style.position = "relative";
        pre.appendChild(btn);
      });
    };

    return { update, finish, row };
  };

  // ── SHARED SSE STREAM CONSUMER — used by both /send and /edit ──
  const consumeStream = async (res, update, finish, row, userMsgRow = null) => {
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop();

      for (const line of lines) {
        if (!line.startsWith("data: ")) continue;
        try {
          const parsed = JSON.parse(line.slice(6));
          if (parsed.token) {
            update(parsed.token);
            messagesEl.scrollTop = messagesEl.scrollHeight;
          }
          if (parsed.done) {
            conversationId = parsed.conversation_id || conversationId;
            if (userMsgRow && parsed.user_message_id) {
              userMsgRow.dataset.messageId = parsed.user_message_id;
            }
            finish();
            if (parsed.grounded) {
              const tag = document.createElement("div");
              tag.className = "muted";
              tag.style.cssText = "font-size:0.75rem;width:100%;margin:-10px auto 0;padding:0 80px;";
              tag.textContent = "✦ grounded in your documents";
              messagesEl.appendChild(tag);
            }
            loadHistory(true);
          }
          if (parsed.error) {
            row.remove();
            addMsg("bot", "⚠️ " + parsed.error);
          }
        } catch {}
      }
    }
  };

  // ── SEND — used by both the composer submit AND edit-during-generation ──
  const sendMessage = async (text, docId, docName) => {
    input.value = "";
    input.style.height = "auto";
    attachedDocumentId = null;
    attachedDocumentName = null;
    const fp = document.getElementById("filePreview");
    if (fp) fp.style.display = "none";

    const userMsgRow = addMsg("user", text, docName).row;
    activeUserRow = userMsgRow;
    if (shareBtnNav) shareBtnNav.style.display = "flex";

    const { update, finish, row } = addStreamingMsg();

    const controller = new AbortController();
    activeAbortController = controller;

    try {
      const res = await fetch("/chat/send", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "same-origin",
        body: JSON.stringify({ message: text, conversation_id: conversationId, document_id: docId }),
        signal: controller.signal,
      });
      await consumeStream(res, update, finish, row, userMsgRow);
    } catch (err) {
      if (err.name === "AbortError") return;
      row.remove();
      addMsg("bot", "⚠️ Network error: " + err.message);
    } finally {
      activeAbortController = null;
      activeUserRow = null;
    }
  };

  composer.addEventListener("submit", (e) => {
    e.preventDefault();
    const text = input.value.trim();
    if (!text) return;
    sendMessage(text, attachedDocumentId, attachedDocumentName);
  });

  input?.addEventListener("input", () => {
    input.style.height = "auto";
    input.style.height = Math.min(input.scrollHeight, 120) + "px";
  });

  input?.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      composer.requestSubmit();
    }
  });

  document.querySelectorAll(".chip").forEach((c) =>
    c.addEventListener("click", () => {
      input.value = c.dataset.p;
      input.focus();
    })
  );

  newChatBtn?.addEventListener("click", () => {
    conversationId = null;
    messagesEl.innerHTML = "";
    location.reload();
  });

  let historyCache = null;
  let historyCacheTime = 0;
  const CACHE_TTL = 30000;

  const loadHistory = async (force = false) => {
    const now = Date.now();
    if (!force && historyCache && (now - historyCacheTime) < CACHE_TTL) {
      renderHistory(historyCache);
      return;
    }
    const res = await fetch("/chat/history", { credentials: "same-origin" });
    const { conversations = [] } = await res.json();
    historyCache = conversations;
    historyCacheTime = now;
    renderHistory(conversations);
  };

  const renderHistory = (conversations) => {
    historyList.innerHTML = "";
    conversations.forEach((c) => {
      const li = document.createElement("li");
      li.style.cssText = "display:flex;align-items:center;justify-content:space-between;gap:6px;";

      const title = document.createElement("span");
      title.textContent = c.title || "Untitled";
      title.style.cssText = "flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;cursor:pointer;";
      title.addEventListener("click", async () => {
        conversationId = c.id;
        messagesEl.innerHTML = "";
        const res = await fetch(`/chat/messages/${c.id}`, { credentials: "same-origin" });
        const { messages = [] } = await res.json();
        messages.forEach((m) => addMsg(m.role, m.content, null, m.id));
      });

      const delBtn = document.createElement("button");
      delBtn.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14H6L5 6"/><path d="M10 11v6M14 11v6"/><path d="M9 6V4h6v2"/></svg>`;
      delBtn.title = "Delete";
      delBtn.style.cssText = "background:none;border:none;cursor:pointer;color:#666;padding:2px;flex-shrink:0;opacity:0;transition:opacity 0.2s;";
      li.addEventListener("mouseenter", () => delBtn.style.opacity = "1");
      li.addEventListener("mouseleave", () => delBtn.style.opacity = "0");
      delBtn.addEventListener("click", async (e) => {
        e.stopPropagation();
        if (!confirm("Delete this conversation?")) return;
        await fetch(`/chat/history/${c.id}`, { method: "DELETE", credentials: "same-origin" });
        if (conversationId === c.id) {
          conversationId = null;
          messagesEl.innerHTML = "";
          location.reload();
        }
        loadHistory(true);
      });

      li.appendChild(title);
      li.appendChild(delBtn);
      historyList.appendChild(li);
    });
  };

  uploadInput?.addEventListener("change", async () => {
    const file = uploadInput.files[0];
    if (!file) return;

    const filePreview = document.getElementById("filePreview");
    const filePreviewName = document.getElementById("filePreviewName");
    filePreviewName.textContent = file.name;
    filePreview.style.display = "block";

    document.getElementById("filePreviewRemove").onclick = () => {
      filePreview.style.display = "none";
      uploadInput.value = "";
      attachedDocumentId = null;
      attachedDocumentName = null;
    };

    const attachBtn = document.querySelector(".composer__attach");
    attachBtn.disabled = true;
    filePreviewName.textContent = "Uploading...";

    const fd = new FormData();
    fd.append("file", file);
    try {
      const res = await fetch("/documents/upload", { method: "POST", body: fd, credentials: "same-origin" });
      const data = await res.json();
      if (data.error) {
        alert(data.error);
        filePreview.style.display = "none";
      } else {
        attachedDocumentId = data.document.id;
        attachedDocumentName = file.name;
        filePreviewName.textContent = file.name;
      }
    } catch (err) {
      alert("Upload failed: " + err.message);
      filePreview.style.display = "none";
    } finally {
      attachBtn.disabled = false;
      uploadInput.value = "";
    }
  });

  loadHistory(true);

  window.shareConversation = async function () {
    if (!conversationId) { alert("Start a conversation first!"); return; }
    const btn = document.getElementById("shareBtn");
    if (btn) { btn.textContent = "Sharing..."; btn.disabled = true; }
    try {
      const res = await fetch(`/chat/share/${conversationId}`, { method: "POST", credentials: "same-origin" });
      const data = await res.json();
      if (data.ok) {
        const url = `${window.location.origin}/share/${data.share_id}`;
        await navigator.clipboard.writeText(url);
        if (btn) {
          btn.innerHTML = "✓ Link Copied!";
          setTimeout(() => { btn.innerHTML = ICON_SHARE; btn.disabled = false; }, 3000);
        }
      } else {
        if (btn) { btn.innerHTML = ICON_SHARE; btn.disabled = false; }
        alert(data.error || "Failed to share");
      }
    } catch (err) {
      if (btn) { btn.innerHTML = ICON_SHARE; btn.disabled = false; }
      alert("Network error: " + err.message);
    }
  };
})();