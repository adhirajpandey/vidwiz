import { build } from 'vite';
import assert from 'node:assert/strict';
import { copyFile, readFile, writeFile } from 'node:fs/promises';
import { renderDocument } from './render-document.mjs';

await build({ plugins: [{
  name: 'verify-public-startup',
  generateBundle(_, bundle) {
    const entry = Object.values(bundle).find(asset => asset.type === 'chunk' && asset.isEntry);
    assert.ok(entry, 'client entry exists');
    const modules = new Set();
    const visited = new Set();
    const visit = chunk => {
      if (visited.has(chunk.fileName)) return;
      visited.add(chunk.fileName);
      Object.keys(chunk.modules).forEach(id => modules.add(id.replaceAll('\\', '/')));
      chunk.imports.forEach(file => { if (bundle[file]?.type === 'chunk') visit(bundle[file]); });
    };
    visit(entry);
    for (const id of modules) {
      assert.ok(!['/src/app/Application.tsx', '/src/app/PublicPages.tsx', '/@tanstack/query-core/', '/@tanstack/react-query/', '/@radix-ui/react-tooltip/', '/@radix-ui/react-dropdown-menu/'].some(path => id.includes(path)), `workspace/public document module in landing startup: ${id}`);
    }
  },
}] });
await copyFile('src/assets/fonts/OFL.txt', 'dist/OFL.txt');
await build({
  build: { ssr: 'src/entry-server.tsx', outDir: 'dist-ssr' },
});
const { renderPage } = await import('../dist-ssr/entry-server.js');
const template = await readFile('dist/index.html', 'utf8');
for (const [path, file] of [
  ['/support', 'support.html'],
  ['/privacy', 'privacy.html'],
  ['/', 'index.html'],
  ['/404', '404.html'],
  [null, 'app.html'],
]) {
  const { head, body } = renderPage(path);
  await writeFile(`dist/${file}`, renderDocument(template, { head, body, prerendered: path !== null }));
}
const { verifyBuild } = await import('./verify-build.mjs');
await verifyBuild();
