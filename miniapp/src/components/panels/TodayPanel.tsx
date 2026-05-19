import {
  Bell,
  CalendarDays,
  ListChecks,
  NotebookPen,
  Plus,
  RefreshCw,
  Users,
} from "lucide-react";
import type { FormEvent, ReactNode } from "react";
import { useState } from "react";
import { ActionButton } from "../ActionButton";
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

export function TodayPanel({ state, loading, error, onMutate, onRefresh }: TodayPanelProps) {
  const [taskText, setTaskText] = useState("");
  const [noteText, setNoteText] = useState("");
  const [reminderText, setReminderText] = useState("");
  const [person, setPerson] = useState({ name: "", note: "" });
  const today = new Date();
  const activeDay = today.getDate();

  async function submitTask(event: FormEvent) {
    event.preventDefault();
    if (!taskText.trim()) {
      return;
    }
    await onMutate("/api/miniapp/task", { text: taskText.trim() });
    setTaskText("");
  }

  async function submitNote(event: FormEvent) {
    event.preventDefault();
    if (!noteText.trim()) {
      return;
    }
    await onMutate("/api/miniapp/note", { text: noteText.trim() });
    setNoteText("");
  }

  async function submitReminder(event: FormEvent) {
    event.preventDefault();
    if (!reminderText.trim()) {
      return;
    }
    await onMutate("/api/miniapp/reminder", { text: reminderText.trim() });
    setReminderText("");
  }

  async function submitPerson(event: FormEvent) {
    event.preventDefault();
    if (!person.name.trim() || !person.note.trim()) {
      return;
    }
    await onMutate("/api/miniapp/person", {
      name: person.name.trim(),
      note: person.note.trim(),
    });
    setPerson({ name: "", note: "" });
  }

  const agendaItems = [
    ...(state?.reminders ?? []).map((item) => ({
      id: item.id,
      title: item.snippet,
      detail: item.due_at,
      type: "Напоминание",
    })),
    ...(state?.tasks ?? []).map((item) => ({
      id: item.id,
      title: item.snippet,
      detail: item.tags.slice(0, 3).join(", ") || "Задача",
      type: "Задача",
    })),
  ].slice(0, 6);

  return (
    <section className="grid gap-4" aria-label="Сегодня">
      <StatusStrip loading={loading} error={error} onRefresh={onRefresh} />

      <div className="grid grid-cols-[0.85fr_1.15fr] gap-3 max-[680px]:grid-cols-1">
        <section className="glass-panel glass-panel-tight p-4">
          <div className="section-title">
            <span>Повестка</span>
            <CalendarDays size={20} className="text-[var(--accent)]" />
          </div>
          <div className="mt-4 grid grid-cols-7 gap-2 text-center text-sm font-black">
            {["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"].map((day) => (
              <span key={day} className="dim-text">
                {day}
              </span>
            ))}
            {Array.from({ length: 35 }, (_, index) => {
              const day = index + 1;
              return (
                <span
                  key={day}
                  className={
                    day === activeDay
                      ? "rounded-xl bg-[var(--accent)] py-2 text-zinc-950 shadow-[0_0_18px_rgba(0,196,180,0.42)]"
                      : "py-2 text-zinc-100"
                  }
                >
                  {day <= 31 ? day : ""}
                </span>
              );
            })}
          </div>
          <p className="muted-text mt-4 text-sm leading-5">{state?.agenda || state?.digest}</p>
        </section>

        <section className="glass-panel glass-panel-tight p-4">
          <div className="section-title">
            <span>Дела</span>
            <span className="text-sm text-[var(--accent)]">{agendaItems.length}</span>
          </div>
          <div className="mt-4 grid gap-2">
            {agendaItems.map((item, index) => (
              <article
                key={`${item.type}-${item.id}`}
                className={index === 0 ? "record-row record-row-active" : "record-row"}
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <span className="app-kicker">{item.type}</span>
                    <strong className="mt-1 block truncate text-base text-white">
                      {item.title}
                    </strong>
                    <span className="muted-text mt-1 block truncate text-sm">{item.detail}</span>
                  </div>
                  <span className="muted-text whitespace-nowrap text-sm">
                    {index === 0 ? "сейчас" : "далее"}
                  </span>
                </div>
              </article>
            ))}
            {!loading && agendaItems.length === 0 && (
              <article className="record-row">
                <strong className="block text-base text-white">Нет запланированных дел</strong>
                <span className="muted-text mt-1 block text-sm">Добавь задачу или напоминание.</span>
              </article>
            )}
          </div>
        </section>
      </div>

      <div className="grid grid-cols-4 gap-2 max-[620px]:grid-cols-2">
        <MetricCard label="Задачи" value={String(state?.tasks.length ?? 0)} />
        <MetricCard label="Напоминания" value={String(state?.reminders.length ?? 0)} />
        <MetricCard label="Заметки" value={String(state?.notes.length ?? 0)} />
        <MetricCard label="Фокус" value={String(state?.focus.length ?? 0)} />
      </div>

      <section className="glass-panel glass-panel-tight grid gap-2 p-3">
        <QuickForm
          icon={<ListChecks size={16} />}
          value={taskText}
          label="Задача"
          onChange={setTaskText}
          onSubmit={submitTask}
        />
        <QuickForm
          icon={<NotebookPen size={16} />}
          value={noteText}
          label="Заметка"
          onChange={setNoteText}
          onSubmit={submitNote}
        />
        <QuickForm
          icon={<Bell size={16} />}
          value={reminderText}
          label="Напоминание"
          onChange={setReminderText}
          onSubmit={submitReminder}
        />
        <PersonForm person={person} onChange={setPerson} onSubmit={submitPerson} />
      </section>

      <div className="grid grid-cols-4 gap-2 max-[620px]:grid-cols-2">
        {todayActions.map((action) => (
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

function PersonForm({
  person,
  onChange,
  onSubmit,
}: {
  person: { name: string; note: string };
  onChange: (person: { name: string; note: string }) => void;
  onSubmit: (event: FormEvent) => void;
}) {
  return (
    <form
      className="grid grid-cols-[94px_1fr_1.4fr_46px] gap-2 max-[620px]:grid-cols-1"
      onSubmit={onSubmit}
    >
      <label className="flex items-center gap-2 text-xs font-black uppercase text-[var(--muted)]">
        <Users size={16} />
        Человек
      </label>
      <input
        className="surface-input px-3 py-2 text-sm"
        value={person.name}
        placeholder="Имя"
        onChange={(event) => onChange({ ...person, name: event.target.value })}
      />
      <input
        className="surface-input px-3 py-2 text-sm"
        value={person.note}
        placeholder="Заметка"
        onChange={(event) => onChange({ ...person, note: event.target.value })}
      />
      <button className="icon-button !h-11 !w-full" type="submit" aria-label="Добавить человека">
        <Plus size={16} />
      </button>
    </form>
  );
}

function MetricCard({ label, value }: { label: string; value: string }) {
  return (
    <article className="metric-card">
      <span>{label}</span>
      <strong>{value}</strong>
    </article>
  );
}

function QuickForm({
  icon,
  label,
  value,
  onChange,
  onSubmit,
}: {
  icon: ReactNode;
  label: string;
  value: string;
  onChange: (value: string) => void;
  onSubmit: (event: FormEvent) => void;
}) {
  return (
    <form className="grid grid-cols-[94px_1fr_46px] gap-2 max-[520px]:grid-cols-1" onSubmit={onSubmit}>
      <label className="flex items-center gap-2 text-xs font-black uppercase text-[var(--muted)]">
        {icon}
        {label}
      </label>
      <input
        className="surface-input px-3 py-2 text-sm"
        value={value}
        placeholder={label}
        onChange={(event) => onChange(event.target.value)}
      />
      <button className="icon-button !h-11 !w-full" type="submit" aria-label={`Добавить: ${label}`}>
        <Plus size={16} />
      </button>
    </form>
  );
}

function StatusStrip({
  loading,
  error,
  onRefresh,
}: {
  loading: boolean;
  error: string;
  onRefresh: () => Promise<void>;
}) {
  if (!loading && !error) {
    return null;
  }
  return (
    <div className="glass-panel glass-panel-tight flex items-center justify-between gap-3 p-3 text-sm text-[var(--muted)]">
      <span>{loading ? "Загружаю актуальные данные" : error}</span>
      <button className="icon-button !h-9 !w-9" type="button" onClick={() => void onRefresh()}>
        <RefreshCw size={15} />
      </button>
    </div>
  );
}
