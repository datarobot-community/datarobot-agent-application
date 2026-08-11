import { useEffect, useRef } from 'react';
import { CheckCircle2, Loader2, Circle, XCircle, X } from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';
import type { ProgressState } from './types';

const removeAfter = 2000;

export function ChatProgress({
  progress,
  deleteProgress,
}: {
  progress: ProgressState;
  deleteProgress: (progressId: string) => void;
}) {
  const progressTimeoutsRef = useRef<Record<string, number>>({});
  useEffect(() => {
    Object.entries(progress).forEach(([id, p]) => {
      const allDone = p.every(({ done }) => !!done);
      if (allDone && !progressTimeoutsRef.current[id]) {
        progressTimeoutsRef.current[id] = window.setTimeout(() => {
          console.debug('Remove progress data', id);
          deleteProgress(id);
        }, removeAfter);
      }
    });
  }, [progress]);

  const handleClose = (id: string) => {
    deleteProgress(id);
    // Clear timeout if exists
    if (progressTimeoutsRef.current[id]) {
      clearTimeout(progressTimeoutsRef.current[id]);
      delete progressTimeoutsRef.current[id];
    }
  };

  if (Object.keys(progress).length === 0) {
    return null;
  }

  return (
    <div className="mb-4 space-y-3">
      {Object.entries(progress).map(([id, p]) => {
        const allDone = p.every(({ done }) => !!done);
        const hasError = p.some(({ error }) => !!error);
        const completedCount = p.filter(({ done }) => !!done).length;
        const errorCount = p.filter(({ error }) => !!error).length;
        const totalCount = p.length;

        return (
          <Card
            key={id}
            className={cn(
              'py-0 transition-all duration-300',
              allDone && !hasError && 'border-green-500/30 opacity-80',
              hasError && 'border-red-500/30 opacity-80'
            )}
          >
            <CardContent className="p-4">
              <div className="mb-3 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  {hasError ? (
                    <XCircle className="size-4 text-red-500" />
                  ) : allDone ? (
                    <CheckCircle2 className="size-4 text-green-500" />
                  ) : (
                    <Loader2 className="size-4 animate-spin text-blue-500" />
                  )}
                  <span className="mn-label">
                    {hasError ? 'Failed' : allDone ? 'Completed' : 'Processing'}
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  <Badge
                    variant={hasError ? 'destructive' : allDone ? 'info' : 'default'}
                    className="caption-01"
                  >
                    {hasError
                      ? `${errorCount} error${errorCount > 1 ? 's' : ''}`
                      : `${completedCount}/${totalCount}`}
                  </Badge>
                  {hasError && (
                    <button
                      onClick={() => handleClose(id)}
                      className={`
                        text-muted-foreground transition-colors
                        hover:text-foreground
                      `}
                      aria-label="Close"
                    >
                      <X className="size-4" />
                    </button>
                  )}
                </div>
              </div>

              <div className="space-y-2">
                {p.map(step => (
                  <div key={step.name}>
                    <div
                      className={cn(
                        'flex items-center gap-2 body transition-all duration-200',
                        step.done ? 'text-muted-foreground' : 'text-foreground',
                        step.error && 'text-red-500'
                      )}
                    >
                      {step.error ? (
                        <XCircle className="size-3.5 shrink-0 text-red-500" />
                      ) : step.done ? (
                        <CheckCircle2 className="size-3.5 shrink-0 text-green-500" />
                      ) : (
                        <Circle className="size-3.5 shrink-0 text-muted-foreground" />
                      )}
                      <span className={cn(step.done && !step.error && 'line-through')}>
                        {step.name}
                      </span>
                    </div>
                    {step.error && (
                      <div className="mt-1 ml-5.5 caption-01 text-red-500/80">{step.error}</div>
                    )}
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        );
      })}
    </div>
  );
}
