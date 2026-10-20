import { useEffect, useState } from 'react';
import type { ReactNode } from 'react';
import { useLocation } from 'react-router-dom';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { Chrome } from 'lucide-react';
import { authApi } from '../../api';
import config from '../../config';
import { useNotify } from '../../hooks/useNotify';
import { PROFILE_KEY, useProfile } from '../../hooks/useProfile';
import PageTitle from '../../components/PageTitle';
import Button from '../../components/ui/Button';
import { Input } from '../../components/ui/Input';
import CreditsSection from './CreditsSection';
import TokensSection from './TokensSection';

function Section({ id, title, children }: { id: string; title: string; children: ReactNode }) {
  return (
    <section id={id} aria-labelledby={`${id}-title`} className="moment-anchor rounded-[14px] border border-border bg-card p-6">
      <h2 id={`${id}-title`} className="display mb-4 text-xl">{title}</h2>
      {children}
    </section>
  );
}

function AccountSection() {
  const profile = useProfile();
  const queryClient = useQueryClient();
  const notify = useNotify();
  const [name, setName] = useState('');
  useEffect(() => { if (profile.data?.name) setName(profile.data.name); }, [profile.data?.name]);
  const update = useMutation({
    mutationFn: authApi.updateProfile,
    onSuccess: data => {
      queryClient.setQueryData(PROFILE_KEY, data);
      notify.success('Saved');
    },
    onError: error => notify.error(error, 'Not saved', 'Your settings could not be saved.'),
  });
  return (
    <div className="space-y-5">
      <div className="space-y-1.5">
        <label htmlFor="name" className="text-sm font-medium">Name</label>
        <div className="flex gap-2">
          <Input id="name" value={name} onChange={event => setName(event.target.value)} maxLength={100} />
          <Button onClick={() => update.mutate({ name: name.trim() })} disabled={!name.trim() || name === profile.data?.name || update.isPending}>Save</Button>
        </div>
        <p className="text-xs text-muted-foreground">{profile.data?.email}</p>
      </div>
      <label className="flex cursor-pointer items-start gap-3">
        <input
          type="checkbox"
          className="mt-1 accent-[hsl(var(--foreground))]"
          checked={profile.data?.ai_moments_default ?? false}
          disabled={!profile.data || update.isPending}
          onChange={event => update.mutate({ ai_moments_default: event.target.checked })}
        />
        <span>
          <span className="block text-sm font-medium">Add an AI line to new moments</span>
          <span className="block text-xs text-muted-foreground">1 credit per moment. Phone and extension captures use this unless they say otherwise.</span>
        </span>
      </label>
    </div>
  );
}

export default function SettingsPage() {
  const location = useLocation();
  useEffect(() => {
    if (location.hash) document.getElementById(location.hash.slice(1))?.scrollIntoView();
  }, [location.hash]);
  return (
    <div className="mx-auto max-w-2xl space-y-5">
      <PageTitle title="Settings" />
      <h1 className="display text-4xl">Settings</h1>
      <Section id="account" title="Account"><AccountSection /></Section>
      <Section id="credits" title="Credits"><CreditsSection /></Section>
      <Section id="tokens" title="API tokens"><TokensSection /></Section>
      <Section id="extension" title="Browser extension">
        <p className="mb-3 text-sm leading-6 text-muted-foreground">Capture on YouTube with one key. The extension signs in with this account automatically.</p>
        <a href={config.CHROME_WEBSTORE_URL} target="_blank" rel="noopener noreferrer" className="inline-flex h-10 items-center gap-2 rounded-lg border border-border px-4 text-sm font-medium hover:bg-muted">
          <Chrome className="size-4" />Get the extension
        </a>
      </Section>
    </div>
  );
}
