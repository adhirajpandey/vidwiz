import { Link } from 'react-router-dom';
import PageTitle from '../../components/PageTitle';

export default function NotFoundPage() {
  return (
    <section className="mx-auto max-w-xl py-16 text-center">
      <PageTitle title="Page not found" />
      <h1 className="display text-4xl">Page not found</h1>
      <p className="mt-4 text-muted-foreground">This address does not match a VidWiz page.</p>
      <Link to="/" className="mt-6 inline-block font-semibold underline underline-offset-4">Go to VidWiz</Link>
    </section>
  );
}
