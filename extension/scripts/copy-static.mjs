import { cp, mkdir, readFile, writeFile } from "node:fs/promises";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";

const browser = process.argv[2] ?? "chrome";
const output = resolve(fileURLToPath(new URL("../", import.meta.url)), process.argv[3] ?? "dist");
if (browser !== "chrome" && browser !== "firefox") throw new Error(`Unsupported browser target: ${browser}`);
await mkdir(output, { recursive: true });
await cp(new URL("../manifest.json", import.meta.url), resolve(output, "manifest.json"));
await cp(new URL("../static/", import.meta.url), output, { recursive: true });
try {
  await cp(new URL("../src/data/", import.meta.url), resolve(output, "data"), { recursive: true });
} catch (error) {
  const code = error && typeof error === "object" && "code" in error ? error.code : undefined;
  if (code !== "ENOENT") throw error;
  // Private, operator-provided offline lexicons are intentionally not in the public repo.
}

if (browser === "firefox") {
  // Firefox MV3 uses a background page; it does not run background.service_worker.
  const manifest = JSON.parse(await readFile(resolve(output, "manifest.json"), "utf8"));
  delete manifest.minimum_chrome_version;
  manifest.background = { page: "background/background.html" };
  manifest.browser_specific_settings = { gecko: { id: "jlpt-ai-review-dictionary@local" } };
  await writeFile(resolve(output, "manifest.json"), JSON.stringify(manifest, null, 2) + "\n");
}
