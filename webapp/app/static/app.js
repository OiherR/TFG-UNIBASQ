const chat = document.getElementById("chat");
const form = document.getElementById("form");
const input = document.getElementById("input");
const updatedAt = document.getElementById("updatedAt");
const loading = document.getElementById("loading");
const conversationsList = document.getElementById("conversationsList");

const STORAGE_KEY = "tfg_conversations_v1";
const CURRENT_KEY = "tfg_current_conversation_id";

let langButtons;

// Modal
const aboutBtn = document.getElementById("sideAbout");
const aboutModal = document.getElementById("aboutModal");
const closeAboutBtn = document.getElementById("closeAboutBtn");

// =======================
// TRADUCCIONES
// =======================
const translations = {
  eu: {
    brandTitle: "Laguntzailea-TFG",
    brandSub: "Kontsulta-laguntzailea",
    newChat: "Kontsulta berria",
    send: "Bidali",
    clear: "Garbitu historiala",
    lastUpdate: "Azken eguneraketa",
    myQueries: "Nire kontsultak",
    help: "Laguntza",
    unibasq: "UNIBASQen orria",
    about: "Proiektuari buruz",
    inputPlaceholder: "Galdetu nahi duzuna",
    tabConversation: "Elkarrizketa",
    emptyText: "Bilatu UNIBASQ-en dagoen informazioa hemendik",
    aboutText: `
      Proiektu honek <strong>GraphRAG</strong> arkitekturan oinarritutako kontsulta-laguntzaile bat garatzen du, unibertsitateko irakasleen ebaluazio eta akreditazio prozesuei lotutako araudia interpretatzeko helburuarekin.

    Bere helburua <strong>UNIBASQ</strong>, <strong>ANECA</strong> eta <strong>BOE</strong> bezalako erakunde ofizialetatik eratorritako informazioan oinarritutako erantzun argiak, zehatzak eta fidagarriak eskaintzea da.

    Sistemak informazioaren berreskuratzea eta ezagutzaren adierazpena konbinatzen ditu, bilaketa bektoriala, RDF grafo semantikoak, SPARQL kontsultak eta hizkuntza-eredu handiak (LLM) integratuz. Horri esker, erantzunak testuinguru egokiarekin aberasten dira eta egiaztatu gabeko informazioaren sorrera murrizten da.

    Horrela, laguntzaileak araudi konplexua hizkuntza naturalean kontsultatzeko aukera ematen du, ebaluazio- eta akreditazio-prozesuen ulermena eta irisgarritasuna hobetuz.

    `,
    delete: "Ezabatu",
    confirmDeleteConversation: "Ziur zaude kontsulta hau ezabatu nahi duzula?",
    confirmClearHistory: "Ziur zaude historiala OSO-OSORIK ezabatu nahi duzula?",
    loadingText: "⏳ UNIBASQeko datuak aztertzen...",
    connectionError:
      "Errore bat gertatu da konexioan. Mesedez, ziurtatu Ollama eta Backend-a piztuta daudela.",
    genericAnswerError: "Ezin izan da erantzunik lortu.",
    close: "Itxi"
  },
  es: {
    brandTitle: "Asistente-TFG",
    brandSub: "Asistente de consultas",
    newChat: "Nueva consulta",
    send: "Enviar",
    clear: "Limpiar historial",
    lastUpdate: "Última actualización",
    myQueries: "Mis consultas",
    help: "Ayuda",
    unibasq: "Página de UNIBASQ",
    about: "Sobre el proyecto",
    inputPlaceholder: "Escribe tu consulta",
    tabConversation: "Conversación",
    emptyText: "Busca aquí la información disponible en UNIBASQ",
    aboutText: `
      Este proyecto desarrolla un asistente de consultas basado en la arquitectura <strong>GraphRAG</strong>, orientado a la interpretación de normativa académica y procesos de acreditación del profesorado universitario.

      Su objetivo es proporcionar respuestas claras, precisas y fundamentadas a partir de información oficial procedente de organismos como <strong>UNIBASQ</strong>, <strong>ANECA</strong> y el <strong>BOE</strong>.

      El sistema combina técnicas de recuperación de información y representación del conocimiento, integrando búsqueda vectorial, grafos semánticos (RDF), consultas estructuradas mediante SPARQL y modelos de lenguaje (LLM). Esta combinación permite enriquecer las respuestas con contexto relevante y reducir la generación de información no verificada.

      De este modo, el asistente facilita la consulta de normativa compleja en lenguaje natural, mejorando la accesibilidad y comprensión de los procesos de evaluación y acreditación académica.

    `,
    delete: "Eliminar",
    confirmDeleteConversation: "¿Seguro que quieres eliminar esta consulta?",
    confirmClearHistory: "¿Seguro que quieres borrar TODO el historial?",
    loadingText: "⏳ Analizando los datos de UNIBASQ...",
    connectionError:
      "Se ha producido un error de conexión. Asegúrate de que Ollama y el Backend están encendidos.",
    genericAnswerError: "No se ha podido obtener una respuesta.",
    close: "Cerrar"
  }
};

