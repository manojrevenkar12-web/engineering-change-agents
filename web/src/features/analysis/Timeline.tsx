import { motion, useReducedMotion } from "framer-motion";
import type { Span } from "../../shared/api/types";
import { spanColor, timeline as t } from "../../theme/tokens";

/** The agents' work on a shared clock: tooling and compliance run side by side, crash waits for compliance. */
export function Timeline({ spans, runKey }: { spans: Span[]; runKey: string }) {
  const reduce = useReducedMotion();
  const shown = spans.filter((s) => s.kind !== "agent");
  const end = Math.max(1, ...spans.map((s) => s.end));
  const pos = (ms: number) => `${(ms / end) * 100}%`;
  return (
    <div className="timeline" role="list" aria-label="Steps of this analysis">
      {shown.map((s, i) => (
        <div key={`${runKey}-${i}`} className="timeline__row" role="listitem" style={{ height: t.row }}>
          <span className="timeline__label" title={s.detail}>
            {s.name}
          </span>
          <span className="timeline__lane">
            <motion.span
              className={`timeline__bar ${s.status !== "ok" ? "timeline__bar--error" : ""}`}
              style={{ left: pos(s.start), width: `max(${pos(s.end - s.start)}, ${t.minBar}px)`, height: t.bar, background: spanColor[s.kind] }}
              initial={reduce ? false : { scaleX: 0 }}
              animate={{ scaleX: 1 }}
              transition={{ delay: i * t.stagger, duration: t.grow }}
            />
          </span>
          <span className="sr-only">
            {s.kind} {s.name} from {Math.round(s.start)} to {Math.round(s.end)} ms
          </span>
        </div>
      ))}
      <p className="legend">
        <span>
          <span className="swatch" style={{ background: spanColor.model }} /> model call
        </span>
        <span>
          <span className="swatch" style={{ background: spanColor.tool }} /> MCP tool call
        </span>
        <span>{(end / 1000).toFixed(1)} s end to end</span>
      </p>
    </div>
  );
}
