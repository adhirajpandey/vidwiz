import { useState } from 'react';
import type { FormEvent } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Check, Copy, KeyRound, Trash2 } from 'lucide-react';
import { authApi } from '../../api';
import type { ApiTokenCreated } from '../../api';
import config from '../../config';
import { useNotify } from '../../hooks/useNotify';
import Button from '../../components/ui/Button';
import { Input } from '../../components/ui/Input';
import { formatRelative } from '../../lib/format';
import { phoneCaptureExample } from './phoneCapture';

function CopyButton({ text, label }: { text: string; label: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <Button size="sm" onClick={async () => {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    }} aria-label={label}>
      {copied ? <Check className="size-3.5" /> : <Copy className="size-3.5" />}{copied ? 'Copied' : 'Copy'}
    </Button>
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
    mutationFn: (id: number) => authApi.revokeToken(id),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ['tokens'] }),
    onError: error => notify.error(error, 'Token not revoked', 'The token could not be revoked.'),
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
      {tokens.data && tokens.data.length > 0 && (
        <ul className="divide-y divide-border rounded-lg border border-border">
          {tokens.data.map(token => (
            <li key={token.id} className="flex items-center justify-between gap-3 px-3 py-2.5">
              <div className="min-w-0">
                <p className="truncate text-sm font-medium">{token.name} <span className="font-mono text-xs text-muted-foreground">…{token.token_hint}</span></p>
                <p className="text-xs text-muted-foreground">
                  Created {formatRelative(token.created_at)}, {token.last_used_at ? `last used ${formatRelative(token.last_used_at)}` : 'never used'}
                </p>
              </div>
              <Button variant="danger" size="sm" onClick={() => revoke.mutate(token.id)} disabled={revoke.isPending}>
                <Trash2 className="size-3.5" />Revoke
              </Button>
            </li>
          ))}
        </ul>
      )}
      <details className="rounded-lg border border-border p-3 text-sm">
        <summary className="cursor-pointer font-medium">Capture from your phone</summary>
        <div className="mt-3 space-y-2 text-muted-foreground">
          <p>Send the video title and current time from an automation (for example MacroDroid or iOS Shortcuts). VidWiz finds the video, saves the moment, and adds the AI line if your default is on.</p>
          <pre className="overflow-x-auto rounded-md bg-muted p-3 font-mono text-xs text-foreground">{phoneCaptureExample(config.API_URL)}</pre>
          <p>Send <code className="font-mono">video</code> with a link instead of <code className="font-mono">title</code> when the app can share the URL.</p>
        </div>
      </details>
    </div>
  );
}
