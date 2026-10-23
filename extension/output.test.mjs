// node --test extension/output.test.mjs
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, parse } from "node:path";
import { after, describe, it } from "node:test";
import { fileURLToPath } from "node:url";
import { unsafeOutput } from "./output.mjs";

const source = dirname(fileURLToPath(import.meta.url));
const scratch = mkdtempSync(join(tmpdir(), "vidwiz-extension-"));
after(() => rmSync(scratch, { recursive: true, force: true }));

describe("unsafeOutput", () => {
  it("refuses the source, its ancestors, and the filesystem root", () => {
    for (const out of [source, dirname(source), dirname(dirname(source)), parse(source).root]) {
      assert.match(unsafeOutput(out, source, "VidWiz"), /contains the extension source/, out);
    }
  });

  it("refuses source folders and dist itself", () => {
    assert.match(unsafeOutput(join(source, "icons"), source, "VidWiz"), /inside the extension source/);
    assert.match(unsafeOutput(join(source, "distant"), source, "VidWiz"), /inside the extension source/);
    assert.match(unsafeOutput(join(source, "dist"), source, "VidWiz"), /holds every build/);
  });

  it("allows folders under dist", () => {
    assert.equal(unsafeOutput(join(source, "dist", "prod"), source, "VidWiz"), null);
    assert.equal(unsafeOutput(join(source, "dist", "dev", "nested"), source, "VidWiz"), null);
  });

  it("allows a new or empty folder outside the source", () => {
    assert.equal(unsafeOutput(join(scratch, "missing"), source, "VidWiz"), null);
    mkdirSync(join(scratch, "empty"));
    assert.equal(unsafeOutput(join(scratch, "empty"), source, "VidWiz"), null);
  });

  it("allows an earlier build and refuses any other folder with files", () => {
    const build = join(scratch, "build");
    mkdirSync(build);
    writeFileSync(join(build, "manifest.json"), JSON.stringify({ name: "VidWiz" }));
    assert.equal(unsafeOutput(build, source, "VidWiz"), null);

    const other = join(scratch, "other");
    mkdirSync(other);
    writeFileSync(join(other, "manifest.json"), JSON.stringify({ name: "Something else" }));
    assert.match(unsafeOutput(other, source, "VidWiz"), /not an earlier build/);

    const notes = join(scratch, "notes");
    mkdirSync(notes);
    writeFileSync(join(notes, "todo.txt"), "keep me");
    assert.match(unsafeOutput(notes, source, "VidWiz"), /not an earlier build/);
  });
});

describe("build.mjs", () => {
  const build = (out) => execFileSync(process.execPath, [join(source, "build.mjs"), "--out", out], { stdio: "pipe" });

  it("builds into a custom folder and rebuilds over it", () => {
    const out = join(scratch, "custom");
    build(out);
    build(out);
    const manifest = JSON.parse(readFileSync(join(out, "manifest.json"), "utf8"));
    assert.equal(manifest.name, "VidWiz");
    assert.ok(existsSync(join(out, "config.js")));
  });

  it("exits without deleting a folder that is not a build", () => {
    const out = join(scratch, "keep");
    mkdirSync(out);
    writeFileSync(join(out, "todo.txt"), "keep me");
    assert.throws(() => build(out), (error) => error.status === 1 && /Refusing to build/.test(error.stderr));
    assert.equal(readFileSync(join(out, "todo.txt"), "utf8"), "keep me");
  });
});
