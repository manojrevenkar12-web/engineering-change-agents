// Copies the generated results and sample runs into public/data, so the dashboard shows what the report says.
import { cpSync, existsSync, mkdirSync } from "node:fs";
const reports = new URL("../../reports/", import.meta.url);
const data = new URL("../public/data/", import.meta.url);
mkdirSync(data, { recursive: true });
if (!existsSync(new URL("results.json", reports))) console.warn("reports/results.json not found: run `make report` first");
else {
  cpSync(new URL("results.json", reports), new URL("results.json", data));
  cpSync(new URL("runs/", reports), new URL("runs/", data), { recursive: true });
}
