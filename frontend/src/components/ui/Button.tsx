import { forwardRef } from 'react';
import type { ButtonHTMLAttributes } from 'react';
import { cn } from '../../lib/utils';

type Variant = 'primary' | 'save' | 'secondary' | 'ghost' | 'danger';
type Size = 'sm' | 'md' | 'icon';

const variants: Record<Variant, string> = {
  primary: 'bg-accent text-accent-foreground hover:opacity-90',
  // Caption yellow: only for saving a moment.
  save: 'bg-saved text-saved-foreground hover:brightness-105',
  secondary: 'border border-border bg-card text-foreground hover:bg-muted',
  ghost: 'text-muted-foreground hover:bg-muted hover:text-foreground',
  danger: 'text-destructive hover:bg-destructive/10',
};

const sizes: Record<Size, string> = {
  sm: 'h-8 gap-1.5 px-2.5 text-xs',
  md: 'h-10 gap-2 px-4 text-sm',
  icon: 'size-9 justify-center',
};

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
}

const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant = 'secondary', size = 'md', className, type = 'button', ...props },
  ref,
) {
  return (
    <button
      ref={ref}
      type={type}
      className={cn(
        'inline-flex shrink-0 items-center rounded-[9px] font-semibold transition-[color,background-color,filter,opacity] disabled:pointer-events-none disabled:opacity-50',
        variants[variant],
        sizes[size],
        className,
      )}
      {...props}
    />
  );
});

export default Button;
