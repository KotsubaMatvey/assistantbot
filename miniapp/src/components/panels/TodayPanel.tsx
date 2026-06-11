import { Bell, Check, NotebookPen, Plus, RefreshCw } from "lucide-react";
import type { FormEvent } from "react";
import { useMemo, useState } from "react";
import { todayActions } from "../../domain/data";
import type { MiniAppState } from "../../domain/api";
import { eventBus } from "../../domain/events";

type TodayPanelProps = {
  state?: MiniAppState["today"];
  loading: boolean;
  error: string;
  onMutate: (path: string, body: Record<string, unknown>) => Promise<void>;
  onRefresh: () => Promise<void>;
};

type QuickAddKind = "task" | "note" | "reminder";

const quickAddMeta: Record<QuickAddKind, { label: string; placeholder: string; path: string }> = {
  task: { label: "Задача", placeholder: "Например: позвонить врачу", path: "/api/miniapp/task" },
  note: { label: "Заметка", placeholder: "Мысль, факт или решение", path: "/api/miniapp/note" },
  reminder: {
    label: "Напоминание",
    placeholder: "Например: завтра в 9 забрать посылку",
    path: "/api/miniapp/reminder",
  },
};

export function TodayPanel({ state, loading, error, onMutate, onRefresh }: TodayPanelProps) {
  const [quickKind, setQuickKind] = useState<QuickAddKind>("task");
  const [quickText, setQuickText] = useState("");
  const [completing, setCompleting] = useState<string>("");
  const week = useMemo(() => getWeekDays(new Date()), []);

  async function submitQuickAdd(event: FormEvent) {
    event.preventDefault();
    const text = quickText.trim();
    if (!text) {
      return;
    }
    await onMutate(quickAddMeta[quickKind].path, { text });
    setQuickText("");
  }

  async function completeTask(id: string) {
    setCompleting(id);
    try {
      await onMutate("/api/miniapp/task/complete", { id });
    } finally {
      setCompleting("");
    }
  }

  const reminders = state?.reminders ?? [];
  const tasks = (state?.tasks ?? []).filter((task) => !task.tags.includes("reminder"));
  const notes = (state?.notes ?? [])
    .filter((note) => note.type !== "task" && note.type !== "reminder")
    .slice(0, 3);

  return (
    <section className="grid gap-3.5" aria-label="Сегодня">
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

      <section className="card card-pad grid gap-3">
        <div className="week-strip">
          {week.map((day) => (
            <div key={day.iso} className={day.isToday ? "week-day week-day-active" : "week-day"}>
              <span>{day.weekday}</span>
              <strong>{day.date}</strong>
            </div>
          ))}
        </div>
      </section>

      <section className="card card-pad grid gap-2.5">
        <div className="card-title">
          <span>Дальше</span>
          <span className="card-title-meta">
            {reminders.length + tasks.length > 0
              ? `${reminders.length + tasks.length} в работе`
              : ""}
          </span>
        </div>
        <div className="grid gap-2">
          {reminders.map((item) => (
            <article key={`reminder-${item.id}`} className="row">
              <span className="row-icon">
                <Bell size={15} />
              </span>
              <div className="row-body">
                <span className="row-title">{item.snippet}</span>
                <span className="row-sub">{formatDateTime(item.due_at)}</span>
              </div>
            </article>
          ))}
          {tasks.map((item) => (
            <article key={`task-${item.id}`} className="row">
              <button
                className={completing === item.id ? "check check-done" : "check"}
                type="button"
                aria-label="Отметить выполненной"
                disabled={Boolean(completing)}
                onClick={() => void completeTask(item.id)}
              >
                <Check size={14} />
              </button>
              <div className="row-body">
                <span className="row-title">{item.snippet}</span>
                {displayTags(item.tags) && <span className="row-sub">{displayTags(item.tags)}</span>}
              </div>
            </article>
          ))}
          {!loading && reminders.length === 0 && tasks.length === 0 && (
            <article className="empty">
              <strong>Пока пусто</strong>
              <span>Добавь первую задачу или напоминание ниже.</span>
            </article>
          )}
        </div>
      </section>

      <form className="card card-pad grid gap-2.5" onSubmit={(event) => void submitQuickAdd(event)}>
        <div className="segmented" role="tablist" aria-label="Тип записи">
          {(Object.keys(quickAddMeta) as QuickAddKind[]).map((kind) => (
            <button
              key={kind}
              className={quickKind === kind ? "segment segment-active" : "segment"}
              type="button"
              onClick={() => setQuickKind(kind)}
            >
              {quickAddMeta[kind].label}
            </button>
          ))}
        </div>
        <div className="grid grid-cols-[minmax(0,1fr)_42px] gap-2">
          <input
            className="input"
            value={quickText}
            placeholder={quickAddMeta[quickKind].placeholder}
            onChange={(event) => setQuickText(event.target.value)}
          />
          <button
            className="chat-send"
            type="submit"
            aria-label={`Добавить: ${quickAddMeta[quickKind].label}`}
          >
            <Plus size={18} />
          </button>
        </div>
      </form>

      <div className="grid grid-cols-4 gap-2 max-[460px]:grid-cols-2">
        <Stat label="Задачи" value={String(state?.tasks.length ?? 0)} />
        <Stat label="Напоминания" value={String(state?.reminders.length ?? 0)} />
        <Stat label="Заметки" value={String(state?.notes.length ?? 0)} />
        <Stat label="Фокус" value={String(state?.focus.length ?? 0)} />
      </div>

      {notes.length > 0 && (
        <section className="card card-pad grid gap-2.5">
          <div className="card-title">
            <span>Недавние заметки</span>
          </div>
          <div className="grid gap-2">
            {notes.map((item) => (
              <article key={item.id} className="row">
                <span className="row-icon">
                  <NotebookPen size={15} />
                </span>
                <div className="row-body">
                  <span className="row-title">{item.snippet}</span>
                  {displayTags(item.tags) && (
                    <span className="row-sub">{displayTags(item.tags)}</span>
                  )}
                </div>
              </article>
            ))}
          </div>
        </section>
      )}

      <div className="flex flex-wrap gap-2">
        {todayActions.map((action) => (
          <button
            key={action.command}
            className="chip"
            type="button"
            onClick={() => eventBus.emit("command:send", { command: action.command })}
          >
            {action.label}
          </button>
        ))}
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

const serviceTags = new Set(["pricebot", "memory", "task", "reminder", "note", "preference"]);

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

function getWeekDays(today: Date): { iso: string; weekday: string; date: number; isToday: boolean }[] {
  const monday = new Date(today);
  monday.setDate(today.getDate() - ((today.getDay() + 6) % 7));
  return Array.from({ length: 7 }, (_, index) => {
    const day = new Date(monday);
    day.setDate(monday.getDate() + index);
    return {
      iso: day.toISOString().slice(0, 10),
      weekday: day.toLocaleDateString("ru-RU", { weekday: "short" }),
      date: day.getDate(),
      isToday: day.toDateString() === today.toDateString(),
    };
  });
}
