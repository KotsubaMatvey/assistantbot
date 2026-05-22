import type { AssistantState } from "./assistant";
import type { AppEvents, EventBus, TabId } from "./events";
import type { BotCommand, TelegramPayload } from "../types/telegram";

type RuleContext = {
  setAssistantState: (state: AssistantState) => void;
  sendTelegramPayload: (payload: TelegramPayload) => void;
  showToast: (message: string) => void;
  recordEvent?: (name: string, data?: Record<string, unknown>) => void;
};

const tabState: Record<TabId, AssistantState> = {
  today: "thinking",
  finance: "working",
  shopping: "shopping",
  markets: "alert",
  assistant: "idle",
  memory: "thinking",
};

const commandState: Record<BotCommand, AssistantState> = {
  markets: "alert",
  market_brief: "alert",
  status: "working",
  capability_center: "thinking",
  agenda: "thinking",
  lifestyle_context: "thinking",
  compact: "working",
  new: "idle",
  morning: "working",
  evening: "working",
  week: "working",
  price_alerts: "alert",
  check_alerts: "alert",
  pantry: "shopping",
  pantry_plan: "thinking",
  pantry_deals: "shopping",
  budget: "working",
  budget_plan: "working",
  expense: "working",
  income: "working",
  accounts: "working",
  subscriptions: "working",
  cashflow: "working",
  assistants: "happy",
  today: "thinking",
  tasks: "thinking",
  people: "thinking",
  objects: "thinking",
  recent: "thinking",
  sources: "thinking",
  source_list: "thinking",
  source_sync: "working",
  memory_tree: "thinking",
  memory_profile: "thinking",
  weekly_summary: "thinking",
  tools: "happy",
  skills: "happy",
  assistant_capabilities: "happy",
};

export function attachRules(bus: EventBus<AppEvents>, context: RuleContext): () => void {
  const disposers = [
    bus.on("tab:selected", ({ tab }) => {
      context.setAssistantState(tabState[tab]);
      context.recordEvent?.("tab_selected", { tab });
    }),
    bus.on("assistant:set-state", ({ state }) => {
      context.setAssistantState(state);
    }),
    bus.on("command:send", ({ command }) => {
      context.setAssistantState(commandState[command]);
      context.recordEvent?.("command_send", { command });
      context.sendTelegramPayload({ type: "command", command });
    }),
    bus.on("basket:compare", ({ text }) => {
      const cleanText = text.trim();
      if (!cleanText) {
        context.setAssistantState("sad");
        context.showToast("Добавь товары в корзину");
        return;
      }
      context.setAssistantState("working");
      context.recordEvent?.("basket_compare", { chars: cleanText.length });
      context.sendTelegramPayload({ type: "basket_compare", text: cleanText });
    }),
    bus.on("assistant:prompt", ({ text }) => {
      const cleanText = text.trim();
      if (!cleanText) {
        context.setAssistantState("thinking");
        context.showToast("Напиши команду помощнику");
        return;
      }
      context.setAssistantState("thinking");
      context.recordEvent?.("assistant_prompt", { chars: cleanText.length });
      context.sendTelegramPayload({ type: "assistant_message", text: cleanText });
    }),
    bus.on("toast:show", ({ message }) => {
      context.showToast(message);
    }),
  ];
  return () => disposers.forEach((dispose) => dispose());
}
