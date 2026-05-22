import { Activity, BatteryCharging, CircleAlert } from "lucide-react";
import { useEffect, useState } from "react";
import { assistantStates, type AssistantState } from "../domain/assistant";

type PixelAssistantProps = {
  state: AssistantState;
  pulse?: number;
};

export function PixelAssistant({ state, pulse = 0 }: PixelAssistantProps) {
  const meta = assistantStates[state];
  const isAlert = state === "alert" || state === "sad";
  const [isReacting, setIsReacting] = useState(false);

  useEffect(() => {
    if (pulse === 0) {
      return;
    }
    setIsReacting(true);
    const timer = window.setTimeout(() => setIsReacting(false), 360);
    return () => window.clearTimeout(timer);
  }, [pulse]);

  return (
    <section
      className={isReacting ? "glass-panel pixel-shell pixel-shell-reacting" : "glass-panel pixel-shell"}
      aria-label="Пиксельный ассистент"
    >
      <div className="pixel-stage">
        <span className="pixel-aura" aria-hidden="true" />
        <span className="pixel-spark pixel-spark-left" aria-hidden="true" />
        <span className="pixel-spark pixel-spark-right" aria-hidden="true" />
        <div className={`pixel-avatar is-${state}`} aria-hidden="true">
          <span className="pixel-shadow" />
          <span className="pixel-tail" />
          <span className="pixel-hair" />
          <span className="pixel-head" />
          <span className="pixel-ear pixel-ear-left" />
          <span className="pixel-ear pixel-ear-right" />
          <span className="pixel-visor" />
          <span className="pixel-eye pixel-eye-left" />
          <span className="pixel-eye pixel-eye-right" />
          <span className="pixel-beard" />
          <span className="pixel-smirk" />
          <span className="pixel-neck" />
          <span className="pixel-body" />
          <span className="pixel-arm pixel-arm-left" />
          <span className="pixel-arm pixel-arm-right" />
          <span className="pixel-claw pixel-claw-left" />
          <span className="pixel-claw pixel-claw-right" />
          <span className="pixel-band" />
          <span className="pixel-leg pixel-leg-left" />
          <span className="pixel-leg pixel-leg-right" />
          <span className="pixel-shoe pixel-shoe-left" />
          <span className="pixel-shoe pixel-shoe-right" />
          <span className="pixel-prop" />
          <span className="pixel-signal" />
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
