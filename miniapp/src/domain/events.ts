import type { BotCommand } from "../types/telegram";

export type TabId = "today" | "memory" | "finance" | "chat" | "more";

export type AppEvents = {
  "tab:selected": { tab: TabId };
  "command:send": { command: BotCommand };
  "basket:compare": { text: string };
  "toast:show": { message: string };
};

type Handler<T> = (payload: T) => void;

export class EventBus<Events extends Record<string, object>> {
  private handlers: {
    [Name in keyof Events]?: Set<Handler<Events[Name]>>;
  } = {};

  on<Name extends keyof Events>(event: Name, handler: Handler<Events[Name]>): () => void {
    const handlers = this.handlers[event] ?? new Set<Handler<Events[Name]>>();
    handlers.add(handler);
    this.handlers[event] = handlers;
    return () => handlers.delete(handler);
  }

  emit<Name extends keyof Events>(event: Name, payload: Events[Name]): void {
    this.handlers[event]?.forEach((handler) => handler(payload));
  }
}

export const eventBus = new EventBus<AppEvents>();
