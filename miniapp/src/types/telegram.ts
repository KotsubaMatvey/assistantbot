export type TelegramPayload =
  | { type: "command"; command: BotCommand }
  | { type: "basket_compare"; text: string }
  | { type: "assistant_message"; text: string }
  | { type: "task_create"; text: string }
  | { type: "note_create"; text: string }
  | { type: "reminder_create"; text: string }
  | { type: "person_note"; name: string; note: string }
  | {
      type: "finance_transaction";
      kind: "expense" | "income";
      amount: string;
      category: string;
      note?: string;
    }
  | { type: "finance_account"; name: string; balance: string }
  | { type: "finance_subscription"; name: string; amount: string }
  | { type: "receipt_save"; text: string }
  | { type: "source_add"; source_type: "rss" | "github" | "url"; target: string }
  | { type: "source_delete"; id: string }
  | { type: "source_sync"; id?: string };

export type BotCommand =
  | "markets"
  | "market_brief"
  | "status"
  | "capability_center"
  | "agenda"
  | "lifestyle_context"
  | "compact"
  | "new"
  | "morning"
  | "evening"
  | "week"
  | "price_alerts"
  | "check_alerts"
  | "pantry"
  | "pantry_plan"
  | "pantry_deals"
  | "budget"
  | "budget_plan"
  | "expense"
  | "income"
  | "accounts"
  | "subscriptions"
  | "cashflow"
  | "assistants"
  | "today"
  | "tasks"
  | "people"
  | "objects"
  | "recent"
  | "sources"
  | "source_list"
  | "source_sync"
  | "memory_tree"
  | "memory_profile"
  | "weekly_summary"
  | "tools"
  | "skills"
  | "assistant_capabilities";

export type TelegramWebApp = {
  initData?: string;
  initDataUnsafe?: {
    user?: {
      id?: number;
      first_name?: string;
      username?: string;
    };
  };
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
