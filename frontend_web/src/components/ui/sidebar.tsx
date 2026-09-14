'use client';

import * as React from 'react';
import { Slot } from '@radix-ui/react-slot';
import { cva, type VariantProps } from 'class-variance-authority';
import { PanelLeftIcon } from 'lucide-react';

import { useIsMobile } from '@/hooks/use-mobile';
import { cn } from '@/lib/utils';
import { pxToRem, remToPx } from '@/lib/px-to-rem';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Separator } from '@/components/ui/separator';
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet';
import { Skeleton } from '@/components/ui/skeleton';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';
import { DraggableArea, type DraggableEvent } from '@/components/ui/draggable-area';
import { useTranslation } from '@/lib/i18n';

const SIDEBAR_COOKIE_NAME = 'sidebar_state';
const SIDEBAR_WIDTH_COOKIE_NAME = 'sidebar_width';
const SIDEBAR_COOKIE_MAX_AGE = 60 * 60 * 24 * 7;
const SIDEBAR_WIDTH = '16rem';
const SIDEBAR_WIDTH_MOBILE = '18rem';
const SIDEBAR_WIDTH_ICON = '3rem';
const SIDEBAR_KEYBOARD_SHORTCUT = 'b';
const SIDEBAR_MIN_WIDTH = pxToRem(200);
const SIDEBAR_MAX_WIDTH = pxToRem(480);

type SidebarContextProps = {
  state: 'expanded' | 'collapsed';
  open: boolean;
  setOpen: (open: boolean) => void;
  openMobile: boolean;
  setOpenMobile: (open: boolean) => void;
  isMobile: boolean;
  toggleSidebar: () => void;
  sidebarWidth: number;
  setSidebarWidth: (width: number) => void;
  minWidth: number;
  maxWidth: number;
  isResizing: boolean;
  setIsResizing: (isResizing: boolean) => void;
  resizable: boolean;
};

const SidebarContext = React.createContext<SidebarContextProps | null>(null);

function useSidebar() {
  const context = React.useContext(SidebarContext);
  if (!context) {
    throw new Error('useSidebar must be used within a SidebarProvider.');
  }

  return context;
}

function SidebarProvider({
  defaultOpen = true,
  open: openProp,
  onOpenChange: setOpenProp,
  defaultWidth = remToPx(SIDEBAR_WIDTH),
  minWidth = remToPx(SIDEBAR_MIN_WIDTH),
  maxWidth = remToPx(SIDEBAR_MAX_WIDTH),
  resizable = false,
  className,
  style,
  children,
  side = 'left',
  ...props
}: React.ComponentProps<'div'> & {
  defaultOpen?: boolean;
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
  defaultWidth?: number;
  minWidth?: number;
  maxWidth?: number;
  resizable?: boolean;
  side?: 'left' | 'right';
}) {
  const cookieName = `${SIDEBAR_WIDTH_COOKIE_NAME}-${side}`;
  const isMobile = useIsMobile();
  const [openMobile, setOpenMobile] = React.useState(false);
  const [isResizing, setIsResizing] = React.useState(false);
  const [sidebarWidth, _setSidebarWidth] = React.useState(defaultWidth);
  const sidebarWidthRem = pxToRem(sidebarWidth);
  const setSidebarWidth = React.useCallback(
    (width: number) => {
      const clampedWidth = Math.max(minWidth, Math.min(maxWidth, width));
      _setSidebarWidth(clampedWidth);
      // Persist width to cookie
      document.cookie = `${cookieName}=${clampedWidth}; path=/; max-age=${SIDEBAR_COOKIE_MAX_AGE}`;
    },
    [minWidth, maxWidth, cookieName]
  );

  // This is the internal state of the sidebar.
  // We use openProp and setOpenProp for control from outside the component.
  const [_open, _setOpen] = React.useState(defaultOpen);
  const open = openProp ?? _open;
  const setOpen = React.useCallback(
    (value: boolean | ((value: boolean) => boolean)) => {
      const openState = typeof value === 'function' ? value(open) : value;
      if (setOpenProp) {
        setOpenProp(openState);
      } else {
        _setOpen(openState);
      }

      // This sets the cookie to keep the sidebar state.
      document.cookie = `${SIDEBAR_COOKIE_NAME}-${side}=${openState}; path=/; max-age=${SIDEBAR_COOKIE_MAX_AGE}`;
    },
    [setOpenProp, open, side]
  );

  // Helper to toggle the sidebar.
  const toggleSidebar = React.useCallback(() => {
    return isMobile ? setOpenMobile(open => !open) : setOpen(open => !open);
  }, [isMobile, setOpen, setOpenMobile]);

  // Adds a keyboard shortcut to toggle the sidebar.
  React.useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === SIDEBAR_KEYBOARD_SHORTCUT && (event.metaKey || event.ctrlKey)) {
        event.preventDefault();
        toggleSidebar();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [toggleSidebar]);

  // We add a state so that we can do data-state="expanded" or "collapsed".
  // This makes it easier to style the sidebar with Tailwind classes.
  const state = open ? 'expanded' : 'collapsed';

  const contextValue = React.useMemo<SidebarContextProps>(
    () => ({
      state,
      open,
      setOpen,
      isMobile,
      openMobile,
      setOpenMobile,
      toggleSidebar,
      sidebarWidth,
      setSidebarWidth,
      minWidth,
      maxWidth,
      isResizing,
      setIsResizing,
      resizable,
    }),
    [
      state,
      open,
      setOpen,
      isMobile,
      openMobile,
      setOpenMobile,
      toggleSidebar,
      sidebarWidth,
      setSidebarWidth,
      minWidth,
      maxWidth,
      isResizing,
      setIsResizing,
      resizable,
    ]
  );

  return (
    <SidebarContext.Provider value={contextValue}>
      <TooltipProvider delayDuration={0}>
        <div
          data-slot="sidebar-wrapper"
          data-resizing={isResizing}
          style={
            {
              '--sidebar-width': sidebarWidthRem,
              '--sidebar-width-icon': SIDEBAR_WIDTH_ICON,
              ...style,
            } as React.CSSProperties
          }
          className={cn(
            `
                          group/sidebar-wrapper flex min-h-svh w-full
                          has-data-[variant=inset]:bg-sidebar
                        `,
            isResizing && 'cursor-ew-resize select-none',
            className
          )}
          {...props}
        >
          {children}
        </div>
      </TooltipProvider>
    </SidebarContext.Provider>
  );
}

