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

// UI buttons (placeholder)
document.getElementById("logoutBtn").addEventListener("click", () => {
  alert("Amaitu Sesioa (pendiente de implementar)");
});

document.getElementById("newQueryBtn").addEventListener("click", () => {
  chat.innerHTML = `
    <div class="empty">
      <div class="watermark">UPV/EHU</div>
      <div class="empty-text">Bilatu Unibasq dagoen informazioa hemendik</div>
    </div>
  `;
  input.focus();
});

// Tabs 
document.querySelectorAll(".tab").forEach(btn => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach(b => b.classList.remove("active"));
    btn.classList.add("active");
  });
});
