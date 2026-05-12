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
  RefreshCw,
  ShoppingBasket,
  TrendingUp,
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
  { id: "shopping", label: "Покупки", icon: <ShoppingBasket size={16} /> },
  { id: "markets", label: "Рынки", icon: <TrendingUp size={16} /> },
  { id: "assistant", label: "Ассистент", icon: <Bot size={16} /> },
  { id: "memory", label: "Память", icon: <Brain size={16} /> },
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
  { label: "Status", command: "status", icon: <RefreshCw size={16} /> },
  { label: "Compact", command: "compact", icon: <CheckCircle2 size={16} /> },
  { label: "New", command: "new", icon: <Bot size={16} /> },
  { label: "Agenda", command: "agenda", icon: <CalendarCheck size={16} /> },
  { label: "Context", command: "lifestyle_context", icon: <Brain size={16} /> },
  { label: "Morning", command: "morning", icon: <Activity size={16} /> },
  { label: "Assistants", command: "assistants", icon: <Bot size={16} />, primary: true },
];
