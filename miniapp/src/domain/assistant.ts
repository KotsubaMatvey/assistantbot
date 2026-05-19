export type AssistantState =
  | "idle"
  | "thinking"
  | "happy"
  | "alert"
  | "shopping"
  | "sad"
  | "working";

export type AssistantStateMeta = {
  kicker: string;
  title: string;
  copy: string;
};

export const assistantStates: Record<AssistantState, AssistantStateMeta> = {
  idle: {
    kicker: "Система готова",
    title: "Память онлайн",
    copy: "Собирает заметки, задачи, людей, источники и решения в локальную вторую память.",
  },
  thinking: {
    kicker: "Контекст",
    title: "Сканирую память",
    copy: "Проверяю повестку, открытые задачи, источники и последние решения перед следующим действием.",
  },
  happy: {
    kicker: "Синхронизировано",
    title: "Сохранено",
    copy: "Обновление попало в память, а важный контекст остался под рукой.",
  },
  alert: {
    kicker: "Сигнал",
    title: "Нужно внимание",
    copy: "Напоминание, движение рынка или обновление источника готовы к просмотру.",
  },
  shopping: {
    kicker: "Покупки",
    title: "Проверка корзины",
    copy: "Сверяю запасы, ценовые сигналы и корзину перед походом в магазин.",
  },
  sad: {
    kicker: "Перегрузка",
    title: "Сжать сессию",
    copy: "В диалоге стало слишком много шума. Сожми сессию или раздели следующее действие.",
  },
  working: {
    kicker: "В работе",
    title: "Отправляю действие",
    copy: "Передаю действие в локальный API или безопасно переключаюсь на Telegram.",
  },
};
