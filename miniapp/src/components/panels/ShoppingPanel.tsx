import { Database } from "lucide-react";
import { useState } from "react";
import { ActionButton } from "../ActionButton";
import { quickActions, shoppingMetrics } from "../../domain/data";
import { eventBus } from "../../domain/events";

export function ShoppingPanel() {
  const [basket, setBasket] = useState("2x milk 2.5 1L\neggs C1 10 pcs\nsugar 1kg");

  return (
    <section className="grid gap-4" aria-label="Pantry">
      <section className="glass-panel p-4">
        <div className="section-title">
          <span>Pantry Status</span>
          <span className="text-sm text-[var(--accent)]">basket ready</span>
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
          Grocery Run
        </label>
        <textarea
          id="basket"
          className="surface-input min-h-36 p-3 text-sm"
          value={basket}
          onChange={(event) => setBasket(event.target.value)}
        />
        <div className="grid grid-cols-2 gap-2 max-[420px]:grid-cols-1">
          <ActionButton primary onClick={() => eventBus.emit("basket:compare", { text: basket })}>
            Compare
          </ActionButton>
          <ActionButton
            icon={<Database size={16} />}
            onClick={() => eventBus.emit("command:send", { command: "pantry_deals" })}
          >
            Deals
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
