import { Helmet } from 'react-helmet-async';
import { documentTitle } from '../lib/title';

/** Document title for signed-in pages, which are never indexed. Parts go most specific first. */
export default function PageTitle({ title }: { title: string | string[] }) {
  return (
    <Helmet>
      <title>{documentTitle(...[title].flat())}</title>
      <meta name="robots" content="noindex" />
    </Helmet>
  );
}
