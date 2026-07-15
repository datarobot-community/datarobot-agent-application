# AG-UI (Agent-User Interaction Protocol)

[AG-UI](https://docs.ag-ui.com/introduction) is an open, lightweight, event-based protocol that standardizes how AI agents connect to user-facing applications. It is the primary streaming interface used by all agent frameworks in this template.

AG-UI defines a set of event types that agents emit during execution, enabling the frontend and backend to render real-time progress, tool calls, reasoning steps, and final output. For the full protocol specification, see the [AG-UI documentation](https://docs.ag-ui.com/introduction). For details on the event model, see [AG-UI events](https://docs.ag-ui.com/concepts/events).

All `MyAgent.invoke()` implementations yield `(event, pipeline_interactions, usage_metrics)` tuples, where `event` is an AG-UI event object from the `ag_ui.core` module.

Framework support varies by event category:

| Event category | NAT | CrewAI | LlamaIndex | LangGraph |
|---|---|---|---|---|
| Lifecycle events | + | + | + | + |
| Text message events | + | + | + | + |
| Tool events | + | - | + | + |
| State management events | - | - | - | - |
| Reasoning events | + | - | - | - |

## Event types

### Lifecycle events

Control the start and end of an agent run.

| Event | Description |
|---|---|
| `RunStartedEvent` | Emitted once at the beginning of agent execution. |
| `RunFinishedEvent` | Emitted once when the agent has completed execution. |

```python
yield (RunStartedEvent(type=EventType.RUN_STARTED, thread_id=thread_id, run_id=run_id), None, usage_metrics)
# ... agent work ...
yield (RunFinishedEvent(type=EventType.RUN_FINISHED, thread_id=thread_id, run_id=run_id), pipeline_interactions, usage_metrics)
```

### Text message events

Stream text output incrementally as the agent generates it.

| Event | Description |
|---|---|
| `TextMessageStartEvent` | Marks the beginning of a new text message. |
| `TextMessageContentEvent` | Carries a chunk of text content (`delta`). Emitted multiple times as tokens arrive. |
| `TextMessageEndEvent` | Marks the end of the current text message. |

```python
yield (TextMessageStartEvent(type=EventType.TEXT_MESSAGE_START, message_id=msg_id, role="assistant"), None, usage_metrics)
yield (TextMessageContentEvent(type=EventType.TEXT_MESSAGE_CONTENT, message_id=msg_id, delta="Hello "), None, usage_metrics)
yield (TextMessageContentEvent(type=EventType.TEXT_MESSAGE_CONTENT, message_id=msg_id, delta="world!"), None, usage_metrics)
yield (TextMessageEndEvent(type=EventType.TEXT_MESSAGE_END, message_id=msg_id), None, usage_metrics)
```

### Tool events

Report tool invocations and their results during agent execution.

| Event | Description |
|---|---|
| `ToolCallStartEvent` | Emitted when the agent begins calling a tool. Includes tool name and arguments. |
| `ToolCallEndEvent` | Emitted when the tool call completes. Includes the tool's result. |

### State management events

Communicate changes to shared agent state (e.g. for collaborative multi-agent workflows).

| Event | Description |
|---|---|
| `StateSnapshotEvent` | Emits a full snapshot of the current agent state. |
| `StateDeltaEvent` | Emits an incremental update to the agent state. |

### Reasoning events

Expose the agent's internal reasoning or chain-of-thought steps.

| Event | Description |
|---|---|
| `StepStartedEvent` | Marks the beginning of a reasoning or planning step. |
| `StepFinishedEvent` | Marks the completion of a reasoning or planning step. |

## Framework support matrix

Not all event types are supported by every framework. The following table shows the current state of AG-UI integration:

| Event category | NAT | CrewAI | LlamaIndex | LangGraph |
|---|---|---|---|---|
| Lifecycle events | + | + | + | + |
| Text message events | + | + | + | + |
| Tool events | + | - | + | + |
| State management events | - | - | - | - |
| Reasoning events | + | - | - | - |

Legend: `+` supported, `-` not yet implemented.

- Lifecycle and text message events are supported across all frameworks&mdash;every agent emits `RunStarted`/`RunFinished` and streams text via `TextMessageContent` events.
- Tool events are supported in NAT, LlamaIndex, and LangGraph. CrewAI does not yet emit tool call events.
- State management events are not implemented in any framework.
- Reasoning events are only supported in NAT, which exposes internal planning and reasoning steps.

## Using AG-UI in the Base agent

The Base agent gives you full manual control over AG-UI events. You yield each event explicitly in your `invoke()` method, which means you can emit any event type regardless of framework support:

```python
class MyAgent(BaseAgent[None]):
    async def invoke(self, run_agent_input: RunAgentInput) -> InvokeReturn:
        user_prompt = extract_user_prompt_content(run_agent_input)
        thread_id = run_agent_input.thread_id
        run_id = run_agent_input.run_id
        message_id = str(uuid.uuid4())

        yield (RunStartedEvent(type=EventType.RUN_STARTED, thread_id=thread_id, run_id=run_id), None, usage_metrics)
        yield (TextMessageStartEvent(type=EventType.TEXT_MESSAGE_START, message_id=message_id, role="assistant"), None, usage_metrics)
        yield (TextMessageContentEvent(type=EventType.TEXT_MESSAGE_CONTENT, message_id=message_id, delta="Response text"), None, usage_metrics)
        yield (TextMessageEndEvent(type=EventType.TEXT_MESSAGE_END, message_id=message_id), None, usage_metrics)
        yield (RunFinishedEvent(type=EventType.RUN_FINISHED, thread_id=thread_id, run_id=run_id), pipeline_interactions, usage_metrics)
```

## Using AG-UI with framework agents

For LangGraph, CrewAI, LlamaIndex, and NAT agents, AG-UI event emission is handled automatically by the `datarobot_genai` framework adapters. The factory helpers (`datarobot_agent_class_from_langgraph`, etc.) wrap the native framework execution into an AG-UI event stream. You do not need to yield AG-UI events manually — the adapter translates framework-native events (e.g. LangGraph node outputs, CrewAI task completions) into the appropriate AG-UI events.