function Sidebar({
  side = 'left',
  variant = 'sidebar',
  collapsible = 'offcanvas',
  className,
  children,
  ...props
}: React.ComponentProps<'div'> & {
  side?: 'left' | 'right';
  variant?: 'sidebar' | 'floating' | 'inset';
  collapsible?: 'offcanvas' | 'icon' | 'none';
}) {
  const { isMobile, state, openMobile, setOpenMobile, resizable } = useSidebar();
  const { t } = useTranslation();

  if (collapsible === 'none') {
    return (
      <div
        data-slot="sidebar"
        className={cn(
          `
                      flex h-full w-(--sidebar-width) flex-col bg-sidebar
                      text-sidebar-foreground
                    `,
          className
        )}
        {...props}
      >
        {children}
      </div>
    );
  }

  if (isMobile) {
    return (
      <Sheet open={openMobile} onOpenChange={setOpenMobile} {...props}>
        <SheetContent
          data-sidebar="sidebar"
          data-slot="sidebar"
          data-mobile="true"
          className={`
                      p-0 w-(--sidebar-width) bg-sidebar text-sidebar-foreground
                      [&>button]:hidden
                    `}
          style={
            {
              '--sidebar-width': SIDEBAR_WIDTH_MOBILE,
            } as React.CSSProperties
          }
          side={side}
        >
          <SheetHeader className="sr-only">
            <SheetTitle>{t('Sidebar')}</SheetTitle>
            <SheetDescription>{t('Displays the mobile sidebar.')}</SheetDescription>
          </SheetHeader>
          <div className="flex size-full flex-col">{children}</div>
        </SheetContent>
      </Sheet>
    );
  }

  return (
    <div
      className={`
              group peer
              md:block
              hidden text-sidebar-foreground
            `}
      data-state={state}
      data-collapsible={state === 'collapsed' ? collapsible : ''}
      data-variant={variant}
      data-side={side}
      data-slot="sidebar"
    >
      {/* This is what handles the sidebar gap on desktop */}
      <div
        data-slot="sidebar-gap"
        className={cn(
          `
                      relative w-(--sidebar-width) bg-transparent
                      transition-[width] ease-linear
                    `,
          // Disable transition during resize for smooth dragging
          '[[data-resizing=true]_&]:transition-none',
          'group-data-[collapsible=offcanvas]:w-0',
          'group-data-[side=right]:rotate-180',
          variant === 'floating' || variant === 'inset'
            ? `
                          group-data-[collapsible=icon]:w-[calc(var(--sidebar-width-icon)+(--spacing(4)))]
                        `
            : `
                          group-data-[collapsible=icon]:w-(--sidebar-width-icon)
                        `
        )}
      />
      <div
        data-slot="sidebar-container"
        className={cn(
          `
                      inset-y-0
                      md:flex
                      fixed z-10 hidden h-svh w-(--sidebar-width)
                      transition-[left,right,width] ease-linear
                    `,
          // Disable transition during resize for smooth dragging
          '[[data-resizing=true]_&]:transition-none',
          side === 'left'
            ? `
                          left-0 border-r border-sidebar-border
                          group-data-[collapsible=offcanvas]:left-[calc(var(--sidebar-width)*-1)]
                        `
            : `
                          right-0 border-l border-sidebar-border
                          group-data-[collapsible=offcanvas]:right-[calc(var(--sidebar-width)*-1)]
                        `,
          // Adjust the padding for floating and inset variants.
          variant === 'floating' || variant === 'inset'
            ? `
                          p-2
                          group-data-[collapsible=icon]:w-[calc(var(--sidebar-width-icon)+(--spacing(4))+2px)]
                        `
            : `
                          group-data-[collapsible=icon]:w-(--sidebar-width-icon)
                          group-data-[side=left]:border-r
                          group-data-[side=right]:border-l
                        `,
          className
        )}
        {...props}
      >
        <div
          data-sidebar="sidebar"
          data-slot="sidebar-inner"
          className={`
                      group-data-[variant=floating]:shadow-sm
                      group-data-[variant=floating]:rounded-lg flex size-full flex-col
                      bg-sidebar
                      group-data-[variant=floating]:border
                      group-data-[variant=floating]:border-sidebar-border
                    `}
        >
          {children}
        </div>
        {resizable && <SidebarResizeHandle />}
      </div>
    </div>
  );
}

