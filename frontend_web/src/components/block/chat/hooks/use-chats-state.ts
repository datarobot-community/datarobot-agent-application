import { createStore, type StateCreator } from 'zustand/vanilla';
import { immer } from 'zustand/middleware/immer';
import type { MessageResponse, ToolInvocationData } from '@/api/chat/types';
import {
  type ToolSerialized,
  type ChatStateEvent,
  type ChatStateEventByType,
  type ProgressState,
  isToolInvocationPart,
} from '@/components/block/chat/types';
import { useStore } from 'zustand/react';
import { HttpAgent } from '@ag-ui/client';
import { createAgent } from '@/components/block/chat/agent';
import type { Draft } from 'immer';

export interface CreateChatArgs {
  id: string;
}

export interface ChatState {
  id: string;
  agent: HttpAgent;
  state: Record<string, unknown>;
  events: ChatStateEvent[];
  message: MessageResponse | null;
  reasoningMessage: MessageResponse | null;
  userInput: string;
  progress: ProgressState;
  initialState: Record<string, unknown>;
  isAgentRunning: boolean;
  isThinking: boolean;
  isBackground: boolean;
  setEvents: (events: ChatStateEvent[]) => void;
  finishStepEvent: (name: string) => void;
  addEvent: (event: ChatStateEvent) => void;
  addToolArgs: ({
    toolCallId,
    args,
  }: {
    toolCallId: string;
    args: Record<string, unknown>;
  }) => void;
  addToolResult: ({
    toolCallId,
    result,
    endTime,
  }: {
    toolCallId: string;
    result: string;
    endTime?: number;
  }) => void;
  setState: (nextState: Record<string, unknown>) => void;
  setMessage: (message: MessageResponse | null) => void;
  setReasoningMessage: (message: MessageResponse | null) => void;
  setProgress: (cb: (progress: ProgressState) => void) => void;
  deleteProgress: (progressId: string) => void;
  setUserInput: (userInput: string) => void;
  setInitialState: (initialState: Record<string, unknown>) => void;
  setIsAgentRunning: (isAgentRunning: boolean) => void;
  setIsThinking: (isThinking: boolean) => void;
  setIsBackground: (background: boolean) => void;
  /**
   * HttpAgent `subscribe` teardown for the active run. Set while a run is in progress;
   * `deleteChatState` invokes it before abort/removal so no further events are delivered.
   */
  agentRunUnsubscribe: (() => void) | null;
  registerAgentRunUnsubscribe: (fn: (() => void) | null) => void;
  deleteChatState: () => void;
}

interface ChatsState {
  chats: Record<string, ChatState>;
  initialMessages: MessageResponse[];
  tools: Record<string, ToolSerialized>;
  addChat: (chatId: string) => ChatState;
}

function updateToolPart(
  state: Draft<ChatsState>,
  chatId: string,
  toolCallId: string,
  cb: (inv: ToolInvocationData) => void
) {
  if (!state.chats[chatId]) return;
  for (const ev of state.chats[chatId].events) {
    const parts = (ev.value as MessageResponse).content?.parts;
    if (!parts?.length) continue;
    for (const part of parts) {
      if (isToolInvocationPart(part)) {
        const inv = part.toolInvocation;
        if (inv?.toolCallId === toolCallId) {
          cb(inv);
          return;
        }
      }
    }
  }
}

