const chat = document.getElementById("chat");
const form = document.getElementById("form");
const input = document.getElementById("input");
const updatedAt = document.getElementById("updatedAt");

updatedAt.textContent = new Date().toLocaleString();

function clearEmpty() {
  const empty = chat.querySelector(".empty");
  if (empty) empty.remove();
}

function addMsg(role, text) {
  clearEmpty();
  const div = document.createElement("div");
  div.className = `msg ${role}`;
  div.textContent = text;
  chat.appendChild(div);
  chat.scrollTop = chat.scrollHeight;
  return div;
}

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  const message = input.value.trim();
  if (!message) return;

  addMsg("user", message);
  input.value = "";

  const thinking = addMsg("bot", "Pentsatzen...");

  try {
    const res = await fetch("/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message })
    });

    const data = await res.json();
    thinking.textContent = data.answer ?? "Ez dago erantzunik.";
  } catch (err) {
    thinking.textContent = "Error konektatzean.";
  }
});

// UI buttons
const logoutBtn = document.getElementById("logoutBtn");
logoutBtn?.addEventListener("click", () => {
  alert("Amaitu Sesioa (pendiente de implementar)");
});

const newQueryBtn = document.getElementById("newQueryBtn");
newQueryBtn?.addEventListener("click", () => {
  chat.innerHTML = `
    <div class="empty">
      <div class="watermark">UPV/EHU</div>
      <div class="empty-text">Bilatu Unibasq dagoen informazioa hemendik</div>
    </div>
  `;
  input.focus();
});

/* =========================
   MODAL: Proiektuari buruz
   ========================= */
document.addEventListener("DOMContentLoaded", () => {
  const aboutBtn = document.getElementById("sideAbout");      // botón del sidebar
  const aboutModal = document.getElementById("aboutModal");   // backdrop
  const closeAboutBtn = document.getElementById("closeAboutBtn");

  // Debug rápido (mira en consola F12)
  console.log("[about modal]", {
    aboutBtn: !!aboutBtn,
    aboutModal: !!aboutModal,
    closeAboutBtn: !!closeAboutBtn
  });

  if (!aboutBtn || !aboutModal || !closeAboutBtn) return;

  const openAbout = () => {
    aboutModal.classList.add("open");
    aboutModal.setAttribute("aria-hidden", "false");
  };

  const closeAbout = () => {
    aboutModal.classList.remove("open");
    aboutModal.setAttribute("aria-hidden", "true");
  };

  aboutBtn.addEventListener("click", openAbout);
  closeAboutBtn.addEventListener("click", closeAbout);

  // cerrar clicando fuera del cuadro
  aboutModal.addEventListener("click", (e) => {
    if (e.target === aboutModal) closeAbout();
  });

  // cerrar con ESC
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && aboutModal.classList.contains("open")) closeAbout();
  });
});