function SidebarTrigger({ className, onClick, ...props }: React.ComponentProps<typeof Button>) {
  const { toggleSidebar } = useSidebar();
  const { t } = useTranslation();

  return (
    <Button
      data-sidebar="trigger"
      data-slot="sidebar-trigger"
      variant="ghost"
      size="icon"
      className={cn('size-7', className)}
      onClick={event => {
        onClick?.(event);
        toggleSidebar();
      }}
      {...props}
    >
      <PanelLeftIcon />
      <span className="sr-only">{t('Toggle Sidebar')}</span>
    </Button>
  );
}

function SidebarRail({ className, ...props }: React.ComponentProps<'button'>) {
  const { toggleSidebar } = useSidebar();
  const { t } = useTranslation();
  const title = t('Toggle Sidebar');
  return (
    <button
      data-sidebar="rail"
      data-slot="sidebar-rail"
      aria-label={title}
      tabIndex={-1}
      onClick={toggleSidebar}
      title={title}
      className={cn(
        `
                  inset-y-0 w-4
                  group-data-[side=left]:-right-4
                  group-data-[side=right]:left-0
                  after:inset-y-0
                  sm:flex
                  absolute z-20 hidden -translate-x-1/2 transition-all
                  ease-linear
                  after:absolute after:left-1/2 after:w-[2px]
                  hover:after:bg-sidebar-border
                `,
        `
                  in-data-[side=left]:cursor-w-resize
                  in-data-[side=right]:cursor-e-resize
                `,
        `
                  [[data-side=left][data-state=collapsed]_&]:cursor-e-resize
                  [[data-side=right][data-state=collapsed]_&]:cursor-w-resize
                `,
        `
                  group-data-[collapsible=offcanvas]:translate-x-0
                  group-data-[collapsible=offcanvas]:after:left-full
                  hover:group-data-[collapsible=offcanvas]:bg-sidebar
                `,
        '[[data-side=left][data-collapsible=offcanvas]_&]:-right-2',
        '[[data-side=right][data-collapsible=offcanvas]_&]:-left-2',
        className
      )}
      {...props}
    />
  );
}