const createChatSliceFactory = ({ id }: CreateChatArgs) => {
  const createChatSlice: StateCreator<
    ChatsState,
    [['zustand/immer', never]],
    [],
    ChatState
  > = set => {
    return {
      id,
      agent: createAgent({ threadId: id }),
      state: {},
      events: [],
      message: null,
      reasoningMessage: null,
      userInput: '',
      initialState: {},
      progress: {},
      isAgentRunning: false,
      isThinking: false,
      isBackground: false,
      agentRunUnsubscribe: null,
      /* access methods */
      finishStepEvent: (stepName: string) =>
        set(state => {
          if (state.chats[id]) {
            // Match the first still-running step with this name. Using only
            // `name === stepName` would always return the first occurrence,
            // so when the same step name appears across multiple turns the
            // second STEP_FINISHED would re-close the already-closed first
            // step and leave the new one stuck on "In progress".
            const runningStep = state.chats[id].events.find(event => {
              const step = event as ChatStateEventByType<'step'>;
              return step.value?.name === stepName && step.value?.isRunning === true;
            }) as ChatStateEventByType<'step'> | undefined;
            if (runningStep) {
              runningStep.value.isRunning = false;
            }
          }
        }),
      setEvents: (events: ChatStateEvent[]) =>
        set(state => {
          if (state.chats[id]) {
            state.chats[id].events = events;
          }
        }),
      addEvent: (event: ChatStateEvent) =>
        set(state => {
          if (state.chats[id]) {
            state.chats[id].events.push(event);
          }
        }),
      addToolArgs: ({
        toolCallId,
        args,
      }: {
        toolCallId: string;
        args: Record<string, unknown>;
      }) => {
        set(state => {
          updateToolPart(state, id, toolCallId, invocationData => {
            invocationData.args = args;
            invocationData.state = 'call';
          });
        });
      },
      addToolResult: ({
        toolCallId,
        result,
        endTime,
      }: {
        toolCallId: string;
        result: string;
        endTime?: number;
      }) => {
        set(state => {
          updateToolPart(state, id, toolCallId, invocationData => {
            invocationData.result = result;
            invocationData.state = 'result';
            if (endTime !== undefined) {
              invocationData.metadata = {
                ...invocationData.metadata,
                endTime,
              };
            }
          });
        });
      },
      setState: (nextState: Record<string, unknown>) =>
        set(state => {
          if (state.chats[id]) {
            state.chats[id].state = nextState;
          }
        }),
      setMessage: (message: MessageResponse | null) =>
        set(state => {
          if (state.chats[id]) {
            state.chats[id].message = message;
          }
        }),
      setReasoningMessage: (message: MessageResponse | null) =>
        set(state => {
          if (state.chats[id]) {
            state.chats[id].reasoningMessage = message;
          }
        }),
      setProgress: (cb: (progress: ProgressState) => void) =>
        set(state => {
          if (state.chats[id]) {
            cb(state.chats[id].progress);
          }
        }),
      deleteProgress: (progressId: string) =>
        set(state => {
          if (state.chats[id]) {
            delete state.chats[id].progress[progressId];
          }
        }),
      setUserInput: (userInput: string) =>
        set(state => {
          if (state.chats[id]) {
            state.chats[id].userInput = userInput;
          }
        }),
      setInitialState: (initialState: Record<string, unknown>) =>
        set(state => {
          if (state.chats[id]) {
            state.chats[id].initialState = initialState;
          }
        }),
      setIsAgentRunning: (isAgentRunning: boolean) =>
        set(state => {
          if (state.chats[id]) {
            state.chats[id].isAgentRunning = isAgentRunning;
          }
        }),
      setIsThinking: (isThinking: boolean) =>
        set(state => {
          if (state.chats[id]) {
            state.chats[id].isThinking = isThinking;
          }
        }),
      setIsBackground: (background: boolean) =>
        set(state => {
          if (state.chats[id]) {
            state.chats[id].isBackground = background;
          }
        }),
      registerAgentRunUnsubscribe: (fn: (() => void) | null) =>
        set(state => {
          if (state.chats[id]) {
            state.chats[id].agentRunUnsubscribe = fn;
          }
        }),
      deleteChatState: () => {
        const chat = chatsStore.getState().chats[id];
        if (chat) {
          chat.agentRunUnsubscribe?.();
          chat.agent.abortController.abort();
        }
        set(state => {
          if (state.chats[id]) {
            state.chats[id].agentRunUnsubscribe = null;
            delete state.chats[id];
          }
        });
      },
    };
  };

  return createChatSlice;
};

const chatsStore = createStore<ChatsState>()(
  immer((set, get, store) => ({
    chats: {},
    initialMessages: [],
    tools: {},
    addChat: id => {
      const createChatSlice = createChatSliceFactory({ id });
      const chatSlice = createChatSlice(set, get, store);
      set(state => {
        if (!state.chats[id]) {
          state.chats[id] = chatSlice;
        }
      });

      return chatSlice;
    },
  }))
);

export const useChat = (id: string): ChatState => {
  return useStore(chatsStore, state => state.chats[id]);
};

export const useHasChat = (id: string): boolean => {
  return useStore(chatsStore, state => !!state.chats[id]);
};

export const useAddChat = () => {
  return useStore(chatsStore, state => state.addChat);
};

export const useCurrentChatState = (): ((chatId: string) => ChatState | undefined) => {
  return (chatId: string) => chatsStore.getState().chats[chatId];
};
