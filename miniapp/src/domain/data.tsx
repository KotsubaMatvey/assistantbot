import type { ReactNode } from "react";
import {
  Activity,
  Bell,
  Bot,
  Brain,
  CalendarCheck,
  CheckCircle2,
  ClipboardList,
  Database,
  FileSearch,
  ListChecks,
  RefreshCw,
  ShoppingBasket,
  Sparkles,
  TrendingUp,
  Users,
  Wallet,
} from "lucide-react";
import type { TabId } from "./events";
import type { BotCommand } from "../types/telegram";

export type Metric = {
  label: string;
  value: string;
};

export type Action = {
  label: string;
  command: BotCommand;
  icon: ReactNode;
  primary?: boolean;
};

export const tabs: { id: TabId; label: string; icon: ReactNode }[] = [
  { id: "today", label: "Сегодня", icon: <CalendarCheck size={16} /> },
  { id: "assistant", label: "Ассистент", icon: <Bot size={16} /> },
  { id: "finance", label: "Бюджет", icon: <Wallet size={16} /> },
  { id: "memory", label: "Память", icon: <Brain size={16} /> },
  { id: "shopping", label: "Покупки", icon: <ShoppingBasket size={16} /> },
  { id: "markets", label: "Рынки", icon: <TrendingUp size={16} /> },
];

export const todayMetrics: Metric[] = [
  { label: "Лента", value: "/today" },
  { label: "Задачи", value: "/tasks" },
  { label: "Напоминания", value: "/agenda" },
  { label: "Фокус", value: "/morning" },
];

export const financeMetrics: Metric[] = [
  { label: "Баланс", value: "/accounts" },
  { label: "Расходы", value: "/expense" },
  { label: "Доходы", value: "/income" },
  { label: "Прогноз", value: "/cashflow" },
];

export const shoppingMetrics: Metric[] = [
  { label: "Корзина", value: "5 товаров" },
  { label: "Маршрут", value: "2 магазина" },
  { label: "Экономия", value: "312 RUB" },
  { label: "Свежесть", value: "18 мин" },
];

export const quickActions: Action[] = [
  { label: "Ценовые сигналы", command: "price_alerts", icon: <Bell size={16} /> },
  { label: "Запасы", command: "pantry", icon: <Database size={16} /> },
  { label: "Бюджет", command: "budget", icon: <Wallet size={16} /> },
  { label: "План/факт", command: "budget_plan", icon: <ClipboardList size={16} /> },
];

export const assistantActions: Action[] = [
  { label: "Главная", command: "capability_center", icon: <Brain size={16} />, primary: true },
  { label: "Статус", command: "status", icon: <RefreshCw size={16} /> },
  { label: "Сжать", command: "compact", icon: <CheckCircle2 size={16} /> },
  { label: "Новая сессия", command: "new", icon: <Bot size={16} /> },
  { label: "Повестка", command: "agenda", icon: <CalendarCheck size={16} /> },
  { label: "Сегодня", command: "today", icon: <Sparkles size={16} /> },
  { label: "Задачи", command: "tasks", icon: <ClipboardList size={16} /> },
  { label: "Недавнее", command: "recent", icon: <FileSearch size={16} /> },
  { label: "Источники", command: "sources", icon: <Database size={16} /> },
  { label: "Контекст", command: "lifestyle_context", icon: <Brain size={16} /> },
  { label: "Навыки", command: "skills", icon: <Sparkles size={16} /> },
  { label: "Утро", command: "morning", icon: <Activity size={16} /> },
  { label: "Ассистенты", command: "assistants", icon: <Bot size={16} /> },
];

export const todayActions: Action[] = [
  { label: "Повестка", command: "agenda", icon: <CalendarCheck size={16} />, primary: true },
  { label: "Сегодня", command: "today", icon: <Sparkles size={16} /> },
  { label: "Задачи", command: "tasks", icon: <ListChecks size={16} /> },
  { label: "Утро", command: "morning", icon: <Activity size={16} /> },
  { label: "Вечер", command: "evening", icon: <CheckCircle2 size={16} /> },
  { label: "Неделя", command: "week", icon: <ClipboardList size={16} /> },
  { label: "Люди", command: "people", icon: <Users size={16} /> },
  { label: "Объекты", command: "objects", icon: <Database size={16} /> },
];

export const financeActions: Action[] = [
  { label: "Денежный поток", command: "cashflow", icon: <TrendingUp size={16} />, primary: true },
  { label: "Счета", command: "accounts", icon: <Wallet size={16} /> },
  { label: "Бюджет", command: "budget", icon: <ClipboardList size={16} /> },
  { label: "Подписки", command: "subscriptions", icon: <RefreshCw size={16} /> },
  { label: "Чеки", command: "budget_plan", icon: <FileSearch size={16} /> },
  { label: "Фин. контекст", command: "objects", icon: <Database size={16} /> },
];