function SidebarResizeHandle({
  className,
  ...props
}: Omit<React.ComponentProps<'div'>, 'onDragStart' | 'onDrag' | 'onDragEnd'>) {
  const { sidebarWidth, setSidebarWidth, minWidth, maxWidth, isResizing, setIsResizing, state } =
    useSidebar();
  const handleRef = React.useRef<HTMLDivElement>(null);
  const dragStartRef = React.useRef<{
    startX: number;
    startWidth: number;
    side: 'left' | 'right';
  } | null>(null);
  const { t } = useTranslation();

  const handleDragStart = React.useCallback(
    (e: DraggableEvent) => {
      // Detect the sidebar side from the parent group element
      const sidebarGroup = handleRef.current?.closest('[data-side]');
      const side = (sidebarGroup?.getAttribute('data-side') as 'left' | 'right') ?? 'left';

      dragStartRef.current = {
        startX: e.clientX,
        startWidth: sidebarWidth,
        side,
      };
      setIsResizing(true);
    },
    [sidebarWidth, setIsResizing]
  );

  const handleDrag = React.useCallback(
    (e: DraggableEvent) => {
      if (!dragStartRef.current) return;

      const { startX, startWidth, side } = dragStartRef.current;
      const deltaX = e.clientX - startX;
      // For right-side sidebar, invert the delta
      const adjustedDelta = side === 'right' ? -deltaX : deltaX;
      const newWidth = startWidth + adjustedDelta;
      setSidebarWidth(Math.max(minWidth, Math.min(maxWidth, newWidth)));
    },
    [setSidebarWidth, minWidth, maxWidth]
  );

  const handleDragEnd = React.useCallback(() => {
    dragStartRef.current = null;
    setIsResizing(false);
  }, [setIsResizing]);

  // Don't show resize handle when sidebar is collapsed
  if (state === 'collapsed') {
    return null;
  }

  return (
    <DraggableArea
      ref={handleRef}
      areaId="sidebar-resize-handle"
      onDragStart={handleDragStart}
      onDrag={handleDrag}
      onDragEnd={handleDragEnd}
      ariaLabel={t('Resize sidebar')}
      ariaRole="separator"
      data-sidebar="resize-handle"
      data-slot="sidebar-resize-handle"
      data-resizing={isResizing || undefined}
      className={cn(
        `
                  group/resize-handle inset-y-0 w-4
                  group-data-[side=left]:-right-2
                  group-data-[side=right]:-left-2
                  md:block
                  absolute z-20 hidden cursor-ew-resize transition-colors
                `,
        isResizing && 'bg-sidebar-border',
        className
      )}
      {...props}
    >
      {/* 1px resize line */}
      <div
        className={cn(
          `
                      inset-y-0 absolute left-1/2 w-px -translate-x-1/2
                      bg-transparent transition-colors
                      group-hover/resize-handle:bg-accent
                    `,
          isResizing && 'bg-accent'
        )}
      />
    </DraggableArea>
  );
}

function SidebarInset({ className, ...props }: React.ComponentProps<'main'>) {
  return (
    <main
      data-slot="sidebar-inset"
      className={cn(
        'relative flex w-full flex-1 flex-col bg-background',
        `
                  md:peer-data-[variant=inset]:m-2
                  md:peer-data-[variant=inset]:ml-0
                  md:peer-data-[variant=inset]:rounded-xl
                  md:peer-data-[variant=inset]:shadow-sm
                  md:peer-data-[variant=inset]:peer-data-[state=collapsed]:ml-2
                `,
        className
      )}
      {...props}
    />
  );
}

function SidebarInput({ className, ...props }: React.ComponentProps<typeof Input>) {
  return (
    <Input
      data-slot="sidebar-input"
      data-sidebar="input"
      className={cn('w-full', className)}
      {...props}
    />
  );
}

function SidebarHeader({ className, ...props }: React.ComponentProps<'div'>) {
  return (
    <div
      data-slot="sidebar-header"
      data-sidebar="header"
      className={cn('gap-3 p-4 pb-2 flex flex-col', className)}
      {...props}
    />
  );
}

function SidebarFooter({ className, ...props }: React.ComponentProps<'div'>) {
  return (
    <div
      data-slot="sidebar-footer"
      data-sidebar="footer"
      className={cn('gap-2 p-2 flex flex-col', className)}
      {...props}
    />
  );
}

function SidebarSeparator({ className, ...props }: React.ComponentProps<typeof Separator>) {
  return (
    <Separator
      data-slot="sidebar-separator"
      data-sidebar="separator"
      className={cn('mx-2 w-auto bg-sidebar-border', className)}
      {...props}
    />
  );
}

