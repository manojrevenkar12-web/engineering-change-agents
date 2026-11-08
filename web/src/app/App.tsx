import { MotionConfig } from "framer-motion";
import { useState } from "react";
import { base, fetchJSON } from "../shared/api/client";
import type { Analysis, Results } from "../shared/api/types";
import { useResource } from "../shared/hooks/useResource";
import { Empty, ErrorState, Section, Skeleton } from "../shared/ui/States";
import { Tabs } from "../shared/ui/Tabs";
import { pct } from "../shared/format";
import { DecisionTable } from "../features/decisions/DecisionTable";
import { GateChart } from "../features/gate/GateChart";
import { AnalysisView } from "../features/analysis/AnalysisView";
import { StandardsMatrix } from "../features/standards/StandardsMatrix";

const URL = `${base}/results.json`;
type SetName = "heldout" | "dev";

export function App() {
  const res = useResource((s) => fetchJSON<Results>(URL, s), URL);
  return (
    <MotionConfig reducedMotion="user">
      <main className="page">
        <p className="masthead">engineering-change-agents: change board</p>
        {res.state === "loading" && <Skeleton />}
        {res.state === "error" && <ErrorState error={res.error} onRetry={res.retry} />}
        {res.state === "ready" && <Report r={res.data} />}
      </main>
    </MotionConfig>
  );
}

function Report({ r }: { r: Results }) {
  const [set, setSet] = useState<SetName>(r.heldout ? "heldout" : "dev");
  const data = (set === "heldout" ? r.heldout : r.dev) ?? r.dev;
  const full = data.configs.full;
  const proto = data.configs.prototype;
  const n = set === "heldout" ? "40 unseen" : "60 development";
  return (
    <>
      <header className="hero">
        <h1>
          {full && proto
            ? `On ${n} change requests, the agents approved ${full.safety_misses} change${full.safety_misses === 1 ? "" : "s"} that ${full.safety_misses === 1 ? "fails its" : "fail their"} crash target in ${full.runs} runs. The prototype approved ${proto.safety_misses}.`
            : "Results"}
        </h1>
        {full && (
          <p className="hero__lead">
            Where the system decided, it was right {pct(full.accuracy_decided.value)} of the time. It sent {pct(full.deferral_rate.value)} to a full crash
            simulation because the surrogate's interval straddled the target or the input was unlike anything it was trained on. Code decides from the agents' findings, and nothing is
            released until the required people have signed.
          </p>
        )}
      </header>

      <Tabs
        label="Request set"
        value={set}
        onChange={(v) => setSet(v as SetName)}
        items={[
          ...(r.heldout ? [{ id: "heldout", label: "Held-out requests", note: `run ${r.heldout_runs} time${r.heldout_runs === 1 ? "" : "s"}` }] : []),
          { id: "dev", label: "Development requests", note: "used while building" },
        ]}
      />

      <Section id="decisions" title="Decisions, and what each control buys" lead={`Each request analysed ${r.repeats} times with different model draws. Every row below the full design takes one control away.`}>
        <DecisionTable set={data} />
      </Section>

      <RunsSections set={set} />

      <Section
        id="standards"
        title="Architecture standards, checked from the code"
        lead={`Nine standards for agentic solutions on the platform, checked from source, declared spec, configuration and MCP tool metadata. A second solution on the same blueprint (special tool requests) decided ${r.tool_requests.correct} of ${r.tool_requests.requests} as expected.`}
      >
        <StandardsMatrix r={r} />
      </Section>

      <footer className="footer">
        Generated {new Date(r.generated).toLocaleString("en-GB")} from reports/results.json. Crash surrogate {r.lim.version}: interval coverage{" "}
        {pct(r.lim.test_coverage)} on held-back simulations (target {pct(r.lim.target_coverage)}), relative error {(100 * r.lim.test_mape).toFixed(1)}%. All
        data is synthetic.
      </footer>
    </>
  );
}

function RunsSections({ set }: { set: SetName }) {
  const url = `${base}/runs/${set}/full.json`;
  const res = useResource((s) => fetchJSON<Analysis[]>(url, s), url);
  return (
    <>
      <Section id="gate" title="The crash gate" lead="The surrogate decides only when its whole interval lies on one side of the target. Everything else goes to a full simulation.">
        {res.state === "loading" && <Skeleton rows={8} label="Loading analyses" />}
        {res.state === "error" && <ErrorState error={res.error} onRetry={res.retry} />}
        {res.state === "ready" && <GateChart runs={res.data} />}
      </Section>
      <Section id="analysis" title="One analysis, step by step" lead="First run of every request: the agents' timeline, what they found, and what the reviewer removed.">
        {res.state === "loading" && <Skeleton rows={6} label="Loading analyses" />}
        {res.state === "error" && <ErrorState error={res.error} onRetry={res.retry} />}
        {res.state === "ready" && (res.data.length ? <AnalysisView key={set} runs={res.data} /> : <Empty title="No analyses recorded." />)}
      </Section>
    </>
  );
}
