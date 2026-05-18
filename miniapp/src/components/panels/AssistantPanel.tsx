import { Send } from "lucide-react";
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

export function AssistantPanel() {
  const [prompt, setPrompt] = useState("what matters now?");

  return (
    <section className="grid gap-4" aria-label="Agent">
      <section className="glass-panel p-4">
        <div className="section-title">
          <span>Action Console</span>
          <span className="text-sm text-[var(--accent)]">operator mode</span>
        </div>
        <div className="mt-4 grid grid-cols-[1fr_108px] gap-2 max-[420px]:grid-cols-1">
          <input
            id="pixelPrompt"
            className="surface-input p-3 text-sm"
            value={prompt}
            onChange={(event) => setPrompt(event.target.value)}
          />
          <ActionButton
            primary
            icon={<Send size={16} />}
            onClick={() => eventBus.emit("assistant:prompt", { text: prompt })}
          >
            Send
          </ActionButton>
        </div>
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
