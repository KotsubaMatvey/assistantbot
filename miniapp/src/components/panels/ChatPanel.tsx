import { Send, Trash2 } from "lucide-react";
import { useEffect, useRef, useState } from "react";

const promptPresets = [
  "Что важно сейчас?",
  "Собери план на сегодня",
  "Что я недавно решил?",
  "Найди контекст по бюджету",
];

type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  text: string;
};

type ChatPanelProps = {
  onAsk: (text: string) => Promise<string>;
};

const STORAGE_KEY = "miniapp-chat-history-v1";
const MAX_MESSAGES = 40;

export function ChatPanel({ onAsk }: ChatPanelProps) {
  const [messages, setMessages] = useState<ChatMessage[]>(loadMessages);
  const [draft, setDraft] = useState("");
  const [isSending, setIsSending] = useState(false);
  const threadEndRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    try {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(messages.slice(-MAX_MESSAGES)));
    } catch {
      // Persistence must never break the chat.
    }
  }, [messages]);

  useEffect(() => {
    threadEndRef.current?.scrollIntoView({ block: "end" });
  }, [messages, isSending]);

  async function send(text: string) {
    const cleanText = text.trim();
    if (!cleanText || isSending) {
      return;
    }
    setDraft("");
    setMessages((items) =>
      [...items, { id: newId(), role: "user" as const, text: cleanText }].slice(-MAX_MESSAGES),
    );
    setIsSending(true);
    try {
      const answer = await onAsk(cleanText);
      setMessages((items) =>
        [...items, { id: newId(), role: "assistant" as const, text: answer }].slice(-MAX_MESSAGES),
      );
    } finally {
      setIsSending(false);
    }
  }

  function clearHistory() {
    setMessages([]);
    try {
      window.localStorage.removeItem(STORAGE_KEY);
    } catch {
      // ignore
    }
  }

  return (
    <section className="grid gap-3.5" aria-label="Чат с ассистентом">
      <section className="card card-pad grid min-h-[40vh] content-between gap-3.5">
        <div className="grid gap-3">
          <div className="card-title">
            <span>Ассистент</span>
            {messages.length > 0 && (
              <button
                className="icon-btn !h-8 !w-8"
                type="button"
                aria-label="Очистить историю"
                onClick={clearHistory}
              >
                <Trash2 size={14} />
              </button>
            )}
          </div>

          {messages.length === 0 ? (
            <div className="grid gap-3">
              <article className="empty">
                <strong>Спроси о своей памяти</strong>
                <span>
                  Ассистент отвечает по локальным заметкам, задачам и решениям. Вопрос можно
                  начать с готового примера ниже.
                </span>
              </article>
              <div className="flex flex-wrap gap-2">
                {promptPresets.map((item) => (
                  <button
                    key={item}
                    className="chip"
                    type="button"
                    onClick={() => void send(item)}
                  >
                    {item}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <div className="chat-thread">
              {messages.map((message) => (
                <div
                  key={message.id}
                  className={message.role === "user" ? "bubble bubble-user" : "bubble bubble-bot"}
                >
                  {message.text}
                </div>
              ))}
              {isSending && <div className="bubble bubble-bot bubble-pending">Думаю…</div>}
              <div ref={threadEndRef} />
            </div>
          )}
        </div>

        <div className="chat-inputbar">
          <textarea
            className="input"
            rows={1}
            value={draft}
            placeholder="Вопрос к памяти…"
            onChange={(event) => setDraft(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                void send(draft);
              }
            }}
          />
          <button
            className="chat-send"
            type="button"
            aria-label="Отправить"
            disabled={isSending || !draft.trim()}
            onClick={() => void send(draft)}
          >
            <Send size={17} />
          </button>
        </div>
      </section>

      <p className="dim-text m-0 px-1 text-[12px] leading-relaxed">
        Ответы строятся по локальной памяти. Свободный диалог и действия — в чате с ботом в
        Telegram.
      </p>
    </section>
  );
}

function loadMessages(): ChatMessage[] {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) {
      return [];
    }
    const parsed: unknown = JSON.parse(raw);
    if (!Array.isArray(parsed)) {
      return [];
    }
    return parsed
      .filter(
        (item): item is ChatMessage =>
          typeof item === "object" &&
          item !== null &&
          "id" in item &&
          "role" in item &&
          "text" in item &&
          (item.role === "user" || item.role === "assistant"),
      )
      .slice(-MAX_MESSAGES);
  } catch {
    return [];
  }
}

function newId(): string {
  return Math.random().toString(36).slice(2, 10);
}
