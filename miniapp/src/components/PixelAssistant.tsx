import { assistantStates, type AssistantState } from "../domain/assistant";

type PixelAssistantProps = {
  state: AssistantState;
};

export function PixelAssistant({ state }: PixelAssistantProps) {
  const meta = assistantStates[state];
  return (
    <section
      className="grid grid-cols-[92px_1fr] items-center gap-4 rounded-lg border border-zinc-700 bg-zinc-900 p-3 shadow-2xl max-[420px]:grid-cols-1"
      aria-label="Pixel assistant"
    >
      <div className="grid min-h-28 place-items-end rounded-lg bg-zinc-950 shadow-inner max-[420px]:min-h-24">
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
        <p className="text-xs font-black uppercase text-teal-300">{meta.kicker}</p>
        <h2 className="mt-1 text-xl font-black leading-tight text-zinc-50">{meta.title}</h2>
        <p className="mt-2 text-sm leading-5 text-zinc-400">{meta.copy}</p>
      </div>
    </section>
  );
}
