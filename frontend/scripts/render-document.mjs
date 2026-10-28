/** Keep the built scripts/styles while replacing the two explicit template slots. */
export function renderDocument(template, { head, body, prerendered }) {
  if (!template.includes('<!--seo-head-->') || !template.includes('<div id="root"></div>')) {
    throw new Error('Missing SEO head or React root slot in the HTML template');
  }
  return template
    .replace('<!--seo-head-->', () => head)
    .replace('<div id="root"></div>', () => `<div id="root"${prerendered ? ' data-prerendered="true"' : ''}>${body}</div>`);
}
