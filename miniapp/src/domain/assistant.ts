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
    kicker: "Idle",
    title: "Готов к контексту",
    copy: "Сохраняю мысли, задачи, решения и ссылки в second brain.",
  },
  thinking: {
    kicker: "Thinking",
    title: "Собираю контекст",
    copy: "Проверяю память, agenda, задачи и связанные решения.",
  },
  happy: {
    kicker: "Success",
    title: "Готово",
    copy: "Контекст обновлён, важное вынесено наверх.",
  },
  alert: {
    kicker: "Alert",
    title: "Есть сигнал",
    copy: "Проверяю внешние сигналы, рынки и резкие изменения.",
  },
  shopping: {
    kicker: "Shopping mode",
    title: "Сравниваю корзину",
    copy: "Проверяю свежесть цен, pantry и alerts перед покупкой.",
  },
  sad: {
    kicker: "Low battery",
    title: "Нужна разгрузка",
    copy: "Контекста стало много — пора сжать сессию или выделить next action.",
  },
  working: {
    kicker: "Working",
    title: "Считаю",
    copy: "Отправляю безопасный payload в бот и жду ответ в Telegram.",
  },
};
