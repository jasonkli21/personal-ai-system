import { mkdir, readFile, rm, writeFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { build } from "esbuild";

const root = new URL("../", import.meta.url);
const at = (path) => new URL(path, root);
const readJson = async (path) => JSON.parse(await readFile(at(path), "utf8"));

const template = await readJson(".openai/hosting.example.json");
const bound = await readJson(".openai/hosting.json").catch((error) => {
  if (error.code !== "ENOENT") throw error;
  return null;
});
if (bound && (typeof bound.project_id !== "string" || !bound.project_id)) {
  throw new Error("The bound Sites manifest needs a project_id.");
}

await rm(at("dist/"), { recursive: true, force: true });
await mkdir(at("dist/.openai/"), { recursive: true });
await build({
  absWorkingDir: fileURLToPath(root),
  entryPoints: ["src/index.js"],
  outfile: "dist/server/index.js",
  bundle: true,
  format: "esm",
  platform: "neutral",
  target: "es2023",
});
await writeFile(at("dist/.openai/hosting.json"), JSON.stringify({ ...template, ...bound }, null, 2) + "\n");

const source = await readFile(at("dist/server/index.js"), "utf8");
const entry = "data:text/javascript;base64," + Buffer.from(source).toString("base64");
const { default: worker } = await import(entry);
if (typeof worker.fetch !== "function") throw new Error("Sites Worker must export a fetch handler.");
const page = await worker.fetch(new Request("https://example.invalid/"));
if (!page.ok || !(await page.text()).includes("PAS Personal Context")) {
  throw new Error("The built Worker could not render the status page.");
}
console.log(bound ? "Built bound Sites Worker." : "Built unbound Sites Worker for local checks.");
