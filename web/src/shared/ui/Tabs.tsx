import { motion } from "framer-motion";

export interface TabItem {
  id: string;
  label: string;
  note?: string;
}

/** Tabs that keep keyboard order; the underline moves to show what changed. */
export function Tabs({ items, value, onChange, label }: { items: TabItem[]; value: string; onChange: (id: string) => void; label: string }) {
  return (
    <div className="tabs" role="tablist" aria-label={label}>
      {items.map((t) => {
        const on = t.id === value;
        return (
          <button key={t.id} role="tab" aria-selected={on} className={`tab ${on ? "tab--on" : ""}`} onClick={() => onChange(t.id)}>
            <span className="tab__label">{t.label}</span>
            {t.note && <span className="tab__note">{t.note}</span>}
            {on && <motion.span layoutId={`${label}-underline`} className="tab__underline" />}
          </button>
        );
      })}
    </div>
  );
}
