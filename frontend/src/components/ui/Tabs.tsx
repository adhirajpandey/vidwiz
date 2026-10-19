import * as RadixTabs from '@radix-ui/react-tabs';
import type { ComponentPropsWithoutRef } from 'react';
import { cn } from '../../lib/utils';

export const Tabs = RadixTabs.Root;

export function TabsList({ className, ...props }: ComponentPropsWithoutRef<typeof RadixTabs.List>) {
  return <RadixTabs.List className={cn('flex gap-1 overflow-x-auto border-b border-border [scrollbar-width:none]', className)} {...props} />;
}

export function TabsTrigger({ className, ...props }: ComponentPropsWithoutRef<typeof RadixTabs.Trigger>) {
  return (
    <RadixTabs.Trigger
      className={cn(
        '-mb-px inline-flex shrink-0 items-center gap-1.5 whitespace-nowrap border-b-2 border-transparent px-3 py-2.5 text-sm font-semibold text-muted-foreground transition-colors hover:text-foreground data-[state=active]:border-foreground data-[state=active]:text-foreground',
        className,
      )}
      {...props}
    />
  );
}

export const TabsContent = RadixTabs.Content;
