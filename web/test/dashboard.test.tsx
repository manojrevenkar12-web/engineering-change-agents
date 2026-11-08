import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { App } from "../src/app/App";
import type { Analysis, Results, Summary } from "../src/shared/api/types";

const rate = (v: number) => ({ value: v, ci: [v - 0.05, Math.min(1, v + 0.02)] as [number, number], n: 30 });
const summary = (misses: number, acc: number, defer: number): Summary => ({
  runs: 120, requests: 40, safety_misses: misses, accuracy_decided: rate(acc), deferral_rate: rate(defer), accuracy_all: rate(acc),
  false_rejects: 0, fe_requests: 10, crash_runs: 30, variant_recall: rate(1), tool_recall: rate(1), regulation_recall: rate(1),
  limit_correct: rate(1), reports_with_unsupported_figures: 0, injection_in_summary: 0, p95_latency_ms: 6900, cost_per_request_eur: 0.015,
  manual_hours: 10, agent_hours: 0.5,
});
const set = { configs: { full: summary(1, 0.99, 0.25), prototype: summary(13, 0.88, 0.04), "no reviewer": summary(1, 0.99, 0.25) }, comparisons: {} };
const results: Results = {
  generated: "2026-11-08T12:00:00+00:00", repeats: 3, dev: set, heldout: set, heldout_runs: 1,
  tool_requests: { requests: 11, correct: 11 },
  conformance: [
    { solution: "engineering-change-impact", path: "x", passed: 1, total: 1, checks: [{ id: "AS-01", pass: true, evidence: "9 tools declare scope" }] },
    { solution: "prototype-assistant", path: "y", passed: 0, total: 1, checks: [{ id: "AS-01", pass: false, evidence: "imports openai" }] },
  ],
  standards: [{ id: "AS-01", title: "Tools declare scope", why: "Least privilege." }],
  lim: { version: "lim-crash-1", test_coverage: 0.92, target_coverage: 0.9, test_mape: 0.043, rows: { fit: 1 } },
};
const analysis = (id: string, rec: string, truth: string, gate: string): Analysis => ({
  id, request: `Request ${id}`, recommendation: rec, truth, flags: [], part_no: "7", variants: ["P2-ev"], tools: { "WZ-1": "rework" },
  tooling_cost_eur: 1000, lead_weeks: 4, regulations: ["CT-1"], summary: `Summary ${id}.`, removed: [{ sentence: "Saves 9 EUR.", reason: "figures without a source: 9" }],
  notes: [], approval_roles: ["engineer", "safety_owner"], latency_ms: 2000, cost_eur: 0.01,
  crash: { gate, limit_mm: 100, fe_ticket: null, worst: { variant: "P2-ev", intrusion_mm: 90, low_mm: 80, high_mm: 105, in_distribution: gate !== "fe_required", reasons: [] } },
  spans: [
    { name: "intake: read request", kind: "model", start: 0, end: 900, status: "ok", detail: "" },
    { name: "plm.get_part", kind: "tool", start: 900, end: 1000, status: "ok", detail: "" },
  ],
});

function serve(map: Record<string, unknown>, fail = new Set<string>()) {
  vi.stubGlobal("fetch", vi.fn(async (url: string) => {
    if (fail.has(url)) return new Response("no", { status: 500 });
    if (!(url in map)) return new Response("no", { status: 404 });
    return new Response(JSON.stringify(map[url]), { status: 200 });
  }));
}
afterEach(() => vi.unstubAllGlobals());

const runs = [analysis("HEL-001", "approve", "approve", "pass"), analysis("HEL-002", "fe_simulation", "reject", "fe_required")];

describe("dashboard", () => {
  it("loads, then states the held-out safety result", async () => {
    serve({ "/data/results.json": results, "/data/runs/heldout/full.json": runs });
    render(<App />);
    expect(screen.getByRole("status", { name: "Loading results" })).toBeInTheDocument();
    expect(await screen.findByRole("heading", { level: 1 })).toHaveTextContent("approved 1 change that fails its crash target in 120 runs. The prototype approved 13.");
    expect(screen.getByRole("rowheader", { name: "full design" })).toBeInTheDocument();
  });

  it("explains a failed load and retries", async () => {
    const fail = new Set(["/data/results.json"]);
    serve({ "/data/results.json": results }, fail);
    render(<App />);
    expect(await screen.findByRole("alert")).toHaveTextContent("could not be loaded");
    fail.clear();
    await userEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByRole("heading", { level: 1 })).toBeInTheDocument();
  });

  it("draws the gate and filters analyses", async () => {
    serve({ "/data/results.json": results, "/data/runs/heldout/full.json": runs });
    render(<App />);
    expect(await screen.findByText(/sent to full simulation, predicted 90 mm/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Full simulation 1" }));
    expect(screen.getByRole("article", { name: "Analysis HEL-002" })).toBeInTheDocument();
    expect(screen.getByLabelText("Removed by the reviewer")).toHaveTextContent("Saves 9 EUR.");
  });

  it("shows empty runs and switches to development", async () => {
    serve({ "/data/results.json": results, "/data/runs/heldout/full.json": [], "/data/runs/dev/full.json": [] });
    render(<App />);
    expect(await screen.findByText("No analyses recorded.")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("tab", { name: /Development/ }));
    expect(await screen.findByRole("heading", { level: 1 })).toHaveTextContent("60 development");
  });

  it("marks a failing standard", async () => {
    serve({ "/data/results.json": results, "/data/runs/heldout/full.json": runs });
    render(<App />);
    expect(await screen.findByText("imports openai")).toBeInTheDocument();
    expect(screen.getByText("fails")).toBeInTheDocument();
  });
});
