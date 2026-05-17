import { RefreshCw } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
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
  postMiniAppMutation,
  recordMiniAppEvent,
  sendTelegramPayload as sendTelegramWebAppPayload,
  shouldFallbackToTelegram,
  type MiniAppState,
} from "./domain/api";
import type { AssistantState } from "./domain/assistant";
import { eventBus, type TabId } from "./domain/events";
import { attachRules } from "./domain/rules";
import type { TelegramPayload, TelegramWebApp } from "./types/telegram";

export function App() {
  const [activeTab, setActiveTab] = useState<TabId>("today");
  const [assistantState, setAssistantState] = useState<AssistantState>("idle");
  const [toast, setToast] = useState("");
  const [miniState, setMiniState] = useState<MiniAppState | null>(null);
  const [stateLoading, setStateLoading] = useState(true);
  const [stateError, setStateError] = useState("");
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
      setToast("Saved");
      setAssistantState("happy");
      void recordMiniAppEvent("mutation_success", { path });
    } catch (error) {
      const fallbackPayload = miniAppMutationToTelegramPayload(path, body);
      if (fallbackPayload && shouldFallbackToTelegram(error) && sendTelegramWebAppPayload(fallbackPayload)) {
        setAssistantState("happy");
        setToast("Sent to bot");
        void recordMiniAppEvent("mutation_telegram_fallback", { path, type: fallbackPayload.type });
        return;
      }
      setAssistantState("sad");
      setStateError(formatMiniAppError(error));
      void recordMiniAppEvent("mutation_error", { path });
    }
  }, []);

  useEffect(() => {
    if (!telegram) {
      return;
    }
    telegram.ready();
    telegram.expand();
    const bg = telegram.themeParams?.bg_color;
    if (bg) {
      document.documentElement.style.setProperty("--tg-bg", bg);
    }
    void recordMiniAppEvent("app_open", {
      user_id: telegram.initDataUnsafe?.user?.id ?? "",
    });
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
        setToast(`Preview payload: ${serialized}`);
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

  return (
    <main className="mx-auto grid min-h-screen w-full max-w-3xl gap-3 px-4 py-4 text-zinc-50">
      <header className="flex items-center justify-between gap-4">
        <div>
          <p className="text-xs font-black uppercase text-teal-300">Assistant Bot</p>
          <h1 className="mt-1 text-3xl font-black leading-tight">Second brain</h1>
        </div>
        <button
          className="grid size-11 place-items-center rounded-lg border border-zinc-700 bg-zinc-900 text-zinc-50 shadow-2xl"
          type="button"
          aria-label="Обновить статус"
          onClick={() => void refreshState()}
        >
          <RefreshCw size={18} />
        </button>
      </header>

      <PixelAssistant state={assistantState} />
      <Tabs activeTab={activeTab} onSelect={setActiveTab} />

      {activeTab === "today" && (
        <TodayPanel
          state={miniState?.today}
          loading={stateLoading}
          error={stateError}
          onMutate={mutateState}
          onRefresh={refreshState}
        />
      )}
      {activeTab === "assistant" && <AssistantPanel />}
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
          onRefresh={refreshState}
        />
      )}
      {activeTab === "shopping" && <ShoppingPanel />}
      {activeTab === "markets" && <MarketsPanel />}

      <div
        className={
          toast
            ? "fixed bottom-4 right-4 max-w-[calc(100vw-32px)] translate-y-0 rounded-lg bg-teal-300 px-4 py-3 text-sm font-black text-zinc-950 opacity-100 transition"
            : "pointer-events-none fixed bottom-4 right-4 max-w-[calc(100vw-32px)] translate-y-3 rounded-lg bg-teal-300 px-4 py-3 text-sm font-black text-zinc-950 opacity-0 transition"
        }
        role="status"
        aria-live="polite"
      >
        {toast}
      </div>
    </main>
  );
}

function formatMiniAppError(error: unknown): string {
  if (shouldFallbackToTelegram(error)) {
    return "Live API unavailable. Telegram actions still work from inside Mini App.";
  }
  return error instanceof Error ? error.message : "Mini App API error";
}
