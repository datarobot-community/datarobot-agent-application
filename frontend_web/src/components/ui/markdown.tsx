import {
  Component,
  useEffect,
  type ReactNode,
  type ErrorInfo,
  type PropsWithChildren,
  type HTMLAttributes,
} from 'react';
import type { PluggableList } from 'unified';
import ReactMarkdown from 'react-markdown';
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

type MarkdownComponentProps = PropsWithChildren<HTMLAttributes<HTMLElement>>;

export const MARKDOWN_COMPONENTS = {
  ul: ({ children, ...props }: MarkdownComponentProps) => (
    <ul className="my-4 pl-8 leading-relaxed list-disc" {...props}>
      {children}
    </ul>
  ),
  ol: ({ children, ...props }: MarkdownComponentProps) => (
    <ol className="my-4 pl-8 leading-relaxed list-decimal" {...props}>
      {children}
    </ol>
  ),
  li: ({ children, ...props }: MarkdownComponentProps) => (
    <li className="my-1" {...props}>
      {children}
    </li>
  ),
  h1: ({ children, ...props }: MarkdownComponentProps) => (
    <Heading level={2} className="mt-6 mb-4" {...props}>
      {children}
    </Heading>
  ),
  h2: ({ children, ...props }: MarkdownComponentProps) => (
    <Heading level={3} className="mt-6 mb-4" {...props}>
      {children}
    </Heading>
  ),
  h3: ({ children, ...props }: MarkdownComponentProps) => (
    <Heading level={4} className="mt-4 mb-2" {...props}>
      {children}
    </Heading>
  ),
  h4: ({ children, ...props }: MarkdownComponentProps) => (
    <Heading level={5} className="mt-4 mb-2" {...props}>
      {children}
    </Heading>
  ),
  p: ({ children, ...props }: MarkdownComponentProps) => (
    <p className="leading-relaxed body" {...props}>
      {children}
    </p>
  ),
  hr: ({ ...props }: MarkdownComponentProps) => <hr className="mt-4 mb-2" {...props} />,
  th: ({ children, className, ...props }: MarkdownComponentProps) => (
    <th className={cn('px-3 py-2 text-left', className)} {...props}>
      {children}
    </th>
  ),
  td: ({ children, className, ...props }: MarkdownComponentProps) => (
    <td className={cn('px-3 py-2', className)} {...props}>
      {children}
    </td>
  ),
  a: ({ children, ...props }: MarkdownComponentProps) => (
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
}

function MarkdownContent({ content }: MarkdownContentProps) {
  const { theme } = useTheme();

  useEffect(() => {
    applyHighlightTheme(theme);
  }, [theme]);

  if (!content) {
    return null;
  }

  return (
    <ReactMarkdown
      remarkPlugins={REMARK_PLUGINS}
      rehypePlugins={REHYPE_PLUGINS}
      components={MARKDOWN_COMPONENTS}
    >
      {content}
    </ReactMarkdown>
  );
}

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}

class MarkdownErrorBoundary extends Component<
  PropsWithChildren<{ fallbackContent: string }>,
  ErrorBoundaryState
> {
  constructor(props: PropsWithChildren<{ fallbackContent: string }>) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo): void {
    console.error('Markdown rendering error:', error, errorInfo);
  }

  render(): ReactNode {
    if (this.state.hasError) {
      return (
        <div className="body-secondary">
          <p>{this.props.fallbackContent}</p>
        </div>
      );
    }
    return this.props.children;
  }
}

export function Markdown({ content }: { content: string }) {
  return (
    <MarkdownErrorBoundary fallbackContent={content}>
      <MarkdownContent content={content} />
    </MarkdownErrorBoundary>
  );
}
