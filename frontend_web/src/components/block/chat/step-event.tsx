import { Loader2, CheckCircle2 } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { ChatStepEvent as StepEventType } from './types';
import { useMemo } from 'react';

export function StepEvent({ id, name, createdAt, isRunning, threadId }: StepEventType) {
  const Icon = useMemo(() => {
    return isRunning ? Loader2 : CheckCircle2;
  }, [isRunning]);

  // Convert createdAt to Date if it's a string
  const date = typeof createdAt === 'string' ? new Date(createdAt) : createdAt;

  return (
    <div className={cn('flex gap-3 rounded-lg p-4')} data-step-id={id} data-thread-id={threadId}>
      <div className="shrink-0">
        <div
          className={cn(
            'flex size-8 items-center justify-center rounded-full',
            isRunning ? 'bg-blue-500/10 text-blue-500' : 'bg-green-500/10 text-green-500'
          )}
        >
          <Icon className={cn('size-4', isRunning && 'animate-spin')} />
        </div>
      </div>
      <div className="min-w-0 flex-1">
        <div className="mb-1 flex items-center gap-2">
          <span className="mn-label">{name}</span>
          <span className="caption-01">{date.toLocaleTimeString()}</span>
        </div>
        <div className="caption-01">{isRunning ? 'In progress...' : 'Completed'}</div>
      </div>
    </div>
  );
}
