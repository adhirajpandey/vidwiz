import * as RadixTooltip from '@radix-ui/react-tooltip';
import { createContext, useContext } from 'react';
import type { FocusEvent, ReactElement, ReactNode } from 'react';

const Provided = createContext(false);

/** Shared timing, so moving from one hint to the next skips the delay. */
export function TooltipProvider({ children }: { children: ReactNode }) {
  return (
    <RadixTooltip.Provider delayDuration={400} skipDelayDuration={300}>
      <Provided.Provider value>{children}</Provided.Provider>
    </RadixTooltip.Provider>
  );
}

// Keyboard focus shows the hint at once; focus a click or a closing menu moves back stays quiet.
function quietUnlessKeyboard(event: FocusEvent<HTMLElement>) {
  try {
    if (!event.currentTarget.matches(':focus-visible')) event.preventDefault();
  } catch { /* no :focus-visible support: show it */ }
}

/**
 * A short hint for an icon-only control, in ink inverted from the theme. It
 * shows after 400 ms of hover or at once on keyboard focus, and Escape closes
 * it. The control keeps its own accessible name; use this instead of `title`.
 */
export function Tooltip({ label, children, side = 'top', align = 'center' }: {
  label: ReactNode;
  children: ReactElement;
  side?: 'top' | 'bottom' | 'left' | 'right';
  align?: 'start' | 'center' | 'end';
}) {
  const provided = useContext(Provided);
  const tip = (
    <RadixTooltip.Root>
      <RadixTooltip.Trigger asChild onFocus={quietUnlessKeyboard}>{children}</RadixTooltip.Trigger>
      <RadixTooltip.Portal>
        <RadixTooltip.Content
          side={side}
          align={align}
          sideOffset={6}
          collisionPadding={8}
          className="z-50 max-w-64 rounded-[7px] bg-foreground px-2.5 py-1.5 text-xs font-semibold leading-5 text-background shadow-md"
        >
          {label}
        </RadixTooltip.Content>
      </RadixTooltip.Portal>
    </RadixTooltip.Root>
  );
  return provided ? tip : <TooltipProvider>{tip}</TooltipProvider>;
}
