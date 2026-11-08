export const pct = (x: number) => `${Math.round(100 * x)}%`;
export const seconds = (ms: number) => `${(ms / 1000).toFixed(1)} s`;
export const euro = (x: number) => `€${x.toLocaleString("en", { maximumFractionDigits: 0 })}`;
export const decisionLabel: Record<string, string> = {
  approve: "approve",
  reject: "reject",
  fe_simulation: "full simulation",
  engineer_review: "engineer review",
};
