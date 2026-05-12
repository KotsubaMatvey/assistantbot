const tg = window.Telegram?.WebApp;
const toast = document.querySelector(".toast");
const avatar = document.querySelector("[data-pixel-avatar]");
const stateKicker = document.querySelector("[data-state-kicker]");
const stateTitle = document.querySelector("[data-state-title]");
const stateCopy = document.querySelector("[data-state-copy]");

const assistantStates = {
  idle: {
    kicker: "Idle",
    title: "Жду команду",
    copy: "Готов открыть покупки, pantry, бюджет, память или рынки.",
  },
  thinking: {
    kicker: "Thinking",
    title: "Собираю контекст",
    copy: "Проверяю память, pantry и связанные задачи.",
  },
  happy: {
    kicker: "Success",
    title: "Готово",
    copy: "Маршрут найден, экономия посчитана, важное вынесено наверх.",
  },
  alert: {
    kicker: "Alert",
    title: "Есть сигнал",
    copy: "Проверяю price alerts, рынки и резкие изменения.",
  },
  shopping: {
    kicker: "Shopping mode",
    title: "Сравниваю корзину",
    copy: "Проверяю свежесть цен, pantry и alerts перед покупкой.",
  },
  sad: {
    kicker: "Low battery",
    title: "Нужна разгрузка",
    copy: "Цены выросли, бюджет давит или памяти стало слишком много.",
  },
  working: {
    kicker: "Working",
    title: "Считаю",
    copy: "Обновляю данные и отправляю безопасный payload в бот.",
  },
};

const commandStates = {
  markets: "alert",
  price_alerts: "alert",
  check_alerts: "alert",
  pantry: "shopping",
  pantry_plan: "thinking",
  pantry_deals: "shopping",
  budget: "working",
  budget_plan: "working",
  status: "working",
  compact: "working",
  new: "idle",
  agenda: "thinking",
  lifestyle_context: "thinking",
  morning: "working",
  assistants: "happy",
};

if (tg) {
  tg.ready();
  tg.expand();
  document.documentElement.style.setProperty("--bg", tg.themeParams.bg_color || "#101014");
}

document.querySelectorAll(".tab").forEach((button) => {
  button.addEventListener("click", () => {
    const tab = button.dataset.tab;
    document.querySelectorAll(".tab").forEach((item) => item.classList.remove("is-active"));
    document.querySelectorAll(".panel").forEach((item) => item.classList.remove("is-active"));
    button.classList.add("is-active");
    document.getElementById(tab)?.classList.add("is-active");
    setAssistantState(button.dataset.state || "idle");
  });
});

document.querySelectorAll("[data-assistant-state]").forEach((button) => {
  button.addEventListener("click", () => {
    setAssistantState(button.dataset.assistantState || "idle");
  });
});

document.querySelectorAll("[data-action='send']").forEach((button) => {
  button.addEventListener("click", () => {
    const command = button.dataset.payload;
    setAssistantState(button.dataset.state || commandStates[command] || "working");
    sendPayload({ type: "command", command });
  });
});

document.querySelector("[data-action='basket']")?.addEventListener("click", () => {
  const text = document.getElementById("basket")?.value || "";
  setAssistantState("working");
  sendPayload({ type: "basket_compare", text });
});

document.querySelector("[data-action='assistant']")?.addEventListener("click", () => {
  const text = document.getElementById("pixelPrompt")?.value || "";
  setAssistantState("thinking");
  sendPayload({ type: "assistant_message", text });
});

setAssistantState("shopping");

function setAssistantState(state) {
  const next = assistantStates[state] ? state : "idle";
  if (avatar) {
    avatar.className = `pixel-avatar is-${next}`;
  }
  if (stateKicker) {
    stateKicker.textContent = assistantStates[next].kicker;
  }
  if (stateTitle) {
    stateTitle.textContent = assistantStates[next].title;
  }
  if (stateCopy) {
    stateCopy.textContent = assistantStates[next].copy;
  }
}

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
