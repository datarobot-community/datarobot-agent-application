import * as React from 'react';
import * as ScrollAreaPrimitive from '@radix-ui/react-scroll-area';

import { cn } from '@/lib/utils';

function ScrollArea({
  className,
  children,
  scrollViewportRef,
  ...props
}: React.ComponentProps<typeof ScrollAreaPrimitive.Root> & {
  scrollViewportRef?: React.Ref<HTMLDivElement>;
}) {
  return (
    <ScrollAreaPrimitive.Root
      data-slot="scroll-area"
      className={cn('relative', className)}
      {...props}
    >
      {/* 
      [&>div]:block! is a workaround for the issue in Radix UI where the scroll area has display: table
      https://github.com/radix-ui/primitives/issues/2964
      https://github.com/shadcn-ui/ui/issues/8342
      */}
      <ScrollAreaPrimitive.Viewport
        ref={scrollViewportRef}
        data-slot="scroll-area-viewport"
        className={`
                  size-full rounded-[inherit] transition-[color,box-shadow]
                  outline-none
                  focus-visible:ring-[3px] focus-visible:ring-ring/50
                  focus-visible:outline-1
                  [&>div]:block!
                `}
      >
        {children}
      </ScrollAreaPrimitive.Viewport>
      <ScrollBar />
      <ScrollAreaPrimitive.Corner />
    </ScrollAreaPrimitive.Root>
  );
}

function ScrollBar({
  className,
  orientation = 'vertical',
  ...props
}: React.ComponentProps<typeof ScrollAreaPrimitive.ScrollAreaScrollbar>) {
  return (
    <ScrollAreaPrimitive.ScrollAreaScrollbar
      data-slot="scroll-area-scrollbar"
      orientation={orientation}
      className={cn(
        'flex touch-none p-px transition-colors select-none',
        orientation === 'vertical' && `w-2.5 h-full border-l border-l-transparent`,
        orientation === 'horizontal' && `h-2.5 flex-col border-t border-t-transparent`,
        className
      )}
      {...props}
    >
      <ScrollAreaPrimitive.ScrollAreaThumb
        data-slot="scroll-area-thumb"
        className="relative flex-1 rounded-full bg-border"
      />
    </ScrollAreaPrimitive.ScrollAreaScrollbar>
  );
}

export { ScrollArea, ScrollBar };
