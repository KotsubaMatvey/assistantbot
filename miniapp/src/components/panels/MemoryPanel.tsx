import { Brain, Database, RefreshCw, Search, Wrench } from "lucide-react";
import type { FormEvent } from "react";
import { useMemo, useState } from "react";
import { ActionButton } from "../ActionButton";
import type { MiniAppState } from "../../domain/api";
import { eventBus } from "../../domain/events";

type MemoryPanelProps = {
  state?: MiniAppState["memory"];
  loading: boolean;
  error: string;
  onMutate: (path: string, body: Record<string, unknown>) => Promise<void>;
  onRefresh: () => Promise<void>;
};

type BrainFilter = "objects" | "sources" | "events";

export function MemoryPanel({ state, loading, error, onMutate, onRefresh }: MemoryPanelProps) {
  const [source, setSource] = useState({ source_type: "rss", target: "" });
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState<BrainFilter>("objects");
  const health = state?.health;
  const objects = state?.objects.recent ?? [];
  const sources = state?.sources ?? [];
  const events = state?.events ?? [];

  const filteredObjects = useMemo(
    () =>
      objects.filter((item) =>
        [item.title, item.type, item.tags.join(" ")].join(" ").toLowerCase().includes(query.toLowerCase()),
      ),
    [objects, query],
  );
  const filteredSources = useMemo(
    () =>
      sources.filter((item) =>
        [item.url, item.type, item.id].join(" ").toLowerCase().includes(query.toLowerCase()),
      ),
    [sources, query],
  );
  const filteredEvents = useMemo(
    () =>
      events.filter((item) =>
        [item.action, item.detail].join(" ").toLowerCase().includes(query.toLowerCase()),
      ),
    [events, query],
  );

  async function submitSource(event: FormEvent) {
    event.preventDefault();
    if (!source.target.trim()) {
      return;
    }
    await onMutate("/api/miniapp/source", {
      source_type: source.source_type,
      target: source.target.trim(),
    });
    setSource((current) => ({ ...current, target: "" }));
  }

  return (
    <section className="grid gap-4" aria-label="Память">
      {(loading || error) && (
        <div className="glass-panel glass-panel-tight flex items-center justify-between gap-3 p-3 text-sm text-[var(--muted)]">
          <span>{loading ? "Загружаю актуальные данные" : error}</span>
          <button className="icon-button !h-9 !w-9" type="button" onClick={() => void onRefresh()}>
            <RefreshCw size={15} />
          </button>
        </div>
      )}

      <section className="glass-panel p-4">
        <div className="section-title">
          <span>Память</span>
          <span className="text-sm text-[var(--accent)]">
            {health?.profile_exists ? "профиль готов" : "профиля нет"}
          </span>
        </div>
        <label className="surface-input mt-4 flex min-h-14 items-center gap-3 px-4">
          <Search size={20} className="text-[var(--muted)]" />
          <input
            className="min-w-0 flex-1 bg-transparent text-base text-white outline-none"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Поиск по заметкам..."
          />
        </label>
        <div className="mt-4 grid grid-cols-4 gap-2 max-[620px]:grid-cols-2">
          <MetricCard label="Черновики" value={String(health?.raw_captures ?? 0)} />
          <MetricCard label="Дни" value={String(health?.daily_summaries ?? 0)} />
          <MetricCard label="Проекты" value={String(health?.project_summaries ?? 0)} />
          <MetricCard label="Объекты" value={String(state?.objects.total ?? 0)} />
        </div>
      </section>

      <section className="glass-panel glass-panel-tight p-4">
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            {(["objects", "sources", "events"] as BrainFilter[]).map((item) => (
              <button
                key={item}
                className={
                  filter === item
                    ? "rounded-full bg-[var(--accent)] px-3 py-2 text-xs font-black capitalize text-zinc-950"
                    : "rounded-full border border-[var(--line)] px-3 py-2 text-xs font-black capitalize text-[var(--muted)]"
                }
                type="button"
                onClick={() => setFilter(item)}
              >
                {brainFilterLabel(item)}
              </button>
            ))}
          </div>
          <span className="app-kicker">Быстрый поиск</span>
        </div>

        <div className="mt-4 grid gap-2">
          {filter === "objects" &&
            filteredObjects.slice(0, 10).map((item, index) => (
              <article
                key={item.id}
                className={index === 0 ? "record-row record-row-active" : "record-row"}
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <span className="app-kicker">{item.type}</span>
                    <strong className="mt-1 block truncate text-base text-white">
                      {item.title}
                    </strong>
                    <span className="muted-text mt-1 block truncate text-sm">
                      {item.tags.slice(0, 4).join(", ") || "локальная память"}
                    </span>
                  </div>
                  <span className="muted-text whitespace-nowrap text-sm">память</span>
                </div>
              </article>
            ))}

          {filter === "sources" &&
            filteredSources.map((source) => (
              <article key={source.id} className="record-row">
                <div className="grid gap-3">
                  <div>
                    <span className="app-kicker">{source.type}</span>
                    <strong className="mt-1 block break-words text-sm text-white">
                      {source.url}
                    </strong>
                    <span className="muted-text mt-1 block text-xs">
                      {source.enabled ? "включен" : "выключен"}
                      {source.last_error ? ` · ${source.last_error}` : ""}
                    </span>
                  </div>
                  <div className="grid grid-cols-2 gap-2">
                    <ActionButton
                      icon={<RefreshCw size={16} />}
                      onClick={() => void onMutate("/api/miniapp/source/sync", { id: source.id })}
                    >
                      Синхронизировать
                    </ActionButton>
                    <ActionButton
                      onClick={() => void onMutate("/api/miniapp/source/delete", { id: source.id })}
                    >
                      Удалить
                    </ActionButton>
                  </div>
                </div>
              </article>
            ))}

          {filter === "events" &&
            filteredEvents.slice(0, 10).map((event) => (
              <article key={event.id} className="record-row">
                <span className="app-kicker">{event.action}</span>
                <strong className="mt-1 block break-words text-sm text-white">
                  {event.detail || "Событие мини-приложения"}
                </strong>
                <span className="muted-text mt-1 block text-xs">{event.created_at}</span>
              </article>
            ))}
        </div>
      </section>

      <form
        className="glass-panel glass-panel-tight grid grid-cols-[110px_1fr_96px] gap-2 p-3 max-[620px]:grid-cols-1"
        onSubmit={submitSource}
      >
        <select
          className="surface-input min-h-11 px-3 text-sm font-black"
          value={source.source_type}
          onChange={(event) => setSource({ ...source, source_type: event.target.value })}
        >
          <option value="rss">RSS</option>
          <option value="github">GitHub</option>
          <option value="url">URL</option>
        </select>
        <input
          className="surface-input px-3 py-2 text-sm"
          value={source.target}
          placeholder="Ссылка или источник"
          onChange={(event) => setSource({ ...source, target: event.target.value })}
        />
        <button className="action-button action-button-primary" type="submit">
          Добавить
        </button>
      </form>

      <div className="grid grid-cols-2 gap-2 max-[420px]:grid-cols-1">
        <ActionButton
          primary
          icon={<Brain size={16} />}
          onClick={() => eventBus.emit("command:send", { command: "memory_tree" })}
        >
          Дерево памяти
        </ActionButton>
        <ActionButton
          icon={<Database size={16} />}
          onClick={() => eventBus.emit("command:send", { command: "objects" })}
        >
          Объекты
        </ActionButton>
        <ActionButton
          icon={<RefreshCw size={16} />}
          onClick={() => eventBus.emit("command:send", { command: "weekly_summary" })}
        >
          Неделя
        </ActionButton>
        <ActionButton
          icon={<Database size={16} />}
          onClick={() => eventBus.emit("command:send", { command: "source_list" })}
        >
          Источники
        </ActionButton>
        <ActionButton
          icon={<RefreshCw size={16} />}
          onClick={() => void onMutate("/api/miniapp/source/sync", {})}
        >
          Синхронизация
        </ActionButton>
        <ActionButton
          icon={<Wrench size={16} />}
          onClick={() => eventBus.emit("command:send", { command: "tools" })}
        >
          Инструменты
        </ActionButton>
      </div>
    </section>
  );
}

function brainFilterLabel(filter: BrainFilter): string {
  if (filter === "objects") {
    return "объекты";
  }
  if (filter === "sources") {
    return "источники";
  }
  return "события";
}

function MetricCard({ label, value }: { label: string; value: string }) {
  return (
    <article className="metric-card">
      <span>{label}</span>
      <strong>{value}</strong>
    </article>
  );
}
