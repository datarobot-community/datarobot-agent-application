'use client';

import * as React from 'react';
import * as CheckboxPrimitive from '@radix-ui/react-checkbox';
import { Check, Minus } from 'lucide-react';

import { cn } from '@/lib/utils';

const Checkbox = React.forwardRef<
  React.ElementRef<typeof CheckboxPrimitive.Root>,
  React.ComponentPropsWithoutRef<typeof CheckboxPrimitive.Root>
>(({ className, checked, ...props }, ref) => {
  const isIndeterminate = checked === 'indeterminate';

  return (
    <CheckboxPrimitive.Root
      ref={ref}
      className={cn(
        // Layout & sizing
        'peer group size-4 rounded-sm shrink-0',
        // Border & ring
        'border border-primary ring-offset-background',
        // Cursor & interaction
        'hover:not-disabled:border-transparent',
        `
                  hover:not-disabled:data-[state=unchecked]:border-[color-mix(in_oklch,var(--accent)_80%,white)]
                `,
        'disabled:cursor-not-allowed',
        // Focus styles
        `
                  focus-visible:ring-2 focus-visible:ring-ring
                  focus-visible:ring-offset-2 focus-visible:outline-none
                `,
        // Transitions
        'ease-in transition-all duration-200',
        // Checked state
        'data-[state=checked]:bg-accent',
        'data-[state=checked]:border-accent',
        `
                  hover:not-disabled:data-[state=checked]:bg-[color-mix(in_oklch,var(--accent)_80%,white)]
                `,
        // Indeterminate state
        'data-[state=indeterminate]:bg-accent',
        'data-[state=indeterminate]:border-accent',
        'data-[state=indeterminate]:text-primary-foreground',
        `
                  hover:not-disabled:data-[state=indeterminate]:bg-[color-mix(in_oklch,var(--accent)_80%,white)]
                `,
        // Disabled states (combined)
        'disabled:border-muted-foreground',
        'disabled:data-[state=checked]:bg-muted-foreground',
        'disabled:data-[state=checked]:border-muted-foreground',
        'disabled:data-[state=indeterminate]:bg-muted-foreground',
        'disabled:data-[state=indeterminate]:border-muted-foreground',
        // Text color
        'text-primary-foreground',
        className
      )}
      checked={checked}
      {...props}
    >
      <CheckboxPrimitive.Indicator className={cn(`flex items-center justify-center`)}>
        {isIndeterminate ? <Minus className="size-full" /> : <Check className="size-full" />}
      </CheckboxPrimitive.Indicator>
    </CheckboxPrimitive.Root>
  );
});
Checkbox.displayName = CheckboxPrimitive.Root.displayName;

export { Checkbox };
