'use client';
import { type CustomEvent } from '@ag-ui/core';
import type { AgentSubscriber as AgUiAgentSubscriber } from '@ag-ui/client';
import type { ChatState } from '@/components/block/chat/hooks/use-chats-state';
import * as z from 'zod/v4';
import type { ZodType } from 'zod/v4';
import type { ReactElement } from 'react';
import type { MessageResponse } from '@/api/chat/types';

// --- Message UI parts (from @ai-sdk shape; may change when history is finalized) ---

/**
 * A text part of a message.
 */
export type TextUIPart = {
  type: 'text';
  /**
   * The text content.
   */
  text: string;
};
/**
 * A reasoning part of a message.
 */
export type ReasoningUIPart = {
  type: 'reasoning';
  /**
   * The reasoning text.
   */
  reasoning: string;
  details: Array<
    | {
        type: 'text';
        text: string;
        signature?: string;
      }
    | {
        type: 'redacted';
        data: string;
      }
  >;
};

type ToolInvocationMetadata = {
  startTime?: number;
  endTime?: number;
} & Record<string, unknown>;

/**
 * A tool invocation part of a message.
 */
export interface ToolInvocationData {
  state: 'start' | 'call' | 'result';
  toolCallId: string;
  toolName: string;
  args?: Record<string, unknown>;
  result?: string;
  metadata?: ToolInvocationMetadata;
}
export type ToolInvocationUIPart = {
  type: 'tool-invocation';
  /**
   * The tool invocation.
   */
  toolInvocation: ToolInvocationData;
};
/**
 * A source part of a message.
 */
export type SourceUIPart = {
  type: 'source';
  /**
   * The source.
   */
  source: unknown;
};
/**
 * A file part of a message.
 */
export type FileUIPart = {
  type: 'file';
  mimeType: string;
  data: string;
};
/**
 * A step boundary part of a message.
 */
export type StepStartUIPart = {
  type: 'step-start';
};

export type ContentPart =
  | TextUIPart
  | ReasoningUIPart
  | ToolInvocationUIPart
  | SourceUIPart
  | FileUIPart
  | StepStartUIPart;

export type MessageContent = {
  format: number;
  parts: ContentPart[];
  content: string;
};

export function isToolInvocationPart(part: ContentPart): part is ToolInvocationUIPart {
  return part.type === 'tool-invocation';
}

// --- Tool definitions (Zod + optional UI render) ---

export const ToolStatus = {
  EXECUTING: 'executing',
  COMPLETE: 'complete',
} as const;

export interface ToolState<Shape extends Record<string, unknown>> {
  status: (typeof ToolStatus)[keyof typeof ToolStatus];
  args: Shape;
  callback?: (response: unknown) => void | unknown;
}

export interface Tool<Shape extends Record<string, unknown> = Record<string, unknown>> {
  /**
   * Unique name
   */
  name: string;
  /**
   * Describe the instrument, this will be passed to LLM
   */
  description: string;
  /**
   * Define a z.object(), import zod from 'zod/v4
   */
  parameters: ZodType<Shape>;
  /**
   * Handler for a UI action
   */
  handler?: (args: Shape) => void | Promise<void>;
  /**
   * Render custom UI component
   */
  render?: (state: ToolState<Shape>) => ReactElement;
  renderAndWait?: (state: ToolState<Shape>) => ReactElement;
  enabled?: boolean;
  /**
   * If true, this tool can run when the agent is in background mode
   */
  background?: boolean;
}

export interface ToolSerialized {
  name: string;
  description: string;
  parameters: z.core.JSONSchema.JSONSchema;
  enabled?: boolean;
  background?: boolean;
}

// --- Agent / chat events ---

export interface AgentEventContext {
  /** Reactive Zustand slice for the current chat — reflects state at call time */
  chatState: ChatState;
  /** Snapshot getter — safe to call inside async continuations without stale-closure risk */
  getCurrentChatState: () => ChatState | undefined;
  /** Suppress the default useAgUiChat handler. Idempotent, callable anywhere. */
  preventDefault(): void;
  readonly defaultPrevented: boolean;
}

