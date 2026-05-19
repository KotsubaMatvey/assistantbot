import { Activity, RefreshCw, TrendingUp } from "lucide-react";
import { useEffect, useState } from "react";
import { ActionButton } from "../ActionButton";
import { loadMiniAppMarkets, type MiniAppMarkets } from "../../domain/api";
import { eventBus } from "../../domain/events";

export function MarketsPanel() {
  const [markets, setMarkets] = useState<MiniAppMarkets | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function refreshMarkets() {
    setLoading(true);
    setError("");
    try {
      setMarkets(await loadMiniAppMarkets());
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Ошибка API рынков");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void refreshMarkets();
  }, []);

  const btc = markets?.quotes.find((quote) => quote.key === "btc");

  return (
    <section className="grid gap-4" aria-label="Рынки">
      <section className="glass-panel p-5">
        <span className="flex items-center gap-2 text-sm font-black text-[var(--muted)]">
          <TrendingUp size={18} />
          {btc?.name ?? "Bitcoin"}
        </span>
        <strong className="mt-3 block text-5xl font-black leading-none text-white">
          {btc?.value ? `${btc.value}${btc.unit}` : "нет данных"}
        </strong>
        <em className="mt-3 block text-sm not-italic text-[var(--accent)]">
          {btc?.change_percent ? `${btc.change_percent}%` : markets?.risk_regime ?? "загрузка"}
        </em>
      </section>

      {(loading || error) && (
        <div className="glass-panel glass-panel-tight p-3 text-sm text-[var(--muted)]">
          {loading ? "Загружаю актуальные данные" : error}
        </div>
      )}

      <div className="grid grid-cols-2 gap-2">
        {(markets?.quotes ?? []).map((quote, index) => (
          <article
            key={quote.key}
            className={index === 0 ? "record-row record-row-active" : "record-row"}
          >
            <span className="app-kicker">{quote.name}</span>
            <strong className="mt-2 block text-lg text-white">
              {quote.value ? `${quote.value}${quote.unit}` : "нет данных"}
            </strong>
            {quote.error && (
              <span className="mt-1 block text-xs text-[var(--danger)]">{quote.error}</span>
            )}
          </article>
        ))}
      </div>

      <div className="grid grid-cols-3 gap-2 max-[520px]:grid-cols-1">
        <ActionButton primary icon={<RefreshCw size={16} />} onClick={() => void refreshMarkets()}>
          Обновить
        </ActionButton>
        <ActionButton
          icon={<Activity size={16} />}
          onClick={() => eventBus.emit("command:send", { command: "markets" })}
        >
          Отчет в чат
        </ActionButton>
        <ActionButton
          icon={<TrendingUp size={16} />}
          onClick={() => eventBus.emit("command:send", { command: "market_brief" })}
        >
          Рыночный бриф
        </ActionButton>
      </div>
    </section>
  );
}
