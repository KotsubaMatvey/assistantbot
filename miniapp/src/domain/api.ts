import type { TelegramPayload } from "../types/telegram";

export type MiniAppState = {
  user: { id: number };
  today: {
    agenda: string;
    digest: string;
    tasks: { id: string; snippet: string; tags: string[] }[];
    reminders: { id: string; snippet: string; due_at: string }[];
    notes: { id: string; snippet: string; type: string; tags: string[] }[];
    focus: { type: string; title: string; detail: string }[];
  };
  finance: {
    month: string;
    balance: string;
    income: string;
    expenses: string;
    subscriptions_total: string;
    forecast: string;
    budget: {
      limit: string;
      spent: string;
      remaining: string;
      projected: string;
      receipts_count: number;
      categories: { name: string; amount: string }[];
    };
    accounts: { id: string; name: string; balance: string; currency: string }[];
    transactions: {
      id: string;
      kind: string;
      amount: string;
      category: string;
      note: string;
      created_at: string;
    }[];
    subscriptions: { id: string; name: string; amount: string; cycle: string }[];
    receipts: {
      id: string;
      store: string;
      total: string;
      purchased_at: string;
      items_count: number;
    }[];
  };
  memory: {
    health: {
      raw_captures: number;
      daily_summaries: number;
      project_summaries: number;
      profile_exists: boolean;
      weekly_exists: boolean;
      latest_raw: string;
      latest_summary: string;
    };
    objects: {
      total: number;
      by_type: { type: string; count: number }[];
      recent: { id: string; type: string; title: string; tags: string[] }[];
    };
    sources: {
      id: string;
      type: string;
      url: string;
      enabled: boolean;
      last_sync_at: string;
      last_error: string;
    }[];
    events: {
      id: string;
      action: string;
      detail: string;
      created_at: string;
    }[];
  };
  generated_at: string;
};

export type MiniAppMarkets = {
  fetched_at: string;
  sentiment_label: string;
  sentiment_score: string;
  risk_regime: string;
  quotes: {
    key: string;
    name: string;
    value: string;
    unit: string;
    change_percent: string;
    error: string;
  }[];
  data_gaps: string[];
};

export type MiniAppAssistantAnswer = {
  answer: string;
};

const apiBase = (import.meta.env.VITE_MINI_APP_API_BASE_URL as string | undefined) ?? "";
const devUserId = (import.meta.env.VITE_MINI_APP_DEV_USER_ID as string | undefined) ?? "";

export class MiniAppApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "MiniAppApiError";
    this.status = status;
  }
}

export async function loadMiniAppState(): Promise<MiniAppState> {
  const suffix = devUserId ? `?user_id=${encodeURIComponent(devUserId)}` : "";
  return apiRequest<MiniAppState>(`/api/miniapp/state${suffix}`, { method: "GET" });
}

export async function postMiniAppMutation(
  path: string,
  body: Record<string, unknown>,
): Promise<MiniAppState> {
  return apiRequest<MiniAppState>(path, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function loadMiniAppMarkets(): Promise<MiniAppMarkets> {
  const suffix = devUserId ? `?user_id=${encodeURIComponent(devUserId)}` : "";
  return apiRequest<MiniAppMarkets>(`/api/miniapp/markets${suffix}`, { method: "GET" });
}

export async function postMiniAppAssistant(text: string): Promise<MiniAppAssistantAnswer> {
  return apiRequest<MiniAppAssistantAnswer>("/api/miniapp/assistant", {
    method: "POST",
    body: JSON.stringify({ text }),
  });
}

export async function recordMiniAppEvent(
  name: string,
  data: Record<string, unknown> = {},
): Promise<void> {
  try {
    await apiRequest<{ ok: boolean }>("/api/miniapp/event", {
      method: "POST",
      body: JSON.stringify({ name, data }),
    });
  } catch {
    // Telemetry must never block the user action.
  }
}

export function miniAppMutationToTelegramPayload(
  path: string,
  body: Record<string, unknown>,
): TelegramPayload | null {
  if (path === "/api/miniapp/task") {
    return { type: "task_create", text: String(body.text ?? "") };
  }
  if (path === "/api/miniapp/note") {
    return { type: "note_create", text: String(body.text ?? "") };
  }
  if (path === "/api/miniapp/reminder") {
    return { type: "reminder_create", text: String(body.text ?? "") };
  }
  if (path === "/api/miniapp/person") {
    return {
      type: "person_note",
      name: String(body.name ?? ""),
      note: String(body.note ?? ""),
    };
  }
  if (path === "/api/miniapp/receipt") {
    return { type: "receipt_save", text: String(body.text ?? "") };
  }
  if (path === "/api/miniapp/finance/transaction") {
    const kind = String(body.kind ?? "");
    if (kind !== "expense" && kind !== "income") {
      return null;
    }
    return {
      type: "finance_transaction",
      kind,
      amount: String(body.amount ?? ""),
      category: String(body.category ?? ""),
      note: String(body.note ?? ""),
    };
  }
  if (path === "/api/miniapp/finance/account") {
    return {
      type: "finance_account",
      name: String(body.name ?? ""),
      balance: String(body.balance ?? ""),
    };
  }
  if (path === "/api/miniapp/finance/subscription") {
    return {
      type: "finance_subscription",
      name: String(body.name ?? ""),
      amount: String(body.amount ?? ""),
    };
  }
  if (path === "/api/miniapp/source") {
    const sourceType = String(body.source_type ?? "");
    if (sourceType !== "rss" && sourceType !== "github" && sourceType !== "url") {
      return null;
    }
    return {
      type: "source_add",
      source_type: sourceType,
      target: String(body.target ?? ""),
    };
  }
  if (path === "/api/miniapp/source/delete") {
    return { type: "source_delete", id: String(body.id ?? "") };
  }
  if (path === "/api/miniapp/source/sync") {
    return { type: "source_sync", id: String(body.id ?? "") || undefined };
  }
  return null;
}

export function shouldFallbackToTelegram(error: unknown): boolean {
  if (error instanceof MiniAppApiError) {
    return error.status === 401 || error.status === 404 || error.status === 405;
  }
  return error instanceof TypeError;
}

export function sendTelegramPayload(payload: TelegramPayload): boolean {
  const telegram = window.Telegram?.WebApp;
  if (!telegram) {
    return false;
  }
  telegram.sendData(JSON.stringify(payload));
  return true;
}

async function apiRequest<T>(path: string, init: RequestInit): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set("Content-Type", "application/json");
  const initData = window.Telegram?.WebApp?.initData ?? "";
  if (initData) {
    headers.set("X-Telegram-Init-Data", initData);
  }
  if (!initData && devUserId) {
    headers.set("X-Mini-App-Dev-User-Id", devUserId);
  }
  const response = await fetch(`${apiBase}${path}`, { ...init, headers });
  if (!response.ok) {
    const text = await response.text();
    throw new MiniAppApiError(response.status, text || `HTTP ${response.status}`);
  }
  return response.json() as Promise<T>;
}
