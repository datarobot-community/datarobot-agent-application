import { useEffect, useMemo, useRef, useState } from 'react';
import { v4 as uuid } from 'uuid';
import { isCancel } from 'axios';
import {
  type RunAgentInput,
  type RunErrorEvent,
  type RunFinishedEvent,
  type StateSnapshotEvent,
  type TextMessageContentEvent,
  type TextMessageEndEvent,
  type ReasoningMessageContentEvent,
  type ReasoningMessageEndEvent,
  type ReasoningStartEvent,
  type ReasoningEndEvent,
  type TextMessageStartEvent,
  type ToolCallEndEvent,
  type ToolCallStartEvent,
  type CustomEvent,
  type StepStartedEvent,
  type StepFinishedEvent,
} from '@ag-ui/core';
import type { AgentSubscriberParams, ToolCallResultEvent } from '@ag-ui/client';

import {
  createCustomMessageWidget,
  createReasoningMessage,
  createTextMessageFromAgUiEvent,
  createTextMessageFromUserInput,
  createToolMessageFromAgUiEvent,
  messageToStateEvent,
} from '@/components/block/chat/mappers';
import type { MessageResponse } from '@/api/chat/types';
import { useFetchHistory } from '@/api/chat/hooks';
import type {
  Tool,
  ToolSerialized,
  ChatStateEvent,
  AgentEventContext,
  ChatMessageEvent,
} from '@/components/block/chat/types';
import { isProgressDone, isProgressError, isProgressStart } from '@/components/block/chat/types';
import type { ChatProviderInput } from '@/components/block/chat/chat-provider';
import {
  useChat,
  useCurrentChatState,
  type ChatState,
} from '@/components/block/chat/hooks/use-chats-state';

export type UseAgUiChatParams = ChatProviderInput;

