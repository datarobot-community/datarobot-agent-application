'use client';
import { v4 as uuid } from 'uuid';
import type {
  ReasoningMessageChunkEvent,
  ReasoningMessageContentEvent,
  ReasoningMessageEndEvent,
  ReasoningMessageStartEvent,
  TextMessageChunkEvent,
  TextMessageContentEvent,
  TextMessageEndEvent,
  TextMessageStartEvent,
  ToolCallStartEvent,
} from '@ag-ui/core';
import { EventType } from '@ag-ui/core';
import type { MessageResponse } from '@/api/chat/types';
import type { ChatMessageEvent, ChatStateEventByType } from '@/components/block/chat/types';

type AgUiTextEvent =
  | TextMessageStartEvent
  | TextMessageContentEvent
  | TextMessageEndEvent
  | TextMessageChunkEvent;

type AgUiReasoningEvent =
  | ReasoningMessageStartEvent
  | ReasoningMessageContentEvent
  | ReasoningMessageChunkEvent
  | ReasoningMessageEndEvent;

export function createTextMessageFromAgUiEvent(
  event: AgUiTextEvent,
  textMessageBuffer?: string,
  metadata?: Record<string, unknown>
): MessageResponse {
  const baseMessage: MessageResponse = {
    id: event.messageId || '',
    content: {
      format: 2,
      parts: [],
      content: '',
    },
    role: 'assistant',
    createdAt: event.timestamp ? new Date(event.timestamp) : new Date(),
    threadId: '',
    resourceId: '',
    metadata,
  };

  // Map role, converting 'developer' to 'system' for compatibility
  const mapRole = (
    role?: 'user' | 'assistant' | 'system' | 'developer'
  ): 'user' | 'assistant' | 'system' => {
    if (!role || role === 'developer') return 'system';
    return role;
  };

  switch (event.type) {
    case EventType.TEXT_MESSAGE_START:
      return {
        ...baseMessage,
        role: mapRole(event.role),
        id: event.messageId,
      };

    case EventType.TEXT_MESSAGE_CONTENT:
      return {
        ...baseMessage,
        id: event.messageId,
        content: {
          format: 2,
          parts: [
            {
              type: 'text',
              text: textMessageBuffer + event.delta,
            },
          ],
          content: textMessageBuffer + event.delta,
        },
      };

    case EventType.TEXT_MESSAGE_END:
      return {
        ...baseMessage,
        id: event.messageId,
      };

    case EventType.TEXT_MESSAGE_CHUNK:
      return {
        ...baseMessage,
        id: event.messageId || '',
        role: mapRole(event.role),
        content: {
          format: 2,
          parts: event.delta
            ? [
                {
                  type: 'text',
                  text: event.delta,
                },
              ]
            : [],
          content: event.delta || '',
        },
      };

    default:
      return baseMessage;
  }
}

/** Partial tool row at TOOL_CALL_START (args filled in on tool call end). */
export function createToolMessageFromToolCallStartEvent(
  event: ToolCallStartEvent,
  threadId: string,
  startTime: number
): MessageResponse {
  return {
    id: uuid(),
    content: {
      format: 2,
      parts: [
        {
          type: 'tool-invocation',
          toolInvocation: {
            state: 'start',
            toolCallId: event.toolCallId,
            toolName: event.toolCallName,
            metadata: {
              startTime,
              ...(event.parentMessageId != null && event.parentMessageId !== ''
                ? { parentMessageId: event.parentMessageId }
                : {}),
            },
          },
        },
      ],
    },
    role: 'assistant',
    createdAt: event.timestamp ? new Date(event.timestamp) : new Date(),
    threadId,
    resourceId: uuid(),
  };
}

export function createTextMessageFromUserInput({
  message,
  chatId,
  messageId,
}: {
  message: string;
  chatId: string;
  messageId: string;
}): MessageResponse {
  const baseMessage: MessageResponse = {
    id: messageId,
    content: {
      format: 2,
      parts: [
        {
          type: 'text',
          text: message,
        },
      ],
      content: message,
    },
    role: 'user',
    createdAt: new Date(),
    threadId: chatId,
    resourceId: uuid(),
  };

  return baseMessage;
}

export function messageToStateEvent(message: MessageResponse): ChatStateEventByType<'message'> {
  return {
    type: 'message',
    value: message as unknown as ChatMessageEvent,
  };
}

function reasoningPart(reasoningText: string): {
  type: 'reasoning';
  reasoning: string;
  details: Array<{ type: 'text'; text: string }>;
} {
  return {
    type: 'reasoning',
    reasoning: reasoningText,
    details: reasoningText ? [{ type: 'text', text: reasoningText }] : [],
  };
}

export function createReasoningMessage(
  event: AgUiReasoningEvent,
  reasoningMessageBuffer = ''
): MessageResponse {
  const reasoningMessage: MessageResponse = {
    id: event.messageId ?? uuid(),
    role: 'reasoning',
    content: {
      format: 2,
      parts: [],
      content: '',
    },
    createdAt: new Date(),
    threadId: '',
    resourceId: uuid(),
  };

  switch (event.type) {
    case EventType.REASONING_MESSAGE_START:
      return {
        ...reasoningMessage,
        id: event.messageId ?? reasoningMessage.id,
      };
    case EventType.REASONING_MESSAGE_CONTENT: {
      const fullContent = reasoningMessageBuffer + event.delta;
      return {
        ...reasoningMessage,
        id: event.messageId ?? reasoningMessage.id,
        content: {
          format: 2,
          parts: [reasoningPart(fullContent)],
          content: fullContent,
        },
      };
    }
    case EventType.REASONING_MESSAGE_END:
      return {
        ...reasoningMessage,
        id: event.messageId ?? reasoningMessage.id,
      };

    case EventType.REASONING_MESSAGE_CHUNK: {
      return {
        ...reasoningMessage,
        id: event.messageId ?? '',
        content: {
          format: 2,
          parts: event.delta ? [reasoningPart(event.delta)] : [],
          content: event.delta,
        },
      };
    }
    default:
      return reasoningMessage;
  }
}
