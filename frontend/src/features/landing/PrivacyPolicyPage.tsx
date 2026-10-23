import type { ReactNode } from 'react';
import Seo from '../../components/Seo';
import { documentTitle } from '../../lib/title';

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="border-t-2 border-foreground pt-5">
      <h2 className="display mb-4 text-2xl">{title}</h2>
      <div className="space-y-4 leading-7 text-foreground/85">{children}</div>
    </section>
  );
}

export default function PrivacyPolicyPage() {
  return (
    <>
      <Seo
        title={documentTitle('Privacy Policy')}
        description="Read how VidWiz handles your data, including account information, Smart Notes, and product usage details."
        path="/privacy"
      />
      <article className="mx-auto max-w-2xl py-6 md:py-12">
        <header className="mb-14">
          <p className="mb-3 text-sm font-semibold text-muted-foreground">Privacy Policy</p>
          <h1 className="display text-5xl">Your Privacy Matters</h1>
          <p className="mt-5 text-lg leading-8 text-muted-foreground">
            Transparency about how we handle your data is at the core of VidWiz.
          </p>
        </header>

        <div className="space-y-12">
          <Section title="Introduction">
            <p>
              VidWiz ("we," "our," or "us") is committed to protecting your privacy. This Privacy Policy explains how our extension and services interact with your data. By using the VidWiz extension, you agree to the collection and use of information in accordance with this policy.
            </p>
          </Section>

          <Section title="Data Collection and Usage">
            <div>
              <h3 className="mb-2 text-lg font-bold text-foreground">User-Generated Content</h3>
              <p>
                When you use VidWiz to take notes or generate insights from videos, we process and store this content to provide you with our services. This includes:
              </p>
              <ul className="mt-2 list-disc space-y-1 pl-6">
                <li>Notes you create manually or with AI assistance.</li>
                <li>Timestamps and associated video metadata.</li>
                <li>Chat interactions with the Wiz assistant.</li>
              </ul>
            </div>
            <div>
              <h3 className="mb-2 text-lg font-bold text-foreground">Remote API Interaction</h3>
              <p>
                Our extension communicates with our backend servers at <code className="rounded-[5px] bg-surface px-1.5 py-0.5 text-sm">https://api.vidwiz.online/*</code>. This is necessary to:
              </p>
              <ul className="mt-2 list-disc space-y-1 pl-6">
                <li>Authenticate your account.</li>
                <li>Sync your notes across devices.</li>
                <li>Process AI requests for video analysis and chat.</li>
              </ul>
              <p className="mt-2">We do not sell your personal data or user-generated content to third parties.</p>
            </div>
          </Section>

          <Section title="Data Security">
            <p>
              We implement industry-standard security measures to protect your data during transmission and storage. All communication between the extension and our servers is encrypted using simple HTTPS (TLS/SSL). However, please be aware that no method of transmission over the internet is 100% secure.
            </p>
          </Section>

          <Section title="Contact Us">
            <p>If you have any questions about this Privacy Policy, please contact us at:</p>
            <a href="mailto:support@vidwiz.online" className="inline-block font-semibold underline decoration-foreground/30 underline-offset-4 hover:decoration-foreground">
              support@vidwiz.online
            </a>
          </Section>
        </div>
      </article>
    </>
  );
}
