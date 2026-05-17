import { Database } from "lucide-react";
import { useState } from "react";
import { ActionButton } from "../ActionButton";
import { quickActions } from "../../domain/data";
import { eventBus } from "../../domain/events";

export function ShoppingPanel() {
  const [basket, setBasket] = useState("2x молоко 2.5 1 л\nяйца C1 10 шт\nсахар 1 кг");

  return (
    <section className="grid gap-3" aria-label="Покупки">
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
