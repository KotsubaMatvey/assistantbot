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
