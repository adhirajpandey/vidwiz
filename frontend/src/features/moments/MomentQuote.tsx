import { useId, useLayoutEffect, useRef, useState } from 'react';
import { ChevronDown } from 'lucide-react';
import { cn } from '../../lib/utils';

const quoteText = 'border-l-2 border-border pl-3 text-sm leading-6 text-muted-foreground';
const toggle = 'inline-flex items-center gap-1 text-xs font-semibold text-muted-foreground hover:text-foreground';

/**
 * The transcript around a moment. When the moment has its own words (an AI
 * line or a note), the quote folds away behind "What was said". When the quote
 * is all the moment has, it shows as a three-line preview. Either opens to the
 * full quote.
 */
export default function MomentQuote({ quote, folded }: { quote: string; folded: boolean }) {
  const [open, setOpen] = useState(false);
  const id = useId();

  if (folded) {
    return (
      <div>
        <button type="button" aria-expanded={open} aria-controls={id} onClick={() => setOpen(!open)} className={toggle}>
          <ChevronDown className={cn('size-3.5 motion-safe:transition-transform', open && 'rotate-180')} />What was said
        </button>
        {/* Rows from 0fr to 1fr animate the height without measuring it. */}
        <div
          id={id}
          inert={!open}
          className={cn('grid motion-safe:transition-[grid-template-rows] motion-safe:duration-200', open ? 'grid-rows-[1fr]' : 'grid-rows-[0fr]')}
        >
          <div className="overflow-hidden">
            <blockquote className={cn(quoteText, 'mt-1.5')}>{quote}</blockquote>
          </div>
        </div>
      </div>
    );
  }
  return <QuotePreview quote={quote} open={open} onToggle={() => setOpen(!open)} />;
}

function QuotePreview({ quote, open, onToggle }: { quote: string; open: boolean; onToggle: () => void }) {
  const ref = useRef<HTMLQuoteElement>(null);
  const [clipped, setClipped] = useState(false);

  useLayoutEffect(() => {
    const element = ref.current;
    if (!element || open) return;
    const check = () => setClipped(element.scrollHeight > element.clientHeight + 1);
    check();
    if (typeof ResizeObserver === 'undefined') return;
    const observer = new ResizeObserver(check);
    observer.observe(element);
    return () => observer.disconnect();
  }, [open, quote]);

  return (
    <div className="space-y-1">
      <blockquote ref={ref} className={cn(quoteText, !open && 'line-clamp-3')}>{quote}</blockquote>
      {(clipped || open) && (
        <button type="button" aria-expanded={open} onClick={onToggle} className={toggle}>
          <ChevronDown className={cn('size-3.5 motion-safe:transition-transform', open && 'rotate-180')} />
          {open ? 'Show less' : 'Show all'}
        </button>
      )}
    </div>
  );
}
