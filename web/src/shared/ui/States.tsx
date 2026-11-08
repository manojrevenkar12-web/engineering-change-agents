import type { ReactNode } from "react";

export function Section({ id, title, lead, children }: { id: string; title: string; lead?: string; children: ReactNode }) {
  return (
    <section className="section" aria-labelledby={`${id}-title`}>
      <h2 id={`${id}-title`} className="section__title">
        {title}
      </h2>
      {lead && <p className="section__lead">{lead}</p>}
      {children}
    </section>
  );
}

export function Skeleton({ rows = 4, label = "Loading results" }: { rows?: number; label?: string }) {
  return (
    <div className="skeleton" role="status" aria-label={label}>
      {Array.from({ length: rows }, (_, i) => (
        <div key={i} className="skeleton__row" />
      ))}
    </div>
  );
}

export function ErrorState({ error, onRetry }: { error: Error; onRetry: () => void }) {
  return (
    <div className="state state--error" role="alert">
      <p className="state__title">The results could not be loaded.</p>
      <p className="state__body">{error.message}</p>
      <button className="button" onClick={onRetry}>
        Try again
      </button>
    </div>
  );
}

export function Empty({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="state">
      <p className="state__title">{title}</p>
      {children && <p className="state__body">{children}</p>}
    </div>
  );
}

export function Decision({ value }: { value: string }) {
  return <span className={`decision decision--${value}`}>{value.replace("_", " ")}</span>;
}
