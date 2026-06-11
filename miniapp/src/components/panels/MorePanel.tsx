import { Home, RefreshCw, ShoppingBasket, TrendingDown, TrendingUp } from "lucide-react";
import { useEffect, useState } from "react";
import { serviceActions, shoppingActions } from "../../domain/data";
import { loadMiniAppMarkets, type MiniAppMarkets } from "../../domain/api";
import { eventBus } from "../../domain/events";
import type { HomeScreenStatus } from "../../types/telegram";

type MorePanelProps = {
  homeStatus: HomeScreenStatus | "";
  onAddHomeShortcut: () => void;
};

function formatQuoteValue(value: string, unit: string): string {
  if (!value) {
    return "—";
  }
  const parsed = Number.parseFloat(value);
  if (!Number.isFinite(parsed)) {
    return `${value}${unit}`;
  }
  const formatted = parsed.toLocaleString("ru-RU", {
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  });
  return unit ? `${formatted} ${unit.trim()}` : formatted;
}

export function MorePanel({ homeStatus, onAddHomeShortcut }: MorePanelProps) {
  const [basket, setBasket] = useState("");
  const [markets, setMarkets] = useState<MiniAppMarkets | null>(null);
  const [marketsLoading, setMarketsLoading] = useState(false);
  const [marketsError, setMarketsError] = useState("");

  async function refreshMarkets() {
    setMarketsLoading(true);
    setMarketsError("");
    try {
      setMarkets(await loadMiniAppMarkets());
    } catch (caught) {
      setMarketsError(caught instanceof Error ? caught.message : "Ошибка API рынков");
    } finally {
      setMarketsLoading(false);
    }
  }

  useEffect(() => {
    void refreshMarkets();
  }, []);

  return (
    <section className="grid gap-3.5" aria-label="Ещё">
      <section className="card card-pad grid gap-2.5">
        <div className="card-title">
          <span>Покупки</span>
          <span className="card-title-meta">сравнение корзины</span>
        </div>
        <textarea
          className="input min-h-24 resize-none"
          value={basket}
          placeholder={"2x молоко 2.5% 1 л\nяйца C1 10 шт\nсахар 1 кг"}
          onChange={(event) => setBasket(event.target.value)}
        />
        <button
          className="btn btn-primary"
          type="button"
          onClick={() => eventBus.emit("basket:compare", { text: basket })}
        >
          <ShoppingBasket size={15} />
          <span>Сравнить цены</span>
        </button>
        <div className="flex flex-wrap gap-2">
          {shoppingActions.map((action) => (
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

      <section className="card card-pad grid gap-2.5">
        <div className="card-title">
          <span>Рынки</span>
          <button
            className="icon-btn !h-8 !w-8"
            type="button"
            aria-label="Обновить котировки"
            onClick={() => void refreshMarkets()}
          >
            <RefreshCw size={14} className={marketsLoading ? "animate-spin" : undefined} />
          </button>
        </div>
        {marketsError && <div className="notice notice-error">{marketsError}</div>}
        <div className="grid grid-cols-2 gap-2">
          {(markets?.quotes ?? []).map((quote) => {
            const change = Number.parseFloat(quote.change_percent);
            const hasChange = Number.isFinite(change);
            const negative = hasChange && change < 0;
            return (
              <article key={quote.key} className="stat">
                <span>{quote.name}</span>
                <strong>{formatQuoteValue(quote.value, quote.unit)}</strong>
                {hasChange && (
                  <em
                    className="mt-1 flex items-center gap-1 text-[12px] font-semibold not-italic"
                    style={{ color: negative ? "var(--danger)" : "var(--success)" }}
                  >
                    {negative ? <TrendingDown size={12} /> : <TrendingUp size={12} />}
                    {change.toFixed(2)}%
                  </em>
                )}
              </article>
            );
          })}
          {!marketsLoading && !marketsError && (markets?.quotes ?? []).length === 0 && (
            <article className="empty col-span-2">
              <strong>Котировки не загружены</strong>
              <span>Нажми обновить, чтобы подтянуть рыночные данные.</span>
            </article>
          )}
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            className="chip"
            type="button"
            onClick={() => eventBus.emit("command:send", { command: "markets" })}
          >
            Отчёт в чат
          </button>
          <button
            className="chip"
            type="button"
            onClick={() => eventBus.emit("command:send", { command: "market_brief" })}
          >
            Рыночный бриф
          </button>
        </div>
      </section>

      <section className="card card-pad grid gap-2.5">
        <div className="card-title">
          <span>Сервис</span>
        </div>
        <div className="flex flex-wrap gap-2">
          {serviceActions.map((action) => (
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
        <button
          className="btn"
          type="button"
          disabled={homeStatus === "unsupported" || homeStatus === "added"}
          onClick={onAddHomeShortcut}
        >
          <Home size={15} />
          <span>
            {homeStatus === "added" ? "Уже на главном экране" : "Добавить на главный экран"}
          </span>
        </button>
      </section>
    </section>
  );
}
