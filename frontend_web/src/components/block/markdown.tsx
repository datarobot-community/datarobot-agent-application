'use client';
import {
  Component,
  useEffect,
  type ReactNode,
  type ErrorInfo,
  type PropsWithChildren,
  type ComponentType,
  type JSX,
  useMemo,
} from 'react';
import type { PluggableList } from 'unified';
import ReactMarkdown, { type ExtraProps } from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import rehypeHighlight from 'rehype-highlight';
import { Heading } from '@/components/ui/heading';
import { cn } from '@/lib/utils';
import { SquareArrowOutUpRight } from 'lucide-react';
import { useTheme } from '@/theme/theme-provider';
import hljsLightUrl from 'highlight.js/styles/github.min.css?url';
import hljsDarkUrl from 'highlight.js/styles/github-dark-dimmed.min.css?url';
import 'katex/dist/katex.min.css';
import { unwrapMarkdownCodeBlocks } from '@/lib/unwrap-markdown-code-blocks';

type MarkdownComponents = {
  [Key in keyof JSX.IntrinsicElements]?:
    | ComponentType<JSX.IntrinsicElements[Key] & ExtraProps>
    | keyof JSX.IntrinsicElements;
};

/* eslint-disable @typescript-eslint/no-unused-vars */
export const MARKDOWN_COMPONENTS: MarkdownComponents = {
  ul: ({ children, node, ...props }) => (
    <ul className="my-4 pl-8 leading-relaxed list-disc" {...props}>
      {children}
    </ul>
  ),
  ol: ({ children, node, ...props }) => (
    <ol className="my-4 pl-8 leading-relaxed list-decimal" {...props}>
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
    <p className="leading-relaxed body" {...props}>
      {children}
    </p>
  ),
  hr: ({ node, ...props }) => <hr className="mt-4 mb-2" {...props} />,
  table: ({ children, className, node, ...props }) => (
    <div
      className={`
              my-2 rounded-lg flex flex-1 flex-col overflow-hidden border
              border-border bg-background
            `}
    >
      <table
        className={cn(
          `
                      border-spacing-0 rounded-lg h-fit w-full table-fixed
                      border-separate overflow-auto
                    `,
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
        `
                  p-0 font-normal border-sidebar-border bg-background
                  text-secondary-foreground
                `,
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
                  p-3 pl-2 font-normal border-r border-b border-border
                  bg-background text-left text-secondary-foreground
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
                  p-3 pl-2 leading-5 border-r border-b border-border
                  bg-background text-left text-ellipsis whitespace-nowrap
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

const REMARK_PLUGINS: PluggableList = [remarkGfm, remarkMath];
const REHYPE_PLUGINS: PluggableList = [rehypeKatex, rehypeHighlight];

const HIGHLIGHT_LINK_ID = 'highlight-theme-link';

const THEME_HREFS: Record<'light' | 'dark', string> = {
  light: hljsLightUrl,
  dark: hljsDarkUrl,
};

function applyHighlightTheme(theme: 'light' | 'dark'): void {
  let linkEl = document.getElementById(HIGHLIGHT_LINK_ID) as HTMLLinkElement | null;
  if (!linkEl) {
    linkEl = document.createElement('link');
    linkEl.id = HIGHLIGHT_LINK_ID;
    linkEl.rel = 'stylesheet';
    document.head.appendChild(linkEl);
  }
  linkEl.href = THEME_HREFS[theme];
}

interface MarkdownContentProps {
  content: string;
  className?: string;
  unwrapMarkdown?: boolean;
}

function MarkdownContent({ content, className, unwrapMarkdown = true }: MarkdownContentProps) {
  const { theme } = useTheme();
  const transformedContent = useMemo(
    () => (unwrapMarkdown ? unwrapMarkdownCodeBlocks(content) : content),
    [content, unwrapMarkdown]
  );

  useEffect(() => {
    applyHighlightTheme(theme);
  }, [theme]);

  if (!content) {
    return null;
  }

  return (
    <div className={className}>
      <ReactMarkdown
        remarkPlugins={REMARK_PLUGINS}
        rehypePlugins={REHYPE_PLUGINS}
        components={MARKDOWN_COMPONENTS}
      >
        {transformedContent}
      </ReactMarkdown>
    </div>
  );
}

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}

class MarkdownErrorBoundary extends Component<
  PropsWithChildren<{ fallbackContent: string; className?: string }>,
  ErrorBoundaryState
> {
  constructor(props: PropsWithChildren<{ fallbackContent: string; className?: string }>) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo): void {
    console.error('Markdown rendering error:', error, errorInfo);
  }

  componentDidUpdate(
    prevProps: PropsWithChildren<{
      fallbackContent: string;
      className?: string;
    }>
  ): void {
    if (this.state.hasError && prevProps.fallbackContent !== this.props.fallbackContent) {
      this.setState({ hasError: false, error: null });
    }
  }

  render(): ReactNode {
    if (this.state.hasError) {
      return (
        <div className={cn('body-secondary', this.props.className)}>
          <p>{this.props.fallbackContent}</p>
        </div>
      );
    }
    return this.props.children;
  }
}

export function Markdown({
  children,
  className,
  unwrapMarkdown = true,
}: {
  children: string;
  className?: string;
  unwrapMarkdown?: boolean;
}) {
  return (
    <MarkdownErrorBoundary fallbackContent={children} className={className}>
      <MarkdownContent content={children} className={className} unwrapMarkdown={unwrapMarkdown} />
    </MarkdownErrorBoundary>
  );
}
