import { AlertCircle } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { ChatErrorEvent } from './types';
import { useTranslation } from '@/lib/i18n';

export function ChatError({ error, createdAt, testId = 'chat-error-message' }: ChatErrorEvent) {
  const { t } = useTranslation();
  // Convert createdAt to Date if it's a string
  const date = typeof createdAt === 'string' ? new Date(createdAt) : createdAt;

  return (
    <div
      className={cn('flex gap-3 rounded-lg p-4', 'border border-destructive/20 bg-destructive/10')}
      data-testid={testId}
    >
      <div className="shrink-0">
        <div
          className={cn(
            'flex size-8 items-center justify-center rounded-full',
            'text-destructive-background bg-destructive/20'
          )}
        >
          <AlertCircle className="size-4" />
        </div>
      </div>
      <div className="min-w-0 flex-1">
        <div className="mb-1 flex items-center gap-2">
          <span className="mn-label text-destructive">{t('Error')}</span>
          <span className="caption-01">{date.toLocaleTimeString()}</span>
        </div>
        <div className="body break-words whitespace-pre-wrap text-destructive">{error}</div>
      </div>
    </div>
  );
}
