import { Loader2 } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useTranslation } from '@/lib/i18n';

export function ThinkingEvent() {
  const { t } = useTranslation();
  return (
    <div className={cn('gap-3 p-4 rounded-lg flex bg-card')}>
      <div className="shrink-0">
        <div
          className={cn(
            'size-8 flex items-center justify-center rounded-full',
            'bg-blue-500/10 text-blue-500'
          )}
        >
          <Loader2 className={cn('size-4 animate-spin')} />
        </div>
      </div>
      <div className="min-w-0 flex-1">
        <div className="mb-1 gap-2 flex h-full items-center">
          <span className="flex h-full items-center mn-label" data-testid="thinking-loading">
            {t('Thinking')}
          </span>
        </div>
      </div>
    </div>
  );
}
