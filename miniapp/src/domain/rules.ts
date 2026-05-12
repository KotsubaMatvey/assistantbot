import type { AssistantState } from "./assistant";
import type { AppEvents, EventBus, TabId } from "./events";
import type { BotCommand, TelegramPayload } from "../types/telegram";

type RuleContext = {
  setAssistantState: (state: AssistantState) => void;
  sendTelegramPayload: (payload: TelegramPayload) => void;
  showToast: (message: string) => void;
};

const tabState: Record<TabId, AssistantState> = {
  shopping: "shopping",
  markets: "alert",
  assistant: "idle",
  memory: "thinking",
};

const commandState: Record<BotCommand, AssistantState> = {
  markets: "alert",
  status: "working",
  agenda: "thinking",
  lifestyle_context: "thinking",
  compact: "working",
  new: "idle",
  morning: "working",
  price_alerts: "alert",
  check_alerts: "alert",
  pantry: "shopping",
  pantry_plan: "thinking",
  pantry_deals: "shopping",
  budget: "working",
  budget_plan: "working",
  assistants: "happy",
};

export function attachRules(bus: EventBus<AppEvents>, context: RuleContext): () => void {
  const disposers = [
    bus.on("tab:selected", ({ tab }) => {
      context.setAssistantState(tabState[tab]);
    }),
    bus.on("assistant:set-state", ({ state }) => {
      context.setAssistantState(state);
    }),
    bus.on("command:send", ({ command }) => {
      context.setAssistantState(commandState[command]);
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
      context.sendTelegramPayload({ type: "assistant_message", text: cleanText });
    }),
    bus.on("toast:show", ({ message }) => {
      context.showToast(message);
    }),
  ];
  return () => disposers.forEach((dispose) => dispose());
}
