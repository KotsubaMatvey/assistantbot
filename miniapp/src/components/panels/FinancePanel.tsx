import { CreditCard, Plus, ReceiptText, Repeat, TrendingUp, Wallet } from "lucide-react";
import type { FormEvent, ReactNode } from "react";
import { useState } from "react";
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
    <section className="grid gap-3" aria-label="Финансы">
      {(loading || error) && (
        <div className="rounded-lg border border-zinc-700 bg-zinc-900 p-3 text-sm text-zinc-400">
          {loading ? "Loading live data" : error}
        </div>
      )}

      <div className="grid grid-cols-4 gap-2 max-[620px]:grid-cols-2">
        <MetricCard label="Баланс" value={state?.balance ?? "0.00"} />
        <MetricCard label="Расходы" value={state?.expenses ?? "0.00"} />
        <MetricCard label="Доходы" value={state?.income ?? "0.00"} />
        <MetricCard label="Прогноз" value={state?.forecast ?? "0.00"} />
      </div>

      <div className="grid gap-3 rounded-lg border border-zinc-700 bg-zinc-900 p-3">
        <MoneyForm
          icon={<CreditCard size={16} />}
          title="Expense"
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
          title="Income"
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
          title="Account"
          first={account.name}
          second={account.balance}
          onFirst={(name) => setAccount((current) => ({ ...current, name }))}
          onSecond={(balance) => setAccount((current) => ({ ...current, balance }))}
          onSubmit={(event) => void submitAccount(event)}
        />
        <PairForm
          icon={<Repeat size={16} />}
          title="Subscription"
          first={subscription.name}
          second={subscription.amount}
          onFirst={(name) => setSubscription((current) => ({ ...current, name }))}
          onSecond={(amount) => setSubscription((current) => ({ ...current, amount }))}
          onSubmit={(event) => void submitSubscription(event)}
        />
        <form className="grid gap-2" onSubmit={(event) => void submitReceipt(event)}>
          <label className="flex items-center gap-2 text-xs font-black uppercase text-zinc-400">
            <ReceiptText size={16} />
            Receipt
          </label>
          <textarea
            className="min-h-24 rounded-lg border border-zinc-700 bg-zinc-950 p-3 text-sm text-zinc-50 outline-none"
            value={receipt}
            onChange={(event) => setReceipt(event.target.value)}
          />
          <button
            className="flex min-h-10 items-center justify-center gap-2 rounded-lg border border-teal-300 bg-teal-300 px-3 text-sm font-black text-zinc-950"
            type="submit"
          >
            <Plus size={16} />
            Save receipt
          </button>
        </form>
      </div>

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
            left={`${item.kind}: ${item.category}`}
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
    <article className="rounded-lg border border-zinc-700 bg-zinc-900 p-3">
      <span className="block text-xs font-black text-zinc-400">{label}</span>
      <strong className="mt-2 block text-lg leading-tight text-zinc-50">{value}</strong>
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
    <form className="grid grid-cols-[118px_1fr_1fr_1.4fr_44px] gap-2 max-[720px]:grid-cols-1" onSubmit={onSubmit}>
      <label className="flex items-center gap-2 text-xs font-black uppercase text-zinc-400">
        {icon}
        {title}
      </label>
      <input
        className="min-w-0 rounded-lg border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm text-zinc-50 outline-none"
        inputMode="decimal"
        value={amount}
        onChange={(event) => onAmount(event.target.value)}
      />
      <input
        className="min-w-0 rounded-lg border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm text-zinc-50 outline-none"
        value={category}
        onChange={(event) => onCategory(event.target.value)}
      />
      <input
        className="min-w-0 rounded-lg border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm text-zinc-50 outline-none"
        value={note}
        onChange={(event) => onNote(event.target.value)}
      />
      <button
        className="grid min-h-10 place-items-center rounded-lg border border-teal-300 bg-teal-300 text-zinc-950"
        type="submit"
        aria-label={`Save ${title}`}
      >
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
    <form className="grid grid-cols-[118px_1fr_1fr_44px] gap-2 max-[620px]:grid-cols-1" onSubmit={onSubmit}>
      <label className="flex items-center gap-2 text-xs font-black uppercase text-zinc-400">
        {icon}
        {title}
      </label>
      <input
        className="min-w-0 rounded-lg border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm text-zinc-50 outline-none"
        value={first}
        onChange={(event) => onFirst(event.target.value)}
      />
      <input
        className="min-w-0 rounded-lg border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm text-zinc-50 outline-none"
        inputMode="decimal"
        value={second}
        onChange={(event) => onSecond(event.target.value)}
      />
      <button
        className="grid min-h-10 place-items-center rounded-lg border border-teal-300 bg-teal-300 text-zinc-950"
        type="submit"
        aria-label={`Save ${title}`}
      >
        <Plus size={16} />
      </button>
    </form>
  );
}

function DataRow({ left, right, detail = "" }: { left: string; right: string; detail?: string }) {
  return (
    <article className="flex items-center justify-between gap-4 rounded-lg border border-zinc-700 bg-zinc-900 p-3 max-[520px]:items-start max-[520px]:flex-col">
      <div>
        <strong className="block text-sm text-zinc-50">{left}</strong>
        {detail && <span className="mt-1 block text-xs text-zinc-400">{detail}</span>}
      </div>
      <b className="whitespace-nowrap text-teal-300">{right}</b>
    </article>
  );
}
