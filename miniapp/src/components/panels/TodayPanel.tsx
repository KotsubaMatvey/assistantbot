import { Bell, ListChecks, NotebookPen, Plus, RefreshCw, Users } from "lucide-react";
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

  return (
    <section className="grid gap-3" aria-label="Сегодня">
      <StatusStrip loading={loading} error={error} onRefresh={onRefresh} />

      <div className="grid grid-cols-4 gap-2 max-[620px]:grid-cols-2">
        <MetricCard label="Tasks" value={String(state?.tasks.length ?? 0)} />
        <MetricCard label="Reminders" value={String(state?.reminders.length ?? 0)} />
        <MetricCard label="Notes" value={String(state?.notes.length ?? 0)} />
        <MetricCard label="Focus" value={String(state?.focus.length ?? 0)} />
      </div>

      <div className="grid gap-2">
        {(state?.focus ?? []).slice(0, 5).map((item) => (
          <article
            key={`${item.type}-${item.detail}-${item.title}`}
            className="grid grid-cols-[86px_1fr] items-center gap-3 rounded-lg border border-zinc-700 bg-zinc-900 p-3"
          >
            <span className="text-xs font-black uppercase text-teal-300">{item.type}</span>
            <div>
              <strong className="block text-sm text-zinc-50">{item.title}</strong>
              <span className="mt-1 block text-xs text-zinc-400">{item.detail}</span>
            </div>
          </article>
        ))}
        {!loading && !state?.focus.length && (
          <article className="rounded-lg border border-zinc-700 bg-zinc-900 p-3 text-sm text-zinc-400">
            Focus block empty
          </article>
        )}
      </div>

      <div className="grid gap-2 rounded-lg border border-zinc-700 bg-zinc-900 p-3">
        <QuickForm
          icon={<ListChecks size={16} />}
          value={taskText}
          label="Task"
          onChange={setTaskText}
          onSubmit={submitTask}
        />
        <QuickForm
          icon={<NotebookPen size={16} />}
          value={noteText}
          label="Note"
          onChange={setNoteText}
          onSubmit={submitNote}
        />
        <QuickForm
          icon={<Bell size={16} />}
          value={reminderText}
          label="Reminder"
          onChange={setReminderText}
          onSubmit={submitReminder}
        />
        <PersonForm person={person} onChange={setPerson} onSubmit={submitPerson} />
      </div>

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
    <form className="grid grid-cols-[94px_1fr_1.4fr_44px] gap-2 max-[620px]:grid-cols-1" onSubmit={onSubmit}>
      <label className="flex items-center gap-2 text-xs font-black uppercase text-zinc-400">
        <Users size={16} />
        Person
      </label>
      <input
        className="min-w-0 rounded-lg border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm text-zinc-50 outline-none"
        value={person.name}
        onChange={(event) => onChange({ ...person, name: event.target.value })}
      />
      <input
        className="min-w-0 rounded-lg border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm text-zinc-50 outline-none"
        value={person.note}
        onChange={(event) => onChange({ ...person, note: event.target.value })}
      />
      <button
        className="grid min-h-10 place-items-center rounded-lg border border-teal-300 bg-teal-300 text-zinc-950"
        type="submit"
        aria-label="Add Person"
      >
        <Plus size={16} />
      </button>
    </form>
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
    <form className="grid grid-cols-[94px_1fr_44px] gap-2 max-[520px]:grid-cols-1" onSubmit={onSubmit}>
      <label className="flex items-center gap-2 text-xs font-black uppercase text-zinc-400">
        {icon}
        {label}
      </label>
      <input
        className="min-w-0 rounded-lg border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm text-zinc-50 outline-none"
        value={value}
        onChange={(event) => onChange(event.target.value)}
      />
      <button
        className="grid min-h-10 place-items-center rounded-lg border border-teal-300 bg-teal-300 text-zinc-950"
        type="submit"
        aria-label={`Add ${label}`}
      >
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
  );
}
