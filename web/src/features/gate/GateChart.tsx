import { motion, useReducedMotion } from "framer-motion";
import type { Analysis } from "../../shared/api/types";
import { color, gate as g } from "../../theme/tokens";
import { Empty } from "../../shared/ui/States";

const MIN = 0.6; // intrusion as a share of the target, left edge
const MAX = 1.6;
const GATE_COLOR: Record<string, string> = { pass: color.pass, fail: color.fail, fe_required: color.defer };
const GATE_LABEL: Record<string, string> = { pass: "decided: within target", fail: "decided: exceeds", fe_required: "sent to full simulation" };

const x = (ratio: number) => `${((Math.min(MAX, Math.max(MIN, ratio)) - MIN) / (MAX - MIN)) * 100}%`;

/** Every crash-relevant analysis: the surrogate's interval against the target. The memorable part of the page. */
export function GateChart({ runs }: { runs: Analysis[] }) {
  const reduce = useReducedMotion();
  const rows = runs
    .filter((r) => r.crash?.worst && r.crash.limit_mm)
    .map((r) => ({ r, w: r.crash!.worst!, limit: r.crash!.limit_mm! }))
    .sort((a, b) => a.w.high_mm / a.limit - b.w.high_mm / b.limit);
  if (!rows.length) return <Empty title="No crash-relevant analyses in this set." />;
  return (
    <figure className="gate">
      <div className="gate__axis" aria-hidden>
        {[0.6, 0.8, 1.0, 1.2, 1.4, 1.6].map((t) => (
          <span key={t} className={`gate__tick ${t === 1 ? "gate__tick--target" : ""}`} style={{ left: x(t) }}>
            {t === 1 ? "target" : `${Math.round(t * 100)}%`}
          </span>
        ))}
      </div>
      <ol className="gate__rows">
        {rows.map(({ r, w, limit }, i) => {
          const c = GATE_COLOR[r.crash!.gate] ?? color.muted;
          const exceeds = r.truth === "reject";
          return (
            <li key={r.id} className="gate__row" style={{ height: g.row }}>
              <span className="gate__label">
                {r.id}
                {!w.in_distribution && <span className="gate__ood"> unseen input</span>}
              </span>
              <span className="gate__lane">
                <span className="gate__target" style={{ left: x(1) }} />
                <motion.span
                  className="gate__interval"
                  style={{ left: x(w.low_mm / limit), width: `calc(${x(w.high_mm / limit)} - ${x(w.low_mm / limit)})`, height: g.bar, background: c }}
                  initial={reduce ? false : { scaleX: 0 }}
                  animate={{ scaleX: 1 }}
                  transition={{ delay: i * g.stagger, duration: g.grow }}
                />
                <span className="gate__point" style={{ left: x(w.intrusion_mm / limit), width: g.marker, height: g.marker }} />
              </span>
              <span className={`gate__truth ${exceeds ? "bad" : "good"}`}>{exceeds ? "exceeds in truth" : "within in truth"}</span>
              <span className="sr-only">
                {GATE_LABEL[r.crash!.gate]}, predicted {w.intrusion_mm} mm ({w.low_mm} to {w.high_mm}) against {limit} mm
              </span>
            </li>
          );
        })}
      </ol>
      <figcaption className="legend">
        {Object.entries(GATE_LABEL).map(([k, v]) => (
          <span key={k}>
            <span className="swatch" style={{ background: GATE_COLOR[k] }} /> {v}
          </span>
        ))}
        <span>Dot: point prediction. Bar: calibrated interval, worst variant. Scale: intrusion as a share of the strictest target.</span>
      </figcaption>
    </figure>
  );
}
