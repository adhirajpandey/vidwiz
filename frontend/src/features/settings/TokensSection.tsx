import { useEffect, useRef, useState } from 'react';
import type { FormEvent } from 'react';
import { useMutation, useMutationState, useQuery, useQueryClient } from '@tanstack/react-query';
import { Check, Copy, KeyRound, Trash2 } from 'lucide-react';
import { authApi } from '../../api';
import type { ApiTokenCreated, ApiTokenRead } from '../../api';
import config from '../../config';
import { useNotify } from '../../hooks/useNotify';
import Button from '../../components/ui/Button';
import ErrorState from '../../components/ui/ErrorState';
import { Input } from '../../components/ui/Input';
import { formatRelative } from '../../lib/format';
import { phoneCaptureExample } from './phoneCapture';

function CopyButton({ text, label }: { text: string; label: string }) {
  const [copied, setCopied] = useState(false);
  const notify = useNotify();
  return (
    <>
      <Button size="sm" onClick={async () => {
        try {
          await navigator.clipboard.writeText(text);
        } catch (cause) {
          notify.error(cause, 'Not copied', 'Select the token and copy it yourself.');
          return;
        }
        setCopied(true);
        setTimeout(() => setCopied(false), 1500);
      }} aria-label={label}>
        {copied ? <Check className="size-3.5" /> : <Copy className="size-3.5" />}{copied ? 'Copied' : 'Copy'}
      </Button>
      <span role="status" className="sr-only">{copied ? 'Copied' : ''}</span>
    </>
  );
}

/** A token row. Revoke asks inline first, like deleting a moment. */
function TokenRow({ token, pending, onRevoke }: { token: ApiTokenRead; pending: boolean; onRevoke: () => void }) {
  const [confirming, setConfirming] = useState(false);
  const revokeButton = useRef<HTMLButtonElement>(null);
  const confirmButton = useRef<HTMLButtonElement>(null);
  useEffect(() => { if (confirming) confirmButton.current?.focus(); }, [confirming]);
  const cancel = () => { setConfirming(false); setTimeout(() => revokeButton.current?.focus()); };
  return (
    <li className="flex flex-wrap items-center justify-between gap-3 px-3 py-2.5" onKeyDown={event => { if (confirming && !pending && event.key === 'Escape') cancel(); }}>
      <div className="min-w-0">
        <p className="truncate text-sm font-medium">{token.name} <span className="font-mono text-xs text-muted-foreground">…{token.token_hint}</span></p>
        <p className="text-xs text-muted-foreground">
          Created {formatRelative(token.created_at)}, {token.last_used_at ? `last used ${formatRelative(token.last_used_at)}` : 'never used'}
        </p>
      </div>
      {confirming ? (
        <div role="group" aria-label={`Revoke ${token.name}`} className="flex items-center gap-2">
          <p className="text-xs text-muted-foreground">Clients using it stop saving.</p>
          <Button ref={confirmButton} variant="danger" size="sm" onClick={onRevoke} disabled={pending}>Revoke</Button>
          <Button variant="ghost" size="sm" onClick={cancel} disabled={pending}>Cancel</Button>
        </div>
      ) : (
        <Button ref={revokeButton} variant="danger" size="sm" onClick={() => setConfirming(true)} aria-label={`Revoke ${token.name}`}>
          <Trash2 className="size-3.5" />Revoke
        </Button>
      )}
    </li>
  );
}

export default function TokensSection() {
  const queryClient = useQueryClient();
  const notify = useNotify();
  const [name, setName] = useState('');
  const [created, setCreated] = useState<ApiTokenCreated | null>(null);
  const tokens = useQuery({ queryKey: ['tokens'], queryFn: authApi.listTokens });
  const create = useMutation({
    mutationFn: (tokenName: string) => authApi.createToken(tokenName),
    onSuccess: token => {
      setCreated(token);
      setName('');
      void queryClient.invalidateQueries({ queryKey: ['tokens'] });
    },
    onError: error => notify.error(error, 'Token not created', 'The token could not be created.'),
  });
  const revoke = useMutation({
    mutationKey: ['revokeToken'],
    mutationFn: (id: number) => authApi.revokeToken(id),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ['tokens'] }),
    onError: error => notify.error(error, 'Token not revoked', 'The token could not be revoked.'),
  });

  // Every revoke in flight, not just the latest one.
  const revoking = useMutationState({
    filters: { mutationKey: ['revokeToken'], status: 'pending' },
    select: mutation => mutation.state.variables as number,
  });

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (name.trim()) create.mutate(name.trim());
  };

  return (
    <div className="space-y-4">
      <p className="text-sm leading-6 text-muted-foreground">
        Tokens let capture clients, such as a phone automation, save moments for you. They can only capture; they cannot read your library.
      </p>
      {created && (
        <div role="status" className="space-y-2 rounded-[10px] bg-saved-soft p-3">
          <p className="text-sm font-medium">Copy “{created.name}” now. It is not shown again.</p>
          <div className="flex gap-2">
            <code className="min-w-0 flex-1 truncate rounded-md bg-card px-2 py-1.5 font-mono text-xs">{created.token}</code>
            <CopyButton text={created.token} label="Copy token" />
          </div>
        </div>
      )}
      <form onSubmit={submit} className="flex gap-2">
        <Input value={name} onChange={event => setName(event.target.value)} placeholder="Token name, e.g. Phone" aria-label="Token name" maxLength={80} />
        <Button type="submit" variant="primary" disabled={!name.trim() || create.isPending}><KeyRound className="size-4" />Create</Button>
      </form>
      {tokens.isPending && <p role="status" className="text-sm text-muted-foreground">Loading tokens…</p>}
      {tokens.isError && <ErrorState compact headingLevel={3} title={tokens.data ? 'Tokens did not refresh' : 'Tokens did not load'} message="Check your connection and try again." onRetry={() => void tokens.refetch()} />}
      {tokens.data?.length === 0 && <p className="text-sm text-muted-foreground">No tokens yet.</p>}
      {tokens.data && tokens.data.length > 0 && (
        <ul className="divide-y divide-border rounded-lg border border-border">
          {tokens.data.map(token => (
            <TokenRow key={token.id} token={token} pending={revoking.includes(token.id)} onRevoke={() => revoke.mutate(token.id)} />
          ))}
        </ul>
      )}
      <details className="rounded-lg border border-border p-3 text-sm">
        <summary className="font-medium">Capture from your phone</summary>
        <div className="mt-3 space-y-2 text-muted-foreground">
          <p>Send the video title and current time from an automation (for example MacroDroid or iOS Shortcuts). VidWiz finds the video, saves the moment, and adds the AI line if your default is on.</p>
          <pre className="overflow-x-auto rounded-md bg-muted p-3 font-mono text-xs text-foreground">{phoneCaptureExample(config.API_URL)}</pre>
          <p>Send <code className="font-mono">video</code> with a link instead of <code className="font-mono">title</code> when the app can share the URL.</p>
        </div>
      </details>
    </div>
  );
}
