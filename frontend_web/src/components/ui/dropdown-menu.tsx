'use client';

import * as React from 'react';
import * as DropdownMenuPrimitive from '@radix-ui/react-dropdown-menu';
import { Checkbox } from '@/components/ui/checkbox';
import { ChevronRightIcon, CircleIcon } from 'lucide-react';

import { cn } from '@/lib/utils';

function DropdownMenu({ ...props }: React.ComponentProps<typeof DropdownMenuPrimitive.Root>) {
  return <DropdownMenuPrimitive.Root data-slot="dropdown-menu" {...props} />;
}

function DropdownMenuPortal({
  ...props
}: React.ComponentProps<typeof DropdownMenuPrimitive.Portal>) {
  return <DropdownMenuPrimitive.Portal data-slot="dropdown-menu-portal" {...props} />;
}

function DropdownMenuTrigger({
  ...props
}: React.ComponentProps<typeof DropdownMenuPrimitive.Trigger>) {
  return <DropdownMenuPrimitive.Trigger data-slot="dropdown-menu-trigger" {...props} />;
}

function DropdownMenuContent({
  className,
  sideOffset = 4,
  ...props
}: React.ComponentProps<typeof DropdownMenuPrimitive.Content>) {
  return (
    <DropdownMenuPrimitive.Portal>
      <DropdownMenuPrimitive.Content
        data-slot="dropdown-menu-content"
        sideOffset={sideOffset}
        className={cn(
          // Background & Text
          'bg-input text-foreground',
          // Positioning & Layering
          `
                      z-50
                      origin-(--radix-dropdown-menu-content-transform-origin)
                    `,
          // Sizing
          `
                      max-h-(--radix-dropdown-menu-content-available-height)
                      min-w-[8rem]
                    `,
          // Overflow
          'overflow-x-hidden overflow-y-auto',
          // Shape & Border
          'shadow-md rounded-md border',
          // Spacing
          'py-2',
          // Animations (open / close)
          `
                      data-[state=closed]:animate-out
                      data-[state=open]:animate-in
                    `,
          `
                      data-[state=closed]:fade-out-0
                      data-[state=open]:fade-in-0
                    `,
          `
                      data-[state=closed]:zoom-out-95
                      data-[state=open]:zoom-in-95
                    `,
          // Animations based on menu side
          'data-[side=bottom]:slide-in-from-top-2',
          'data-[side=top]:slide-in-from-bottom-2',
          'data-[side=left]:slide-in-from-right-2',
          'data-[side=right]:slide-in-from-left-2',
          className
        )}
        {...props}
      />
    </DropdownMenuPrimitive.Portal>
  );
}

function DropdownMenuGroup({ ...props }: React.ComponentProps<typeof DropdownMenuPrimitive.Group>) {
  return <DropdownMenuPrimitive.Group data-slot="dropdown-menu-group" {...props} />;
}

function DropdownMenuItem({
  className,
  inset,
  selected = false,
  variant = 'default',
  testId,
  ...props
}: React.ComponentProps<typeof DropdownMenuPrimitive.Item> & {
  inset?: boolean;
  selected?: boolean;
  variant?: 'default' | 'destructive';
  testId?: string;
}) {
  return (
    <DropdownMenuPrimitive.Item
      data-slot="dropdown-menu-item"
      data-inset={inset}
      data-variant={variant}
      data-testid={testId}
      className={cn(
        `
                  daisbled:cursor-default
                  gap-2 px-4 py-2 text-sm
                  data-[inset]:pl-8
                  [&_svg:not([class*='size-'])]:size-4
                  relative flex cursor-pointer items-center text-foreground
                  outline-hidden select-none
                  focus:bg-sidebar-accent
                  data-[disabled]:pointer-events-none data-[disabled]:opacity-50
                  data-[variant=destructive]:text-destructive
                  data-[variant=destructive]:focus:bg-destructive/10
                  data-[variant=destructive]:focus:text-destructive
                  dark:data-[variant=destructive]:focus:bg-destructive/20
                  [&_svg]:pointer-events-none [&_svg]:shrink-0
                  [&_svg:not([class*='text-'])]:text-muted-foreground
                  data-[variant=destructive]:*:[svg]:text-destructive!
                `,
        selected && 'border-l-2 border-accent bg-secondary',
        className
      )}
      {...props}
    />
  );
}

