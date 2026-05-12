import { Activity, TrendingUp } from "lucide-react";
import { ActionButton } from "../ActionButton";
import { eventBus } from "../../domain/events";

const markets = [
  ["BTC.D", "53.2%"],
  ["S&P 500", "5,108"],
  ["Nasdaq", "16,340"],
  ["Dow Jones", "39,120"],
];

export function MarketsPanel() {
  return (
    <section className="grid gap-3" aria-label="Рынки">
      <div className="rounded-lg border border-zinc-700 bg-zinc-900 p-5">
        <span className="flex items-center gap-2 text-sm font-black text-zinc-400">
          <TrendingUp size={18} />
          BTC
        </span>
        <strong className="mt-2 block text-4xl font-black leading-none text-zinc-50">$70,240</strong>
        <em className="mt-2 block text-sm not-italic text-teal-300">+1.45%</em>
      </div>
      <div className="grid grid-cols-2 gap-2">
        {markets.map(([label, value]) => (
          <article key={label} className="rounded-lg border border-zinc-700 bg-zinc-900 p-3">
            <span className="block text-xs font-black text-zinc-400">{label}</span>
            <strong className="mt-2 block text-lg text-zinc-50">{value}</strong>
          </article>
        ))}
      </div>
      <ActionButton
        primary
        icon={<Activity size={16} />}
        onClick={() => eventBus.emit("command:send", { command: "markets" })}
      >
        Свежие рынки
      </ActionButton>
    </section>
  );
}
