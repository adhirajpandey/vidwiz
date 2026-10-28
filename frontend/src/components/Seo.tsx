import { Helmet } from 'react-helmet-async';

type SeoProps = {
  title: string;
  description: string;
  path?: string;
  ogType?: 'website' | 'article';
  ogImage?: string;
  noIndex?: boolean;
};

const SITE_URL = 'https://vidwiz.online';
const DEFAULT_OG_IMAGE_URL = `${SITE_URL}/og-image.png`;

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
  const pageUrl = path ? `${SITE_URL}${normalizePath(path)}` : undefined;
  const resolvedOgImage = ogImage ?? DEFAULT_OG_IMAGE_URL;

  return (
    <Helmet defer={false}>
      <title>{title}</title>
      <meta name="description" content={description} />
      {pageUrl && <link rel="canonical" href={pageUrl} />}

      <meta property="og:title" content={title} />
      <meta property="og:description" content={description} />
      <meta property="og:type" content={ogType} />
      {pageUrl && <meta property="og:url" content={pageUrl} />}
      <meta property="og:site_name" content="VidWiz" />
      <meta property="og:image" content={resolvedOgImage} />
      {!ogImage && <meta property="og:image:width" content="1200" />}
      {!ogImage && <meta property="og:image:height" content="630" />}
      {!ogImage && <meta property="og:image:alt" content="VidWiz. Tap once. Find it later." />}
      <meta name="twitter:card" content="summary_large_image" />
      <meta name="twitter:title" content={title} />
      <meta name="twitter:description" content={description} />
      <meta name="twitter:image" content={resolvedOgImage} />
      {!ogImage && <meta name="twitter:image:alt" content="VidWiz. Tap once. Find it later." />}

      <meta name="robots" content={noIndex ? 'noindex, follow' : 'index, follow'} />
    </Helmet>
  );
}