function DropdownMenuCheckboxItem({
  className,
  children,
  checked,
  ...props
}: React.ComponentProps<typeof DropdownMenuPrimitive.CheckboxItem>) {
  return (
    <DropdownMenuPrimitive.CheckboxItem
      data-slot="dropdown-menu-checkbox-item"
      className={cn(
        `
                  group gap-2 py-1.5 pr-2 pl-10 text-sm
                  [&_svg:not([class*='size-'])]:size-4
                  relative flex cursor-pointer items-center outline-hidden
                  select-none
                  focus:bg-secondary
                  disabled:cursor-default
                  data-[disabled]:pointer-events-none
                  data-[disabled]:text-muted-foreground
                  [&_svg]:pointer-events-none [&_svg]:shrink-0
                `,
        className
      )}
      checked={checked}
      {...props}
    >
      <span className="left-4 absolute flex">
        <Checkbox
          checked={checked}
          disabled={props.disabled}
          className={`
                      group-hover:border-[color-mix(in_oklch,var(--accent)_80%,white)]
                      group-hover:data-[state=checked]:bg-[color-mix(in_oklch,var(--accent)_80%,white)]
                    `}
        />
      </span>
      {children}
    </DropdownMenuPrimitive.CheckboxItem>
  );
}

function DropdownMenuRadioGroup({
  ...props
}: React.ComponentProps<typeof DropdownMenuPrimitive.RadioGroup>) {
  return <DropdownMenuPrimitive.RadioGroup data-slot="dropdown-menu-radio-group" {...props} />;
}

function DropdownMenuRadioItem({
  className,
  children,
  ...props
}: React.ComponentProps<typeof DropdownMenuPrimitive.RadioItem>) {
  return (
    <DropdownMenuPrimitive.RadioItem
      data-slot="dropdown-menu-radio-item"
      className={cn(
        // Make this a group to target children on hover
        'group gap-2 relative flex items-center',
        // Spacing
        'py-1.5 pr-2 pl-10',
        // Typography
        'text-sm outline-hidden select-none',
        // Cursor / Interactivity
        `
                  cursor-pointer
                  disabled:cursor-default
                `,
        // Focus
        'focus:bg-secondary',
        // Disabled state
        // 'data-[disabled]:pointer-events-none data-[disabled]:opacity-50',
        `
                  data-[disabled]:pointer-events-none
                  data-[disabled]:cursor-not-allowed
                  data-[disabled]:text-muted-foreground
                `,
        `
                  data-[state=checked]:data-[disabled]:[&>*]:border-muted-foreground
                `,
        // SVG / Child elements
        `
                  [&_svg:not([class*='size-'])]:size-4
                  [&_svg]:pointer-events-none [&_svg]:shrink-0
                `,
        // Checked state
        'data-[state=checked]:[&>*]:border-accent',
        className
      )}
      {...props}
    >
      <span
        className={cn(
          // Positioning
          'left-4 pointer-events-none absolute',
          // Layout / Flex
          'size-4 flex items-center justify-center',
          // Shape / Border / Shadow
          'rounded-2xl shadow-xs border border-primary',
          // Transitions
          'transition-[border,color,fill,box-shadow]',
          // Hover state
          `
                      group-hover:border-[color-mix(in_oklch,var(--accent)_80%,white)]
                    `,
          // Disabled state
          'group-data-[disabled]:border-muted-foreground'
        )}
      >
        <DropdownMenuPrimitive.ItemIndicator>
          <CircleIcon
            className={cn(
              // Size
              'size-2',
              // Colors
              'fill-accent stroke-accent',
              // Hover state
              `
                              group-hover:fill-[color-mix(in_oklch,var(--accent)_80%,white)]
                            `,
              `
                              group-hover:stroke-[color-mix(in_oklch,var(--accent)_80%,white)]
                            `,
              // Disabled state
              `
                              group-data-[disabled]:fill-muted-foreground
                              group-data-[disabled]:stroke-muted-foreground
                            `
            )}
          />
        </DropdownMenuPrimitive.ItemIndicator>
      </span>
      {children}
    </DropdownMenuPrimitive.RadioItem>
  );
}

