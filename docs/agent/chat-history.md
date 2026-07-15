# Multi-turn chat history

Agent applications support multi-turn conversation context across all frameworks (LangGraph, CrewAI, LlamaIndex, NAT, and Base). When prior messages are included in a request, `datarobot-genai` injects them into the agent so later turns can reference earlier exchanges.

| Section | Description |
|---|---|
| [How history reaches the agent](#how-history-reaches-the-agent) | Request shape and backend behavior. |
| [Injection modes](#injection-modes) | Text summary vs structured replay. |
| [Framework behavior](#framework-behavior) | Per-framework opt-in and defaults. |
| [Prompt placeholder pattern](#prompt-placeholder-pattern) | Optional `{chat_history}` text-summary placement (CrewAI, NAT). |
| [Configuration](#configuration) | `max_history_messages` and `structured_history`. |
| [Testing locally](#testing-locally) | CLI and evaluation examples. |
| [Chat history vs agent memory](#chat-history-vs-agent-memory) | How this differs from persistent memory. |

## How history reaches the agent

Requests use the AG-UI [`RunAgentInput`](https://docs.ag-ui.com/) shape. Prior turns are carried in the `messages` array (role/content pairs). The current user turn is the last user message; earlier user and assistant messages are treated as history.

| Source | Behavior |
|---|---|
| Starter UI (`dr run dev`) | The FastAPI backend persists each turn, then rebuilds the full stored conversation into `RunAgentInput.messages` before forwarding to the agent. See [Multi-turn chat history](../fastapi_server/README.md#multi-turn-chat-history). |
| Agent CLI | Pass prior messages with `--file` (completion JSON) or embed them in the payload accepted by `nat dragent run` / `nat dragent query`. |
| Direct API / evaluation | Build a `RunAgentInput` with a `messages` list (see [Local evaluation](./evaluation.md)). |

The agent does not load chat history from a database itself. History must be present on the inbound request (or supplied by the backend wrapper, as in this template).

## Injection modes

`datarobot-genai` supports two ways to pass prior turns to the model:

### Text summary (`{chat_history}` placeholder)

When a prompt or template declares a `{chat_history}` variable, prior turns are formatted as a plain-text block (for example, `Prior conversation:\nUser: …\nAssistant: …`) and substituted into that placeholder. CrewAI and NAT templates can opt in to this mode; LangGraph templates in this repo omit the placeholder by default.

### Structured history (native messages)

When no `{chat_history}` placeholder is declared (or when structured replay is enabled explicitly), prior turns&mdash;including tool calls and assistant reasoning folded into answers&mdash;are replayed as native framework messages (`HumanMessage` / `AIMessage` / `ToolMessage` for LangGraph, `ChatMessage` for LlamaIndex, and so on).

Structured replay preserves tool-call structure across turns and is the default for LlamaIndex and LangGraph templates that omit `{chat_history}`.

## Framework behavior

Chat history is optional at runtime (single-turn requests work without prior messages). Templates either omit `{chat_history}` and rely on structured replay (LangGraph, LlamaIndex defaults) or declare the placeholder for text-summary injection (CrewAI, NAT opt-in).

| Framework | Default in this template | Opt-in / opt-out |
|---|---|---|
| [LangGraph](./frameworks/langgraph.md) | Structured history (no placeholder in `prompt_template`) | Add `{chat_history}` to the template for text summary instead. |
| [CrewAI](./frameworks/crewai.md) | Opt-in text only | Include `"chat_history"` in `kickoff_inputs` and `{chat_history}` in agent/task text. Omit the key to disable. |
| [LlamaIndex](./frameworks/llamaindex.md) | Structured history (no placeholder) | Add `{chat_history}` to prompts for text summary, or pass `structured_history=False` to disable replay. |
| [NAT](./frameworks/nat.md) | Passed through DRAgent to underlying LLM calls | Add `{chat_history}` at the end of `system_prompt` fields in `workflow.yaml` for text summary. |
| [Base](./frameworks/base.md) | Manual | Build the message list yourself from `run_agent_input.messages`. |

See the linked framework guides for code examples.

## Prompt placeholder pattern

LangGraph and LlamaIndex templates in this repo use structured history by default&mdash;no `{chat_history}` placeholder is required. For text-summary injection, declare `{chat_history}` as a self-contained section at the end of a system prompt or template message&mdash;not embedded mid-sentence. When history is empty, the placeholder resolves to an empty string; when history exists, the injected block is a multi-line `Prior conversation:` section.

LangGraph (structured history default; no placeholder):

```python
prompt_template = ChatPromptTemplate.from_messages([
    (
        "system",
        "You are a helpful assistant that plans and writes content based on the user's topic.",
    ),
    ("user", "The topic is {topic}."),
])
```

CrewAI `backstory` / task `description`, NAT `system_prompt` (text-summary opt-in):

```yaml
system_prompt: |
  You are a content planner for the topic {topic}.

  {chat_history}
```

Avoid patterns such as `Chat history is provided via {chat_history} (it may be empty).`&mdash;injecting a multi-line history block mid-sentence produces malformed prompts.

## Configuration

History replay is bounded and can be tuned when constructing `MyAgent` in `register.py`:

| Parameter | Default | Description |
|---|---|---|
| `max_history_messages` | `20` | Maximum number of prior messages to include. |
| `structured_history` | Framework-dependent | Set `structured_history=False` on `MyAgent(...)` to disable structured replay. |

```python
agent = MyAgent(llm=llm, structured_history=False, max_history_messages=10)
```

## Testing locally

### Multi-turn via CLI

Save a completion payload that includes prior `messages`, then run:

```sh
task agent:cli -- execute --file /path/to/chat-history-completion.json
```

Example payload (LangGraph topic prompt):

```json
{
  "messages": [
    {"role": "user", "content": "{\"topic\": \"Generative AI\"}"},
    {"role": "assistant", "content": "Generative AI refers to models that create new content..."},
    {"role": "user", "content": "{\"topic\": \"Summarize what we discussed so far\"}"}
  ],
  "stream": false
}
```

For deployed agents:

```sh
task agent:cli -- execute-deployment --file /path/to/chat-history-completion.json --deployment_id DEPLOYMENT_ID
```

The agent component ships a reference template as `example-chat-history-completion.json` in the [af-component-agent](https://github.com/datarobot-community/af-component-agent) examples directory.

### Multi-turn in tests

Build a `RunAgentInput` with prior turns in `messages` (see [Local evaluation](./evaluation.md#invoking-the-agent-in-tests)):

```python
from ag_ui.core import Message

from tests.eval_helpers import invoke_agent_text, make_run_input

run_input = make_run_input(
    Message(role="user", content='{"topic": "AI safety"}'),
    Message(role="assistant", content="AI safety covers alignment, robustness, and governance."),
    Message(role="user", content='{"topic": "Elaborate on the first point"}'),
)
response_text = await invoke_agent_text(run_input)
```

### Multi-turn in the starter UI

With `dr run dev`, open [http://localhost:5173](http://localhost:5173), send several messages in the same chat, and confirm the agent refers to earlier turns. No extra agent code is required when the template uses structured history defaults or declares `{chat_history}` for text summary.

## Chat history vs agent memory

| | Chat history | [Agent memory](./agent-memory.md) |
|---|---|---|
| Scope | Current conversation (recent turns) | Persistent facts across conversations |
| Storage | FastAPI DB / Memory Space (`USE_APPLICATION_MEMORY_SPACE`) | `dr_mem0_memory` / Mem0 / DataRobot Memory Service |
| Injection | Automatic from `RunAgentInput.messages` | Retrieved before each turn by `streaming_memory_agent` |
| Agent code | Structured history by default; optional `{chat_history}` for text summary | Configured in `workflow.yaml`; no `myagent.py` changes |

Use chat history for within-thread context ("what did I ask two messages ago?"). Use agent memory for long-term user facts ("remember my preferred tone" across sessions).
