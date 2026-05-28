import { type PropsWithChildren, useEffect, useRef } from 'react';
import { ChatMessages } from './chat-messages';
import { ChatTextInput } from './chat-input';
import { ChatProgress } from './chat-progress';
import { useChatContext } from '@/components/block/chat/hooks/use-chat-context';
import { ScrollArea } from '@/components/ui/scroll-area';
import { type MessageResponse, type ChatStateEvent } from './types';

export type ChatProps = {
  initialMessages?: MessageResponse[];
} & PropsWithChildren;

const THRESHOLD = 100;

export function useChatScroll({
  chatId,
  events,
  enabled = true,
}: {
  chatId: string;
  events: ChatStateEvent[];
  enabled?: boolean;
}) {
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const shouldAutoscrollRef = useRef<boolean>(true);

  const onChatScroll = () => {
    if (!scrollContainerRef.current || !events.length) {
      return;
    }
    const { scrollTop, scrollHeight, clientHeight } = scrollContainerRef.current;
    const distanceFromBottom = scrollHeight - scrollTop - clientHeight;
    shouldAutoscrollRef.current = distanceFromBottom <= THRESHOLD;
  };

  useEffect(() => {
    if (!enabled) {
      return;
    }
    if (scrollContainerRef.current) {
      scrollContainerRef.current.scrollTop = scrollContainerRef.current.scrollHeight;
    }
  }, [chatId, enabled]);

  useEffect(() => {
    if (!enabled) {
      return;
    }
    if (scrollContainerRef.current && shouldAutoscrollRef.current) {
      scrollContainerRef.current.scrollTop = scrollContainerRef.current.scrollHeight;
    }
  }, [events, enabled]);

  return { scrollContainerRef, onChatScroll };
}

export function Chat({ initialMessages, children }: ChatProps) {
  const {
    chatId,
    sendTextMessage,
    userInput,
    setUserInput,
    combinedEvents,
    progress,
    deleteProgress,
    isLoadingHistory,
    setInitialMessages,
    isAgentRunning,
  } = useChatContext();
  useEffect(() => {
    if (initialMessages) {
      setInitialMessages(initialMessages);
    }
  }, []);

  const { scrollContainerRef, onChatScroll } = useChatScroll({
    chatId,
    events: combinedEvents,
    enabled: !children,
  });

  return (
    <div className="flex size-full min-w-0 flex-col gap-4 p-2">
      {children || (
        <>
          <ScrollArea
            className="mb-5 min-h-0 w-full flex-1"
            scrollViewportRef={scrollContainerRef}
            onWheel={onChatScroll}
          >
            <div className="w-full justify-self-center">
              <ChatMessages
                isLoading={isLoadingHistory}
                messages={combinedEvents}
                chatId={chatId}
              />
              <ChatProgress progress={progress || {}} deleteProgress={deleteProgress} />
            </div>
          </ScrollArea>

          <ChatTextInput
            userInput={userInput}
            setUserInput={setUserInput}
            onSubmit={sendTextMessage}
            runningAgent={isAgentRunning}
          />
        </>
      )}
    </div>
  );
}