updatedAt.textContent = new Date().toLocaleString();

// =======================
// HELPERS
// =======================
function getLang() {
  return localStorage.getItem("lang") || "eu";
}

function t() {
  return translations[getLang()] || translations.eu;
}

function clearEmpty() {
  const empty = chat.querySelector(".empty");
  if (empty) empty.remove();
}

function addMsg(role, text) {
  clearEmpty();
  const div = document.createElement("div");
  div.className = `msg ${role}`;

  if (role === "bot") {
    div.innerHTML = window.marked ? marked.parse(text) : text;
  } else {
    div.textContent = text;
  }

  chat.appendChild(div);
  chat.scrollTop = chat.scrollHeight;
  return div;
}

// =======================
// MODAL
// =======================
function openAboutModal() {
  if (!aboutModal) return;
  aboutModal.style.display = "flex";
  aboutModal.classList.add("open");
  aboutModal.setAttribute("aria-hidden", "false");
}

function closeAboutModal() {
  if (!aboutModal) return;
  aboutModal.style.display = "none";
  aboutModal.classList.remove("open");
  aboutModal.setAttribute("aria-hidden", "true");
}

// =======================
// IDIOMA
// =======================
function setLanguage(lang) {
  localStorage.setItem("lang", lang);
  applyLanguage(lang);
  renderConversations();
  loadConversationToUI(getCurrentId());
}

