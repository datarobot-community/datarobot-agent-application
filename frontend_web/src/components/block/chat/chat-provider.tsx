import { type PropsWithChildren } from 'react';
import { useAgUiChat } from '@/components/block/chat/hooks/use-ag-ui-chat';
import { ChatContext } from '@/components/block/chat/context';
import type { AgentSubscriber } from './types';

export type ChatProviderInput = {
  chatId: string;
  refetchChats?: () => Promise<unknown>;
  runInBackground?: boolean;
  isNewChat?: boolean;
  subscriber?: AgentSubscriber;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  forwardedProps?: any;
};
export type ChatProviderProps = ChatProviderInput & PropsWithChildren;

export function ChatProvider({
  children,
  chatId,
  runInBackground = false,
  isNewChat = false,
  subscriber,
  refetchChats: refetchChatsFromProps,
  forwardedProps,
}: ChatProviderProps) {
  const refetchChats = refetchChatsFromProps ?? (() => Promise.resolve());
  const value = useAgUiChat({
    chatId,
    isNewChat,
    runInBackground,
    refetchChats,
    subscriber,
    forwardedProps,
  });
  return <ChatContext.Provider value={value}>{children}</ChatContext.Provider>;
}