function SidebarContent({ className, ...props }: React.ComponentProps<'div'>) {
  return (
    <div
      data-slot="sidebar-content"
      data-sidebar="content"
      className={cn(
        `
                  min-h-0 gap-2 flex flex-1 flex-col overflow-auto
                  group-data-[collapsible=icon]:overflow-hidden
                `,
        className
      )}
      {...props}
    />
  );
}

function SidebarGroup({ className, ...props }: React.ComponentProps<'div'>) {
  return (
    <div
      data-slot="sidebar-group"
      data-sidebar="group"
      className={cn('min-w-0 p-2 relative flex w-full flex-col', className)}
      {...props}
    />
  );
}

function SidebarGroupLabel({
  className,
  asChild = false,
  ...props
}: React.ComponentProps<'div'> & { asChild?: boolean }) {
  const Comp = asChild ? Slot : 'div';

  return (
    <Comp
      data-slot="sidebar-group-label"
      data-sidebar="group-label"
      className={cn(
        `
                  h-8 px-2 text-sm font-medium
                  [&>svg]:size-4
                  flex shrink-0 items-center rounded-md
                  text-sidebar-foreground/70 ring-sidebar-ring
                  transition-[margin,opacity] duration-200 ease-linear
                  outline-none
                  focus-visible:ring-2
                  [&>svg]:shrink-0
                `,
        `
                  group-data-[collapsible=icon]:-mt-8
                  group-data-[collapsible=icon]:opacity-0
                `,
        className
      )}
      {...props}
    />
  );
}

function SidebarGroupAction({
  className,
  asChild = false,
  ...props
}: React.ComponentProps<'button'> & { asChild?: boolean }) {
  const Comp = asChild ? Slot : 'button';

  return (
    <Comp
      data-slot="sidebar-group-action"
      data-sidebar="group-action"
      className={cn(
        `
                  top-3.5 right-3 w-5 p-0
                  [&>svg]:size-4
                  absolute flex aspect-square items-center justify-center
                  rounded-md text-sidebar-foreground ring-sidebar-ring
                  outline-hidden transition-transform
                  hover:bg-sidebar-accent hover:text-sidebar-accent-foreground
                  focus-visible:ring-2
                  [&>svg]:shrink-0
                `,
        // Increases the hit area of the button on mobile.
        `
                  after:-inset-2
                  md:after:hidden
                  after:absolute
                `,
        'group-data-[collapsible=icon]:hidden',
        className
      )}
      {...props}
    />
  );
}

function SidebarGroupContent({ className, ...props }: React.ComponentProps<'div'>) {
  return (
    <div
      data-slot="sidebar-group-content"
      data-sidebar="group-content"
      className={cn('text-sm w-full', className)}
      {...props}
    />
  );
}

function SidebarMenu({ className, ...props }: React.ComponentProps<'ul'>) {
  return (
    <ul
      data-slot="sidebar-menu"
      data-sidebar="menu"
      className={cn(`not-prose min-w-0 gap-2 flex w-full list-none flex-col`, className)}
      {...props}
    />
  );
}

function SidebarMenuItem({
  className,
  testId,
  ...props
}: React.ComponentProps<'li'> & { testId?: string }) {
  return (
    <li
      data-slot="sidebar-menu-item"
      data-sidebar="menu-item"
      data-testid={testId}
      className={cn('group/menu-item relative', className)}
      {...props}
    />
  );
}