function applyLanguage(lang) {
  if (!translations[lang]) lang = "eu";

  const tr = translations[lang];

  langButtons?.forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.lang === lang);
  });

  const brandTitle = document.querySelector(".brand-title");
  const brandSub = document.querySelector(".brand-sub");
  const newQueryBtn = document.getElementById("newQueryBtn");
  const clearHistoryBtn = document.getElementById("clearHistoryBtn");
  const sendBtn = document.getElementById("sendBtn");
  const sideTitles = document.querySelectorAll(".side-title");
  const unibasqLink = document.querySelector('a[href*="unibasq"]');
  const sideAbout = document.getElementById("sideAbout");
  const mainTitle = document.querySelector(".main-title");
  const mainSub = document.querySelector(".main-sub");
  const tab = document.querySelector(".tab");
  const inputEl = document.getElementById("input");
  const emptyText = document.querySelector(".empty-text");
  const modalTitle = document.getElementById("aboutModalTitle");
  const modalP = document.getElementById("aboutModalText");
  const loadingSpan = loading?.querySelector("span");

  if (brandTitle) brandTitle.textContent = tr.brandTitle;
  if (brandSub) brandSub.textContent = tr.brandSub;
  if (newQueryBtn) newQueryBtn.textContent = "✎ " + tr.newChat;
  if (clearHistoryBtn) clearHistoryBtn.textContent = "🧹 " + tr.clear;
  if (sendBtn) sendBtn.textContent = tr.send;

  if (sideTitles[0]) sideTitles[0].textContent = tr.myQueries;
  if (sideTitles[1]) sideTitles[1].textContent = tr.help;

  if (unibasqLink) unibasqLink.textContent = tr.unibasq;
  if (sideAbout) sideAbout.textContent = "ℹ️ " + tr.about;

  const currentConv = getConversation(getCurrentId());

  if (mainTitle) {
    if (!currentConv || isDefaultConversationTitle(currentConv.title)) {
      mainTitle.textContent = tr.newChat;
    } else {
      mainTitle.textContent = currentConv.title;
    }
  }

  if (mainSub && mainSub.childNodes[0]) {
    mainSub.childNodes[0].textContent = tr.lastUpdate + ": ";
  }
  if (tab) tab.textContent = tr.tabConversation;

  if (inputEl) inputEl.placeholder = tr.inputPlaceholder;
  if (emptyText) emptyText.textContent = tr.emptyText;

  if (modalTitle) modalTitle.textContent = tr.about;
  if (modalP) modalP.innerHTML = tr.aboutText;
  if (closeAboutBtn) closeAboutBtn.setAttribute("aria-label", tr.close);

  if (loadingSpan) loadingSpan.textContent = tr.loadingText;
}

// =======================
// SUBMIT
// =======================
form?.addEventListener("submit", async (e) => {
  e.preventDefault();

  const message = input.value.trim();
  if (!message) return;

  const currentId = ensureCurrentConversation();

  // Mostrar mensaje del usuario
  addMsg("user", message);
  input.value = "";

  // Guardar mensaje del usuario en localStorage
  updateConversation(currentId, (conv) => {
    const msgs = conv.messages || [];

    if (msgs.length === 0) {
      conv.title = formatTitle(message);
    }

    msgs.push({
      role: "user",
      text: message
    });

    return {
      ...conv,
      messages: msgs,
      updatedAt: Date.now()
    };
  });

  renderConversations();

  if (loading) loading.style.display = "flex";

  try {
    const res = await fetch("/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message })
    });

    const data = await res.json();
    const answer = data.answer || t().genericAnswerError;

    // Mostrar respuesta del bot
    addMsg("bot", answer);

    // Guardar respuesta del bot en localStorage
    updateConversation(currentId, (conv) => {
      const msgs = conv.messages || [];

      msgs.push({
        role: "bot",
        text: answer
      });

      return {
        ...conv,
        messages: msgs,
        updatedAt: Date.now()
      };
    });

    renderConversations();

  } catch (err) {
    const errorMsg = t().connectionError;

    addMsg("bot", errorMsg);

    updateConversation(currentId, (conv) => {
      const msgs = conv.messages || [];

      msgs.push({
        role: "bot",
        text: errorMsg
      });

      return {
        ...conv,
        messages: msgs,
        updatedAt: Date.now()
      };
    });

    console.error(err);
  }

  if (loading) loading.style.display = "none";
});
// =======================
// HISTORIAL
// =======================
function loadConversations() {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY) || "[]");
  } catch {
    return [];
  }
}

function saveConversations(convs) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(convs));
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
  const v = (text || "").trim();
  if (!v) return getLang() === "es" ? "Nueva consulta" : "Kontsulta berria";
  return v.length > 28 ? v.slice(0, 28) + "…" : v;
}

function isDefaultConversationTitle(title) {
  return (
    !title ||
    title === translations.es.newChat ||
    title === translations.eu.newChat
  );
}

function ensureCurrentConversation() {
  let convs = loadConversations();
  let id = getCurrentId();

  if (!id || !convs.some((c) => c.id === id)) {
    const defaultTitle = getLang() === "es" ? "Nueva consulta" : "Kontsulta berria";

    id = newId();
    convs.unshift({
      id,
      title: defaultTitle,
      createdAt: Date.now(),
      updatedAt: Date.now(),
      messages: []
    });
    saveConversations(convs);
    setCurrentId(id);
  }
  return id;
}

