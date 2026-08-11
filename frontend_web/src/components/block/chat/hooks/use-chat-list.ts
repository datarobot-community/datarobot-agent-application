import { useEffect, useMemo, useRef, useState } from 'react';
import { v4 as uuid } from 'uuid';
import type { ChatListItem } from '@/api/chat/types';
import { useDeleteChat, useFetchChats } from '@/api/chat/hooks';
import {
  useAddChat,
  useCurrentChatState,
  useHasChat,
} from '@/components/block/chat/hooks/use-chats-state';

export type UseChatListParams = {
  chatId: string;
  setChatId: (id: string) => void;
  /**
   * Set to true if "No chats selected" state should be shown
   */
  showStartChat?: boolean;
};

export function useChatList({ chatId, setChatId, showStartChat = false }: UseChatListParams) {
  const [newChat, setNewChat] = useState<ChatListItem | null>(null);
  const hasChat = useHasChat(chatId);

  const addChatToState = useAddChat();
  const { mutateAsync: deleteChatMutation, isPending: isDeletingChat } = useDeleteChat();
  const { data: chats, isLoading: isLoadingChats, refetch: refetchChats } = useFetchChats();
  const getCurrentChatState = useCurrentChatState();
  /**
   * Returns new chat id
   */
  const createChat = (name: string): string => {
    const newChatID = uuid();
    setNewChat({
      id: newChatID,
      name: name,
      userId: '',
      createdAt: new Date(),
      updatedAt: null,
    });
    addChatToState(newChatID);
    return newChatID;
  };

  function addChatHandler() {
    const newChatID = createChat('New');
    setChatId(newChatID);
  }

  // Sync: register an external chatId in the in-memory chats set when not yet tracked
  useEffect(() => {
    if (!hasChat && chatId && !isLoadingChats) {
      addChatToState(chatId);
    }
  }, [hasChat, chatId, isLoadingChats]);

  // Init: auto-create a chat on load when no chatId is present and start-chat screen is off
  const autoCreatedRef = useRef(false);
  useEffect(() => {
    if (!chatId && !isLoadingChats && !showStartChat && !autoCreatedRef.current) {
      autoCreatedRef.current = true;
      addChatHandler();
    }
  }, [chatId, isLoadingChats, showStartChat]);

  // Derive: treat newChat as pending only until the server confirms it
  const pendingNewChat = useMemo(
    () => (newChat && !chats?.some(c => c.id === newChat.id) ? newChat : null),
    [chats, newChat]
  );

  const chatsWithNew = useMemo(() => {
    if (!pendingNewChat) return chats;
    return [pendingNewChat, ...(chats ?? [])];
  }, [chats, pendingNewChat]);

  const deleteChat = (id: string) => {
    return deleteChatMutation({ chatId: id }).then(response => {
      const chat = getCurrentChatState(id);
      if (chat) {
        chat.deleteChatState();
      }
      return response;
    });
  };

  function deleteChatHandler(id: string, callbackFn: () => void) {
    deleteChat(id)
      .catch(error => console.error(error))
      .finally(callbackFn);
  }

  return {
    isNewChat: pendingNewChat?.id === chatId,
    hasChat,
    chatId,
    setChatId,
    chats: chatsWithNew,
    newChat: pendingNewChat,
    setNewChat,
    isLoadingChats,
    refetchChats,
    deleteChat,
    isDeletingChat,
    addChatHandler,
    deleteChatHandler,
  };
}
