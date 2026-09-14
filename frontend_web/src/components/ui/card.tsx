import * as React from 'react';
import { cva, type VariantProps } from 'class-variance-authority';
import { cn } from '@/lib/utils';

function Card({ className, ...props }: React.ComponentProps<'div'>) {
  return (
    <div
      data-slot="card"
      className={cn(
        `
                  gap-3 py-4 shadow-sm rounded-xl flex flex-col border bg-card
                  text-card-foreground
                `,
        className
      )}
      {...props}
    />
  );
}

function CardHeader({ className, ...props }: React.ComponentProps<'div'>) {
  return (
    <div
      data-slot="card-header"
      className={cn(
        `
                  gap-2 px-4
                  [.border-b]:pb-4
                  @container/card-header grid auto-rows-min
                  grid-rows-[auto_auto] items-start
                  has-data-[slot=card-action]:grid-cols-[1fr_auto]
                `,
        className
      )}
      {...props}
    />
  );
}

const titleVariants = cva('font-semibold leading-none', {
  variants: {
    size: {
      small: 'text-sm',
      medium: 'text-base',
      large: 'text-2xl',
    },
  },
  defaultVariants: {
    size: 'medium',
  },
});

function CardTitle({
  className,
  size,
  ...props
}: React.ComponentProps<'div'> & VariantProps<typeof titleVariants>) {
  return (
    <div data-slot="card-title" className={cn(titleVariants({ size }), className)} {...props} />
  );
}

function CardDescription({ className, ...props }: React.ComponentProps<'div'>) {
  return (
    <div
      data-slot="card-description"
      className={cn('text-sm text-muted-foreground', className)}
      {...props}
    />
  );
}

function CardAction({ className, ...props }: React.ComponentProps<'div'>) {
  return (
    <div
      data-slot="card-action"
      className={cn('col-start-2 row-span-2 row-start-1 self-start justify-self-end', className)}
      {...props}
    />
  );
}

function CardContent({ className, ...props }: React.ComponentProps<'div'>) {
  return <div data-slot="card-content" className={cn('px-4', className)} {...props} />;
}

function CardFooter({ className, ...props }: React.ComponentProps<'div'>) {
  return (
    <div
      data-slot="card-footer"
      className={cn(
        `
                  px-4
                  [.border-t]:pt-4
                  flex items-center
                `,
        className
      )}
      {...props}
    />
  );
}

export { Card, CardHeader, CardFooter, CardTitle, CardAction, CardDescription, CardContent };
