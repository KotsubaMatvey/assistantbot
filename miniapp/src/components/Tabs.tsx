import { tabs } from "../domain/data";
import { eventBus, type TabId } from "../domain/events";

type TabsProps = {
  activeTab: TabId;
  onSelect: (tab: TabId) => void;
};

export function Tabs({ activeTab, onSelect }: TabsProps) {
  return (
    <nav className="tabbar" aria-label="Разделы">
      {tabs.map((tab) => (
        <button
          key={tab.id}
          className={activeTab === tab.id ? "tab tab-active" : "tab"}
          type="button"
          onClick={() => {
            onSelect(tab.id);
            eventBus.emit("tab:selected", { tab: tab.id });
          }}
          title={tab.label}
        >
          {tab.icon}
          <span>{tab.label}</span>
        </button>
      ))}
    </nav>
  );
}
