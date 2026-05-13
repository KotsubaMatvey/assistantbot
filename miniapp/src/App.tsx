import { RefreshCw } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { PixelAssistant } from "./components/PixelAssistant";
import { Tabs } from "./components/Tabs";
import { AssistantPanel } from "./components/panels/AssistantPanel";
import { MarketsPanel } from "./components/panels/MarketsPanel";
import { MemoryPanel } from "./components/panels/MemoryPanel";
import { ShoppingPanel } from "./components/panels/ShoppingPanel";
import type { AssistantState } from "./domain/assistant";
import { eventBus, type TabId } from "./domain/events";
import { attachRules } from "./domain/rules";
import type { TelegramPayload, TelegramWebApp } from "./types/telegram";

export function App() {
  const [activeTab, setActiveTab] = useState<TabId>("assistant");
  const [assistantState, setAssistantState] = useState<AssistantState>("idle");
  const [toast, setToast] = useState("");
  const telegram = useMemo<TelegramWebApp | undefined>(() => window.Telegram?.WebApp, []);

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
  }, [telegram]);

  useEffect(() => {
    return attachRules(eventBus, {
      setAssistantState,
      showToast: setToast,
      sendTelegramPayload: (payload: TelegramPayload) => {
        const serialized = JSON.stringify(payload);
        if (telegram) {
          telegram.sendData(serialized);
          setToast("Отправлено в бот");
          return;
        }
        setToast(`Preview payload: ${serialized}`);
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
          onClick={() => eventBus.emit("command:send", { command: "status" })}
        >
          <RefreshCw size={18} />
        </button>
      </header>

      <PixelAssistant state={assistantState} />
      <Tabs activeTab={activeTab} onSelect={setActiveTab} />

      {activeTab === "shopping" && <ShoppingPanel />}
      {activeTab === "markets" && <MarketsPanel />}
      {activeTab === "assistant" && <AssistantPanel />}
      {activeTab === "memory" && <MemoryPanel />}

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