function getConversation(id) {
  return loadConversations().find((c) => c.id === id);
}

function updateConversation(id, updaterFn) {
  const convs = loadConversations();
  const idx = convs.findIndex((c) => c.id === id);
  if (idx === -1) return;

  convs[idx] = updaterFn({ ...convs[idx] });
  convs.sort((a, b) => (b.updatedAt || 0) - (a.updatedAt || 0));
  saveConversations(convs);
}

function deleteConversation(id) {
  const convs = loadConversations().filter((c) => c.id !== id);
  saveConversations(convs);

  const currentId = getCurrentId();
  if (currentId === id) {
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

function renderConversations() {
  if (!conversationsList) return;

  const convs = loadConversations();
  const currentId = getCurrentId();

  conversationsList.innerHTML = "";

  convs.forEach((conv) => {
    const row = document.createElement("div");
    row.className = "conv-row";

    const btn = document.createElement("button");
    btn.className = "side-item" + (conv.id === currentId ? " active" : "");

    const titleToShow = isDefaultConversationTitle(conv.title)
      ? t().newChat
      : conv.title;

    btn.textContent = "💬 " + titleToShow;

    btn.addEventListener("click", () => {
      setCurrentId(conv.id);
      loadConversationToUI(conv.id);
      renderConversations();
    });

    const del = document.createElement("button");
    del.className = "icon-btn danger";
    del.type = "button";
    del.title = t().delete;
    del.textContent = "🗑️";

    del.addEventListener("click", (e) => {
      e.stopPropagation();
      const ok = confirm(t().confirmDeleteConversation);
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

  const mainTitle = document.querySelector(".main-title");

  if (mainTitle) {
    if (isDefaultConversationTitle(conv.title)) {
      mainTitle.textContent = t().newChat;
    } else {
      mainTitle.textContent = conv.title;
    }
  }

  chat.innerHTML = "";

  if (!conv.messages || conv.messages.length === 0) {
    chat.innerHTML = `
      <div class="empty">
        <div class="watermark">UPV/EHU</div>
        <div class="empty-text">${t().emptyText}</div>
      </div>
    `;
    return;
  }

  conv.messages.forEach((m) => addMsg(m.role, m.text));
}

function startNewConversation() {
  const defaultTitle = getLang() === "es" ? "Nueva consulta" : "Kontsulta berria";

  const id = newId();
  const convs = loadConversations();

  convs.unshift({
    id,
    title: defaultTitle,
    createdAt: Date.now(),
    updatedAt: Date.now(),
    messages: []
  });

  saveConversations(convs);
  setCurrentId(id);
  loadConversationToUI(id);
  renderConversations();
}

// =======================
// EVENTOS
// =======================
document.getElementById("newQueryBtn")?.addEventListener("click", startNewConversation);

document.getElementById("clearHistoryBtn")?.addEventListener("click", () => {
  const convs = loadConversations();
  if (!convs.length) return;

  const ok = confirm(t().confirmClearHistory);
  if (!ok) return;

  clearHistory();
});

document.addEventListener("DOMContentLoaded", () => {
  langButtons = document.querySelectorAll(".lang-btn");

  langButtons.forEach((btn) => {
    btn.addEventListener("click", () => {
      setLanguage(btn.dataset.lang);
    });
  });

  aboutBtn?.addEventListener("click", openAboutModal);
  closeAboutBtn?.addEventListener("click", closeAboutModal);

  aboutModal?.addEventListener("click", (e) => {
    if (e.target === aboutModal) {
      closeAboutModal();
    }
  });

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      closeAboutModal();
    }
  });

  ensureCurrentConversation();
  renderConversations();
  loadConversationToUI(getCurrentId());
  applyLanguage(getLang());
});