const chat = document.getElementById("chat");
const form = document.getElementById("form");
const input = document.getElementById("input");
const updatedAt = document.getElementById("updatedAt");
const loading = document.getElementById("loading");

updatedAt.textContent = new Date().toLocaleString();

function clearEmpty() {
  const empty = chat.querySelector(".empty");
  if (empty) empty.remove();
}

/**
 * Añade mensajes al chat con seguridad para 'marked'
 */
function addMsg(role, text) {
  clearEmpty();
  const div = document.createElement("div");
  div.className = `msg ${role}`;
  
  if (role === "bot") {
    // CAMBIO 2: Seguridad si marked no está cargado
    div.innerHTML = (window.marked ? marked.parse(text) : text);
  } else {
    div.textContent = text;
  }
  
  chat.appendChild(div);
  chat.scrollTop = chat.scrollHeight;
  return div;
}

// ========================================================
// SUBMIT HANDLER (REFORZADO)
// ========================================================
form.addEventListener("submit", async (e) => {
  e.preventDefault();
  const message = input.value.trim();
  if (!message) return;

  addMsg("user", message);
  input.value = "";

  // Guardar mensaje usuario en historial
  const id = ensureCurrentConversation();
  updateConversation(id, (c) => {
    const msgs = c.messages || [];
    msgs.push({ role: "user", text: message, ts: Date.now() });
    c.messages = msgs;
    if (!c.title || c.title === "Kontsulta berria") c.title = formatTitle(message);
    c.updatedAt = Date.now();
    return c;
  });
  renderConversations();

  // CAMBIO 3: Evitar colgado si loading no existe
  if (loading) loading.style.display = "flex";
  chat.scrollTop = chat.scrollHeight;

  try {
    const res = await fetch("/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message })
    });

    const data = await res.json();
    const botText = data.answer ?? "Ezin izan da erantzunik lortu.";
    
    if (loading) loading.style.display = "none";
    addMsg("bot", botText);

    // Guardar respuesta éxito en historial
    const id2 = ensureCurrentConversation();
    updateConversation(id2, (c) => {
      const msgs = c.messages || [];
      msgs.push({ role: "bot", text: botText, ts: Date.now() });
      c.messages = msgs;
      c.updatedAt = Date.now();
      return c;
    });
    renderConversations();
    
  } catch (err) {
    // CAMBIO 3 (bis): Ocultar loading en error
    if (loading) loading.style.display = "none";
    
    const errorText = "Errore bat gertatu da konexioan. Mesedez, ziurtatu Ollama eta Backend-a piztuta daudela.";
    addMsg("bot", errorText);

    // CAMBIO 1: Guardar también el ERROR en el historial
    const idErr = ensureCurrentConversation();
    updateConversation(idErr, (c) => {
      const msgs = c.messages || [];
      msgs.push({ role: "bot", text: errorText, ts: Date.now() });
      c.messages = msgs;
      c.updatedAt = Date.now();
      return c;
    });
    renderConversations();
    console.error(err);
  }
});

// ========================================================
// LÓGICA DE HISTORIAL (Mantenida igual, es sólida)
// ========================================================
const conversationsList = document.getElementById("conversationsList");
const STORAGE_KEY = "tfg_conversations_v1";
const CURRENT_KEY = "tfg_current_conversation_id";

function loadConversations() {
  try { return JSON.parse(localStorage.getItem(STORAGE_KEY) || "[]"); }
  catch { return []; }
}

function saveConversations(convs) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(convs));
}
function deleteConversation(id) {
  const convs = loadConversations().filter(c => c.id !== id);
  saveConversations(convs);

  const currentId = getCurrentId();
  if (currentId === id) {
    // si borras la conversación actual, selecciona otra o crea nueva
    if (convs.length > 0) {
      setCurrentId(convs[0].id);
      loadConversationToUI(convs[0].id);
    } else {
      localStorage.removeItem(CURRENT_KEY);
      startNewConversation();
      return;
    }
  }
  renderConversations();
}

