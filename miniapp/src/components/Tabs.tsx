import { tabs } from "../domain/data";
import { eventBus, type TabId } from "../domain/events";

type TabsProps = {
  activeTab: TabId;
  onSelect: (tab: TabId) => void;
};

export function Tabs({ activeTab, onSelect }: TabsProps) {
  return (
    <nav className="tab-bar" aria-label="Разделы">
      {tabs.map((tab) => (
        <button
          key={tab.id}
          className={activeTab === tab.id ? "tab-button tab-button-active" : "tab-button"}
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
