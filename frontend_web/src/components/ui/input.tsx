import * as React from 'react';

import { cn } from '@/lib/utils';

const Input = React.forwardRef<HTMLInputElement, React.ComponentProps<'input'>>(
  ({ className, type, ...props }, ref) => {
    return (
      <input
        type={type}
        className={cn(
          `
                      h-9 px-3 py-2 text-base shadow-xs
                      md:text-sm
                      rounded-lg flex field-sizing-content w-full border
                      border-border bg-input
                      transition-[color,box-shadow,border] duration-300
                      outline-none
                      placeholder:text-muted-foreground
                      hover:border-muted-foreground
                      focus:border-accent
                      disabled:cursor-not-allowed disabled:border-border/20
                      placeholder:disabled:text-muted-foreground/50
                      aria-invalid:border-destructive-foreground
                    `,
          className
        )}
        ref={ref}
        {...props}
      />
    );
  }
);
Input.displayName = 'Input';

export { Input };
