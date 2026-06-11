import type { AppEvents, EventBus } from "./events";
import type { TelegramPayload } from "../types/telegram";

type RuleContext = {
  sendTelegramPayload: (payload: TelegramPayload) => void;
  showToast: (message: string) => void;
  recordEvent?: (name: string, data?: Record<string, unknown>) => void;
};

export function attachRules(bus: EventBus<AppEvents>, context: RuleContext): () => void {
  const disposers = [
    bus.on("tab:selected", ({ tab }) => {
      context.recordEvent?.("tab_selected", { tab });
    }),
    bus.on("command:send", ({ command }) => {
      context.recordEvent?.("command_send", { command });
      context.sendTelegramPayload({ type: "command", command });
    }),
    bus.on("basket:compare", ({ text }) => {
      const cleanText = text.trim();
      if (!cleanText) {
        context.showToast("Добавь товары в корзину");
        return;
      }
      context.recordEvent?.("basket_compare", { chars: cleanText.length });
      context.sendTelegramPayload({ type: "basket_compare", text: cleanText });
    }),
    bus.on("toast:show", ({ message }) => {
      context.showToast(message);
    }),
  ];
  return () => disposers.forEach((dispose) => dispose());
}
