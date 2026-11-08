export type Interval = [number, number];
export interface Rate {
  value: number;
  ci: Interval;
  n: number;
}

export interface Summary {
  runs: number;
  requests: number;
  safety_misses: number;
  accuracy_decided: Rate;
  deferral_rate: Rate;
  accuracy_all: Rate;
  false_rejects: number;
  fe_requests: number;
  crash_runs: number;
  variant_recall: Rate;
  tool_recall: Rate;
  regulation_recall: Rate;
  limit_correct: Rate;
  reports_with_unsupported_figures: number;
  injection_in_summary: number;
  p95_latency_ms: number;
  cost_per_request_eur: number;
  manual_hours: number;
  agent_hours: number;
}

export interface SetResults {
  configs: Record<string, Summary>;
  comparisons: Record<string, Record<string, { diff: number; ci: Interval }>>;
  fingerprint?: string;
}

export interface Check {
  id: string;
  pass: boolean;
  evidence: string;
}

export interface Conformance {
  solution: string;
  path: string;
  checks: Check[];
  passed: number;
  total: number;
}

export interface Results {
  generated: string;
  repeats: number;
  dev: SetResults;
  heldout: SetResults | null;
  heldout_runs: number;
  tool_requests: { requests: number; correct: number };
  conformance: Conformance[];
  standards: { id: string; title: string; why: string }[];
  lim: { version: string; test_coverage: number; target_coverage: number; test_mape: number; rows: Record<string, number> };
}

export interface Span {
  name: string;
  kind: "agent" | "model" | "tool";
  start: number;
  end: number;
  status: string;
  detail: string;
}

export interface Prediction {
  variant: string;
  intrusion_mm: number;
  low_mm: number;
  high_mm: number;
  in_distribution: boolean;
  reasons: string[];
}

export interface Analysis {
  id: string;
  request: string;
  recommendation: string;
  truth: string;
  flags: string[];
  part_no: string | null;
  variants: string[];
  tools: Record<string, string>;
  tooling_cost_eur: number;
  lead_weeks: number;
  regulations: string[];
  crash: { gate: string; limit_mm: number | null; fe_ticket: string | null; worst: Prediction | null } | null;
  summary: string;
  removed: { sentence: string; reason: string }[];
  notes: string[];
  approval_roles: string[];
  latency_ms: number;
  cost_eur: number;
  spans: Span[];
}
