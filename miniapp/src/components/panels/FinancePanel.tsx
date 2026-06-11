import { ArrowDownLeft, ArrowUpRight, Plus, ReceiptText, Repeat, Wallet } from "lucide-react";
import type { CSSProperties, FormEvent } from "react";
import { useMemo, useState } from "react";
import { financeActions } from "../../domain/data";
import type { MiniAppState } from "../../domain/api";
import { eventBus } from "../../domain/events";

type FinancePanelProps = {
  state?: MiniAppState["finance"];
  loading: boolean;
  error: string;
  onMutate: (path: string, body: Record<string, unknown>) => Promise<void>;
};

type AddKind = "expense" | "income" | "account" | "subscription" | "receipt";

const addKinds: { id: AddKind; label: string }[] = [
  { id: "expense", label: "Расход" },
  { id: "income", label: "Доход" },
  { id: "account", label: "Счёт" },
  { id: "subscription", label: "Подписка" },
  { id: "receipt", label: "Чек" },
];

type BudgetSlice = {
  name: string;
  amount: string;
  value: number;
  percent: number;
  color: string;
};

export function FinancePanel({ state, loading, error, onMutate }: FinancePanelProps) {
  const [addKind, setAddKind] = useState<AddKind>("expense");
  const [amount, setAmount] = useState("");
  const [category, setCategory] = useState("");
  const [note, setNote] = useState("");
  const [receipt, setReceipt] = useState("");

  const budgetSlices = useMemo(() => getBudgetSlices(state?.budget.categories ?? []), [state]);
  const chartStyle = useMemo(() => budgetChartStyle(budgetSlices), [budgetSlices]);
  const budgetProgress = getBudgetProgress(state?.budget.spent, state?.budget.limit);
  const hasBudgetLimit = parseMoney(state?.budget.limit ?? "") > 0;

  async function submitAdd(event: FormEvent) {
    event.preventDefault();
    if (addKind === "receipt") {
      if (!receipt.trim()) {
        return;
      }
      await onMutate("/api/miniapp/receipt", { text: receipt });
      setReceipt("");
      return;
    }
    if (addKind === "expense" || addKind === "income") {
      if (!amount.trim() || !category.trim()) {
        return;
      }
      await onMutate("/api/miniapp/finance/transaction", {
        kind: addKind,
        amount: amount.trim(),
        category: category.trim(),
        note: note.trim(),
      });
    }
    if (addKind === "account") {
      if (!category.trim() || !amount.trim()) {
        return;
      }
      await onMutate("/api/miniapp/finance/account", {
        name: category.trim(),
        balance: amount.trim(),
      });
    }
    if (addKind === "subscription") {
      if (!category.trim() || !amount.trim()) {
        return;
      }
      await onMutate("/api/miniapp/finance/subscription", {
        name: category.trim(),
        amount: amount.trim(),
      });
    }
    setAmount("");
    setCategory("");
    setNote("");
  }

  const transactions = (state?.transactions ?? []).slice(0, 8);
  const accounts = state?.accounts ?? [];
  const subscriptions = state?.subscriptions ?? [];

  return (
    <section className="grid gap-3.5" aria-label="Бюджет">
      {(loading || error) && (
        <div className={error ? "notice notice-error" : "notice"}>
          <span>{loading ? "Загружаю данные…" : error}</span>
        </div>
      )}

      <section className="card card-pad grid gap-3.5">
        <div className="card-title">
          <span>Обзор</span>
          <span className="card-title-meta">{state?.month ?? ""}</span>
        </div>
        <div className="grid grid-cols-4 gap-2 max-[460px]:grid-cols-2">
          <Stat label="Баланс" value={state?.balance ?? "0.00"} />
          <Stat label="Расходы" value={state?.expenses ?? "0.00"} tone="danger" />
          <Stat label="Доходы" value={state?.income ?? "0.00"} tone="success" />
          <Stat label="Прогноз" value={state?.forecast ?? "0.00"} />
        </div>
        {hasBudgetLimit && (
          <div className="grid gap-2">
            <div className="flex items-center justify-between gap-3 text-[12.5px]">
              <span className="muted-text font-medium">
                Бюджет: {state?.budget.spent} из {state?.budget.limit}
              </span>
              <strong className="text-[var(--text)]">{Math.round(budgetProgress)}%</strong>
            </div>
            <div
              className={budgetProgress >= 100 ? "progress progress-over" : "progress"}
              aria-hidden="true"
            >
              <span style={{ width: `${Math.min(100, budgetProgress)}%` }} />
            </div>
          </div>
        )}
      </section>

      {budgetSlices.length > 0 && (
        <section className="card card-pad grid gap-3.5">
          <div className="card-title">
            <span>Категории</span>
            <span className="card-title-meta">{state?.month ?? ""}</span>
          </div>
          <div className="flex items-center gap-5 max-[460px]:flex-col">
            <div className="donut" style={chartStyle}>
              <div className="donut-center">
                <span>Остаток</span>
                <strong>{state?.budget.remaining ?? "0.00"}</strong>
              </div>
            </div>
            <div className="grid min-w-0 flex-1 gap-2.5 self-stretch">
              {budgetSlices.slice(0, 5).map((slice) => (
                <div className="cat-row" key={slice.name}>
                  <div className="cat-row-head">
                    <span>
                      <i
                        className="legend-dot"
                        style={{ background: slice.color, color: slice.color }}
                      />
                      {slice.name}
                    </span>
                    <strong>{slice.amount}</strong>
                  </div>
                  <div className="cat-bar" aria-hidden="true">
                    <span
                      style={{
                        background: slice.color,
                        color: slice.color,
                        width: `${Math.round(slice.percent)}%`,
                      }}
                    />
                  </div>
                </div>
              ))}
            </div>
          </div>
        </section>
      )}

      <form className="card card-pad grid gap-2.5" onSubmit={(event) => void submitAdd(event)}>
        <div className="segmented" role="tablist" aria-label="Тип записи">
          {addKinds.map((kind) => (
            <button
              key={kind.id}
              className={addKind === kind.id ? "segment segment-active" : "segment"}
              type="button"
              onClick={() => setAddKind(kind.id)}
            >
              {kind.label}
            </button>
          ))}
        </div>
        {addKind === "receipt" ? (
          <div className="grid gap-2">
            <textarea
              className="input min-h-24 resize-none"
              value={receipt}
              placeholder={"магазин: Магнит\nмолоко 89.90\nхлеб 45"}
              onChange={(event) => setReceipt(event.target.value)}
            />
            <button className="btn btn-primary" type="submit">
              <ReceiptText size={15} />
              <span>Сохранить чек</span>
            </button>
          </div>
        ) : (
          <div className="grid grid-cols-[minmax(0,1fr)_minmax(0,1.4fr)_42px] gap-2 max-[460px]:grid-cols-[minmax(0,1fr)_42px]">
            <input
              className="input"
              inputMode="decimal"
              value={amount}
              placeholder={addKind === "account" ? "Баланс" : "Сумма"}
              onChange={(event) => setAmount(event.target.value)}
            />
            <input
              className="input max-[460px]:col-start-1"
              value={category}
              placeholder={
                addKind === "expense"
                  ? "Категория"
                  : addKind === "income"
                    ? "Источник"
                    : "Название"
              }
              onChange={(event) => setCategory(event.target.value)}
            />
            {(addKind === "expense" || addKind === "income") && (
              <input
                className="input col-span-2 max-[460px]:col-span-1 max-[460px]:col-start-1"
                value={note}
                placeholder="Комментарий (не обязательно)"
                onChange={(event) => setNote(event.target.value)}
              />
            )}
            <button
              className="chat-send col-start-3 row-start-1 max-[460px]:col-start-2"
              type="submit"
              aria-label="Сохранить"
            >
              <Plus size={18} />
            </button>
          </div>
        )}
      </form>

      {(accounts.length > 0 || subscriptions.length > 0) && (
        <section className="card card-pad grid gap-2.5">
          <div className="card-title">
            <span>Счета и подписки</span>
          </div>
          <div className="grid gap-2">
            {accounts.map((item) => (
              <article key={`account-${item.id}`} className="row">
                <span className="row-icon">
                  <Wallet size={15} />
                </span>
                <div className="row-body">
                  <span className="row-title">{item.name}</span>
                  <span className="row-sub">Счёт</span>
                </div>
                <span className="row-meta">
                  {item.balance} {item.currency}
                </span>
              </article>
            ))}
            {subscriptions.map((item) => (
              <article key={`subscription-${item.id}`} className="row">
                <span className="row-icon">
                  <Repeat size={15} />
                </span>
                <div className="row-body">
                  <span className="row-title">{item.name}</span>
                  <span className="row-sub">Подписка · {item.cycle}</span>
                </div>
                <span className="row-meta">{item.amount}</span>
              </article>
            ))}
          </div>
        </section>
      )}

      <section className="card card-pad grid gap-2.5">
        <div className="card-title">
          <span>Операции</span>
          <span className="card-title-meta">{state?.month ?? ""}</span>
        </div>
        <div className="grid gap-2">
          {transactions.map((item) => (
            <article key={item.id} className="row">
              <span
                className="row-icon"
                style={
                  item.kind === "income"
                    ? { background: "var(--success-soft)", color: "var(--success)" }
                    : { background: "var(--danger-soft)", color: "var(--danger)" }
                }
              >
                {item.kind === "income" ? (
                  <ArrowDownLeft size={15} />
                ) : (
                  <ArrowUpRight size={15} />
                )}
              </span>
              <div className="row-body">
                <span className="row-title">{item.category}</span>
                <span className="row-sub">{item.note || formatDate(item.created_at)}</span>
              </div>
              <span
                className="row-meta"
                style={{ color: item.kind === "income" ? "var(--success)" : "var(--text)" }}
              >
                {item.kind === "income" ? "+" : "−"}
                {item.amount}
              </span>
            </article>
          ))}
          {!loading && transactions.length === 0 && (
            <article className="empty">
              <strong>Операций пока нет</strong>
              <span>Добавь расход, доход или чек выше.</span>
            </article>
          )}
        </div>
      </section>

      <div className="flex flex-wrap gap-2">
        {financeActions.map((action) => (
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
  );
}

function Stat({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone?: "success" | "danger";
}) {
  return (
    <article className="stat">
      <span>{label}</span>
      <strong
        style={
          tone === "success"
            ? { color: "var(--success)" }
            : tone === "danger"
              ? { color: "var(--danger)" }
              : undefined
        }
      >
        {value}
      </strong>
    </article>
  );
}

const budgetColors = ["#8b7bff", "#2dd4bf", "#ff5fa2", "#ffb35c", "#5ea2ff"];

function getBudgetSlices(categories: { name: string; amount: string }[]): BudgetSlice[] {
  const items = categories
    .map((category, index) => ({
      name: category.name,
      amount: category.amount,
      value: parseMoney(category.amount),
      color: budgetColors[index % budgetColors.length],
    }))
    .filter((category) => category.value > 0);
  const total = items.reduce((sum, category) => sum + category.value, 0);
  if (total <= 0) {
    return [];
  }
  return items.map((category) => ({
    ...category,
    percent: Math.max(3, (category.value / total) * 100),
  }));
}

function budgetChartStyle(slices: BudgetSlice[]): CSSProperties {
  if (slices.length === 0) {
    return { background: "conic-gradient(var(--surface-3) 0 100%)" };
  }
  let cursor = 0;
  const total = slices.reduce((sum, slice) => sum + slice.value, 0);
  const stops = slices.map((slice) => {
    const start = cursor;
    cursor += (slice.value / total) * 100;
    return `${slice.color} ${start.toFixed(1)}% ${cursor.toFixed(1)}%`;
  });
  return { background: `conic-gradient(${stops.join(", ")})` };
}

function getBudgetProgress(spent?: string, limit?: string): number {
  const spentValue = parseMoney(spent ?? "");
  const limitValue = parseMoney(limit ?? "");
  if (limitValue <= 0) {
    return 0;
  }
  return Math.max(0, (spentValue / limitValue) * 100);
}

function parseMoney(value: string): number {
  return Number.parseFloat(value.replace(",", ".")) || 0;
}

function formatDate(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleDateString("ru-RU", { day: "numeric", month: "short" });
}