const sidebarMenuButtonVariants = cva(
  `
      peer/menu-button gap-2 p-2 text-sm
      group-has-data-[sidebar=menu-action]/menu-item:pr-8
      group-data-[collapsible=icon]:size-8! group-data-[collapsible=icon]:p-2!
      [&>svg]:size-4
      flex w-full items-center overflow-hidden rounded-md text-left
      ring-sidebar-ring outline-hidden transition-[width,height,padding]
      hover:bg-sidebar-accent hover:text-sidebar-accent-foreground
      focus-visible:ring-2
      active:bg-sidebar-accent active:text-sidebar-accent-foreground
      aria-disabled:pointer-events-none aria-disabled:opacity-50
      data-[state=open]:hover:bg-sidebar-accent
      data-[state=open]:hover:text-sidebar-accent-foreground
      [&>span:last-child]:truncate
      [&>svg]:shrink-0
    `,
  {
    variants: {
      variant: {
        default: `
                  hover:bg-sidebar-accent hover:text-sidebar-accent-foreground
                `,
        outline: `
                  bg-background shadow-[0_0_0_1px_hsl(var(--sidebar-border))]
                  hover:bg-sidebar-accent hover:text-sidebar-accent-foreground
                  hover:shadow-[0_0_0_1px_hsl(var(--sidebar-accent))]
                `,
      },
      size: {
        default: 'h-8 text-sm',
        sm: 'h-7 text-xs',
        lg: `
                  h-12 text-sm
                  group-data-[collapsible=icon]:p-0!
                `,
      },
      disabled: {
        true: `
                  pointer-events-none cursor-not-allowed text-muted-foreground
                  hover:bg-sidebar hover:text-muted-foreground
                `,
        false: 'cursor-pointer',
      },
      isActive: {
        true: `
                  ml-[-2px] rounded-l-none border-l-2 border-l-accent
                  bg-sidebar-accent text-sidebar-accent-foreground
                `,
        false: '',
      },
      isActiveAncestor: {
        true: 'bg-sidebar-accent text-sidebar-accent-foreground',
        false: '',
      },
    },
    defaultVariants: {
      variant: 'default',
      size: 'default',
      isActive: false,
      isActiveAncestor: false,
    },
  }
);

function SidebarMenuButton({
  asChild = false,
  isActive = false,
  isActiveAncestor = false,
  variant = 'default',
  size = 'default',
  disabled = false,
  tooltip,
  className,
  testId,
  ...props
}: React.ComponentProps<'button'> & {
  asChild?: boolean;
  isActive?: boolean;
  isActiveAncestor?: boolean;
  tooltip?: string | React.ComponentProps<typeof TooltipContent>;
  testId?: string;
} & VariantProps<typeof sidebarMenuButtonVariants>) {
  const Comp = asChild ? Slot : 'button';
  const { isMobile, state } = useSidebar();

  const button = (
    <Comp
      data-slot="sidebar-menu-button"
      data-sidebar="menu-button"
      data-size={size}
      data-active={isActive}
      data-active-ancestor={isActiveAncestor}
      disabled={disabled}
      data-testid={testId}
      className={cn(
        sidebarMenuButtonVariants({
          variant,
          size,
          disabled,
          isActive,
          isActiveAncestor,
        }),
        className
      )}
      {...props}
    />
  );

  if (!tooltip) {
    return button;
  }

  if (typeof tooltip === 'string') {
    tooltip = {
      children: tooltip,
    };
  }

  return (
    <Tooltip>
      <TooltipTrigger asChild>{button}</TooltipTrigger>
      <TooltipContent
        side="right"
        align="center"
        hidden={state !== 'collapsed' || isMobile}
        {...tooltip}
      />
    </Tooltip>
  );
}

function SidebarMenuAction({
  className,
  asChild = false,
  showOnHover = false,
  ...props
}: React.ComponentProps<'button'> & {
  asChild?: boolean;
  showOnHover?: boolean;
}) {
  const Comp = asChild ? Slot : 'button';

  return (
    <Comp
      data-slot="sidebar-menu-action"
      data-sidebar="menu-action"
      className={cn(
        `
                  top-1.5 right-1 w-5 p-0
                  [&>svg]:size-4
                  absolute flex aspect-square items-center justify-center
                  rounded-md text-sidebar-foreground ring-sidebar-ring
                  transition-transform outline-none
                  peer-hover/menu-button:text-sidebar-accent-foreground
                  hover:bg-sidebar-accent hover:text-sidebar-accent-foreground
                  focus-visible:ring-2
                  [&>svg]:shrink-0
                `,
        // Increases the hit area of the button on mobile.
        `
                  after:-inset-2
                  md:after:hidden
                  after:absolute
                `,
        'peer-data-[size=sm]/menu-button:top-1',
        'peer-data-[size=default]/menu-button:top-1.5',
        'peer-data-[size=lg]/menu-button:top-2.5',
        'group-data-[collapsible=icon]:hidden',
        showOnHover &&
          `
                      md:opacity-0
                      group-focus-within/menu-item:opacity-100
                      group-hover/menu-item:opacity-100
                      peer-data-[active=true]/menu-button:text-sidebar-accent-foreground
                      data-[state=open]:opacity-100
                    `,
        className
      )}
      {...props}
    />
  );
}

