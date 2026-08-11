# Chat history

Agent applications support **multi-turn chat history** across all frameworks (LangGraph, CrewAI, LlamaIndex, and NAT). When a request includes prior user and assistant messages, `datarobot-genai` extracts them from the AG-UI `RunAgentInput` and injects them into the agent as conversation context so the model can reference earlier turns.

This is **session chat history**&mdash;the messages you send in the current request. It is separate from [persistent agent memory](./agent-memory.md), which recalls facts across conversations for the same user.

| Section | Description |
|---|---|
| [How it works](#how-it-works) | Request shape and automatic injection. |
| [Framework behavior](#framework-behavior) | How each framework receives prior turns. |
| [Template opt-in](#template-opt-in) | `{chat_history}` and `kickoff_inputs` for CrewAI. |
| [Configuration](#configuration) | `max_history_messages` and `structured_history`. |
| [Testing locally](#testing-locally) | Dev server and multi-turn payloads. |
| [Further reading](#further-reading) | Related implementation PRs. |

## How it works

DRAgent agents receive input as [AG-UI](https://docs.ag-ui.com/introduction) `RunAgentInput` objects. The `messages` field carries the conversation transcript. `datarobot-genai` reads prior turns from `messages` (everything before the final user message) and makes them available to your agent:

1. **Extract**&mdash;`extract_history_messages()` normalizes prior turns (including tool calls and reasoning when present) and truncates to `max_history_messages` (default `20`).
2. **Inject**&mdash;each framework adapter either replays structured native messages to the model or fills a `{chat_history}` text placeholder in your prompts.

Deployed agents and HTTP clients that use the OpenAI-style chat-completions shape send the same information: a `messages` array whose last entry is the current user turn. Earlier `user`, `assistant`, `tool`, and `system` entries become history.

Example multi-turn `messages` array (chat-completions style):

```json
{
  "messages": [
    { "role": "user", "content": "Artificial Intelligence" },
    {
      "role": "assistant",
      "content": "Artificial Intelligence (AI) is the simulation of human intelligence by machines."
    },
    { "role": "user", "content": "Which topic did I ask about before?" }
  ]
}
```

The agent can answer the follow-up because the first user turn and assistant reply are injected as context.

## Framework behavior

| Framework | Default in this template | How prior turns reach the model |
|---|---|---|
| **LangGraph** | Structured history | Prior turns replay as native `HumanMessage` / `AIMessage` / `ToolMessage` objects before the current turn. The prompt template uses `{topic}` only&mdash;no `{chat_history}` placeholder. |
| **LlamaIndex** | Structured history | Prior turns pass to `AgentWorkflow.run()` as native `ChatMessage` history (tool calls preserved). System prompts do not declare `{chat_history}`. |
| **CrewAI** | Text summary via `{chat_history}` | The template includes `"chat_history": ""` in `kickoff_inputs` and `{chat_history}` at the end of task descriptions. The base class fills it with a plain-text `Prior conversation:\n...` block when history exists. |
| **NAT** | Message list on the orchestrator | Prior messages in the request are passed through to the `per_user_tool_calling_agent` orchestrator as conversation context. No YAML placeholder is required. |
| **Base** | Manual | Implement history yourself in `invoke()` using `run_agent_input.messages` or `history_messages()`. |

### Structured history vs text summary

**Structured history** (LangGraph and LlamaIndex defaults)&mdash;prior turns are replayed as role-tagged messages with tool metadata intact. This preserves tool-call sequences across turns.

**Text summary** (CrewAI default in this template)&mdash;prior turns flatten to a transcript such as `user: ...\nassistant: ...`. CrewAI's `Crew.kickoff()` accepts only string variables, so this is the supported pattern for CrewAI agents.

You can switch LangGraph or LlamaIndex to a text summary by adding `{chat_history}` to your prompt (LangGraph `ChatPromptTemplate` or LlamaIndex user message). You can disable structured replay with `structured_history=False` on `MyAgent(...)`.

## Template opt-in

Chat history injection is **automatic when the client sends prior turns in `messages`**:

- **LangGraph / LlamaIndex**&mdash;structured replay is on by default when the prompt has no `{chat_history}` variable.
- **CrewAI**&mdash;include `"chat_history": ""` in `kickoff_inputs` and place `{chat_history}` at the **end** of a task `description` or agent `backstory` as a self-contained section. On the first turn the value stays empty; when history exists the base class replaces it with a `Prior conversation:` block.
- **NAT**&mdash;no template change; send prior messages in the request.

To **disable** history for a framework agent, omit the `{chat_history}` key from CrewAI `kickoff_inputs`, set `structured_history=False` on LangGraph/LlamaIndex `MyAgent`, or set `max_history_messages=0`.

## Configuration

Pass these kwargs when constructing `MyAgent` in `register.py` (or override on the class):

| Parameter | Default | Description |
|---|---|---|
| `max_history_messages` | `20` (or `DATAROBOT_GENAI_MAX_HISTORY_MESSAGES`) | Maximum prior messages to include. Set to `0` to disable history. |
| `structured_history` | `True` (LangGraph, LlamaIndex) | When `True` and the prompt has no `{chat_history}`, replay native messages. When `False`, only the current turn is sent unless you use `{chat_history}`. |

```python
agent = MyAgent(llm=llm, structured_history=False, max_history_messages=10)
```

## Testing locally

`task agent:cli -- execute --user_prompt "..."` sends a **single-turn** prompt. To exercise multi-turn history, start the dev server and POST a full AG-UI payload to the streaming endpoint:

```sh
dr run agent:dev
```

In another terminal:

```sh
curl -sN -X POST "http://localhost:8842/generate/stream" \
  -H "Content-Type: application/json" \
  -d '{
    "threadId": "test-thread",
    "runId": "test-run",
    "messages": [
      {"id": "1", "role": "user", "content": "{\"topic\": \"Generative AI\"}"},
      {"id": "2", "role": "assistant", "content": "Generative AI creates new content from learned patterns."},
      {"id": "3", "role": "user", "content": "{\"topic\": \"What topic did we discuss?\"}"}
    ],
    "tools": [],
    "context": [],
    "forwardedProps": {},
    "state": {}
  }'
```

Parse the `data:` lines in the response for AG-UI text events. For deployed agents, send the same `messages` array through the deployment chat-completions or `/generate/stream` API.

## Chat history vs agent memory

| | Chat history | [Agent memory](./agent-memory.md) |
|---|---|---|
| **Scope** | Messages in the current request | Facts stored across sessions per user |
| **Configuration** | Built into `datarobot-genai` adapters | `use_agent_memory` at project generation + `workflow.yaml` |
| **Use when** | The client sends the full or partial transcript | The agent should recall durable facts without the client resending them |

Both can be enabled together: the client supplies recent turns as chat history while `streaming_memory_agent` retrieves long-term memories for the same user.

## Further reading

| Resource | Description |
|---|---|
| [datarobot-genai#163](https://github.com/datarobot-oss/datarobot-genai/pull/163) | Core chat history extraction and framework adapters. |
| [af-component-agent#392](https://github.com/datarobot-community/af-component-agent/pull/392) | Template integration for all frameworks. |
| [af-component-agent#412](https://github.com/datarobot-community/af-component-agent/pull/412) | Chat-completions example with prior `messages`. |
| [LangGraph agent](./frameworks/langgraph.md#chat-history) | Structured history and prompt templates. |
| [CrewAI agent](./frameworks/crewai.md#chat-history) | `{chat_history}` and `kickoff_inputs`. |
| [LlamaIndex agent](./frameworks/llamaindex.md#chat-history) | Structured `ChatMessage` replay. |
| [NAT agent](./frameworks/nat.md#chat-history) | YAML orchestrator and request messages. |
