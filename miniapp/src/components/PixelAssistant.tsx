import { Activity, BatteryCharging, CircleAlert } from "lucide-react";
import { assistantStates, type AssistantState } from "../domain/assistant";

type PixelAssistantProps = {
  state: AssistantState;
};

export function PixelAssistant({ state }: PixelAssistantProps) {
  const meta = assistantStates[state];
  const isAlert = state === "alert" || state === "sad";

  return (
    <section className="glass-panel pixel-shell" aria-label="Pixel assistant">
      <div className="pixel-stage">
        <div className={`pixel-avatar is-${state}`} aria-hidden="true">
          <span className="pixel-hair" />
          <span className="pixel-head" />
          <span className="pixel-ear pixel-ear-left" />
          <span className="pixel-ear pixel-ear-right" />
          <span className="pixel-eye pixel-eye-left" />
          <span className="pixel-eye pixel-eye-right" />
          <span className="pixel-beard" />
          <span className="pixel-smirk" />
          <span className="pixel-neck" />
          <span className="pixel-body" />
          <span className="pixel-arm pixel-arm-left" />
          <span className="pixel-arm pixel-arm-right" />
          <span className="pixel-band" />
          <span className="pixel-leg pixel-leg-left" />
          <span className="pixel-leg pixel-leg-right" />
          <span className="pixel-shoe pixel-shoe-left" />
          <span className="pixel-shoe pixel-shoe-right" />
          <span className="pixel-prop" />
        </div>
      </div>
      <div>
        <div className="flex items-center gap-2">
          <span className="app-kicker">{meta.kicker}</span>
          {isAlert ? (
            <CircleAlert size={14} className="text-[var(--accent-2)]" />
          ) : state === "working" ? (
            <BatteryCharging size={14} className="text-[var(--accent)]" />
          ) : (
            <Activity size={14} className="text-[var(--accent)]" />
          )}
        </div>
        <h2 className="pixel-status">{meta.title}</h2>
        <p className="pixel-status-copy">{meta.copy}</p>
      </div>
    </section>
  );
}
