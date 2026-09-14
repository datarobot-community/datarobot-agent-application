import * as React from 'react';
import { cva, type VariantProps } from 'class-variance-authority';

import { cn } from '@/lib/utils';

const ALERT_VARIANT = {
  destructive: 'destructive',
  info: 'info',
  warning: 'warning',
  success: 'success',
};

const alertVariants = cva(
  `
      gap-y-0.5 p-4
      has-[>svg]:gap-x-3
      [&>svg]:size-5
      rounded-lg relative grid w-full grid-cols-[0_1fr] items-start border
      bg-input body
      has-[>svg]:grid-cols-[calc(var(--spacing)*5)_1fr]
    `,
  {
    variants: {
      variant: {
        [ALERT_VARIANT.info]: `
                  border-primary
                  [&>svg]:text-primary
                `,
        [ALERT_VARIANT.destructive]: `
                  border-destructive-foreground
                  [&>svg]:text-destructive-foreground
                `,
        [ALERT_VARIANT.warning]: `
                  border-warning/75
                  [&>svg]:text-warning/75
                `,
        [ALERT_VARIANT.success]: `
                  border-success/75
                  [&>svg]:text-success/75
                `,
      },
    },
    defaultVariants: {
      variant: ALERT_VARIANT.info,
    },
  }
);

function Alert({
  className,
  variant,
  ...props
}: React.ComponentProps<'div'> & VariantProps<typeof alertVariants>) {
  return (
    <div
      data-slot="alert"
      role="alert"
      className={cn(alertVariants({ variant }), className)}
      {...props}
    />
  );
}

function AlertTitle({ className, ...props }: React.ComponentProps<'div'>) {
  return (
    <div
      data-slot="alert-title"
      className={cn(
        `
                  min-h-4 tracking-tight
                  [&:not(:last-child)]:mb-1
                  col-start-2 line-clamp-1 body
                `,
        className
      )}
      {...props}
    />
  );
}

function AlertDescription({ className, ...props }: React.ComponentProps<'div'>) {
  return (
    <div
      data-slot="alert-description"
      className={cn(
        `
                  gap-1
                  [&_p]:leading-relaxed
                  col-start-2 grid justify-items-start caption-01
                `,
        className
      )}
      {...props}
    />
  );
}

function AlertFooter({ className, ...props }: React.ComponentProps<'div'>) {
  return (
    <div
      data-slot="alert-footer"
      className={cn(
        `
                  mt-4 min-h-0 gap-4
                  [&>*:first-child]:pl-0
                  col-start-2 flex items-center body
                  [&>a]:no-underline
                `,
        className
      )}
      {...props}
    />
  );
}

export { Alert, AlertTitle, AlertDescription, AlertFooter, ALERT_VARIANT };
