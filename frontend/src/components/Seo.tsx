import { Helmet } from 'react-helmet-async';

type SeoProps = {
  title: string;
  description: string;
  path: string;
  ogType?: 'website' | 'article';
  ogImage?: string;
  noIndex?: boolean;
};

const SITE_URL = 'https://vidwiz.online';

function normalizePath(path: string): string {
  if (!path.startsWith('/')) {
    return `/${path}`;
  }
  if (path !== '/' && path.endsWith('/')) {
    return path.slice(0, -1);
  }
  return path;
}

export default function Seo({
  title,
  description,
  path,
  ogType = 'website',
  ogImage,
  noIndex = false,
}: SeoProps) {
  const normalizedPath = normalizePath(path);
  const pageUrl = `${SITE_URL}${normalizedPath}`;

  return (
    <Helmet defer={false}>
      <title>{title}</title>
      <meta name="description" content={description} />
      <link rel="canonical" href={pageUrl} />

      <meta property="og:title" content={title} />
      <meta property="og:description" content={description} />
      <meta property="og:type" content={ogType} />
      <meta property="og:url" content={pageUrl} />
      {ogImage ? <meta property="og:image" content={ogImage} /> : null}

      {noIndex ? <meta name="robots" content="noindex, nofollow" /> : null}
    </Helmet>
  );
}
