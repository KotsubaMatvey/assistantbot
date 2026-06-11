import type { ReactNode } from "react";
import {
  Brain,
  CalendarCheck,
  Ellipsis,
  MessageCircle,
  Wallet,
} from "lucide-react";
import type { TabId } from "./events";
import type { BotCommand } from "../types/telegram";

export type Action = {
  label: string;
  command: BotCommand;
};

export const tabs: { id: TabId; label: string; icon: ReactNode }[] = [
  { id: "today", label: "Сегодня", icon: <CalendarCheck size={19} /> },
  { id: "memory", label: "Память", icon: <Brain size={19} /> },
  { id: "finance", label: "Бюджет", icon: <Wallet size={19} /> },
  { id: "chat", label: "Чат", icon: <MessageCircle size={19} /> },
  { id: "more", label: "Ещё", icon: <Ellipsis size={19} /> },
];

export const todayActions: Action[] = [
  { label: "Повестка", command: "agenda" },
  { label: "Утро", command: "morning" },
  { label: "Вечер", command: "evening" },
  { label: "Неделя", command: "week" },
];

export const financeActions: Action[] = [
  { label: "Денежный поток", command: "cashflow" },
  { label: "Бюджет", command: "budget" },
  { label: "План/факт", command: "budget_plan" },
];

export const memoryActions: Action[] = [
  { label: "Дерево памяти", command: "memory_tree" },
  { label: "Итоги недели", command: "weekly_summary" },
  { label: "Недавнее", command: "recent" },
  { label: "Люди", command: "people" },
];

export const serviceActions: Action[] = [
  { label: "Статус", command: "status" },
  { label: "Сжать сессию", command: "compact" },
  { label: "Новая сессия", command: "new" },
  { label: "Навыки", command: "skills" },
  { label: "Инструменты", command: "tools" },
  { label: "Возможности", command: "assistant_capabilities" },
];

export const shoppingActions: Action[] = [
  { label: "Запасы", command: "pantry" },
  { label: "Акции", command: "pantry_deals" },
  { label: "Ценовые сигналы", command: "price_alerts" },
];
