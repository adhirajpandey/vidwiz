import { useQuery } from '@tanstack/react-query';
import { Coins } from 'lucide-react';
import { useState } from 'react';
import { paymentsApi } from '../../api';
import { useNotify } from '../../hooks/useNotify';
import { useProfile } from '../../hooks/useProfile';
import Button from '../../components/ui/Button';

export default function CreditsSection() {
  const profile = useProfile();
  const products = useQuery({ queryKey: ['credit-products'], queryFn: paymentsApi.listProducts, staleTime: 3600_000 });
  const notify = useNotify();
  const [buying, setBuying] = useState<string | null>(null);

  const buy = async (productId: string) => {
    setBuying(productId);
    try {
      const session = await paymentsApi.createCheckoutSession({ product_id: productId });
      window.location.href = session.checkout_url;
    } catch (cause) {
      notify.error(cause, 'Checkout did not start', 'Checkout could not be started.');
      setBuying(null);
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <div className="flex size-10 items-center justify-center rounded-lg bg-accent-soft text-accent"><Coins className="size-5" /></div>
        <div>
          <p className="text-2xl font-semibold tabular">{profile.data?.credits_balance ?? '—'}</p>
          <p className="text-xs text-muted-foreground">credits</p>
        </div>
      </div>
      <ul className="space-y-1 text-sm text-muted-foreground">
        <li>AI line on a moment: 1 credit, charged once per moment</li>
        <li>Ask about a video: 5 credits once per video, then free within the daily limit</li>
        <li>Moments, search, saved passages, and library questions: free</li>
      </ul>
      {products.data && (
        <div className="grid gap-2 sm:grid-cols-3">
          {products.data.products.map(product => (
            <button
              key={product.product_id}
              type="button"
              disabled={buying !== null}
              onClick={() => void buy(product.product_id)}
              className="rounded-lg border border-border p-3 text-left hover:border-accent hover:bg-accent-soft disabled:opacity-60"
            >
              <p className="font-semibold tabular">{product.credits} credits</p>
              <p className="text-sm text-muted-foreground tabular">₹{product.price_inr}</p>
            </button>
          ))}
        </div>
      )}
      {buying && <Button disabled size="sm">Opening checkout…</Button>}
    </div>
  );
}
