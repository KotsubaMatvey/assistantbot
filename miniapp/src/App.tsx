import { RefreshCw } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Tabs } from "./components/Tabs";
import { ChatPanel } from "./components/panels/ChatPanel";
import { FinancePanel } from "./components/panels/FinancePanel";
import { MemoryPanel } from "./components/panels/MemoryPanel";
import { MorePanel } from "./components/panels/MorePanel";
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
import { eventBus, type TabId } from "./domain/events";
import { attachRules } from "./domain/rules";
import type { HomeScreenStatus, TelegramPayload, TelegramWebApp } from "./types/telegram";

export function App() {
  const [activeTab, setActiveTab] = useState<TabId>("today");
  const [toast, setToast] = useState("");
  const [miniState, setMiniState] = useState<MiniAppState | null>(null);
  const [stateLoading, setStateLoading] = useState(true);
  const [stateError, setStateError] = useState("");
  const [homeStatus, setHomeStatus] = useState<HomeScreenStatus | "">("");
  const screenRef = useRef<HTMLElement | null>(null);
  const telegram = useMemo<TelegramWebApp | undefined>(() => window.Telegram?.WebApp, []);
  const firstName = telegram?.initDataUnsafe?.user?.first_name ?? "";

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
    setStateError("");
    void recordMiniAppEvent("mutation_submit", { path });
    try {
      setMiniState(await postMiniAppMutation(path, body));
      setToast("Сохранено");
      void recordMiniAppEvent("mutation_success", { path });
    } catch (error) {
      const fallbackPayload = miniAppMutationToTelegramPayload(path, body);
      if (
        fallbackPayload &&
        shouldFallbackToTelegram(error) &&
        sendTelegramWebAppPayload(fallbackPayload)
      ) {
        setToast("Отправлено в бот");
        void recordMiniAppEvent("mutation_telegram_fallback", { path, type: fallbackPayload.type });
        return;
      }
      setStateError(formatMiniAppError(error));
      void recordMiniAppEvent("mutation_error", { path });
    }
  }, []);

  const askAssistant = useCallback(async (text: string): Promise<string> => {
    const cleanText = text.trim();
    if (!cleanText) {
      return "Напиши запрос ассистенту.";
    }
    void recordMiniAppEvent("assistant_query_submit", { chars: cleanText.length });
    try {
      const result = await postMiniAppAssistant(cleanText);
      void recordMiniAppEvent("assistant_query_success", {
        chars: cleanText.length,
        answer_chars: result.answer.length,
      });
      return result.answer;
    } catch (error) {
      if (
        shouldFallbackToTelegram(error) &&
        sendTelegramWebAppPayload({ type: "assistant_message", text: cleanText })
      ) {
        void recordMiniAppEvent("assistant_query_telegram_fallback", { chars: cleanText.length });
        return "Отправил запрос в бот. Ответ появится в Telegram.";
      }
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
    void recordMiniAppEvent("home_screen_prompt", { status: homeStatus || "unknown" });
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
    const safeCall = (call: () => void) => {
      try {
        call();
      } catch {
        // Old Telegram clients throw on unsupported WebApp methods.
      }
    };
    const bg = "#0d0f13";
    document.documentElement.style.setProperty("--tg-bg", bg);
    safeCall(() => telegram.setHeaderColor?.(bg));
    safeCall(() => telegram.setBackgroundColor?.(bg));
    safeCall(() => telegram.disableVerticalSwipes?.());
    safeCall(() => telegram.enableClosingConfirmation?.());
    safeCall(() => telegram.expand());
    safeCall(() => telegram.requestFullscreen?.());
    syncViewport();
    telegram.onEvent?.("viewportChanged", syncViewport);
    telegram.onEvent?.("homeScreenAdded", handleHomeScreenAdded);
    telegram.onEvent?.("homeScreenChecked", handleHomeScreenChecked);
    safeCall(() => telegram.checkHomeScreenStatus?.(setHomeStatus));
    safeCall(() => telegram.ready());
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
      showToast: setToast,
      sendTelegramPayload: (payload: TelegramPayload) => {
        if (sendTelegramWebAppPayload(payload)) {
          setToast("Отправлено в бот");
          return;
        }
        setToast(`Предпросмотр: ${JSON.stringify(payload)}`);
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
    screenRef.current?.scrollTo({ top: 0 });
  }, [activeTab]);

  return (
    <main ref={screenRef} className="screen grid gap-3.5">
      <header className="topbar">
        <div className="min-w-0">
          <h1 className="topbar-title">{greeting(firstName)}</h1>
          <p className="topbar-sub">{formatToday()}</p>
        </div>
        <div className="flex items-center gap-2">
          <button
            className="icon-btn"
            type="button"
            aria-label="Обновить данные"
            onClick={() => void refreshState()}
          >
            <RefreshCw size={17} className={stateLoading ? "animate-spin" : undefined} />
          </button>
        </div>
      </header>

      {activeTab === "today" && (
        <TodayPanel
          state={miniState?.today}
          loading={stateLoading}
          error={stateError}
          onMutate={mutateState}
          onRefresh={refreshState}
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
      {activeTab === "finance" && (
        <FinancePanel
          state={miniState?.finance}
          loading={stateLoading}
          error={stateError}
          onMutate={mutateState}
        />
      )}
      {activeTab === "chat" && <ChatPanel onAsk={askAssistant} />}
      {activeTab === "more" && (
        <MorePanel homeStatus={homeStatus} onAddHomeShortcut={addHomeShortcut} />
      )}

      <Tabs activeTab={activeTab} onSelect={setActiveTab} />

      <div className={toast ? "toast toast-visible" : "toast"} role="status" aria-live="polite">
        {toast}
      </div>
    </main>
  );
}

function isHomeScreenStatus(value: string): value is HomeScreenStatus {
  return value === "unsupported" || value === "unknown" || value === "added" || value === "missed";
}

function greeting(firstName: string): string {
  const hour = new Date().getHours();
  const base =
    hour >= 5 && hour < 12
      ? "Доброе утро"
      : hour >= 12 && hour < 18
        ? "Добрый день"
        : hour >= 18 && hour < 23
          ? "Добрый вечер"
          : "Доброй ночи";
  return firstName ? `${base}, ${firstName}` : base;
}

function formatToday(): string {
  return new Date().toLocaleDateString("ru-RU", {
    weekday: "long",
    day: "numeric",
    month: "long",
  });
}

function formatMiniAppError(error: unknown): string {
  if (shouldFallbackToTelegram(error)) {
    return "Основной API недоступен. Действия через Telegram внутри мини-приложения все еще работают.";
  }
  return error instanceof Error ? error.message : "Ошибка API мини-приложения";
}
