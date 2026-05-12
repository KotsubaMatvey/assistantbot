import { Send } from "lucide-react";
import { useState } from "react";
import { ActionButton } from "../ActionButton";
import { assistantActions } from "../../domain/data";
import { eventBus } from "../../domain/events";
import type { AssistantState } from "../../domain/assistant";

const states: { state: AssistantState; label: string }[] = [
  { state: "idle", label: "Idle" },
  { state: "thinking", label: "Thinking" },
  { state: "happy", label: "Success" },
  { state: "alert", label: "Alert" },
  { state: "shopping", label: "Shopping" },
  { state: "sad", label: "Low battery" },
  { state: "working", label: "Working" },
];

export function AssistantPanel() {
  const [prompt, setPrompt] = useState("что важно утром?");

  return (
    <section className="grid gap-3" aria-label="Ассистент">
      <div className="grid gap-3 rounded-lg border border-zinc-700 bg-zinc-900 p-3">
        <label className="text-xs font-black text-zinc-400" htmlFor="pixelPrompt">
          Команда помощнику
        </label>
        <div className="grid grid-cols-[1fr_108px] gap-2 max-[420px]:grid-cols-1">
          <input
            id="pixelPrompt"
            className="min-w-0 rounded-lg border border-zinc-700 bg-zinc-950 p-3 text-sm text-zinc-50 outline-none"
            value={prompt}
            onChange={(event) => setPrompt(event.target.value)}
          />
          <ActionButton
            icon={<Send size={16} />}
            onClick={() => eventBus.emit("assistant:prompt", { text: prompt })}
          >
            Send
          </ActionButton>
        </div>
      </div>

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
