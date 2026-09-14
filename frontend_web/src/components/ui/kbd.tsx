import { cn } from '@/lib/utils';

function Kbd({ className, ...props }: React.ComponentProps<'kbd'>) {
  return (
    <kbd
      data-slot="kbd"
      className={cn(
        `
                  h-5 min-w-5 gap-1 px-1 text-xs font-medium rounded-sm
                  pointer-events-none inline-flex w-fit items-center justify-center
                  bg-muted font-sans text-muted-foreground select-none
                `,
        "[&_svg:not([class*='size-'])]:size-3",
        `
                  [[data-slot=tooltip-content]_&]:bg-background/20
                  [[data-slot=tooltip-content]_&]:text-background
                  dark:[[data-slot=tooltip-content]_&]:bg-background/10
                `,
        className
      )}
      {...props}
    />
  );
}

function KbdGroup({ className, ...props }: React.ComponentProps<'div'>) {
  return (
    <kbd
      data-slot="kbd-group"
      className={cn('gap-1 inline-flex items-center', className)}
      {...props}
    />
  );
}

export { Kbd, KbdGroup };
