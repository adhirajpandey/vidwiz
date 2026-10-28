import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { JSDOM } from 'jsdom';

export async function verifyBuild() {
  const pages = [['/', 'index.html'], ['/support', 'support.html'], ['/privacy', 'privacy.html']];
  for (const [path, file] of [...pages, [null, 'app.html'], [null, '404.html']]) {
    const html = await readFile(`dist/${file}`, 'utf8');
    const { document } = new JSDOM(html).window;
    assert.equal(document.querySelectorAll('title').length, 1, `${file}: one title`);
    assert.equal(document.querySelectorAll('meta[name="description"]').length, 1, `${file}: one description`);
    assert.equal(document.querySelectorAll('meta[name="robots"]').length, 1, `${file}: one robots directive`);
    assert.equal(document.querySelector('meta[name="robots"]').content, path ? 'index, follow' : 'noindex, follow');
    assert.equal(document.querySelectorAll('link[rel="canonical"]').length, path ? 1 : 0);
    if (path) assert.equal(document.querySelector('link[rel="canonical"]').href, `https://vidwiz.online${path}`);
    const root = document.getElementById('root');
    if (file === 'app.html') {
      assert.equal(root.innerHTML, '');
      assert.equal(root.dataset.prerendered, undefined);
    } else {
      assert.equal(root.dataset.prerendered, 'true');
      assert.equal(root.querySelectorAll('h1').length, 1, `${file}: rendered page heading`);
      if (path) assert.ok(root.textContent.length > 100, `${file}: rendered content`);
      else assert.ok(root.textContent.includes('Page not found'));
    }
    assert.ok(document.querySelector('script[type="module"][src^="/assets/"]'), `${file}: built client entry`);
    assert.ok(document.querySelector('link[rel="stylesheet"][href^="/assets/"]'), `${file}: built CSS`);
    assert.ok(!html.includes('<!--seo-head-->'));
    assert.equal(document.querySelector('script[src*="accounts.google.com"]'), null, `${file}: sign-in loads on demand`);
    assert.equal(document.querySelector('link[href*="fonts.googleapis.com"]'), null, `${file}: fonts are self-hosted`);
    if (file === 'index.html') {
      assert.equal(root.querySelectorAll('.hero .rv').length, 0, 'hero is visible without reveal effects');
      assert.equal(root.querySelectorAll('video[poster], video[src]').length, 0, 'no eager video or hidden poster requests');
      const preloads = [...document.querySelectorAll('link[rel="preload"][as="image"][media]')];
      assert.equal(preloads.length, 2, 'one hero preload per viewport');
      for (const preload of preloads) {
        assert.match(preload.getAttribute('href'), /^\/assets\/.+-[\w-]+\.webp$/);
        await readFile(`dist${preload.getAttribute('href')}`);
      }
      for (const source of root.querySelectorAll('picture source')) {
        await readFile(`dist${source.getAttribute('srcset')}`);
      }
    }
  }
  const sitemap = new JSDOM(await readFile('dist/sitemap.xml', 'utf8'), { contentType: 'text/xml' });
  assert.deepEqual([...sitemap.window.document.querySelectorAll('loc')].map(node => node.textContent).sort(),
    pages.map(([path]) => `https://vidwiz.online${path}`).sort());
  console.log('Verified public HTML, application shell, not-found page, and sitemap.');
}
