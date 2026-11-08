import type { SetResults } from "../../shared/api/types";
import { pct, seconds } from "../../shared/format";

const ORDER = ["full", "prototype"];

export function DecisionTable({ set }: { set: SetResults }) {
  const names = [...ORDER.filter((n) => n in set.configs), ...Object.keys(set.configs).filter((n) => !ORDER.includes(n))];
  return (
    <div className="scroll">
      <table className="table">
        <caption className="sr-only">Decisions by configuration</caption>
        <thead>
          <tr>
            <th scope="col">Configuration</th>
            <th scope="col">Approved although the crash target is exceeded</th>
            <th scope="col">Correct where it decided</th>
            <th scope="col">Sent to full simulation</th>
            <th scope="col">Figures without a source</th>
            <th scope="col">Attachment instruction in report</th>
            <th scope="col">p95</th>
          </tr>
        </thead>
        <tbody>
          {names.map((n) => {
            const m = set.configs[n]!;
            return (
              <tr key={n} className={n === "full" ? "row--design" : undefined}>
                <th scope="row">{n === "full" ? "full design" : n}</th>
                <td className={`num ${m.safety_misses ? "bad" : "good"}`}>
                  {m.safety_misses} of {m.runs}
                </td>
                <td className="num">
                  {pct(m.accuracy_decided.value)} <span className="small">({pct(m.accuracy_decided.ci[0])}–{pct(m.accuracy_decided.ci[1])})</span>
                </td>
                <td className="num">{pct(m.deferral_rate.value)}</td>
                <td className={`num ${m.reports_with_unsupported_figures ? "bad" : ""}`}>{m.reports_with_unsupported_figures}</td>
                <td className={`num ${m.injection_in_summary ? "bad" : ""}`}>{m.injection_in_summary}</td>
                <td className="num">{seconds(m.p95_latency_ms)}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
