import type { ReactNode } from "react";

type ActionButtonProps = {
  children: ReactNode;
  icon?: ReactNode;
  primary?: boolean;
  onClick: () => void;
};

export function ActionButton({ children, icon, primary = false, onClick }: ActionButtonProps) {
  return (
    <button
      className={
        primary
          ? "flex min-h-11 items-center justify-center gap-2 rounded-lg border border-teal-300 bg-teal-300 px-3 text-sm font-black text-zinc-950"
          : "flex min-h-11 items-center justify-center gap-2 rounded-lg border border-zinc-700 bg-zinc-800 px-3 text-sm font-black text-zinc-50"
      }
      type="button"
      onClick={onClick}
    >
      {icon}
      <span>{children}</span>
    </button>
  );
}