function clearHistory() {
  localStorage.removeItem(STORAGE_KEY);
  localStorage.removeItem(CURRENT_KEY);
  startNewConversation();
}
function getCurrentId() {
  return localStorage.getItem(CURRENT_KEY);
}

function setCurrentId(id) {
  localStorage.setItem(CURRENT_KEY, id);
}

function newId() {
  return "c_" + Math.random().toString(16).slice(2) + "_" + Date.now();
}

function formatTitle(text) {
  const t = (text || "").trim();
  if (!t) return "Kontsulta berria";
  return t.length > 28 ? t.slice(0, 28) + "…" : t;
}

function ensureCurrentConversation() {
  let convs = loadConversations();
  let id = getCurrentId();

  if (!id || !convs.some(c => c.id === id)) {
    id = newId();
    convs.unshift({
      id, title: "Kontsulta berria", createdAt: Date.now(), updatedAt: Date.now(), messages: []
    });
    saveConversations(convs);
    setCurrentId(id);
  }
  return id;
}

function getConversation(id) {
  const convs = loadConversations();
  return convs.find(c => c.id === id);
}

function updateConversation(id, updaterFn) {
  const convs = loadConversations();
  const idx = convs.findIndex(c => c.id === id);
  if (idx === -1) return;
  const updated = updaterFn({ ...convs[idx] });
  convs[idx] = updated;
  convs.sort((a, b) => (b.updatedAt || 0) - (a.updatedAt || 0));
  saveConversations(convs);
}

function renderConversations() {
  if (!conversationsList) return;
  const convs = loadConversations();
  const currentId = getCurrentId();
  conversationsList.innerHTML = "";

  convs.forEach(conv => {
    const row = document.createElement("div");
    row.className = "conv-row";

    const btn = document.createElement("button");
    btn.className = "side-item" + (conv.id === currentId ? " active" : "");
    btn.textContent = "💬 " + (conv.title || "Kontsulta berria");
    btn.addEventListener("click", () => {
      setCurrentId(conv.id);
      loadConversationToUI(conv.id);
      renderConversations();
    });

    const del = document.createElement("button");
    del.className = "icon-btn danger";
    del.type = "button";
    del.title = "Ezabatu";
    del.textContent = "🗑️";

    del.addEventListener("click", (e) => {
      e.stopPropagation();
      const ok = confirm("Ziur zaude kontsulta hau ezabatu nahi duzula?");
      if (!ok) return;
      deleteConversation(conv.id);
    });

    row.appendChild(btn);
    row.appendChild(del);
    conversationsList.appendChild(row);
  });
}

function loadConversationToUI(id) {
  const conv = getConversation(id);
  if (!conv) return;
  chat.innerHTML = "";
  if (!conv.messages || conv.messages.length === 0) {
    chat.innerHTML = `
      <div class="empty">
        <div class="watermark"><div class="watermark-text">UPV/EHU</div></div>
        <div class="empty-text">Bilatu UNIBASQ-en dagoen informazioa hemendik</div>
      </div>
    `;
    return;
  }
  conv.messages.forEach(m => addMsg(m.role, m.text));
}

function startNewConversation() {
  const id = newId();
  const convs = loadConversations();
  convs.unshift({
    id, title: "Kontsulta berria", createdAt: Date.now(), updatedAt: Date.now(), messages: []
  });
  saveConversations(convs);
  setCurrentId(id);
  loadConversationToUI(id);
  renderConversations();
}

document.getElementById("newQueryBtn")?.addEventListener("click", startNewConversation);

document.addEventListener("DOMContentLoaded", () => {
  ensureCurrentConversation();
  renderConversations();
  loadConversationToUI(getCurrentId());
});
document.getElementById("clearHistoryBtn")?.addEventListener("click", () => {
  const convs = loadConversations();
  if (!convs.length) return;

  const ok = confirm("Ziur zaude historiala OSO-OSORIK ezabatu nahi duzula?");
  if (!ok) return;

  clearHistory();
});