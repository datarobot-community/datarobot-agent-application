# Base agent

The base agent is a minimal agent implementation that provides the scaffolding required by DataRobot without imposing a specific agentic framework. Use it as a starting point for full control over the agent logic, or to integrate a framework not covered by the other templates.

## `myagent.py`

Unlike the other frameworks, the base agent does not use a factory helper (`datarobot_agent_class_from_*`). Instead, `MyAgent` extends `BaseAgent` directly and implements `invoke()` as an async generator that yields `(event, pipeline_interactions, usage_metrics)` tuples:

```python
from datarobot_genai.core.agents import BaseAgent, extract_user_prompt_content

class MyAgent(BaseAgent[None]):
    async def invoke(self, run_agent_input: RunAgentInput) -> InvokeReturn:
        user_prompt_content = extract_user_prompt_content(run_agent_input)

        yield (RunStartedEvent(...), None, usage_metrics)
        yield (TextMessageStartEvent(...), None, usage_metrics)
        yield (TextMessageContentEvent(..., delta="streaming success"), None, usage_metrics)
        yield (TextMessageEndEvent(...), None, usage_metrics)
        yield (RunFinishedEvent(...), pipeline_interactions, usage_metrics)
```

The MCP tools context is a no-op by default since there is no framework-specific MCP adapter. Add one by implementing `mcp_tools_context` or wiring tools manually.

## `register.py`

The base agent registration has LLM and tool wiring commented out by default — uncomment to enable:

```python
class BaseAgentConfig(AgentBaseConfig, name="base_agent"):
    tool_names: list[FunctionGroupRef] = []


@register_per_user_function(
    config_type=BaseAgentConfig,
    input_type=RunAgentInput,
    streaming_output_type=DRAgentEventResponse,
)
async def base_agent(config: BaseAgentConfig, builder: Builder) -> AsyncGenerator[Any, None]:
    from agent.myagent import MyAgent, mcp_tools_context

    # Uncomment to get an LLM and tools from NAT.
    from nat.builder.framework_enum import LLMFrameworkEnum
    llm = await builder.get_llm(config.llm_name, wrapper_type=LLMFrameworkEnum.LANGCHAIN)
    workflow_tools = await builder.get_tools(config.tool_names, wrapper_type=LLMFrameworkEnum.LANGCHAIN)

    async def _response_fn(input_message: RunAgentInput) -> ...:
        forwarded_headers = extract_datarobot_headers_from_context()
        authorization_context = extract_authorization_from_context()
        mcp_config = MCPConfig(
            forwarded_headers=forwarded_headers,
            authorization_context=authorization_context,
        )
        async with mcp_tools_context(mcp_config) as mcp_tools:
            agent = MyAgent(
                verbose=config.verbose,
                forwarded_headers=forwarded_headers,
                tools=[mcp_tools+workflow_tools],
            )
            async for event, pipeline_interactions, usage_metrics in agent.invoke(input_message):
                yield DRAgentEventResponse(
                    events=[event],
                    usage_metrics=usage_metrics,
                    pipeline_interactions=pipeline_interactions,
                )

    yield FunctionInfo.from_fn(_response_fn, description=config.description)
```

## `workflow.yaml`

The `workflow.yaml` file configures the base agent's front end, LLM, and authentication settings:

```yaml
general:
  front_end:
    _type: dragent_fastapi
    step_adaptor:
      mode: "off"
    a2a:
      server:
        name: "Base Agent"
        description: "A custom base agent."
      skills:
        - id: base_agent
          name: "Base Agent"
          description: "Runs the base agent."

llms:
  datarobot_llm:
    _type: datarobot-llm-component

workflow:
  _type: base_agent
  llm_name: datarobot_llm
  description: Base agent example

authentication:
  datarobot_auth:
    _type: datarobot_api_key
```

## Prompt modification

The base agent has no built-in prompt system, providing full control over how prompts are constructed and sent to the LLM. Since `invoke()` is a raw async generator, messages are constructed manually and the LLM is called directly.

### Manual prompt construction

Unlike framework-based agents, the base agent does not use `make_system_prompt()`, `create_agent()`, or prompt templates. Build the messages list manually:

```python
from datarobot_genai.core.agents import BaseAgent, extract_user_prompt_content

class MyAgent(BaseAgent[None]):
    async def invoke(self, run_agent_input: RunAgentInput) -> InvokeReturn:
        user_prompt = extract_user_prompt_content(run_agent_input)

        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": str(user_prompt)},
        ]

        # Call the LLM directly.
        response = await self.llm.achat(messages)

        # Yield AG-UI events with the response.
        yield (RunStartedEvent(...), None, usage_metrics)
        yield (TextMessageStartEvent(...), None, usage_metrics)
        yield (TextMessageContentEvent(..., delta=response.content), None, usage_metrics)
        yield (TextMessageEndEvent(...), None, usage_metrics)
        yield (RunFinishedEvent(...), pipeline_interactions, usage_metrics)
```

### How to modify

Modify the base agent's prompt behavior in the following ways:

- **Change the system prompt** — edit the `"system"` message content in the messages list.
- **Add chat history** — use `self.history_messages(run_agent_input)` or `self.build_history_summary(run_agent_input)` from `BaseAgent`, or read `run_agent_input.messages` directly. See [Chat history](../chat-history.md).
- **Implement multi-step workflows** — make multiple LLM calls with different system prompts and aggregate the results.
- **Add structured output** — include format instructions in the system prompt (for example, "Respond in JSON with keys: title, summary").
- **Use `make_system_prompt()`** — optionally import it from `datarobot_genai.core.agents` for consistent formatting, even though it is not required.

### Tips

Keep the following guidance in mind when working with the base agent:

- The base agent is the most flexible but requires the most manual work.
- Use it for precise control over the message sequence, or when integrating an LLM client that doesn't fit the other frameworks.
- Consider migrating to a framework-based agent if the prompt logic grows complex enough to benefit from structured abstractions.

## When to use

Use the base agent in the following scenarios:

- Building a fully custom agent that doesn't fit any of the supported frameworks.
- Emitting AG-UI events manually for fine-grained control over streaming.
- Prototyping with the simplest possible starting point.

## Extending

Extend the base agent using the following steps:

1. Add an LLM — use `get_llm()` from `datarobot_genai.langgraph.llm` (or another provider) and call it inside `invoke()`.
2. Add tools — implement tool calls within `invoke()` using any preferred library.
3. Enable DRAgent tools — uncomment the `builder.get_llm()` and `builder.get_tools()` lines in `register.py` and add the appropriate `framework_wrappers`.
