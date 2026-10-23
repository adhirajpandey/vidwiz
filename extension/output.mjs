// Decide whether build.mjs may wipe and rewrite an output folder.
import { existsSync, readdirSync, readFileSync, realpathSync } from "node:fs";
import { basename, dirname, isAbsolute, join, relative, resolve, sep } from "node:path";

function contains(parent, child) {
  const path = relative(parent, child);
  return path === "" || (path !== ".." && !path.startsWith(`..${sep}`) && !isAbsolute(path));
}

// Follow symlinks in the part of `path` that exists; keep the rest as written.
// The last segment stays as written, so a symlink at `path` itself is only unlinked.
function realLocation(path) {
  const missing = [basename(path)];
  let current = dirname(path);
  while (!existsSync(current) && dirname(current) !== current) {
    missing.unshift(basename(current));
    current = dirname(current);
  }
  return join(realpathSync(current), ...missing);
}

/**
 * Returns why `out` is unsafe to delete, or null when it is safe.
 * `source` is the extension folder. The output may be inside `source/dist`
 * or outside the source. An existing non-empty folder must hold an earlier
 * build of the extension `name`, so a mistyped path never wipes other files.
 */
export function unsafeOutput(out, source, name) {
  out = resolve(out);
  if (out === dirname(out)) return "it contains the extension source";
  out = realLocation(out);
  source = realpathSync(source);
  if (contains(out, source)) return "it contains the extension source";
  if (contains(source, out) && !contains(join(source, "dist"), out)) {
    return "it is inside the extension source; use a folder under dist/";
  }
  if (out === join(source, "dist")) return "it holds every build; use a folder under dist/";
  if (!existsSync(out) || readdirSync(out).length === 0) return null;
  // A source checkout has build.mjs; a build never does.
  if (!existsSync(join(out, "build.mjs"))) {
    try {
      if (JSON.parse(readFileSync(join(out, "manifest.json"), "utf8")).name === name) return null;
    } catch {
      // Not an earlier build.
    }
  }
  return "it is not empty and is not an earlier build of this extension";
}
