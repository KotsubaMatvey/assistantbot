const tg = window.Telegram?.WebApp;
const toast = document.querySelector(".toast");

if (tg) {
  tg.ready();
  tg.expand();
  document.documentElement.style.setProperty("--bg", tg.themeParams.bg_color || "#f6f4ef");
}

document.querySelectorAll(".tab").forEach((button) => {
  button.addEventListener("click", () => {
    const tab = button.dataset.tab;
    document.querySelectorAll(".tab").forEach((item) => item.classList.remove("is-active"));
    document.querySelectorAll(".panel").forEach((item) => item.classList.remove("is-active"));
    button.classList.add("is-active");
    document.getElementById(tab)?.classList.add("is-active");
  });
});

document.querySelectorAll("[data-action='send']").forEach((button) => {
  button.addEventListener("click", () => {
    sendPayload({ type: "command", command: button.dataset.payload });
  });
});

document.querySelector("[data-action='basket']")?.addEventListener("click", () => {
  const text = document.getElementById("basket")?.value || "";
  sendPayload({ type: "basket_compare", text });
});

function sendPayload(payload) {
  const serialized = JSON.stringify(payload);
  if (tg) {
    tg.sendData(serialized);
    showToast("Отправлено в бот");
    return;
  }
  showToast(`Preview payload: ${serialized}`);
}

function showToast(text) {
  toast.textContent = text;
  toast.classList.add("is-visible");
  window.setTimeout(() => toast.classList.remove("is-visible"), 2200);
}
