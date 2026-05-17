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
  { id: "finance", label: "Финансы", icon: <Wallet size={16} /> },
  { id: "memory", label: "Память", icon: <Brain size={16} /> },
  { id: "shopping", label: "Покупки", icon: <ShoppingBasket size={16} /> },
  { id: "markets", label: "Рынки", icon: <TrendingUp size={16} /> },
];

export const todayMetrics: Metric[] = [
  { label: "Timeline", value: "/today" },
  { label: "Tasks", value: "/tasks" },
  { label: "Reminders", value: "/agenda" },
  { label: "Focus", value: "/morning" },
];

export const financeMetrics: Metric[] = [
  { label: "Баланс", value: "/accounts" },
  { label: "Расходы", value: "/expense" },
  { label: "Доходы", value: "/income" },
  { label: "Прогноз", value: "/cashflow" },
];

export const shoppingMetrics: Metric[] = [
  { label: "Корзина", value: "5 товаров" },
  { label: "Лучший маршрут", value: "2 магазина" },
  { label: "Экономия", value: "312 ₽" },
  { label: "Свежесть", value: "18 мин" },
];

export const quickActions: Action[] = [
  { label: "Price alerts", command: "price_alerts", icon: <Bell size={16} /> },
  { label: "Pantry", command: "pantry", icon: <Database size={16} /> },
  { label: "Budget", command: "budget", icon: <Wallet size={16} /> },
  { label: "Plan vs fact", command: "budget_plan", icon: <ClipboardList size={16} /> },
];

export const assistantActions: Action[] = [
  { label: "Home", command: "capability_center", icon: <Brain size={16} />, primary: true },
  { label: "Status", command: "status", icon: <RefreshCw size={16} /> },
  { label: "Compact", command: "compact", icon: <CheckCircle2 size={16} /> },
  { label: "New", command: "new", icon: <Bot size={16} /> },
  { label: "Agenda", command: "agenda", icon: <CalendarCheck size={16} /> },
  { label: "Today", command: "today", icon: <Sparkles size={16} /> },
  { label: "Tasks", command: "tasks", icon: <ClipboardList size={16} /> },
  { label: "Recent", command: "recent", icon: <FileSearch size={16} /> },
  { label: "Sources", command: "sources", icon: <Database size={16} /> },
  { label: "Context", command: "lifestyle_context", icon: <Brain size={16} /> },
  { label: "Skills", command: "skills", icon: <Sparkles size={16} /> },
  { label: "Morning", command: "morning", icon: <Activity size={16} /> },
  { label: "Assistants", command: "assistants", icon: <Bot size={16} /> },
];

export const todayActions: Action[] = [
  { label: "Agenda", command: "agenda", icon: <CalendarCheck size={16} />, primary: true },
  { label: "Today", command: "today", icon: <Sparkles size={16} /> },
  { label: "Tasks", command: "tasks", icon: <ListChecks size={16} /> },
  { label: "Morning", command: "morning", icon: <Activity size={16} /> },
  { label: "Evening", command: "evening", icon: <CheckCircle2 size={16} /> },
  { label: "Week", command: "week", icon: <ClipboardList size={16} /> },
  { label: "People", command: "people", icon: <Users size={16} /> },
  { label: "Objects", command: "objects", icon: <Database size={16} /> },
];

export const financeActions: Action[] = [
  { label: "Cashflow", command: "cashflow", icon: <TrendingUp size={16} />, primary: true },
  { label: "Accounts", command: "accounts", icon: <Wallet size={16} /> },
  { label: "Budget", command: "budget", icon: <ClipboardList size={16} /> },
  { label: "Subscriptions", command: "subscriptions", icon: <RefreshCw size={16} /> },
  { label: "Receipts", command: "budget_plan", icon: <FileSearch size={16} /> },
  { label: "Finance context", command: "objects", icon: <Database size={16} /> },
];
