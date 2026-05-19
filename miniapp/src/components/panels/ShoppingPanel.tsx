import { Database } from "lucide-react";
import { useState } from "react";
import { ActionButton } from "../ActionButton";
import { quickActions, shoppingMetrics } from "../../domain/data";
import { eventBus } from "../../domain/events";

export function ShoppingPanel() {
  const [basket, setBasket] = useState("2x молоко 2.5% 1 л\nяйца C1 10 шт\nсахар 1 кг");

  return (
    <section className="grid gap-4" aria-label="Покупки">
      <section className="glass-panel p-4">
        <div className="section-title">
          <span>Статус запасов</span>
          <span className="text-sm text-[var(--accent)]">корзина готова</span>
        </div>
        <div className="mt-4 grid grid-cols-4 gap-2 max-[620px]:grid-cols-2">
          {shoppingMetrics.map((metric) => (
            <article className="metric-card" key={metric.label}>
              <span>{metric.label}</span>
              <strong>{metric.value}</strong>
            </article>
          ))}
        </div>
      </section>

      <section className="glass-panel glass-panel-tight grid gap-3 p-3">
        <label className="app-kicker" htmlFor="basket">
          Поход в магазин
        </label>
        <textarea
          id="basket"
          className="surface-input min-h-36 p-3 text-sm"
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
            Акции
          </ActionButton>
        </div>
      </section>

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
