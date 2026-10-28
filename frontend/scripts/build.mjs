import { build } from 'vite';
import { copyFile, readFile, writeFile } from 'node:fs/promises';
import { renderDocument } from './render-document.mjs';

await build();
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
