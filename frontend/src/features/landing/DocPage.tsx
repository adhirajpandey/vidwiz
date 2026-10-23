import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';

/** Layout shared by the public text pages, /privacy and /support. */
export function DocSection({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="border-t-2 border-foreground pt-5">
      <h2 className="display mb-4 text-2xl">{title}</h2>
      <div className="space-y-4 leading-7 text-foreground/85">{children}</div>
    </section>
  );
}

export function DocLink({ href, to, children }: { href?: string; to?: string; children: ReactNode }) {
  const className = 'font-semibold underline decoration-foreground/30 underline-offset-4 hover:decoration-foreground';
  if (to) return <Link to={to} className={className}>{children}</Link>;
  const external = href?.startsWith('http');
  return (
    <a href={href} className={className} {...(external ? { target: '_blank', rel: 'noopener noreferrer' } : {})}>
      {children}
    </a>
  );
}

export function DocCode({ children }: { children: ReactNode }) {
  return <code className="rounded-[5px] bg-surface px-1.5 py-0.5 text-sm [overflow-wrap:anywhere]">{children}</code>;
}

export default function DocPage({ eyebrow, title, intro, children }: { eyebrow: string; title: string; intro: ReactNode; children: ReactNode }) {
  return (
    <article className="mx-auto max-w-2xl py-6 md:py-12">
      <header className="mb-14">
        <p className="mb-3 text-sm font-semibold text-muted-foreground">{eyebrow}</p>
        <h1 className="display text-5xl">{title}</h1>
        <p className="mt-5 text-lg leading-8 text-muted-foreground">{intro}</p>
      </header>
      <div className="space-y-12">{children}</div>
    </article>
  );
}
