import { FileText, Globe, Plus, RefreshCw, Rss, Search, Trash2 } from "lucide-react";
import type { FormEvent } from "react";
import { useMemo, useState } from "react";
import { memoryActions } from "../../domain/data";
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

const filters: { id: BrainFilter; label: string }[] = [
  { id: "objects", label: "Объекты" },
  { id: "sources", label: "Источники" },
  { id: "events", label: "События" },
];

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
        [item.title, item.type, item.tags.join(" ")]
          .join(" ")
          .toLowerCase()
          .includes(query.toLowerCase()),
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
    <section className="grid gap-3.5" aria-label="Память">
      {(loading || error) && (
        <div className={error ? "notice notice-error" : "notice"}>
          <span>{loading ? "Загружаю данные…" : error}</span>
          <button
            className="icon-btn !h-8 !w-8"
            type="button"
            aria-label="Обновить"
            onClick={() => void onRefresh()}
          >
            <RefreshCw size={14} />
          </button>
        </div>
      )}

      <div className="grid grid-cols-4 gap-2 max-[460px]:grid-cols-2">
        <Stat label="Черновики" value={String(health?.raw_captures ?? 0)} />
        <Stat label="Дни" value={String(health?.daily_summaries ?? 0)} />
        <Stat label="Проекты" value={String(health?.project_summaries ?? 0)} />
        <Stat label="Объекты" value={String(state?.objects.total ?? 0)} />
      </div>

      <section className="card card-pad grid gap-2.5">
        <label className="input flex items-center gap-2.5">
          <Search size={16} className="shrink-0 text-[var(--dim)]" />
          <input
            className="min-w-0 flex-1 border-0 bg-transparent text-sm text-[var(--text)] outline-none placeholder:text-[var(--dim)]"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Поиск по памяти…"
          />
        </label>
        <div className="segmented" role="tablist" aria-label="Раздел памяти">
          {filters.map((item) => (
            <button
              key={item.id}
              className={filter === item.id ? "segment segment-active" : "segment"}
              type="button"
              onClick={() => setFilter(item.id)}
            >
              {item.label}
            </button>
          ))}
        </div>

        <div className="grid gap-2">
          {filter === "objects" &&
            filteredObjects.slice(0, 10).map((item) => (
              <article key={item.id} className="row">
                <span className="row-icon">
                  <FileText size={15} />
                </span>
                <div className="row-body">
                  <span className="row-title">{item.title}</span>
                  <span className="row-sub">
                    {item.type}
                    {displayTags(item.tags) ? ` · ${displayTags(item.tags)}` : ""}
                  </span>
                </div>
              </article>
            ))}
          {filter === "objects" && !loading && filteredObjects.length === 0 && (
            <article className="empty">
              <strong>Объекты не найдены</strong>
              <span>Попробуй другой запрос или добавь новую заметку.</span>
            </article>
          )}

          {filter === "sources" &&
            filteredSources.map((item) => (
              <article key={item.id} className="row">
                <span className="row-icon">
                  {item.type === "rss" ? <Rss size={15} /> : <Globe size={15} />}
                </span>
                <div className="row-body">
                  <span className="row-title" style={{ overflowWrap: "anywhere" }}>
                    {item.url}
                  </span>
                  <span className="row-sub">
                    {item.type} · {item.enabled ? "включен" : "выключен"}
                    {item.last_error ? ` · ${item.last_error}` : ""}
                  </span>
                </div>
                <span className="flex shrink-0 gap-1.5">
                  <button
                    className="icon-btn !h-8 !w-8"
                    type="button"
                    aria-label="Синхронизировать"
                    onClick={() => void onMutate("/api/miniapp/source/sync", { id: item.id })}
                  >
                    <RefreshCw size={13} />
                  </button>
                  <button
                    className="icon-btn !h-8 !w-8"
                    type="button"
                    aria-label="Удалить"
                    onClick={() => void onMutate("/api/miniapp/source/delete", { id: item.id })}
                  >
                    <Trash2 size={13} />
                  </button>
                </span>
              </article>
            ))}
          {filter === "sources" && !loading && filteredSources.length === 0 && (
            <article className="empty">
              <strong>Источников пока нет</strong>
              <span>Добавь RSS, GitHub или URL-источник ниже.</span>
            </article>
          )}

          {filter === "events" &&
            filteredEvents.slice(0, 10).map((item) => (
              <article key={item.id} className="row">
                <div className="row-body">
                  <span className="row-title" style={{ overflowWrap: "anywhere" }}>
                    {item.detail || item.action}
                  </span>
                  <span className="row-sub">
                    {item.action} · {formatDateTime(item.created_at)}
                  </span>
                </div>
              </article>
            ))}
          {filter === "events" && !loading && filteredEvents.length === 0 && (
            <article className="empty">
              <strong>Событий нет</strong>
              <span>Здесь появятся действия и синхронизации.</span>
            </article>
          )}
        </div>
      </section>

      <form
        className="card card-pad grid grid-cols-[96px_minmax(0,1fr)_42px] gap-2 max-[460px]:grid-cols-[minmax(0,1fr)_42px]"
        onSubmit={(event) => void submitSource(event)}
      >
        <select
          className="input max-[460px]:col-span-2"
          value={source.source_type}
          aria-label="Тип источника"
          onChange={(event) => setSource({ ...source, source_type: event.target.value })}
        >
          <option value="rss">RSS</option>
          <option value="github">GitHub</option>
          <option value="url">URL</option>
        </select>
        <input
          className="input"
          value={source.target}
          placeholder="Ссылка на источник"
          onChange={(event) => setSource({ ...source, target: event.target.value })}
        />
        <button className="chat-send" type="submit" aria-label="Добавить источник">
          <Plus size={18} />
        </button>
      </form>

      <div className="flex flex-wrap gap-2">
        {memoryActions.map((action) => (
          <button
            key={action.command}
            className="chip"
            type="button"
            onClick={() => eventBus.emit("command:send", { command: action.command })}
          >
            {action.label}
          </button>
        ))}
        <button
          className="chip"
          type="button"
          onClick={() => void onMutate("/api/miniapp/source/sync", {})}
        >
          Синхронизировать всё
        </button>
      </div>
    </section>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <article className="stat">
      <span>{label}</span>
      <strong>{value}</strong>
    </article>
  );
}

const serviceTags = new Set(["pricebot", "memory", "task", "reminder", "note", "preference", "fact"]);

function displayTags(tags: string[]): string {
  return tags
    .filter((tag) => !serviceTags.has(tag))
    .slice(0, 3)
    .join(" · ");
}

function formatDateTime(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  const day = date.toLocaleDateString("ru-RU", { day: "numeric", month: "short" });
  const time = date.toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" });
  return `${day}, ${time}`;
}
