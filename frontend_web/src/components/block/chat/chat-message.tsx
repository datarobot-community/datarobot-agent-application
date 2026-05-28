import { memo, useMemo, Component, type ReactNode, type ErrorInfo } from 'react';
import {
  User,
  Bot,
  Cog,
  Hammer,
  Wrench,
  ChevronRight,
  CheckCircle2,
  Loader2,
  AlertTriangle,
  Brain,
} from 'lucide-react';
import { CodeBlock } from '@/components/ui/code-block';
import { cn } from '@/lib/utils';
import type { ContentPart, ToolInvocationUIPart, ChatMessageEvent } from './types';
import { useChatContext } from '@/components/block/chat/hooks/use-chat-context';
import { Badge } from '@/components/ui/badge';
import { StreamingMarkdown } from '@/components/ui/streaming-markdown';
import { useTranslation } from '@/lib/i18n';

interface ChatMessageErrorBoundaryProps {
  children: ReactNode;
  message: ChatMessageEvent;
  title: string;
}

interface ChatMessageErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}

class ChatMessageErrorBoundary extends Component<
  ChatMessageErrorBoundaryProps,
  ChatMessageErrorBoundaryState
> {
  constructor(props: ChatMessageErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): ChatMessageErrorBoundaryState {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('ChatMessage render error:', error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className={'flex gap-3 rounded-lg bg-card p-4'}>
          <div className="shrink-0">
            <div className="flex size-8 items-center justify-center rounded-full bg-destructive/20 text-destructive">
              <AlertTriangle className="size-4" />
            </div>
          </div>
          <div className="min-w-0 flex-1">
            <div className="mb-1 flex items-center gap-2">
              <span className="mn-label text-destructive">{this.props.title}</span>
            </div>
            <CodeBlock code={JSON.stringify(this.props.message, null, 2)} />
            {this.state.error && (
              <div className="my-2 caption-01">
                <div>{this.state.error.message}</div>
                <div>{this.state.error.stack}</div>
              </div>
            )}
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

export function UniversalContentPart({ part }: { part: ContentPart }) {
  if (part.type === 'text') {
    return <TextContentPart content={part.text} />;
  }
  if (part.type === 'reasoning') {
    return <TextContentPart content={part.reasoning} />;
  }
  if (part.type === 'tool-invocation') {
    return <ToolInvocationPart part={part} />;
  }
  return <CodeBlock code={JSON.stringify(part, null, '  ')} />;
}

export function TextContentPart({ content }: { content: string }) {
  return <StreamingMarkdown>{content ? content : ''}</StreamingMarkdown>;
}

function ToolInvocationLoading() {
  return <Loader2 className="my-2 size-4 animate-spin text-muted-foreground" />;
}

function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(2)}s`;
}

export function ToolInvocationPart({ part }: { part: ToolInvocationUIPart }) {
  const { t } = useTranslation();
  const { toolInvocation } = part;
  const { toolName } = toolInvocation;
  const ctx = useChatContext();
  const tool = ctx.getTool(toolName);
  const duration =
    toolInvocation.metadata?.endTime && toolInvocation.metadata?.startTime
      ? toolInvocation.metadata.endTime - toolInvocation.metadata.startTime
      : undefined;
  const durationReadable = duration ? formatDuration(duration) : undefined;

  const hasResult = !!toolInvocation.result;
  const result = useMemo(() => {
    if (!hasResult) {
      return '';
    }

    try {
      if (toolInvocation.result) {
        return JSON.stringify(JSON.parse(toolInvocation.result), null, '  ');
      }
    } catch (e) {
      // eslint-disable-next-line no-console
      console.debug('Tool result is not a JSON', toolInvocation.result, e);
    }
    return toolInvocation.result || '';
  }, [toolInvocation.result, hasResult]);

  if (tool?.render) {
    if (!toolInvocation.args) {
      return <ToolInvocationLoading />;
    }
    // In this case UI element is a tool, so args is passed there as a props
    return tool.render({ status: 'complete', args: toolInvocation.args });
  }
  if (tool?.renderAndWait) {
    if (!toolInvocation.args) {
      return <ToolInvocationLoading />;
    }
    return tool.renderAndWait({
      status: 'complete',
      args: toolInvocation.args,
      callback: event => {
        // eslint-disable-next-line no-console
        console.debug('Tool render event', event);
      },
    });
  }

  return (
    <div
      className={`
        my-2 overflow-hidden rounded-lg border border-border bg-card/50
        dark:bg-card/30
      `}
    >
      {/* Header */}
      <div
        className={`
          flex items-center gap-2 border-b border-border bg-muted/30 px-3 py-2
          dark:bg-muted/20
        `}
      >
        <Wrench className="size-4 text-muted-foreground" />
        <span className="body-secondary">{t('Tool Call')}</span>
        <Badge variant="default" className="code">
          {toolInvocation.toolName}
        </Badge>
        {durationReadable && <span className="flex body-secondary">{durationReadable}</span>}
        {hasResult ? (
          <CheckCircle2
            className={`
              ml-auto size-4 text-green-500
              dark:text-green-400
            `}
          />
        ) : (
          <Loader2 className="ml-auto size-4 animate-spin text-muted-foreground" />
        )}
      </div>

      {/* Arguments Section */}
      {toolInvocation.args && (
        <div
          className={`
            border-b border-border
            last:border-b-0
          `}
        >
          <div className="flex items-center gap-1.5 bg-muted/20 caption-01 px-3 py-1.5">
            <ChevronRight className="size-3" />
            {t('Arguments')}
          </div>
          <CodeBlock code={JSON.stringify(toolInvocation.args, null, '  ')} />
        </div>
      )}

      {/* Result Section */}
      {result && (
        <div>
          <div className="flex items-center gap-1.5 bg-muted/20 caption-01 px-3 py-1.5">
            <ChevronRight className="size-3" />
            {t('Result')}
          </div>
          <CodeBlock code={result} />
        </div>
      )}
    </div>
  );
}

function ChatMessageContent({
  id,
  role,
  threadId,
  resourceId,
  content,
  type = 'default',
}: ChatMessageEvent) {
  const isUser = role === 'user';
  const Icon = useMemo(() => {
    if (isUser) {
      return User;
    } else if (role === 'system') {
      return Cog;
    } else if (role === 'reasoning') {
      return Brain;
    } else if (content.parts.some(({ type }) => type === 'tool-invocation')) {
      return Hammer;
    } else {
      return Bot;
    }
  }, [role, content.parts]);

  return (
    <div
      className={cn('flex gap-3 rounded-lg p-4', isUser ? 'bg-card' : '')}
      data-message-id={id}
      data-thread-id={threadId}
      data-resource-id={resourceId}
      data-testid={`${type}-${role}-message-${id}`}
    >
      <div className="shrink-0">
        <div
          className={cn(
            'flex size-8 items-center justify-center rounded-full',
            isUser
              ? 'bg-primary text-primary-foreground'
              : role === 'assistant'
                ? 'bg-secondary text-secondary-foreground'
                : role === 'reasoning'
                  ? 'bg-muted text-muted-foreground'
                  : 'bg-accent text-foreground'
          )}
        >
          <Icon className="size-4" />
        </div>
      </div>
      <div className="min-w-0 flex-1">
        <div className="mb-1 flex items-center gap-2">
          <span className="mn-label capitalize">{role}</span>
        </div>
        <div
          className={`
            overflow-hidden body text-wrap break-words
            [line-break:anywhere]
          `}
        >
          {content.parts.map((part, i) => (
            <UniversalContentPart key={i} part={part} />
          ))}
        </div>
      </div>
    </div>
  );
}

export function ChatMessage(props: ChatMessageEvent) {
  const { t } = useTranslation();
  return (
    <ChatMessageErrorBoundary message={props} title={t('Failed to render message')}>
      <ChatMessageContent {...props} />
    </ChatMessageErrorBoundary>
  );
}

export const ChatMessageMemo = memo(ChatMessage);
