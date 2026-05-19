import { Home, RefreshCw } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { PixelAssistant } from "./components/PixelAssistant";
import { Tabs } from "./components/Tabs";
import { AssistantPanel } from "./components/panels/AssistantPanel";
import { FinancePanel } from "./components/panels/FinancePanel";
import { MarketsPanel } from "./components/panels/MarketsPanel";
import { MemoryPanel } from "./components/panels/MemoryPanel";
import { ShoppingPanel } from "./components/panels/ShoppingPanel";
import { TodayPanel } from "./components/panels/TodayPanel";
import {
  loadMiniAppState,
  miniAppMutationToTelegramPayload,
  postMiniAppAssistant,
  postMiniAppMutation,
  recordMiniAppEvent,
  sendTelegramPayload as sendTelegramWebAppPayload,
  shouldFallbackToTelegram,
  type MiniAppState,
} from "./domain/api";
import type { AssistantState } from "./domain/assistant";
import { eventBus, type TabId } from "./domain/events";
import { attachRules } from "./domain/rules";
import type { HomeScreenStatus, TelegramPayload, TelegramWebApp } from "./types/telegram";

export function App() {
  const [activeTab, setActiveTab] = useState<TabId>("today");
  const [assistantState, setAssistantState] = useState<AssistantState>("idle");
  const [toast, setToast] = useState("");
  const [miniState, setMiniState] = useState<MiniAppState | null>(null);
  const [stateLoading, setStateLoading] = useState(true);
  const [stateError, setStateError] = useState("");
  const [homeStatus, setHomeStatus] = useState<HomeScreenStatus | "">("");
  const screenRef = useRef<HTMLElement | null>(null);
  const telegram = useMemo<TelegramWebApp | undefined>(() => window.Telegram?.WebApp, []);

  const refreshState = useCallback(async () => {
    setStateLoading(true);
    setStateError("");
    try {
      setMiniState(await loadMiniAppState());
      void recordMiniAppEvent("state_refresh", { result: "ok" });
    } catch (error) {
      setStateError(formatMiniAppError(error));
      void recordMiniAppEvent("state_refresh", { result: "error" });
    } finally {
      setStateLoading(false);
    }
  }, []);

  const mutateState = useCallback(async (path: string, body: Record<string, unknown>) => {
    setAssistantState("working");
    setStateError("");
    void recordMiniAppEvent("mutation_submit", { path });
    try {
      setMiniState(await postMiniAppMutation(path, body));
      setToast("Сохранено");
      setAssistantState("happy");
      void recordMiniAppEvent("mutation_success", { path });
    } catch (error) {
      const fallbackPayload = miniAppMutationToTelegramPayload(path, body);
      if (fallbackPayload && shouldFallbackToTelegram(error) && sendTelegramWebAppPayload(fallbackPayload)) {
        setAssistantState("happy");
        setToast("Отправлено в бот");
        void recordMiniAppEvent("mutation_telegram_fallback", { path, type: fallbackPayload.type });
        return;
      }
      setAssistantState("sad");
      setStateError(formatMiniAppError(error));
      void recordMiniAppEvent("mutation_error", { path });
    }
  }, []);

  const askAssistant = useCallback(async (text: string): Promise<string> => {
    const cleanText = text.trim();
    if (!cleanText) {
      return "Напиши запрос ассистенту.";
    }
    setAssistantState("thinking");
    setStateError("");
    void recordMiniAppEvent("assistant_query_submit", { chars: cleanText.length });
    try {
      const result = await postMiniAppAssistant(cleanText);
      setAssistantState("happy");
      void recordMiniAppEvent("assistant_query_success", {
        chars: cleanText.length,
        answer_chars: result.answer.length,
      });
      return result.answer;
    } catch (error) {
      if (shouldFallbackToTelegram(error) && sendTelegramWebAppPayload({ type: "assistant_message", text: cleanText })) {
        setAssistantState("happy");
        setToast("Отправлено в бот");
        void recordMiniAppEvent("assistant_query_telegram_fallback", { chars: cleanText.length });
        return "Отправил запрос в бота. Ответ появится в Telegram.";
      }
      setAssistantState("sad");
      setStateError(formatMiniAppError(error));
      void recordMiniAppEvent("assistant_query_error", { chars: cleanText.length });
      return formatMiniAppError(error);
    }
  }, []);

  const addHomeShortcut = useCallback(() => {
    if (!telegram?.addToHomeScreen) {
      setToast("Ярлык недоступен");
      void recordMiniAppEvent("home_screen_unsupported", {});
      return;
    }
    if (homeStatus === "added") {
      setToast("Уже добавлено");
      return;
    }
    telegram.addToHomeScreen();
    setToast("Проверь запрос Telegram");
    void recordMiniAppEvent("home_screen_prompt", {
      status: homeStatus || "unknown",
    });
  }, [homeStatus, telegram]);

  useEffect(() => {
    if (!telegram) {
      return;
    }
    const syncViewport = () => {
      const height = telegram.stableViewportHeight || telegram.viewportHeight || window.innerHeight;
      document.documentElement.style.setProperty("--app-height", `${height}px`);
    };
    const handleHomeScreenAdded = () => {
      setHomeStatus("added");
      setToast("Добавлено на главный экран");
      void recordMiniAppEvent("home_screen_added", {});
    };
    const handleHomeScreenChecked = (event?: unknown) => {
      const status =
        typeof event === "string"
          ? event
          : typeof event === "object" && event && "status" in event
            ? String(event.status)
            : "";
      if (isHomeScreenStatus(status)) {
        setHomeStatus(status);
      }
    };
    const bg = telegram.themeParams?.bg_color || "#121212";
    document.documentElement.style.setProperty("--tg-bg", bg);
    telegram.setHeaderColor?.(bg);
    telegram.setBackgroundColor?.(bg);
    telegram.disableVerticalSwipes?.();
    telegram.enableClosingConfirmation?.();
    telegram.expand();
    try {
      telegram.requestFullscreen?.();
    } catch {
      telegram.expand();
    }
    syncViewport();
    telegram.onEvent?.("viewportChanged", syncViewport);
    telegram.onEvent?.("homeScreenAdded", handleHomeScreenAdded);
    telegram.onEvent?.("homeScreenChecked", handleHomeScreenChecked);
    telegram.checkHomeScreenStatus?.(setHomeStatus);
    telegram.ready();
    void recordMiniAppEvent("app_open", {
      user_id: telegram.initDataUnsafe?.user?.id ?? "",
      fullscreen: Boolean(telegram.isFullscreen),
      expanded: Boolean(telegram.isExpanded),
    });
    return () => {
      telegram.offEvent?.("viewportChanged", syncViewport);
      telegram.offEvent?.("homeScreenAdded", handleHomeScreenAdded);
      telegram.offEvent?.("homeScreenChecked", handleHomeScreenChecked);
    };
  }, [telegram]);

  useEffect(() => {
    return attachRules(eventBus, {
      setAssistantState,
      showToast: setToast,
      sendTelegramPayload: (payload: TelegramPayload) => {
        const serialized = JSON.stringify(payload);
        if (sendTelegramWebAppPayload(payload)) {
          setToast("Отправлено в бот");
          return;
        }
        setToast(`Предпросмотр: ${serialized}`);
      },
      recordEvent: (name, data) => {
        void recordMiniAppEvent(name, data);
      },
    });
  }, [telegram]);

  useEffect(() => {
    if (!toast) {
      return;
    }
    const timer = window.setTimeout(() => setToast(""), 2200);
    return () => window.clearTimeout(timer);
  }, [toast]);

  useEffect(() => {
    void refreshState();
  }, [refreshState]);

  useEffect(() => {
    screenRef.current?.scrollTo({ top: 0, behavior: "smooth" });
  }, [activeTab]);

  return (
    <main ref={screenRef} className="app-screen grid gap-4">
      <header className="app-topbar">
        <div>
          <p className="app-kicker">Бот-ассистент</p>
          <h1 className="app-title">Ассистент</h1>
        </div>
        <div className="app-actions">
          <button
            className="icon-button"
            type="button"
            aria-label="Добавить на главный экран"
            title={homeShortcutTitle(homeStatus)}
            disabled={!telegram?.addToHomeScreen || homeStatus === "unsupported" || homeStatus === "added"}
            onClick={addHomeShortcut}
          >
            <Home size={18} />
          </button>
          <button
            className="icon-button"
            type="button"
            aria-label="Обновить статус"
            onClick={() => void refreshState()}
          >
            <RefreshCw size={18} />
          </button>
        </div>
      </header>

      <PixelAssistant state={assistantState} />

      <section className="assistant-live glass-panel glass-panel-tight p-3">
        <AssistantPanel onAsk={askAssistant} compact />
      </section>

      {activeTab === "today" && (
        <TodayPanel
          state={miniState?.today}
          loading={stateLoading}
          error={stateError}
          onMutate={mutateState}
          onRefresh={refreshState}
        />
      )}
      {activeTab === "finance" && (
        <FinancePanel
          state={miniState?.finance}
          loading={stateLoading}
          error={stateError}
          onMutate={mutateState}
        />
      )}
      {activeTab === "memory" && (
        <MemoryPanel
          state={miniState?.memory}
          loading={stateLoading}
          error={stateError}
          onMutate={mutateState}
          onRefresh={refreshState}
        />
      )}
      {activeTab === "shopping" && <ShoppingPanel />}
      {activeTab === "markets" && <MarketsPanel />}

      <Tabs activeTab={activeTab} onSelect={setActiveTab} />

      <div
        className={
          toast
            ? "fixed right-4 top-4 z-50 max-w-[calc(100vw-32px)] translate-y-0 rounded-2xl bg-[var(--accent)] px-4 py-3 text-sm font-black text-zinc-950 opacity-100 shadow-2xl transition"
            : "pointer-events-none fixed right-4 top-4 z-50 max-w-[calc(100vw-32px)] translate-y-3 rounded-2xl bg-[var(--accent)] px-4 py-3 text-sm font-black text-zinc-950 opacity-0 shadow-2xl transition"
        }
        role="status"
        aria-live="polite"
      >
        {toast}
      </div>
    </main>
  );
}

function isHomeScreenStatus(value: string): value is HomeScreenStatus {
  return value === "unsupported" || value === "unknown" || value === "added" || value === "missed";
}

function homeShortcutTitle(status: HomeScreenStatus | ""): string {
  if (status === "added") {
    return "Уже на главном экране";
  }
  if (status === "unsupported") {
    return "Недоступно на этом устройстве";
  }
  return "Добавить на главный экран";
}

function formatMiniAppError(error: unknown): string {
  if (shouldFallbackToTelegram(error)) {
    return "Основной API недоступен. Действия через Telegram внутри мини-приложения все еще работают.";
  }
  return error instanceof Error ? error.message : "Ошибка API мини-приложения";
}
