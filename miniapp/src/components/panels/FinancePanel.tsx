import { CreditCard, Plus, ReceiptText, Repeat, TrendingUp, Wallet } from "lucide-react";
import type { CSSProperties, FormEvent, ReactNode } from "react";
import { useMemo, useState } from "react";
import { ActionButton } from "../ActionButton";
import { financeActions } from "../../domain/data";
import type { MiniAppState } from "../../domain/api";
import { eventBus } from "../../domain/events";

type FinancePanelProps = {
  state?: MiniAppState["finance"];
  loading: boolean;
  error: string;
  onMutate: (path: string, body: Record<string, unknown>) => Promise<void>;
};

export function FinancePanel({ state, loading, error, onMutate }: FinancePanelProps) {
  const [expense, setExpense] = useState({ amount: "", category: "", note: "" });
  const [income, setIncome] = useState({ amount: "", category: "", note: "" });
  const [account, setAccount] = useState({ name: "", balance: "" });
  const [subscription, setSubscription] = useState({ name: "", amount: "" });
  const [receipt, setReceipt] = useState("");
  const chartStyle = useMemo(() => budgetChartStyle(state?.budget.categories ?? []), [state]);

  async function submitTransaction(kind: "expense" | "income", event: FormEvent) {
    event.preventDefault();
    const value = kind === "expense" ? expense : income;
    if (!value.amount.trim() || !value.category.trim()) {
      return;
    }
    await onMutate("/api/miniapp/finance/transaction", { kind, ...value });
    if (kind === "expense") {
      setExpense({ amount: "", category: "", note: "" });
    } else {
      setIncome({ amount: "", category: "", note: "" });
    }
  }

  async function submitAccount(event: FormEvent) {
    event.preventDefault();
    if (!account.name.trim() || !account.balance.trim()) {
      return;
    }
    await onMutate("/api/miniapp/finance/account", account);
    setAccount({ name: "", balance: "" });
  }

  async function submitSubscription(event: FormEvent) {
    event.preventDefault();
    if (!subscription.name.trim() || !subscription.amount.trim()) {
      return;
    }
    await onMutate("/api/miniapp/finance/subscription", subscription);
    setSubscription({ name: "", amount: "" });
  }

  async function submitReceipt(event: FormEvent) {
    event.preventDefault();
    if (!receipt.trim()) {
      return;
    }
    await onMutate("/api/miniapp/receipt", { text: receipt });
    setReceipt("");
  }

  return (
    <section className="grid gap-4" aria-label="Бюджет">
      {(loading || error) && (
        <div className="glass-panel glass-panel-tight p-3 text-sm text-[var(--muted)]">
          {loading ? "Загружаю актуальные данные" : error}
        </div>
      )}

      <section className="glass-panel grid grid-cols-[1fr_220px] gap-4 p-4 max-[680px]:grid-cols-1">
        <div>
          <div className="section-title">
            <span>Обзор бюджета</span>
            <span className="text-sm text-[var(--accent-2)]">{state?.month ?? "Текущий"}</span>
          </div>
          <div className="mt-4 grid grid-cols-2 gap-2">
            <MetricCard label="Баланс" value={state?.balance ?? "0.00"} />
            <MetricCard label="Расходы" value={state?.expenses ?? "0.00"} />
            <MetricCard label="Доходы" value={state?.income ?? "0.00"} />
            <MetricCard label="Прогноз" value={state?.forecast ?? "0.00"} />
          </div>
        </div>
        <div className="grid place-items-center">
          <div className="budget-ring relative size-44 rounded-full" style={chartStyle}>
            <div className="absolute inset-10 grid place-items-center rounded-full bg-[var(--bg)] text-center">
              <span className="app-kicker">Остаток</span>
              <strong className="text-lg font-black text-white">
                {state?.budget.remaining ?? "0.00"}
              </strong>
            </div>
          </div>
        </div>
      </section>

      <section className="glass-panel glass-panel-tight grid gap-3 p-3">
        <MoneyForm
          icon={<CreditCard size={16} />}
          title="Расход"
          amount={expense.amount}
          category={expense.category}
          note={expense.note}
          onAmount={(amount) => setExpense((current) => ({ ...current, amount }))}
          onCategory={(category) => setExpense((current) => ({ ...current, category }))}
          onNote={(note) => setExpense((current) => ({ ...current, note }))}
          onSubmit={(event) => void submitTransaction("expense", event)}
        />
        <MoneyForm
          icon={<TrendingUp size={16} />}
          title="Доход"
          amount={income.amount}
          category={income.category}
          note={income.note}
          onAmount={(amount) => setIncome((current) => ({ ...current, amount }))}
          onCategory={(category) => setIncome((current) => ({ ...current, category }))}
          onNote={(note) => setIncome((current) => ({ ...current, note }))}
          onSubmit={(event) => void submitTransaction("income", event)}
        />
        <PairForm
          icon={<Wallet size={16} />}
          title="Счет"
          first={account.name}
          second={account.balance}
          onFirst={(name) => setAccount((current) => ({ ...current, name }))}
          onSecond={(balance) => setAccount((current) => ({ ...current, balance }))}
          onSubmit={(event) => void submitAccount(event)}
        />
        <PairForm
          icon={<Repeat size={16} />}
          title="Подписка"
          first={subscription.name}
          second={subscription.amount}
          onFirst={(name) => setSubscription((current) => ({ ...current, name }))}
          onSecond={(amount) => setSubscription((current) => ({ ...current, amount }))}
          onSubmit={(event) => void submitSubscription(event)}
        />
        <form className="grid gap-2" onSubmit={(event) => void submitReceipt(event)}>
          <label className="flex items-center gap-2 text-xs font-black uppercase text-[var(--muted)]">
            <ReceiptText size={16} />
            Чек
          </label>
          <textarea
            className="surface-input min-h-24 p-3 text-sm"
            value={receipt}
            placeholder="Вставь текст чека"
            onChange={(event) => setReceipt(event.target.value)}
          />
          <button className="action-button action-button-primary" type="submit">
            <Plus size={16} />
            Сохранить чек
          </button>
        </form>
      </section>

      <div className="grid gap-2">
        {(state?.accounts ?? []).map((item) => (
          <DataRow key={item.id} left={item.name} right={`${item.balance} ${item.currency}`} />
        ))}
        {(state?.subscriptions ?? []).map((item) => (
          <DataRow key={item.id} left={item.name} right={`${item.amount} / ${item.cycle}`} />
        ))}
        {(state?.transactions ?? []).slice(0, 6).map((item) => (
          <DataRow
            key={item.id}
            left={`${translateTransactionKind(item.kind)}: ${item.category}`}
            right={item.amount}
            detail={item.note}
          />
        ))}
      </div>

      <div className="grid grid-cols-3 gap-2 max-[620px]:grid-cols-2">
        {financeActions.map((action) => (
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

function MetricCard({ label, value }: { label: string; value: string }) {
  return (
    <article className="metric-card">
      <span>{label}</span>
      <strong>{value}</strong>
    </article>
  );
}

function MoneyForm({
  icon,
  title,
  amount,
  category,
  note,
  onAmount,
  onCategory,
  onNote,
  onSubmit,
}: {
  icon: ReactNode;
  title: string;
  amount: string;
  category: string;
  note: string;
  onAmount: (value: string) => void;
  onCategory: (value: string) => void;
  onNote: (value: string) => void;
  onSubmit: (event: FormEvent) => void;
}) {
  return (
    <form
      className="grid grid-cols-[112px_1fr_1fr_1.35fr_44px] gap-2 max-[720px]:grid-cols-1"
      onSubmit={onSubmit}
    >
      <label className="flex items-center gap-2 text-xs font-black uppercase text-[var(--muted)]">
        {icon}
        {title}
      </label>
      <input
        className="surface-input px-3 py-2 text-sm"
        inputMode="decimal"
        value={amount}
        placeholder="Сумма"
        onChange={(event) => onAmount(event.target.value)}
      />
      <input
        className="surface-input px-3 py-2 text-sm"
        value={category}
        placeholder="Категория"
        onChange={(event) => onCategory(event.target.value)}
      />
      <input
        className="surface-input px-3 py-2 text-sm"
        value={note}
        placeholder="Комментарий"
        onChange={(event) => onNote(event.target.value)}
      />
      <button className="icon-button !h-11 !w-full" type="submit" aria-label={`Сохранить: ${title}`}>
        <Plus size={16} />
      </button>
    </form>
  );
}

function PairForm({
  icon,
  title,
  first,
  second,
  onFirst,
  onSecond,
  onSubmit,
}: {
  icon: ReactNode;
  title: string;
  first: string;
  second: string;
  onFirst: (value: string) => void;
  onSecond: (value: string) => void;
  onSubmit: (event: FormEvent) => void;
}) {
  return (
    <form className="grid grid-cols-[112px_1fr_1fr_44px] gap-2 max-[620px]:grid-cols-1" onSubmit={onSubmit}>
      <label className="flex items-center gap-2 text-xs font-black uppercase text-[var(--muted)]">
        {icon}
        {title}
      </label>
      <input
        className="surface-input px-3 py-2 text-sm"
        value={first}
        placeholder="Название"
        onChange={(event) => onFirst(event.target.value)}
      />
      <input
        className="surface-input px-3 py-2 text-sm"
        inputMode="decimal"
        value={second}
        placeholder="Сумма"
        onChange={(event) => onSecond(event.target.value)}
      />
      <button className="icon-button !h-11 !w-full" type="submit" aria-label={`Сохранить: ${title}`}>
        <Plus size={16} />
      </button>
    </form>
  );
}

function DataRow({ left, right, detail = "" }: { left: string; right: string; detail?: string }) {
  return (
    <article className="record-row">
      <div className="flex items-start justify-between gap-4 max-[520px]:flex-col">
        <div className="min-w-0">
          <strong className="block truncate text-sm text-white">{left}</strong>
          {detail && <span className="muted-text mt-1 block truncate text-xs">{detail}</span>}
        </div>
        <b className="whitespace-nowrap text-[var(--accent)]">{right}</b>
      </div>
    </article>
  );
}

function translateTransactionKind(kind: string): string {
  if (kind === "expense") {
    return "Расход";
  }
  if (kind === "income") {
    return "Доход";
  }
  return kind;
}

function budgetChartStyle(categories: { amount: string }[]): CSSProperties {
  const amounts = categories.map((category) => Number.parseFloat(category.amount) || 0);
  const total = amounts.reduce((sum, value) => sum + value, 0);
  if (total <= 0) {
    return {
      background:
        "conic-gradient(var(--accent) 0 65%, var(--accent-2) 65% 82%, #8f6cf0 82% 100%)",
    };
  }
  let cursor = 0;
  const colors = ["var(--accent)", "var(--accent-2)", "#8f6cf0", "#d3d3d3"];
  const stops = amounts.map((amount, index) => {
    const start = cursor;
    cursor += (amount / total) * 100;
    return `${colors[index % colors.length]} ${start.toFixed(1)}% ${cursor.toFixed(1)}%`;
  });
  return { background: `conic-gradient(${stops.join(", ")})` };
}
