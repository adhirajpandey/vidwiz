import * as Dropdown from '@radix-ui/react-dropdown-menu';
import type { ComponentPropsWithoutRef } from 'react';
import { cn } from '../../lib/utils';

export const Menu = Dropdown.Root;
export const MenuTrigger = Dropdown.Trigger;

export function MenuContent({ className, align = 'end', ...props }: ComponentPropsWithoutRef<typeof Dropdown.Content>) {
  return (
    <Dropdown.Portal>
      <Dropdown.Content
        align={align}
        sideOffset={6}
        className={cn('z-50 min-w-44 rounded-lg border border-border bg-card p-1 text-sm shadow-lg', className)}
        {...props}
      />
    </Dropdown.Portal>
  );
}

export function MenuItem({ className, ...props }: ComponentPropsWithoutRef<typeof Dropdown.Item>) {
  return (
    <Dropdown.Item
      className={cn('flex select-none items-center gap-2 rounded-md px-2.5 py-2 outline-none data-[highlighted]:bg-muted', className)}
      {...props}
    />
  );
}

export const MenuSeparator = () => <Dropdown.Separator className="my-1 h-px bg-border" />;