export function useAgUiChat({
  chatId,
  isNewChat,
  runInBackground,
  refetchChats = () => Promise.resolve(),
  subscriber,
}: UseAgUiChatParams) {
  const {
    agent,
    state,
    setState,
    events,
    setEvents,
    finishStepEvent,
    addEvent,
    addToolResult,
    message,
    setMessage,
    reasoningMessage,
    setReasoningMessage,
    progress,
    setProgress,
    deleteProgress,
    userInput,
    setUserInput,
    initialState,
    setInitialState,
    isAgentRunning,
    setIsAgentRunning,
    isThinking,
    setIsThinking,
    setIsBackground,
    registerAgentRunUnsubscribe,
  } = useChat(chatId);
  const getCurrenChatState = useCurrentChatState();
  const [tools, setTools] = useState<Record<string, ToolSerialized>>({});
  const [initialMessages, setInitialMessages] = useState<MessageResponse[]>([]);
  const toolHandlersRef = useRef<
    Record<string, Pick<Tool, 'handler' | 'render' | 'renderAndWait'>>
  >({});
  const subscriberRef = useRef(subscriber);
  useEffect(() => {
    subscriberRef.current = subscriber;
  });

  const {
    data,
    isLoading: isLoadingHistory,
    refetch: refetchHistory,
  } = useFetchHistory({ chatId, enabled: !isAgentRunning && !isNewChat && !events.length });

  const history = isNewChat ? [] : data;

  const agentRef = useRef(agent);
  const toolsRef = useRef(tools);

  useEffect(() => {
    agentRef.current = agent;
    toolsRef.current = tools;
  });

  useEffect(() => {
    setIsBackground(false);
    return () => {
      const chat = getCurrenChatState(chatId);
      if (runInBackground && chat?.isAgentRunning) {
        setIsBackground(true);
        return;
      }
      chat?.agentRunUnsubscribe?.();
    };
  }, [chatId]);

  function buildEventContext(chatState: ChatState): AgentEventContext {
    let prevented = false;
    return {
      chatState,
      getCurrentChatState: () => getCurrenChatState(chatId),
      preventDefault() {
        prevented = true;
      },
      get defaultPrevented() {
        return prevented;
      },
    };
  }

  async function sendMessage(message: string) {
    if (!message.trim()) {
      return;
    }
    const messageId = uuid();
    agent.messages = [{ id: messageId, role: 'user', content: message }];

    const historyMessage = createTextMessageFromUserInput({
      message,
      chatId,
      messageId,
    });
    addEvent({
      type: 'message',
      value: historyMessage,
    });
    setUserInput('');
    setIsAgentRunning(true);
    setIsThinking(true);

    getCurrenChatState(chatId)?.agentRunUnsubscribe?.();

    const { unsubscribe } = agent.subscribe({
      async onTextMessageStartEvent(
        params: { event: TextMessageStartEvent } & AgentSubscriberParams
      ) {
        const chat = getCurrenChatState(chatId);
        if (!chat) return;
        if (subscriberRef.current?.onTextMessageStartEvent) {
          const ctx = buildEventContext(chat);
          await subscriberRef.current.onTextMessageStartEvent(params, ctx);
          if (ctx.defaultPrevented) return;
        }
        const message = createTextMessageFromAgUiEvent(params.event);
        setIsThinking(false);
        setMessage(message);
      },
      async onTextMessageContentEvent(
        params: {
          event: TextMessageContentEvent;
          textMessageBuffer: string;
        } & AgentSubscriberParams
      ) {
        const chat = getCurrenChatState(chatId);
        if (!chat) return;
        if (subscriberRef.current?.onTextMessageContentEvent) {
          const ctx = buildEventContext(chat);
          await subscriberRef.current.onTextMessageContentEvent(params, ctx);
          if (ctx.defaultPrevented) return;
        }
        const { event, textMessageBuffer } = params;
        const message = createTextMessageFromAgUiEvent(event, textMessageBuffer);
        setIsThinking(false);
        setMessage(message);
      },
      async onTextMessageEndEvent(
        params: {
          event: TextMessageEndEvent;
          textMessageBuffer: string;
        } & AgentSubscriberParams
      ) {
        let chat = getCurrenChatState(chatId);
        if (!chat) return;
        if (subscriberRef.current?.onTextMessageEndEvent) {
          const ctx = buildEventContext(chat);
          await subscriberRef.current.onTextMessageEndEvent(params, ctx);
          if (ctx.defaultPrevented) return;
        }
        chat = getCurrenChatState(chatId);
        if (!chat?.message) {
          return;
        }
        addEvent({
          type: 'message',
          value: chat.message as ChatMessageEvent,
        });
        setMessage(null);
      },
      async onReasoningStartEvent(params: { event: ReasoningStartEvent } & AgentSubscriberParams) {
        const chat = getCurrenChatState(chatId);
        if (!chat) return;
        if (subscriberRef.current?.onReasoningStartEvent) {
          const ctx = buildEventContext(chat);
          await subscriberRef.current.onReasoningStartEvent(params, ctx);
          if (ctx.defaultPrevented) return;
        }
        setIsThinking(true);
      },
      async onReasoningMessageContentEvent(
        params: {
          event: ReasoningMessageContentEvent;
          reasoningMessageBuffer: string;
        } & AgentSubscriberParams
      ) {
        const chat = getCurrenChatState(chatId);
        if (!chat) return;
        if (subscriberRef.current?.onReasoningMessageContentEvent) {
          const ctx = buildEventContext(chat);
          await subscriberRef.current.onReasoningMessageContentEvent(params, ctx);
          if (ctx.defaultPrevented) return;
        }
        const { event, reasoningMessageBuffer } = params;
        const reasoningMsg = createReasoningMessage(event, reasoningMessageBuffer);
        setReasoningMessage(reasoningMsg);
        setIsThinking(false);
      },
      async onReasoningMessageEndEvent(
        params: {
          event: ReasoningMessageEndEvent;
          reasoningMessageBuffer: string;
        } & AgentSubscriberParams
      ) {
        let chat = getCurrenChatState(chatId);
        if (!chat) return;
        if (subscriberRef.current?.onReasoningMessageEndEvent) {
          const ctx = buildEventContext(chat);
          await subscriberRef.current.onReasoningMessageEndEvent(params, ctx);
          if (ctx.defaultPrevented) return;
        }
        chat = getCurrenChatState(chatId);
        if (!chat?.reasoningMessage) {
          return;
        }
        addEvent({
          type: 'message',
          value: chat.reasoningMessage as MessageResponse,
        });
        setReasoningMessage(null);
      },
      async onReasoningEndEvent(params: { event: ReasoningEndEvent } & AgentSubscriberParams) {
        const chat = getCurrenChatState(chatId);
        if (!chat) return;
        if (subscriberRef.current?.onReasoningEndEvent) {
          const ctx = buildEventContext(chat);
          await subscriberRef.current.onReasoningEndEvent(params, ctx);
          if (ctx.defaultPrevented) return;
        }
        setIsThinking(false);
      },
      async onToolCallStartEvent(params: { event: ToolCallStartEvent } & AgentSubscriberParams) {
        const chat = getCurrenChatState(chatId);
        if (!chat) return;
        if (subscriberRef.current?.onToolCallStartEvent) {
          const ctx = buildEventContext(chat);
          await subscriberRef.current.onToolCallStartEvent(params, ctx);
          if (ctx.defaultPrevented) return;
        }
        setIsThinking(false);
      },
      async onToolCallEndEvent(
        params: {
          event: ToolCallEndEvent;
          toolCallName: string;
          toolCallArgs: Record<string, unknown>;
        } & AgentSubscriberParams
      ) {
        const chat = getCurrenChatState(chatId);
        if (!chat) return;
        if (subscriberRef.current?.onToolCallEndEvent) {
          const ctx = buildEventContext(chat);
          await subscriberRef.current.onToolCallEndEvent(params, ctx);
          if (ctx.defaultPrevented) return;
        }
        const tool = toolsRef.current[params.toolCallName];
        const toolHandler = toolHandlersRef.current[params.toolCallName];
        const isBackground = chat.isBackground;
        if (tool && toolHandler?.handler && params.toolCallArgs) {
          const canRun = !isBackground || (isBackground && tool.background);
          if (isBackground) {
            // eslint-disable-next-line no-console
            console.debug('Background tool invocation', params, tool);
          }

          if (canRun) {
            toolHandler.handler(params.toolCallArgs);
            addEvent({
              type: 'message',
              value: createToolMessageFromAgUiEvent(
                params.event,
                params.toolCallName,
                params.toolCallArgs
              ),
            });
          }
        } else if (tool && toolHandler?.render && params.toolCallArgs) {
          addEvent({
            type: 'message',
            value: createCustomMessageWidget({
              toolCallArgs: params.toolCallArgs,
              toolCallName: params.toolCallName,
              threadId: chatId,
            }),
          });
        } else {
          addEvent({
            type: 'message',
            value: createToolMessageFromAgUiEvent(
              params.event,
              params.toolCallName,
              params.toolCallArgs
            ),
          });
        }
      },
      async onToolCallResultEvent(
        params: {
          event: ToolCallResultEvent;
        } & AgentSubscriberParams
      ) {
        const chat = getCurrenChatState(chatId);
        if (!chat) return;
        if (subscriberRef.current?.onToolCallResultEvent) {
          const ctx = buildEventContext(chat);
          await subscriberRef.current.onToolCallResultEvent(params, ctx);
          if (ctx.defaultPrevented) return;
        }
        addToolResult({
          toolCallId: params.event.toolCallId,
          result: params.event.content,
        });
      },
      async onStateSnapshotEvent(params: { event: StateSnapshotEvent } & AgentSubscriberParams) {
        const chat = getCurrenChatState(chatId);
        if (!chat) return;
        if (subscriberRef.current?.onStateSnapshotEvent) {
          const ctx = buildEventContext(chat);
          await subscriberRef.current.onStateSnapshotEvent(params, ctx);
          if (ctx.defaultPrevented) return;
        }
        setState(params.state);
      },
      async onStateChanged(
        params: Omit<AgentSubscriberParams, 'input'> & { input?: RunAgentInput }
      ) {
        const chat = getCurrenChatState(chatId);
        if (!chat) return;
        if (subscriberRef.current?.onStateChanged) {
          const ctx = buildEventContext(chat);
          await subscriberRef.current.onStateChanged(params, ctx);
          if (ctx.defaultPrevented) return;
        }
        setIsThinking(false);
        setState(params.state);
      },
      async onStepStartedEvent(params: { event: StepStartedEvent } & AgentSubscriberParams) {
        const chat = getCurrenChatState(chatId);
        if (!chat) return;
        if (subscriberRef.current?.onStepStartedEvent) {
          const ctx = buildEventContext(chat);
          await subscriberRef.current.onStepStartedEvent(params, ctx);
          if (ctx.defaultPrevented) return;
        }
        setIsThinking(false);
        addEvent({
          type: 'step',
          value: {
            id: uuid(),
            threadId: chatId,
            createdAt: new Date(),
            name: params.event.stepName,
            isRunning: true,
          },
        });
      },
      async onStepFinishedEvent(params: { event: StepFinishedEvent } & AgentSubscriberParams) {
        const chat = getCurrenChatState(chatId);
        if (!chat) return;
        if (subscriberRef.current?.onStepFinishedEvent) {
          const ctx = buildEventContext(chat);
          await subscriberRef.current.onStepFinishedEvent(params, ctx);
          if (ctx.defaultPrevented) return;
        }
        finishStepEvent(params.event.stepName);
      },
      async onRunFinishedEvent(
        params: {
          event: RunFinishedEvent;
          result?: unknown;
        } & AgentSubscriberParams
      ) {
        const chat = getCurrenChatState(chatId);
        // chat should be present if onRunFinishedEvent is invoked, adding this just in case
        // zustand store was changed in unexpected way
        if (!chat) {
          agent.abortController.abort();
          unsubscribe();
          return;
        }
        if (subscriberRef.current?.onRunFinishedEvent) {
          const ctx = buildEventContext(chat as ChatState);
          await subscriberRef.current.onRunFinishedEvent(params, ctx);
        }
        chat.agentRunUnsubscribe?.();
        setIsAgentRunning(false);
        setIsThinking(false);
        refetchChats();
      },
      async onCustomEvent(params: { event: CustomEvent } & AgentSubscriberParams) {
        const chat = getCurrenChatState(chatId);
        if (!chat) return;
        if (subscriberRef.current?.onCustomEvent) {
          const ctx = buildEventContext(chat);
          await subscriberRef.current.onCustomEvent(params, ctx);
          if (ctx.defaultPrevented) return;
        }
        const event = params.event;
        if (event?.name !== 'Heartbeat') {
          setIsThinking(false);
        }
        // eslint-disable-next-line no-console
        console.debug('onCustomEvent', params);

        if (isProgressStart(event)) {
          setProgress(state => {
            state[event.value.id] = event.value.steps;
          });
        } else if (isProgressDone(event)) {
          setProgress(state => {
            state[event.value.id] = state[event.value.id].map((s, i) =>
              event.value.step === i ? { ...s, done: true } : s
            );
          });
        } else if (isProgressError(event)) {
          setProgress(state => {
            state[event.value.id] = state[event.value.id].map((s, i) =>
              event.value.step === i ? { ...s, error: event.value.message } : s
            );
          });
        }
      },
      async onRunErrorEvent(params: { event: RunErrorEvent } & AgentSubscriberParams) {
        const chat = getCurrenChatState(chatId);
        // chat should be present if onRunErrorEvent is invoked, adding this just in case
        // zustand store was changed in unexpected way
        if (!chat) {
          agent.abortController.abort();
          unsubscribe();
          return;
        }
        if (subscriberRef.current?.onRunErrorEvent) {
          const ctx = buildEventContext(chat);
          await subscriberRef.current.onRunErrorEvent(params, ctx);
        }
        chat.agentRunUnsubscribe?.();
        setIsAgentRunning(false);
        setIsThinking(false);
        if (params.event.rawEvent?.name === 'AbortError') {
          return;
        }
        addEvent({
          type: 'error',
          value: {
            id: uuid(),
            threadId: chatId,
            createdAt: new Date(),
            error: params.event.message,
          },
        });
      },
    });

    registerAgentRunUnsubscribe(() => {
      unsubscribe();
      agent.abortController.abort();
    });

    try {
      const result = await agent.runAgent({
        tools: Object.values(tools)
          .filter(tool => tool.enabled !== false)
          // eslint-disable-next-line @typescript-eslint/no-unused-vars
          .map(({ background, ...tool }) => tool),
      });
      // eslint-disable-next-line no-console
      console.debug('runAgent result', result);
    } catch (error) {
      setIsAgentRunning(false);
      setIsThinking(false);
      if (isCancel(error) || (error as Error).name === 'AbortError') {
        return;
      }
      console.error(error);
    }
  }

  const combinedEvents: ChatStateEvent[] = useMemo(() => {
    const result: ChatStateEvent[] =
      !isLoadingHistory && !history?.length && initialMessages
        ? [...initialMessages.map(messageToStateEvent)]
        : [];
    if (history?.length) {
      const uiEvents = new Set(events.map(({ value }) => value.id));
      const historyWithoutUiEvents = history
        .filter(message => !uiEvents.has(message.id))
        .map(messageToStateEvent);
      result.push(...historyWithoutUiEvents);
    }
    result.push(...events);
    if (message) {
      result.push(messageToStateEvent(message));
    }

    if (reasoningMessage) {
      result.push(messageToStateEvent(reasoningMessage));
    }

    if (isThinking) {
      result.push({
        type: 'thinking',
        value: {
          id: 'thinking',
          threadId: chatId,
          createdAt: new Date(),
        },
      });
    }
    return result;
  }, [
    chatId,
    history,
    events,
    message,
    reasoningMessage,
    isLoadingHistory,
    isThinking,
    initialMessages,
  ]);

  function registerOrUpdateTool(id: string, tool: ToolSerialized) {
    setTools(state => ({
      ...state,
      [id]: tool,
    }));
  }

  function updateToolHandler(
    name: string,
    handler: Pick<Tool, 'handler' | 'render' | 'renderAndWait'>
  ) {
    toolHandlersRef.current[name] = handler;
  }

  function removeTool(name: string) {
    setTools(state => {
      const copy = { ...state };
      delete copy[name];
      return copy;
    });
    delete toolHandlersRef.current[name];
  }

  function getTool(
    name: string
  ): (ToolSerialized & Pick<Tool, 'handler' | 'render' | 'renderAndWait'>) | null {
    if (tools[name] && toolHandlersRef.current[name]) {
      return {
        ...tools[name],
        ...toolHandlersRef.current[name],
      };
    }

    return null;
  }

  return {
    agent,
    /*state*/
    state,
    setState,
    chatId,
    events,
    setEvents,
    message,
    combinedEvents,
    setMessage,
    userInput,
    setUserInput,
    initialMessages,
    setInitialMessages,
    initialState,
    setInitialState,
    progress,
    setProgress,
    deleteProgress,
    isAgentRunning,
    setIsAgentRunning,
    isThinking,
    setIsThinking,
    setIsBackground,
    /*methods*/
    sendMessage,
    registerOrUpdateTool,
    updateToolHandler,
    removeTool,
    getTool,
    /*resolver*/
    useFetchHistory,
    isLoadingHistory,
    refetchHistory,
  };
}
