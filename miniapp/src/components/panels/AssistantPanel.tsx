import { Clock3, Send } from "lucide-react";
import { useState } from "react";
import { ActionButton } from "../ActionButton";
import { assistantActions } from "../../domain/data";
import { eventBus } from "../../domain/events";
import type { AssistantState } from "../../domain/assistant";

const states: { state: AssistantState; label: string }[] = [
  { state: "idle", label: "Idle" },
  { state: "thinking", label: "Context" },
  { state: "happy", label: "Synced" },
  { state: "alert", label: "Signal" },
  { state: "shopping", label: "Pantry" },
  { state: "sad", label: "Overload" },
  { state: "working", label: "Working" },
];

const promptPresets = [
  "что важно сейчас?",
  "найди контекст по бюджету",
  "собери план на сегодня",
  "что я недавно решил?",
];

type AssistantExchange = {
  prompt: string;
  answer: string;
};

type AssistantPanelProps = {
  onAsk: (text: string) => Promise<string>;
};

export function AssistantPanel({ onAsk }: AssistantPanelProps) {
  const [prompt, setPrompt] = useState("что важно сейчас?");
  const [history, setHistory] = useState<AssistantExchange[]>([]);
  const [isSending, setIsSending] = useState(false);

  const sendPrompt = async () => {
    const cleanPrompt = prompt.trim();
    if (!cleanPrompt) {
      eventBus.emit("toast:show", { message: "Напиши запрос ассистенту" });
      return;
    }
    setIsSending(true);
    try {
      const answer = await onAsk(cleanPrompt);
      setHistory((items) => [
        { prompt: cleanPrompt, answer },
        ...items.filter((item) => item.prompt !== cleanPrompt),
      ].slice(0, 5));
    } finally {
      setIsSending(false);
    }
  };

  return (
    <section className="grid gap-4" aria-label="Agent">
      <section className="glass-panel p-4">
        <div className="section-title">
          <span>Assistant Chat</span>
          <span className="text-sm text-[var(--accent)]">cloud LLM</span>
        </div>
        <div className="mt-4 grid gap-3">
          <textarea
            id="pixelPrompt"
            className="surface-input min-h-28 resize-none p-3 text-sm leading-relaxed"
            value={prompt}
            onChange={(event) => setPrompt(event.target.value)}
            onKeyDown={(event) => {
              if ((event.metaKey || event.ctrlKey) && event.key === "Enter") {
                void sendPrompt();
              }
            }}
          />
          <div className="grid grid-cols-[1fr_118px] gap-2 max-[440px]:grid-cols-1">
            <div className="flex flex-wrap gap-2">
              {promptPresets.map((item) => (
                <button
                  key={item}
                  className="prompt-chip"
                  type="button"
                  onClick={() => setPrompt(item)}
                >
                  {item}
                </button>
              ))}
            </div>
            <ActionButton primary icon={<Send size={16} />} onClick={() => void sendPrompt()}>
              {isSending ? "Thinking" : "Send"}
            </ActionButton>
          </div>
        </div>
        {history.length > 0 && (
          <div className="mt-4 grid gap-2">
            <div className="flex items-center gap-2 text-xs font-black uppercase text-[var(--dim)]">
              <Clock3 size={14} />
              Recent prompts
            </div>
            {history.map((item) => (
              <article key={item.prompt} className="assistant-history-row">
                <button type="button" onClick={() => setPrompt(item.prompt)}>
                  {item.prompt}
                </button>
                <p>{item.answer}</p>
              </article>
            ))}
          </div>
        )}
      </section>

      <section className="glass-panel glass-panel-tight p-3">
        <div className="grid grid-cols-4 gap-2 max-[620px]:grid-cols-2">
          {states.map((item) => (
            <ActionButton
              key={item.state}
              onClick={() => eventBus.emit("assistant:set-state", { state: item.state })}
            >
              {item.label}
            </ActionButton>
          ))}
        </div>
      </section>

      <div className="grid grid-cols-2 gap-2">
        {assistantActions.map((action) => (
          <ActionButton
            key={action.command}
            icon={action.icon}
            primary={action.primary}
            onClick={() => eventBus.emit("command:send", { command: action.command })}
          >
            {action.label}
          </ActionButton>
        ))}
      </div>
    </section>
  );
}
