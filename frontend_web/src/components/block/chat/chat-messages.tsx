import { type PropsWithChildren } from 'react';
import { Skeleton } from '@/components/ui/skeleton';
import { ChatMessageMemo } from './chat-message';
import { ChatError } from './chat-error';
import {
  isErrorStateEvent,
  isMessageStateEvent,
  isStepStateEvent,
  type ChatStateEvent,
  isThinkingEvent,
} from './types';
import { StepEvent } from './step-event';
import { ThinkingEvent } from './thinking-event';

export type ChatMessageProps = {
  isLoading: boolean;
  chatId: string;
  messages?: ChatStateEvent[];
} & PropsWithChildren;

export function ChatMessages({ children, messages, isLoading }: ChatMessageProps) {
  return (
    <div className="gap-2 flex flex-col">
      {isLoading && !messages?.length ? (
        <div className="space-y-4">
          <Skeleton className="h-20 w-full" />
          <Skeleton className="h-20 w-full" />
          <Skeleton className="h-20 w-full" />
        </div>
      ) : (
        children ||
        (messages &&
          messages.map(m => {
            if (isErrorStateEvent(m)) {
              return <ChatError key={m.value.id} {...m.value} />;
            }
            if (isMessageStateEvent(m)) {
              return <ChatMessageMemo key={m.value.id} {...m.value} />;
            }
            if (isStepStateEvent(m)) {
              return <StepEvent key={m.value.id} {...m.value} />;
            }
            if (isThinkingEvent(m)) {
              return <ThinkingEvent key={m.type} />;
            }
          }))
      )}
    </div>
  );
}
