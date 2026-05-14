# Agent-to-Agent (A2A)

Template agents can expose themselves as A2A servers and connect to remote agents via the agent-to-agent protocol. For authentication configuration, see [A2A Authentication](./agent2agent-auth.md).

To expose an agent via A2A:

- Ensure the template has a `general.front_end.a2a` configuration block. Templates include this by default.
- Run the agent with the experimental DRAgent front server: set `ENABLE_DRAGENT_SERVER=true` in your `.env` file.

To connect an agent to a remote agent via A2A:

- Uncomment the `function_groups` and `workflow.tool_names` blocks in `workflow.yaml`.
- Run the agent with the experimental DRAgent front server: set `ENABLE_DRAGENT_SERVER=true` in your `.env` file.

Enable the **ENABLE_RUNTIME_PARAMETERS_IMPROVEMENTS** feature flag in DataRobot to use environment variables in `workflow.yaml` files.

### Agent cards and DataRobot deployments

When the `ENABLE_GENAI_AGENT_TO_AGENT_SUPPORT` feature flag is enabled and you deploy an agent that exposes A2A server endpoints, the agent card is stored in DataRobot during deployment. Use the following endpoints:

- **List deployments with agent cards**&mdash;`GET deployments/?isA2AAgent=true`.
- **Retrieve an agent card**&mdash;`GET deployments/DEPLOYMENT_ID/agentCard`.

## Agent card identity: `external`

Optional fields under `general.front_end.a2a.external` publish additional identity metadata on the agent card and allow overriding the auto-generated agent card URL.

| Field | Purpose |
|-------|---------|
| `external.id` | Catalog discovery identifier. Emitted as the `urn:datarobot:agent:identity:external` extension on the agent card. |
| `external.url` | Overrides the auto-generated agent card endpoint URL. |

```yaml
general:
  front_end:
    a2a:
      external:
        id: "my-agent-id"
        url: "https://my-agent-id.example.com/a2a/"
```

## A2A agents hosted outside of DataRobot

For A2A agents hosted outside of DataRobot:

1. Create an external model with the "Agentic Workflow" target type and the default configuration.
2. Deploy the external model.
3. Push the agent card via `PUT deployments/DEPLOYMENT_ID/agentCard`.

For external deployments, you can also remove the agent card with `DELETE deployments/DEPLOYMENT_ID/agentCard`.

```python
deployments = dr.Deployment.list(filters=DeploymentListFilters(is_a2a_agent=True))
agent_card = deployment.get_agent_card()
# Only available for external deployments.
deployment.upload_agent_card(agent_card)
deployment.delete_agent_card()
```
