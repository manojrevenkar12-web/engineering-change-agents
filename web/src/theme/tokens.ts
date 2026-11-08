// The visual system: an engineering drawing's title block. CSS reads these as custom properties (applyTokens);
// the gate chart and the timeline read them directly.

export const color = {
  paper: "#E8EBEE",
  sheet: "#F7F8F9",
  ink: "#13233A",
  muted: "#53627A",
  faint: "#8794A6",
  rule: "#C6CED8",
  pass: "#2F7D4F",
  passWash: "#DCEDE2",
  fail: "#A33A2B",
  failWash: "#F3DEDA",
  defer: "#A86F07",
  deferWash: "#F4E8CF",
  model: "#3A4FA8",
  tool: "#127A86",
  agent: "#13233A",
} as const;

export const decisionColor: Record<string, string> = {
  approve: color.pass,
  reject: color.fail,
  fe_simulation: color.defer,
  engineer_review: color.muted,
};

export const spanColor: Record<string, string> = { model: color.model, tool: color.tool, agent: color.agent };

export const font = { ui: '"Barlow", "Segoe UI", system-ui, sans-serif' } as const;
export const size = { tick: 11, small: 13, body: 15, lead: 18, title: 22, displayNarrow: 28, display: 40 } as const;
export const space = { 1: 4, 2: 8, 3: 12, 4: 16, 5: 24, 6: 32, 7: 48, 8: 72 } as const;
export const radius = { control: 2, panel: 4 } as const;
export const layout = { contentMax: 1160, measure: 72, breakpoint: 780 } as const;

export const gate = { row: 22, bar: 8, label: 150, truth: 120, marker: 10, stagger: 0.02, grow: 0.35 } as const;
export const timeline = { row: 22, bar: 12, label: 170, minBar: 3, stagger: 0.05, grow: 0.25 } as const;

export function applyTokens(root: HTMLElement = document.documentElement): void {
  const set = (k: string, v: string | number) => root.style.setProperty(k, typeof v === "number" ? `${v}px` : v);
  Object.entries(color).forEach(([k, v]) => set(`--c-${k}`, v));
  Object.entries(size).forEach(([k, v]) => set(`--fs-${k}`, v));
  Object.entries(space).forEach(([k, v]) => set(`--sp-${k}`, v));
  Object.entries(radius).forEach(([k, v]) => set(`--r-${k}`, v));
  set("--font-ui", font.ui);
  set("--content-max", layout.contentMax);
  set("--measure", `${layout.measure}ch`);
  set("--gate-label", gate.label);
  set("--gate-truth", gate.truth);
  set("--tl-label", timeline.label);
}
