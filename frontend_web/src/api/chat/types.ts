import {
  type ContentPart,
  type ToolInvocationUIPart,
  type ToolInvocationData,
} from '@/components/block/chat/types';
export interface ChatListItem {
  id: string;
  userId: string;
  name?: string;
  createdAt: Date;
  updatedAt: Date | null;
  metadata?: Record<string, unknown>;
  initialised?: boolean;
}

type JSONValue =
  | null
  | string
  | number
  | boolean
  | {
      [value: string]: JSONValue;
    }
  | Array<JSONValue>;

export type MessageResponse = {
  id: string;
  role: 'user' | 'assistant' | 'system' | 'reasoning';
  createdAt: Date;
  threadId?: string;
  resourceId?: string;
  type?: string;
  content: MessageContent;
  encryptedValue?: string;
  metadata?: Record<string, unknown>;
};

export type MessageContent = {
  format: number;
  parts: ContentPart[];
  content?: string;
  toolInvocations?: ToolInvocation[];
  reasoning?: string;
  annotations?: JSONValue[] | undefined;
  metadata?: Record<string, unknown>;
};

export type APIChat = {
  name: string;
  thread_id: string;
  user_uuid: string;
  created_at: string;
  update_time: string;
  metadata?: Record<string, unknown>;
};

export type APIToolCall = {
  id: string;
  type: 'function';
  function: {
    name: string;
    arguments: string;
  };
  encryptedValue: string | null;
};

export type MessageHistoryResponse = {
  id: string;
  role: 'user' | 'assistant' | 'tool' | 'system' | 'developer' | 'reasoning' | 'activity';
  content: string | null;
  name: string | null;
  encryptedValue: string | null;
  inProgress: boolean;
  error: string | null;
  toolCalls: APIToolCall[] | null;
  timestamp?: number;
};

export type APIChatWithMessages = APIChat & {
  messages: MessageHistoryResponse[];
};

// --- ToolResult (copied from @ai-sdk) ---

/**
 * Typed tool result that is returned by `generateText` and `streamText`.
 * It contains the tool call ID, the tool name, the tool arguments, and the tool result.
 */
export interface ToolResult<NAME extends string, INPUT, OUTPUT> {
  /**
   * ID of the tool call. This ID is used to match the tool call with the tool result.
   */
  toolCallId: string;
  /**
   * Name of the tool that was called.
   */
  toolName: NAME;
  /**
   * Arguments of the tool call. This is a JSON-serializable object that matches the tool's input schema.
   */
  input: INPUT;
  /**
   * Result of the tool call. This is the result of the tool's execution.
   */
  output: OUTPUT;
  /**
   * Whether the tool result has been executed by the provider.
   */
  providerExecuted?: boolean;
  /**
   * Whether the tool is dynamic.
   */
  dynamic?: boolean;
}

export type ToolInvocation =
  | ({
      state: 'partial-call';
      step?: number;
    } & ToolCall<string, Record<string, unknown>>)
  | ({
      state: 'call';
      step?: number;
    } & ToolCall<string, Record<string, unknown>>)
  | ({
      state: 'result';
      step?: number;
    } & ToolResult<string, Record<string, unknown>, Record<string, unknown>>);

interface ToolCall<NAME extends string, INPUT> {
  toolCallId: string;
  toolName: NAME;
  input: INPUT;
  providerExecuted?: boolean;
  dynamic?: boolean;
}

export type ChatResponse = {
  id: string;
  title?: string;
  resourceId?: string;
  userId?: string;
  createdAt: Date;
  updatedAt: Date | null;
  metadata?: Record<string, unknown>;
  initialised?: boolean;
};

export type { ContentPart, ToolInvocationUIPart, ToolInvocationData };
