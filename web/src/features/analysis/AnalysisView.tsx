import { useMemo, useState } from "react";
import type { Analysis } from "../../shared/api/types";
import { Decision, Empty } from "../../shared/ui/States";
import { decisionLabel, euro, seconds } from "../../shared/format";
import { Timeline } from "./Timeline";

type Filter = "all" | "deferred" | "wrong";

export function AnalysisView({ runs }: { runs: Analysis[] }) {
  const [filter, setFilter] = useState<Filter>("all");
  const shown = useMemo(
    () =>
      runs.filter((r) =>
        filter === "all" ? true : filter === "deferred" ? r.recommendation === "fe_simulation" : r.recommendation !== r.truth && r.recommendation !== "fe_simulation",
      ),
    [runs, filter],
  );
  const [picked, setPicked] = useState<string | null>(null);
  const current = shown.find((r) => r.id === picked) ?? shown[0];
  const counts = {
    all: runs.length,
    deferred: runs.filter((r) => r.recommendation === "fe_simulation").length,
    wrong: runs.filter((r) => r.recommendation !== r.truth && r.recommendation !== "fe_simulation").length,
  };
  return (
    <div className="analyses">
      <div>
        <div className="chips" role="group" aria-label="Show analyses">
          {(["all", "deferred", "wrong"] as Filter[]).map((f) => (
            <button key={f} className={`chip ${filter === f ? "chip--on" : ""}`} aria-pressed={filter === f} onClick={() => setFilter(f)}>
              {f === "all" ? "All" : f === "deferred" ? "Full simulation" : "Not as in truth"} {counts[f]}
            </button>
          ))}
        </div>
        {shown.length ? (
          <ol className="analyses__list">
            {shown.map((r) => (
              <li key={r.id}>
                <button className={`analysis-item ${current?.id === r.id ? "analysis-item--on" : ""}`} onClick={() => setPicked(r.id)}>
                  <span className="analysis-item__id">{r.id}</span>
                  <Decision value={r.recommendation} />
                </button>
              </li>
            ))}
          </ol>
        ) : (
          <Empty title="Nothing in this filter." />
        )}
      </div>
      {current && <Detail r={current} />}
    </div>
  );
}

function Detail({ r }: { r: Analysis }) {
  const tools = Object.entries(r.tools);
  return (
    <article className="detail" aria-label={`Analysis ${r.id}`}>
      <p className="detail__request">{r.request}</p>
      <dl className="facts">
        <div>
          <dt>Recommendation</dt>
          <dd>
            <Decision value={r.recommendation} />
          </dd>
        </div>
        <div>
          <dt>In truth</dt>
          <dd>{decisionLabel[r.truth]}</dd>
        </div>
        <div>
          <dt>Signatures needed</dt>
          <dd>{r.approval_roles.join(" and ").replace("_", " ")}</dd>
        </div>
        <div>
          <dt>Time</dt>
          <dd className="num">{seconds(r.latency_ms)}</dd>
        </div>
      </dl>
      <Timeline spans={r.spans} runKey={r.id} />
      <div className="detail__grid">
        <div>
          <h3>Variants</h3>
          <p>{r.variants.join(", ") || "none resolved"}</p>
          <h3>Documents</h3>
          <p>{r.regulations.join(", ") || "none"}</p>
        </div>
        <div>
          <h3>Special tools</h3>
          {tools.length ? (
            <ul className="plain">
              {tools.map(([id, a]) => (
                <li key={id}>
                  {id}: {a}
                </li>
              ))}
              <li className="small">
                {euro(r.tooling_cost_eur)}, up to {r.lead_weeks} weeks
              </li>
            </ul>
          ) : (
            <p>none affected</p>
          )}
        </div>
      </div>
      <blockquote className="summary">{r.summary}</blockquote>
      {r.removed.length > 0 && (
        <ul className="removed" aria-label="Removed by the reviewer">
          {r.removed.map((x, i) => (
            <li key={i}>
              <s>{x.sentence}</s> <span className="small">removed: {x.reason}</span>
            </li>
          ))}
        </ul>
      )}
      {r.notes.length > 0 && <p className="small">Model mistakes caught or left: {r.notes.join("; ")}.</p>}
    </article>
  );
}
