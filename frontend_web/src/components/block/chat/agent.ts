'use client';
import { HttpAgent } from '@ag-ui/client';
import type { HttpAgentConfig } from '@ag-ui/client';
import type {
  BaseEvent,
  RunAgentInput,
  TextMessageContentEvent,
  TextMessageEndEvent,
  Message,
} from '@ag-ui/core';
import { EventType } from '@ag-ui/core';

import { AG_UI_ENDPOINT } from '@/constants/endpoints';

export interface BufferedHttpAgentConfig extends HttpAgentConfig {
  /** Number of TEXT_MESSAGE_CONTENT deltas to accumulate before flushing. Default: 5 */
  bufferSize?: number;
  /** Maximum milliseconds to wait before flushing a partial buffer. Default: 150 */
  maxBufferTime?: number;
}

interface ContentBuffer {
  deltas: string[];
  firstEvent: TextMessageContentEvent;
  timerId: ReturnType<typeof setTimeout> | null;
}

// Derive the Observable type directly from HttpAgent to avoid importing rxjs,
// which would create a pnpm dual-instance type conflict (rxjs@7.8.1 vs rxjs@7.8.2).
type AgentRunResult = ReturnType<HttpAgent['run']>;

export class BufferedHttpAgent extends HttpAgent {
  private readonly bufferSize: number;
  private readonly maxBufferTime: number;

  constructor({ bufferSize = 5, maxBufferTime = 150, ...config }: BufferedHttpAgentConfig) {
    super(config);
    this.bufferSize = bufferSize;
    this.maxBufferTime = maxBufferTime;
  }

  run(input: RunAgentInput): AgentRunResult {
    return this.applyContentBuffer(super.run(input));
  }

  private applyContentBuffer(source$: AgentRunResult): AgentRunResult {
    const { bufferSize, maxBufferTime } = this;

    // Instantiate via source$.constructor so the returned Observable belongs to the same
    // rxjs instance as @ag-ui/client, avoiding the pnpm dual-instance conflict at runtime.
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const ObservableCtor: new (fn: any) => AgentRunResult = (source$ as any).constructor;

    return new ObservableCtor(
      (observer: {
        next: (event: BaseEvent) => void;
        error: (err: unknown) => void;
        complete: () => void;
      }) => {
        const buffers = new Map<string, ContentBuffer>();

        function flushBuffer(messageId: string): void {
          const buf = buffers.get(messageId);
          if (!buf) return;
          buffers.delete(messageId);
          if (buf.timerId !== null) clearTimeout(buf.timerId);
          if (buf.deltas.length === 0) return;
          observer.next({
            ...buf.firstEvent,
            delta: buf.deltas.join(''),
            timestamp: Date.now(),
          } as TextMessageContentEvent);
        }

        function scheduleFlush(messageId: string, buf: ContentBuffer): void {
          if (buf.timerId !== null) clearTimeout(buf.timerId);
          buf.timerId = setTimeout(() => flushBuffer(messageId), maxBufferTime);
        }

        const subscription = source$.subscribe({
          next(event: BaseEvent) {
            if (event.type === EventType.TEXT_MESSAGE_CONTENT) {
              const ev = event as TextMessageContentEvent;
              let buf = buffers.get(ev.messageId);
              if (!buf) {
                buf = { deltas: [], firstEvent: ev, timerId: null };
                buffers.set(ev.messageId, buf);
                scheduleFlush(ev.messageId, buf);
              }
              buf.deltas.push(ev.delta);
              if (buf.deltas.length >= bufferSize) {
                flushBuffer(ev.messageId);
              }
            } else if (event.type === EventType.TEXT_MESSAGE_END) {
              const ev = event as TextMessageEndEvent;
              flushBuffer(ev.messageId);
              observer.next(event);
            } else {
              observer.next(event);
            }
          },
          error(err: unknown) {
            for (const messageId of [...buffers.keys()]) {
              flushBuffer(messageId);
            }
            observer.error(err);
          },
          complete() {
            for (const messageId of [...buffers.keys()]) {
              flushBuffer(messageId);
            }
            observer.complete();
          },
        });

        return () => {
          for (const buf of buffers.values()) {
            if (buf.timerId !== null) clearTimeout(buf.timerId);
          }
          subscription.unsubscribe();
        };
      }
    );
  }
}

export function createAgent({
  url = AG_UI_ENDPOINT,
  threadId,
  initialMessages = [],
  initialState = {},
  bufferSize,
  maxBufferTime,
}: {
  url?: string;
  threadId: string;
  initialMessages?: Message[];
  initialState?: Record<string, unknown>;
  bufferSize?: number;
  maxBufferTime?: number;
}) {
  return new BufferedHttpAgent({
    url,
    threadId,
    agentId: threadId,
    initialMessages,
    initialState,
    bufferSize,
    maxBufferTime,
  });
}
