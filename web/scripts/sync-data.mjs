import { copyFile, mkdir } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import path from "node:path";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const destination = path.join(root, "web/public/data");
await mkdir(destination, { recursive: true });
for (const file of ["events.json", "summary.json", "phase7_results.json", "triage_example.json"]) {
  await copyFile(path.join(root, "frontend/data", file), path.join(destination, file));
  console.log(`Copied ${file}`);
}
