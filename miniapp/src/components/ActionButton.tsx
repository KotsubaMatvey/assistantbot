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
      className={primary ? "action-button action-button-primary" : "action-button"}
      type="button"
      onClick={onClick}
    >
      {icon}
      <span>{children}</span>
    </button>
  );
}
