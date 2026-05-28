'use client';

import { createContext } from 'react';
import { useAgUiChat } from '@/components/block/chat/hooks/use-ag-ui-chat';
import { HttpAgent } from '@ag-ui/client';

export type AgUiChatReturn = ReturnType<typeof useAgUiChat>;

export const ChatContext = createContext<AgUiChatReturn>({
  agent: new HttpAgent({ url: '' }),
  /*state*/
  state: {},
  setState: () => {},
  chatId: '',
  events: [],
  setEvents: () => {},
  message: null,
  combinedEvents: [],
  setMessage: () => {},
  userInput: '',
  setUserInput: () => {},
  initialMessages: [],
  setInitialMessages: () => {},
  initialState: {},
  setInitialState: () => {},
  progress: {},
  setProgress: () => {},
  deleteProgress: () => {},
  isAgentRunning: false,
  setIsAgentRunning: () => {},
  isThinking: false,
  setIsThinking: () => {},
  setIsBackground: () => {},
  /*methods*/
  sendMessage: () => Promise.resolve(undefined),
  sendTextMessage: () => Promise.resolve(undefined),
  registerOrUpdateTool: () => {},
  updateToolHandler: () => {},
  removeTool: () => {},
  getTool: () => null,
  /*resolver*/
  useFetchHistory: (() => ({})) as unknown as AgUiChatReturn['useFetchHistory'],
  isLoadingHistory: false,
  refetchHistory: (() => Promise.resolve(undefined)) as unknown as AgUiChatReturn['refetchHistory'],
});
