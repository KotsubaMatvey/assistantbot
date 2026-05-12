import { Bell, ClipboardList, Database } from "lucide-react";
import type { ReactNode } from "react";
import { useState } from "react";
import { ActionButton } from "../ActionButton";
import { quickActions, shoppingMetrics } from "../../domain/data";
import { eventBus } from "../../domain/events";

export function ShoppingPanel() {
  const [basket, setBasket] = useState("2x молоко 2.5 1 л\nяйца C1 10 шт\nсахар 1 кг");

  return (
    <section className="grid gap-3" aria-label="Покупки">
      <div className="grid grid-cols-4 gap-2 max-[620px]:grid-cols-2">
        {shoppingMetrics.map((metric) => (
          <article key={metric.label} className="rounded-lg border border-zinc-700 bg-zinc-900 p-3">
            <span className="block text-xs font-black text-zinc-400">{metric.label}</span>
            <strong className="mt-2 block text-lg leading-tight text-zinc-50">{metric.value}</strong>
          </article>
        ))}
      </div>

      <div className="grid gap-3 rounded-lg border border-zinc-700 bg-zinc-900 p-3">
        <label className="text-xs font-black text-zinc-400" htmlFor="basket">
          Список покупок
        </label>
        <textarea
          id="basket"
          className="min-h-32 rounded-lg border border-zinc-700 bg-zinc-950 p-3 text-sm text-zinc-50 outline-none"
          value={basket}
          onChange={(event) => setBasket(event.target.value)}
        />
        <div className="grid grid-cols-2 gap-2 max-[420px]:grid-cols-1">
          <ActionButton primary onClick={() => eventBus.emit("basket:compare", { text: basket })}>
            Сравнить
          </ActionButton>
          <ActionButton
            icon={<Database size={16} />}
            onClick={() => eventBus.emit("command:send", { command: "pantry_deals" })}
          >
            Докупки
          </ActionButton>
        </div>
      </div>

      <div className="grid gap-2">
        <PriceRow
          title="Молоко 2.5 1 л x2"
          detail="Лучше: Магнит, акция, 109 ₽/л, совпадение 96%"
          price="180 ₽"
        />
        <PriceRow
          title="Яйца C1 10 шт"
          detail="Лучше: Smart, обычная цена, около средней"
          price="104 ₽"
        />
      </div>

      <div className="grid grid-cols-2 gap-2 max-[620px]:grid-cols-1">
        <SignalCard
          icon={<Database size={18} />}
          label="Pantry"
          title="Молоко заканчивается"
          copy="Проверить склад и список докупок."
          button="План"
          onClick={() => eventBus.emit("command:send", { command: "pantry_plan" })}
        />
        <SignalCard
          icon={<Bell size={18} />}
          label="Alerts"
          title="3 сигнала"
          copy="Проверить цены ниже порога и ниже средней."
          button="Проверить"
          onClick={() => eventBus.emit("command:send", { command: "check_alerts" })}
        />
      </div>

      <div className="grid grid-cols-4 gap-2 max-[620px]:grid-cols-2">
        {quickActions.map((action) => (
          <ActionButton
            key={action.command}
            icon={action.icon}
            onClick={() => eventBus.emit("command:send", { command: action.command })}
          >
            {action.label}
          </ActionButton>
        ))}
      </div>
    </section>
  );
}

function PriceRow({ title, detail, price }: { title: string; detail: string; price: string }) {
  return (
    <article className="flex items-center justify-between gap-4 rounded-lg border border-zinc-700 bg-zinc-900 p-3 max-[520px]:items-start max-[520px]:flex-col">
      <div>
        <strong className="block text-zinc-50">{title}</strong>
        <span className="mt-1 block text-sm text-zinc-400">{detail}</span>
      </div>
      <b className="whitespace-nowrap text-teal-300">{price}</b>
    </article>
  );
}

function SignalCard({
  icon,
  label,
  title,
  copy,
  button,
  onClick,
}: {
  icon: ReactNode;
  label: string;
  title: string;
  copy: string;
  button: string;
  onClick: () => void;
}) {
  return (
    <article className="rounded-lg border border-zinc-700 bg-zinc-900 p-3">
      <span className="flex items-center gap-2 text-xs font-black text-zinc-400">
        {icon}
        {label}
      </span>
      <strong className="mt-2 block text-zinc-50">{title}</strong>
      <p className="my-3 text-sm leading-5 text-zinc-400">{copy}</p>
      <ActionButton icon={<ClipboardList size={16} />} onClick={onClick}>
        {button}
      </ActionButton>
    </article>
  );
}
