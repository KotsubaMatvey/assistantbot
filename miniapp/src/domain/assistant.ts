export type AssistantState =
  | "idle"
  | "thinking"
  | "happy"
  | "alert"
  | "shopping"
  | "sad"
  | "working";

export type AssistantStateMeta = {
  kicker: string;
  title: string;
  copy: string;
};

export const assistantStates: Record<AssistantState, AssistantStateMeta> = {
  idle: {
    kicker: "System ready",
    title: "Brain online",
    copy: "Captures notes, tasks, people, sources, and decisions into the local second brain.",
  },
  thinking: {
    kicker: "Context mode",
    title: "Scanning memory",
    copy: "Checking agenda, open tasks, source notes, and recent decisions before the next action.",
  },
  happy: {
    kicker: "Synced",
    title: "Saved cleanly",
    copy: "The update landed in memory and the most important context stays near the surface.",
  },
  alert: {
    kicker: "Signal",
    title: "Needs attention",
    copy: "A reminder, market move, or source update is ready for review.",
  },
  shopping: {
    kicker: "Pantry mode",
    title: "Basket check",
    copy: "Reviews pantry, price alerts, and basket context before a grocery run.",
  },
  sad: {
    kicker: "Overloaded",
    title: "Compact session",
    copy: "The thread is getting noisy. Compress the session or split the next action.",
  },
  working: {
    kicker: "Working",
    title: "Sending payload",
    copy: "Submitting the action to the local API or falling back to Telegram safely.",
  },
};