function SidebarMenuBadge({ className, ...props }: React.ComponentProps<'div'>) {
  return (
    <div
      data-slot="sidebar-menu-badge"
      data-sidebar="menu-badge"
      className={cn(
        `
                  right-1 h-5 min-w-5 px-1 text-xs font-medium
                  pointer-events-none absolute flex items-center justify-center
                  rounded-md text-sidebar-foreground tabular-nums select-none
                `,
        `
                  peer-hover/menu-button:text-sidebar-accent-foreground
                  peer-data-[active=true]/menu-button:text-sidebar-accent-foreground
                `,
        'peer-data-[size=sm]/menu-button:top-1',
        'peer-data-[size=default]/menu-button:top-1.5',
        'peer-data-[size=lg]/menu-button:top-2.5',
        'group-data-[collapsible=icon]:hidden',
        className
      )}
      {...props}
    />
  );
}

function SidebarMenuSkeleton({
  className,
  showIcon = false,
  ...props
}: React.ComponentProps<'div'> & {
  showIcon?: boolean;
}) {
  // Random width between 50 to 90%.
  const width = React.useMemo(() => {
    return `${Math.floor(Math.random() * 40) + 50}%`;
  }, []);

  return (
    <div
      data-slot="sidebar-menu-skeleton"
      data-sidebar="menu-skeleton"
      className={cn('h-8 gap-2 px-2 flex items-center rounded-md', className)}
      {...props}
    >
      {showIcon && <Skeleton className="size-4 rounded-md" data-sidebar="menu-skeleton-icon" />}
      <Skeleton
        className="h-4 max-w-(--skeleton-width) flex-1"
        data-sidebar="menu-skeleton-text"
        style={
          {
            '--skeleton-width': width,
          } as React.CSSProperties
        }
      />
    </div>
  );
}

function SidebarMenuSub({ className, ...props }: React.ComponentProps<'ul'>) {
  return (
    <ul
      data-slot="sidebar-menu-sub"
      data-sidebar="menu-sub"
      className={cn(
        `
                  mt-1 ml-1 min-w-0 gap-2 py-0.5 pl-2.5 flex translate-x-px
                  flex-col
                `,
        'group-data-[collapsible=icon]:hidden',
        'list-none',
        className
      )}
      {...props}
    />
  );
}

function SidebarMenuSubItem({ className, ...props }: React.ComponentProps<'li'>) {
  return (
    <li
      data-slot="sidebar-menu-sub-item"
      data-sidebar="menu-sub-item"
      className={cn('group/menu-sub-item relative', className)}
      {...props}
    />
  );
}

function SidebarMenuSubButton({
  asChild = false,
  size = 'md',
  isActive = false,
  className,
  ...props
}: React.ComponentProps<'a'> & {
  asChild?: boolean;
  size?: 'sm' | 'md';
  isActive?: boolean;
}) {
  const Comp = asChild ? Slot : 'a';

  return (
    <Comp
      data-slot="sidebar-menu-sub-button"
      data-sidebar="menu-sub-button"
      data-size={size}
      data-active={isActive}
      className={cn(
        `
                  h-7 min-w-0 gap-2 px-2
                  [&>svg]:size-4
                  flex -translate-x-px items-center overflow-hidden rounded-md
                  text-sidebar-foreground ring-sidebar-ring outline-none
                  hover:bg-sidebar-accent hover:text-sidebar-accent-foreground
                  focus-visible:ring-2
                  active:bg-sidebar-accent active:text-sidebar-accent-foreground
                  disabled:pointer-events-none disabled:opacity-50
                  aria-disabled:pointer-events-none aria-disabled:opacity-50
                  [&>span:last-child]:truncate
                  [&>svg]:shrink-0 [&>svg]:text-sidebar-accent-foreground
                `,
        `
                  data-[active=true]:bg-sidebar-accent
                  data-[active=true]:text-sidebar-accent-foreground
                `,
        size === 'sm' && 'text-xs',
        size === 'md' && 'text-sm',
        'group-data-[collapsible=icon]:hidden',
        className
      )}
      {...props}
    />
  );
}

export {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupAction,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarInput,
  SidebarInset,
  SidebarMenu,
  SidebarMenuAction,
  SidebarMenuBadge,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarMenuSkeleton,
  SidebarMenuSub,
  SidebarMenuSubButton,
  SidebarMenuSubItem,
  SidebarProvider,
  SidebarRail,
  SidebarResizeHandle,
  SidebarSeparator,
  SidebarTrigger,
  useSidebar,
};
