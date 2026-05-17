import { Brain, Database, RefreshCw, Wrench } from "lucide-react";
import { ActionButton } from "../ActionButton";
import type { MiniAppState } from "../../domain/api";
import { eventBus } from "../../domain/events";

type MemoryPanelProps = {
  state?: MiniAppState["memory"];
  loading: boolean;
  error: string;
  onRefresh: () => Promise<void>;
};

export function MemoryPanel({ state, loading, error, onRefresh }: MemoryPanelProps) {
  const health = state?.health;
  return (
    <section className="grid gap-3" aria-label="Память">
      {(loading || error) && (
        <div className="flex items-center justify-between gap-3 rounded-lg border border-zinc-700 bg-zinc-900 p-3 text-sm text-zinc-400">
          <span>{loading ? "Loading live data" : error}</span>
          <button
            className="grid size-9 place-items-center rounded-lg border border-zinc-700 bg-zinc-800 text-zinc-50"
            type="button"
            onClick={() => void onRefresh()}
            aria-label="Refresh"
          >
            <RefreshCw size={15} />
          </button>
        </div>
      )}

      <div className="grid grid-cols-4 gap-2 max-[620px]:grid-cols-2">
        <MetricCard label="Raw" value={String(health?.raw_captures ?? 0)} />
        <MetricCard label="Daily" value={String(health?.daily_summaries ?? 0)} />
        <MetricCard label="Projects" value={String(health?.project_summaries ?? 0)} />
        <MetricCard label="Objects" value={String(state?.objects.total ?? 0)} />
      </div>

      <div className="grid gap-2">
        {(state?.objects.recent ?? []).slice(0, 8).map((item) => (
          <article
            key={item.id}
            className="grid grid-cols-[88px_1fr] gap-3 rounded-lg border border-zinc-700 bg-zinc-900 p-3"
          >
            <span className="text-xs font-black uppercase text-teal-300">{item.type}</span>
            <strong className="text-sm text-zinc-50">{item.title}</strong>
          </article>
        ))}
      </div>

      <div className="grid gap-2">
        {(state?.sources ?? []).map((source) => (
          <article key={source.id} className="rounded-lg border border-zinc-700 bg-zinc-900 p-3">
            <span className="text-xs font-black uppercase text-teal-300">{source.type}</span>
            <strong className="mt-1 block break-words text-sm text-zinc-50">{source.url}</strong>
            <span className="mt-1 block text-xs text-zinc-400">
              {source.enabled ? "enabled" : "disabled"}
              {source.last_error ? ` · ${source.last_error}` : ""}
            </span>
          </article>
        ))}
      </div>

      <div className="grid gap-2">
        {(state?.events ?? []).slice(0, 6).map((event) => (
          <article key={event.id} className="rounded-lg border border-zinc-700 bg-zinc-900 p-3">
            <span className="text-xs font-black uppercase text-teal-300">{event.action}</span>
            <strong className="mt-1 block break-words text-sm text-zinc-50">
              {event.detail || "Mini App event"}
            </strong>
            <span className="mt-1 block text-xs text-zinc-400">{event.created_at}</span>
          </article>
        ))}
      </div>

      <div className="grid grid-cols-2 gap-2 max-[420px]:grid-cols-1">
        <ActionButton
          primary
          icon={<Brain size={16} />}
          onClick={() => eventBus.emit("command:send", { command: "memory_tree" })}
        >
          Memory Tree
        </ActionButton>
        <ActionButton
          icon={<Database size={16} />}
          onClick={() => eventBus.emit("command:send", { command: "objects" })}
        >
          Objects
        </ActionButton>
        <ActionButton
          icon={<RefreshCw size={16} />}
          onClick={() => eventBus.emit("command:send", { command: "weekly_summary" })}
        >
          Weekly
        </ActionButton>
        <ActionButton
          icon={<Database size={16} />}
          onClick={() => eventBus.emit("command:send", { command: "source_list" })}
        >
          Sources
        </ActionButton>
        <ActionButton
          icon={<RefreshCw size={16} />}
          onClick={() => eventBus.emit("command:send", { command: "source_sync" })}
        >
          Sync
        </ActionButton>
        <ActionButton
          icon={<Wrench size={16} />}
          onClick={() => eventBus.emit("command:send", { command: "tools" })}
        >
          Tools
        </ActionButton>
      </div>
    </section>
  );
}

function MetricCard({ label, value }: { label: string; value: string }) {
  return (
    <article className="rounded-lg border border-zinc-700 bg-zinc-900 p-3">
      <span className="block text-xs font-black text-zinc-400">{label}</span>
      <strong className="mt-2 block text-lg leading-tight text-zinc-50">{value}</strong>
    </article>
  );
}
