'use client';

import { useMemo } from 'react';
import { SquareArrowOutUpRight } from 'lucide-react';
import {
  Streamdown,
  type Components,
  type ThemeInput,
  type StreamdownProps,
  type PluginConfig,
  type ControlsConfig,
} from 'streamdown';
import { createCodePlugin } from '@streamdown/code';
import { createMathPlugin } from '@streamdown/math';
import { cn } from '@/lib/utils';
import { unwrapMarkdownCodeBlocks } from '@/lib/unwrap-markdown-code-blocks';
import { Heading } from '@/components/ui/heading';

/* eslint-disable @typescript-eslint/no-unused-vars */
export const MARKDOWN_COMPONENTS: Components = {
  ul: ({ children, node, ...props }) => (
    <ul className="my-4 list-disc pl-8 leading-relaxed" {...props}>
      {children}
    </ul>
  ),
  ol: ({ children, node, ...props }) => (
    <ol className="my-4 list-decimal pl-8 leading-relaxed" {...props}>
      {children}
    </ol>
  ),
  li: ({ children, node, ...props }) => (
    <li className="my-1" {...props}>
      {children}
    </li>
  ),
  h1: ({ children, node, ...props }) => (
    <Heading level={2} className="mt-6 mb-4" {...props}>
      {children}
    </Heading>
  ),
  h2: ({ children, node, ...props }) => (
    <Heading level={3} className="mt-6 mb-4" {...props}>
      {children}
    </Heading>
  ),
  h3: ({ children, node, ...props }) => (
    <Heading level={4} className="mt-4 mb-2" {...props}>
      {children}
    </Heading>
  ),
  h4: ({ children, node, ...props }) => (
    <Heading level={5} className="mt-4 mb-2" {...props}>
      {children}
    </Heading>
  ),
  h5: ({ children, node, ...props }) => (
    <Heading level={6} className="mt-4 mb-2" {...props}>
      {children}
    </Heading>
  ),
  p: ({ children, node, ...props }) => (
    <p className="body leading-relaxed" {...props}>
      {children}
    </p>
  ),
  hr: ({ node, ...props }) => <hr className="mt-4 mb-2" {...props} />,
  table: ({ children, className, node, ...props }) => (
    <div className="my-2 flex flex-1 flex-col overflow-hidden rounded-lg border border-border bg-background">
      <table
        className={cn(
          'h-fit w-full table-fixed border-separate border-spacing-0 overflow-auto rounded-lg',
          className
        )}
        {...props}
      >
        {children}
      </table>
    </div>
  ),
  thead: ({ children, className, node, ...props }) => (
    <thead
      className={cn(
        'border-sidebar-border bg-background p-0 font-normal text-secondary-foreground',
        className
      )}
      {...props}
    >
      {children}
    </thead>
  ),
  th: ({ children, className, node, ...props }) => (
    <th
      className={cn(
        `
          border-r border-b border-border bg-background p-3 pl-2 text-left font-normal text-secondary-foreground
          last:border-r-0
        `,
        className
      )}
      {...props}
    >
      {children}
    </th>
  ),
  td: ({ children, className, node, ...props }) => (
    <td
      className={cn(
        `
          border-r border-b border-border bg-background p-3 pl-2 text-left leading-5 text-ellipsis whitespace-nowrap
          last:border-r-0
          [tr:last-child_&]:border-b-0
        `,
        className
      )}
      {...props}
    >
      {children}
    </td>
  ),
  a: ({ children, node, ...props }) => (
    <a
      target="_blank"
      rel="noopener noreferrer"
      className="inline-flex items-center anchor"
      {...props}
    >
      {children}
      <SquareArrowOutUpRight size={18} className="ml-1" />
    </a>
  ),
};
/* eslint-enable @typescript-eslint/no-unused-vars */

const plugins: PluginConfig = {
  code: createCodePlugin({ themes: ['github-light', 'github-dark-dimmed'] }),
  math: createMathPlugin({ singleDollarTextMath: true }),
};

const shikiTheme: [ThemeInput, ThemeInput] = ['github-light', 'github-dark-dimmed'] as const;

const controlsConfig: ControlsConfig = {
  code: {
    copy: true,
    download: false,
  },
  table: false,
};

export function StreamingMarkdown({
  children,
  className,
  unwrapMarkdown = true,
  ...props
}: {
  children: string;
  className?: string;
  unwrapMarkdown?: boolean;
} & Partial<StreamdownProps>) {
  const transformedContent = useMemo(
    () => (unwrapMarkdown ? unwrapMarkdownCodeBlocks(children) : children),
    [children, unwrapMarkdown]
  );

  if (!children) {
    return null;
  }

  return (
    <div className={className}>
      <Streamdown
        plugins={plugins}
        controls={controlsConfig}
        components={MARKDOWN_COMPONENTS}
        shikiTheme={shikiTheme}
        isAnimating={false}
        {...props}
      >
        {transformedContent}
      </Streamdown>
    </div>
  );
}
