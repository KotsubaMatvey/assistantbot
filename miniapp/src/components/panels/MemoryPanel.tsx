import { CalendarCheck } from "lucide-react";
import { ActionButton } from "../ActionButton";
import { eventBus } from "../../domain/events";

const timeline = [
  ["08:00", "Утренний market-watch отправлен в Telegram."],
  ["09:30", "Корзина сохранена, цены обновлены по выбранным магазинам."],
  ["12:10", "Сводка сессии добавлена в локальную память."],
];

export function MemoryPanel() {
  return (
    <section className="grid gap-3" aria-label="Память">
      <div className="grid gap-2">
        {timeline.map(([time, copy]) => (
          <article
            key={time}
            className="grid grid-cols-[54px_1fr] gap-3 rounded-lg border border-zinc-700 bg-zinc-900 p-3"
          >
            <time className="text-xs font-black text-zinc-400">{time}</time>
            <p className="text-sm leading-5 text-zinc-50">{copy}</p>
          </article>
        ))}
      </div>
      <ActionButton
        primary
        icon={<CalendarCheck size={16} />}
        onClick={() => eventBus.emit("command:send", { command: "agenda" })}
      >
        Открыть agenda
      </ActionButton>
    </section>
  );
}
