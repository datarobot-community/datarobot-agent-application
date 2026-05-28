'use client';

import * as React from 'react';
import * as TabsPrimitive from '@radix-ui/react-tabs';
import { cva, type VariantProps } from 'class-variance-authority';

import { cn } from '@/lib/utils';

type WithTestId<T> = T & { testId?: string };

const TABS_VARIANT = {
  default: 'default',
  underline: 'underline',
} as const;

type TabsVariant = (typeof TABS_VARIANT)[keyof typeof TABS_VARIANT];

const tabsListVariants = cva('inline-flex items-center', {
  variants: {
    variant: {
      [TABS_VARIANT.default]: 'rounded-lg border-2 border-sidebar-border bg-sidebar-border',
      [TABS_VARIANT.underline]: 'border-b border-border',
    },
  },
  defaultVariants: {
    variant: TABS_VARIANT.default,
  },
});

function Tabs({ className, ...props }: React.ComponentProps<typeof TabsPrimitive.Root>) {
  return <TabsPrimitive.Root className={cn(className)} {...props} />;
}

function TabsList({
  className,
  variant = TABS_VARIANT.default,
  testId = 'tabs-list',
  ...props
}: WithTestId<React.ComponentProps<typeof TabsPrimitive.List>> &
  VariantProps<typeof tabsListVariants>) {
  const resolvedVariant: TabsVariant = (variant ?? TABS_VARIANT.default) as TabsVariant;
  const listRef = React.useRef<HTMLDivElement>(null);
  const [indicatorStyle, setIndicatorStyle] = React.useState<{
    left: number;
    width: number;
  } | null>(null);

  const updateIndicator = React.useCallback(() => {
    if (resolvedVariant === TABS_VARIANT.underline && listRef.current) {
      const activeTab = listRef.current.querySelector('[data-state="active"]') as HTMLElement;

      if (activeTab) {
        const listRect = listRef.current.getBoundingClientRect();
        const tabRect = activeTab.getBoundingClientRect();
        setIndicatorStyle({
          left: tabRect.left - listRect.left,
          width: tabRect.width,
        });
      } else {
        setIndicatorStyle(null);
      }
    } else {
      setIndicatorStyle(null);
    }
  }, [resolvedVariant]);

  // Initial update and observe for changes in active state
  React.useEffect(() => {
    if (resolvedVariant === TABS_VARIANT.underline && listRef.current) {
      // Initial update
      updateIndicator();

      // Observe for changes in active state
      const observer = new MutationObserver(() => {
        updateIndicator();
      });

      observer.observe(listRef.current, {
        attributes: true,
        attributeFilter: ['data-state'],
        subtree: true,
      });

      // Also listen for resize events to update position
      const resizeObserver = new ResizeObserver(() => {
        updateIndicator();
      });

      resizeObserver.observe(listRef.current);

      return () => {
        observer.disconnect();
        resizeObserver.disconnect();
      };
    }
  }, [resolvedVariant, updateIndicator]);

  const isUnderline = resolvedVariant === TABS_VARIANT.underline;

  return (
    <TabsPrimitive.List
      data-slot="tabs-list"
      data-testid={testId}
      data-variant={resolvedVariant}
      className={cn(
        tabsListVariants({ variant: resolvedVariant }),
        isUnderline && 'relative',
        'group',
        className
      )}
      {...props}
    >
      <div ref={listRef}>{props.children}</div>
      {isUnderline && indicatorStyle && (
        <span
          className="absolute bottom-0 h-0.5 bg-accent transition-all duration-300 ease-in-out"
          data-testid="tabs-indicator"
          style={{
            left: indicatorStyle.left,
            width: indicatorStyle.width,
          }}
        />
      )}
    </TabsPrimitive.List>
  );
}

function TabsTrigger({
  className,
  value,
  testId = `tabs-trigger-${value}`,
  ...props
}: WithTestId<React.ComponentProps<typeof TabsPrimitive.Trigger>>) {
  return (
    <TabsPrimitive.Trigger
      data-slot="tabs-trigger"
      data-testid={testId ?? 'tabs-trigger'}
      className={cn(
        // Base styles
        `
          inline-flex cursor-pointer items-center justify-center gap-1.5 text-sm font-medium transition-colors select-none
          disabled:cursor-default
        `,
        // Default variant styles
        'rounded-lg px-4 py-1.5 text-secondary-foreground',
        `
          outline-hidden
          focus:bg-muted focus:text-accent-foreground
          focus-visible:border-ring focus-visible:ring-[1px] focus-visible:ring-ring
        `,
        'hover:bg-muted hover:text-accent-foreground',
        `
          focus:z-2
          data-[state=active]:border-accent data-[state=active]:bg-sidebar-accent data-[state=active]:text-foreground
        `,
        'data-[disabled]:pointer-events-none data-[disabled]:text-muted-foreground data-[disabled]:opacity-50',
        // Underline variant styles (when parent has data-variant="underline")
        'group-data-[variant=underline]:rounded-none group-data-[variant=underline]:px-3 group-data-[variant=underline]:py-2',
        'group-data-[variant=underline]:focus-visible:ring-offset-2',
        'group-data-[variant=underline]:hover:bg-transparent',
        'group-data-[variant=underline]:data-[state=active]:border-0 group-data-[variant=underline]:data-[state=active]:bg-transparent',
        className
      )}
      value={value}
      {...props}
    />
  );
}

function TabsContent({
  className,
  value,
  testId = `tabs-content-${value}`,
  ...props
}: WithTestId<React.ComponentProps<typeof TabsPrimitive.Content>>) {
  return (
    <TabsPrimitive.Content
      data-slot="tabs-content"
      data-testid={testId}
      className={cn('mt-2 outline-none', className)}
      value={value}
      {...props}
    />
  );
}

export { Tabs, TabsList, TabsTrigger, TabsContent, TABS_VARIANT };
