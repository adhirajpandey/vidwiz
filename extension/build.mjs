// Build the extension for a given web app and API origin.
//
//   node extension/build.mjs                       # production, into extension/dist/prod
//   node extension/build.mjs --zip                 # also zip it for the Chrome Web Store
//   node extension/build.mjs --web http://localhost:5173 \
//     --api http://localhost:5000/v2 --out extension/dist/dev
//
// Load the output folder with "Load unpacked". Production builds can also be
// loaded straight from extension/.
import { execFileSync } from "node:child_process";
import { cpSync, mkdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const flags = new Set(["zip"]);
const args = Object.fromEntries(
  process.argv.slice(2).reduce((pairs, value, index, all) => {
    if (!value.startsWith("--")) return pairs;
    const name = value.slice(2);
    pairs.push([name, flags.has(name) ? true : all[index + 1]]);
    return pairs;
  }, []),
);
const web = (args.web || "https://vidwiz.online").replace(/\/$/, "");
const apiUrl = (args.api || "https://api.vidwiz.online/v2").replace(/\/$/, "");
const out = resolve(args.out || join(here, "dist", "prod"));

const files = ["api.js", "background.js", "content.js", "popup.html", "popup.css", "popup.js", "icons", "fonts"];
rmSync(out, { recursive: true, force: true });
mkdirSync(out, { recursive: true });
for (const file of files) cpSync(join(here, file), join(out, file), { recursive: true });

writeFileSync(
  join(out, "config.js"),
  `export const CONFIG = ${JSON.stringify({ WEB_URL: web, API_URL: apiUrl }, null, 2)};\n`,
);

const manifest = JSON.parse(readFileSync(join(here, "manifest.json"), "utf8"));
const apiOrigin = new URL(apiUrl).origin;
manifest.host_permissions = ["https://*.youtube.com/*", `${apiOrigin}/*`];
manifest.externally_connectable = { matches: [`${web}/*`] };
writeFileSync(join(out, "manifest.json"), `${JSON.stringify(manifest, null, 2)}\n`);

console.log(`Built ${out}\n  web: ${web}\n  api: ${apiUrl}`);

if (args.zip) {
  // The store wants the files at the zip's root.
  const zipPath = join(dirname(out), `vidwiz-extension-${manifest.version}.zip`);
  rmSync(zipPath, { force: true });
  execFileSync("zip", ["-qr", zipPath, "."], { cwd: out });
  console.log(`  zip: ${zipPath}`);
}
