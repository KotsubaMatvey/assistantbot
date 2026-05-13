export type TelegramPayload =
  | { type: "command"; command: BotCommand }
  | { type: "basket_compare"; text: string }
  | { type: "assistant_message"; text: string };

export type BotCommand =
  | "markets"
  | "status"
  | "agenda"
  | "lifestyle_context"
  | "compact"
  | "new"
  | "morning"
  | "price_alerts"
  | "check_alerts"
  | "pantry"
  | "pantry_plan"
  | "pantry_deals"
  | "budget"
  | "budget_plan"
  | "assistants"
  | "today"
  | "tasks"
  | "recent"
  | "sources"
  | "skills"
  | "assistant_capabilities";

export type TelegramWebApp = {
  themeParams?: {
    bg_color?: string;
    text_color?: string;
    button_color?: string;
  };
  ready: () => void;
  expand: () => void;
  sendData: (data: string) => void;
};

declare global {
  interface Window {
    Telegram?: {
      WebApp?: TelegramWebApp;
    };
  }
}