function DropdownMenuLabel({
  className,
  inset,
  ...props
}: React.ComponentProps<typeof DropdownMenuPrimitive.Label> & {
  inset?: boolean;
}) {
  return (
    <DropdownMenuPrimitive.Label
      data-slot="dropdown-menu-label"
      data-inset={inset}
      className={cn(
        `
                  px-4 py-2
                  data-[inset]:pl-8
                  mn-label
                `,
        className
      )}
      {...props}
    />
  );
}

function DropdownMenuSeparator({
  className,
  ...props
}: React.ComponentProps<typeof DropdownMenuPrimitive.Separator>) {
  return (
    <DropdownMenuPrimitive.Separator
      data-slot="dropdown-menu-separator"
      className={cn('-mx-1 my-1 h-px bg-border', className)}
      {...props}
    />
  );
}

function DropdownMenuShortcut({ className, ...props }: React.ComponentProps<'span'>) {
  return (
    <span
      data-slot="dropdown-menu-shortcut"
      className={cn('tracking-widest ml-auto caption-01', className)}
      {...props}
    />
  );
}

function DropdownMenuSub({ ...props }: React.ComponentProps<typeof DropdownMenuPrimitive.Sub>) {
  return <DropdownMenuPrimitive.Sub data-slot="dropdown-menu-sub" {...props} />;
}

function DropdownMenuSubTrigger({
  className,
  inset,
  children,
  selected = false,
  ...props
}: React.ComponentProps<typeof DropdownMenuPrimitive.SubTrigger> & {
  inset?: boolean;
  selected?: boolean;
}) {
  return (
    <DropdownMenuPrimitive.SubTrigger
      data-slot="dropdown-menu-sub-trigger"
      data-inset={inset}
      className={cn(
        `
                  daisbled:cursor-default
                  gap-2 px-4 py-2 text-sm
                  data-[inset]:pl-8
                  [&_svg:not([class*='size-'])]:size-4
                  flex cursor-pointer items-center outline-hidden select-none
                  focus:bg-sidebar-accent
                  data-[state=open]:bg-secondary
                  [&_svg]:pointer-events-none [&_svg]:shrink-0
                  [&_svg:not([class*='text-'])]:text-muted-foreground
                `,
        selected && 'border-l-2 border-accent',
        className
      )}
      {...props}
    >
      {children}
      <ChevronRightIcon className="size-4 ml-auto" />
    </DropdownMenuPrimitive.SubTrigger>
  );
}

function DropdownMenuSubContent({
  className,
  ...props
}: React.ComponentProps<typeof DropdownMenuPrimitive.SubContent>) {
  return (
    <DropdownMenuPrimitive.SubContent
      data-slot="dropdown-menu-sub-content"
      className={cn(
        `
                  data-[side=bottom]:slide-in-from-top-2
                  data-[side=left]:slide-in-from-right-2
                  data-[side=right]:slide-in-from-left-2
                  data-[side=top]:slide-in-from-bottom-2
                  data-[state=closed]:animate-out data-[state=closed]:fade-out-0
                  data-[state=closed]:zoom-out-95
                  data-[state=open]:animate-in data-[state=open]:fade-in-0
                  data-[state=open]:zoom-in-95
                  py-2 shadow-lg z-50 min-w-[8rem]
                  origin-(--radix-dropdown-menu-content-transform-origin)
                  overflow-hidden rounded-md border bg-input
                  text-secondary-foreground
                `,
        className
      )}
      {...props}
    />
  );
}

export {
  DropdownMenu,
  DropdownMenuPortal,
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuLabel,
  DropdownMenuItem,
  DropdownMenuCheckboxItem,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuSeparator,
  DropdownMenuShortcut,
  DropdownMenuSub,
  DropdownMenuSubTrigger,
  DropdownMenuSubContent,
};