type AgUiHandlerParams<F> = NonNullable<F> extends (params: infer P) => unknown ? P : never;

type HandledEvents =
  | 'onTextMessageStartEvent'
  | 'onTextMessageContentEvent'
  | 'onTextMessageEndEvent'
  | 'onReasoningStartEvent'
  | 'onReasoningMessageContentEvent'
  | 'onReasoningMessageEndEvent'
  | 'onReasoningEndEvent'
  | 'onToolCallStartEvent'
  | 'onToolCallEndEvent'
  | 'onToolCallResultEvent'
  | 'onStateSnapshotEvent'
  | 'onStateChanged'
  | 'onStepStartedEvent'
  | 'onStepFinishedEvent'
  | 'onRunFinishedEvent'
  | 'onCustomEvent'
  | 'onRunErrorEvent';

export type AgentSubscriber = {
  [K in HandledEvents]?: (
    params: AgUiHandlerParams<AgUiAgentSubscriber[K]>,
    ctx: AgentEventContext
  ) => void | Promise<void>;
};

export interface ProgressState {
  [actionName: string]: ProgressStep[];
}
export interface ProgressStep {
  id: string;
  name: string;
  done: boolean;
  error?: string;
}

export interface ProgressStartCustomEvent extends CustomEvent {
  name: 'progress-start';
  value: {
    id: string;
    steps: ProgressStep[];
  };
}

export interface ProgressDoneCustomEvent extends CustomEvent {
  name: 'progress-done';
  value: { id: string; step: number };
}

export interface ProgressErrorCustomEvent extends CustomEvent {
  name: 'progress-error';
  value: { id: string; step: number; message: string };
}

export function isProgressStart(event: CustomEvent): event is ProgressStartCustomEvent {
  return event.name === 'progress-start';
}

export function isProgressDone(event: CustomEvent): event is ProgressDoneCustomEvent {
  return event.name === 'progress-done';
}

export function isProgressError(event: CustomEvent): event is ProgressErrorCustomEvent {
  return event.name === 'progress-error';
}

// --- Chat state event types ---

export type ChatMessageEvent = MessageResponse;

export type ChatStepEvent = {
  id: string;
  threadId: string;
  createdAt: Date;
  name: string;
  isRunning: boolean;
};

export type ChatErrorEvent = {
  id: string;
  threadId: string;
  createdAt: Date;
  error: string;
  testId?: string;
};

export type ChatThinkingEvent = {
  id: string;
  threadId: string;
  createdAt: Date;
};

// --- ChatStateEvent discriminated union ---
export type ChatStateEventByType<T extends ChatStateEvent['type']> = Extract<
  ChatStateEvent,
  { type: T }
>;

export type ChatStateEvent =
  | {
      type: 'step';
      value: ChatStepEvent;
    }
  | {
      type: 'message';
      value: ChatMessageEvent;
    }
  | {
      type: 'error';
      value: ChatErrorEvent;
    }
  | {
      type: 'thinking';
      value: ChatThinkingEvent;
    };

// --- Type guards ---

export function isMessageStateEvent(
  event: ChatStateEvent
): event is ChatStateEventByType<'message'> {
  return event.type === 'message';
}

export function isErrorStateEvent(event: ChatStateEvent): event is ChatStateEventByType<'error'> {
  return event.type === 'error';
}

export function isStepStateEvent(event: ChatStateEvent): event is ChatStateEventByType<'step'> {
  return event.type === 'step';
}

export function isThinkingEvent(event: ChatStateEvent): event is ChatStateEventByType<'thinking'> {
  return event.type === 'thinking';
}

export type {
  ChatListItem,
  MessageResponse,
  APIChat,
  MessageHistoryResponse,
  APIChatWithMessages,
  ToolResult,
  ToolInvocation,
  ChatResponse,
} from '@/api/chat/types';
