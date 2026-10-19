import { Helmet } from 'react-helmet-async';

/** Document title for signed-in pages, which are never indexed. */
export default function PageTitle({ title }: { title: string }) {
  return (
    <Helmet>
      <title>{`${title} · VidWiz`}</title>
      <meta name="robots" content="noindex" />
    </Helmet>
  );
}
