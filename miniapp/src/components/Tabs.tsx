import { tabs } from "../domain/data";
import { eventBus, type TabId } from "../domain/events";

type TabsProps = {
  activeTab: TabId;
  onSelect: (tab: TabId) => void;
};

export function Tabs({ activeTab, onSelect }: TabsProps) {
  return (
    <nav
      className="grid grid-cols-4 gap-1 rounded-lg border border-zinc-700 bg-zinc-950 p-1 max-[520px]:grid-cols-2"
      aria-label="Разделы"
    >
      {tabs.map((tab) => (
        <button
          key={tab.id}
          className={
            activeTab === tab.id
              ? "flex min-h-10 items-center justify-center gap-2 rounded-md bg-teal-300 px-2 text-sm font-black text-zinc-950"
              : "flex min-h-10 items-center justify-center gap-2 rounded-md px-2 text-sm font-black text-zinc-400"
          }
          type="button"
          onClick={() => {
            onSelect(tab.id);
            eventBus.emit("tab:selected", { tab: tab.id });
          }}
        >
          {tab.icon}
          <span>{tab.label}</span>
        </button>
      ))}
    </nav>
  );
}
