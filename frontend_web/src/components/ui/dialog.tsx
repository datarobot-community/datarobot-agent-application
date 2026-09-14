'use client';

import * as React from 'react';
import * as DialogPrimitive from '@radix-ui/react-dialog';
import { XIcon } from 'lucide-react';

import { cn } from '@/lib/utils';
import { useTranslation } from '@/lib/i18n';

function Dialog({ ...props }: React.ComponentProps<typeof DialogPrimitive.Root>) {
  return <DialogPrimitive.Root data-slot="dialog" {...props} />;
}

function DialogTrigger({ ...props }: React.ComponentProps<typeof DialogPrimitive.Trigger>) {
  return <DialogPrimitive.Trigger data-slot="dialog-trigger" {...props} />;
}

function DialogPortal({ ...props }: React.ComponentProps<typeof DialogPrimitive.Portal>) {
  return <DialogPrimitive.Portal data-slot="dialog-portal" {...props} />;
}

function DialogClose({ ...props }: React.ComponentProps<typeof DialogPrimitive.Close>) {
  return <DialogPrimitive.Close data-slot="dialog-close" {...props} />;
}

function DialogOverlay({
  className,
  ...props
}: React.ComponentProps<typeof DialogPrimitive.Overlay>) {
  return (
    <DialogPrimitive.Overlay
      data-slot="dialog-overlay"
      className={cn(
        `
                  data-[state=closed]:animate-out data-[state=closed]:fade-out-0
                  data-[state=open]:animate-in data-[state=open]:fade-in-0
                  inset-0 bg-black/50 fixed z-50
                `,
        className
      )}
      {...props}
    />
  );
}

function DialogContent({
  className,
  children,
  ...props
}: React.ComponentProps<typeof DialogPrimitive.Content>) {
  const { t } = useTranslation();
  return (
    <DialogPortal>
      <DialogOverlay />
      <DialogPrimitive.Content
        data-slot="dialog-content"
        className={cn(
          // Background & Text
          'bg-input text-secondary-foreground',
          // Positioning & Layering
          `
                      fixed top-[50%] left-[50%] z-50
                      origin-(--radix-dialog-content-transform-origin)
                    `,
          // Transform
          '-translate-1/2',
          // Sizing
          'max-w-lg w-full',
          // Overflow
          'overflow-hidden',
          // Shape & Border
          'shadow-lg rounded-md border',
          // Spacing
          'p-6',
          // Animations (open / close)
          `
                      data-[state=closed]:animate-out
                      data-[state=open]:animate-in
                    `,
          `
                      data-[state=closed]:fade-out-0
                      data-[state=open]:fade-in-0
                    `,
          className
        )}
        {...props}
      >
        {children}
        <DialogPrimitive.Close
          className={cn(
            `
                          top-4 right-4 rounded-xs absolute opacity-70
                          ring-offset-background transition-opacity
                          hover:opacity-100
                          focus:ring-2 focus:ring-ring focus:ring-offset-2
                          focus:outline-hidden
                          disabled:pointer-events-none
                          data-[state=open]:bg-secondary
                        `
          )}
        >
          <XIcon className="size-4" />
          <span className="sr-only">{t('Close')}</span>
        </DialogPrimitive.Close>
      </DialogPrimitive.Content>
    </DialogPortal>
  );
}

function DialogHeader({ className, ...props }: React.ComponentProps<'div'>) {
  return (
    <div
      data-slot="dialog-header"
      className={cn(
        `
                  gap-1.5
                  sm:text-left
                  flex flex-col text-center
                `,
        className
      )}
      {...props}
    />
  );
}

function DialogFooter({ className, ...props }: React.ComponentProps<'div'>) {
  return (
    <div
      data-slot="dialog-footer"
      className={cn(
        `
                  gap-2
                  sm:flex-row sm:justify-end
                  flex flex-col-reverse
                `,
        className
      )}
      {...props}
    />
  );
}

function DialogTitle({ className, ...props }: React.ComponentProps<typeof DialogPrimitive.Title>) {
  return (
    <DialogPrimitive.Title
      data-slot="dialog-title"
      className={cn('heading-04 leading-none', className)}
      {...props}
    />
  );
}

function DialogDescription({
  className,
  ...props
}: React.ComponentProps<typeof DialogPrimitive.Description>) {
  return (
    <DialogPrimitive.Description
      data-slot="dialog-description"
      data-testid="dialog-description"
      className={cn('body-secondary', className)}
      {...props}
    />
  );
}

export {
  Dialog,
  DialogTrigger,
  DialogPortal,
  DialogClose,
  DialogOverlay,
  DialogContent,
  DialogHeader,
  DialogFooter,
  DialogTitle,
  DialogDescription,
};
