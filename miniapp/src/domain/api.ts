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

const apiBase = (import.meta.env.VITE_MINI_APP_API_BASE_URL as string | undefined) ?? "";
const devUserId = (import.meta.env.VITE_MINI_APP_DEV_USER_ID as string | undefined) ?? "";

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
    throw new Error(text || `HTTP ${response.status}`);
  }
  return response.json() as Promise<T>;
}
