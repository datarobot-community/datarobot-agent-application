# Dynamic tool registration

Dynamic tool registration lets the MCP server discover DataRobot deployments and expose them as MCP tools automatically. When a tool is invoked, the server proxies the request to the registered deployment.

## Quick start

1. Deploy your model or service to DataRobot.
2. Tag the deployment with `tool` as both the tag name and the tag value.
3. Start the server with dynamic tool registration enabled, if needed.

*Enable auto-discovery on startup (optional):*

```bash
MCP_SERVER_REGISTER_DYNAMIC_TOOLS_ON_STARTUP=true
```

For most deployment types, no additional configuration is needed.

## Supported deployment types

| Deployment type | Configuration needed |
|---|---|
| DataRobot native predictive models | None. Tag the deployment as `tool`. |
| DRUM structured predictions | None. Optionally define `inputSchema` in `model-metadata.yaml`. |
| DRUM agentic workflows | None. Optionally define `inputSchema` in `model-metadata.yaml`. |
| DRUM unstructured models | Define `inputSchema` in `model-metadata.yaml`. |
| Custom servers, such as FastAPI services | Expose an `/info/` endpoint with tool metadata. |

Registering other MCP servers as tools through dynamic tool registration is not supported.

## Registration requirements

All deployments must:

- be active
- be tagged with `tool` as both the name and value

Additional requirements depend on the deployment type:

- DataRobot native models: no extra requirements
- DRUM unstructured models: define `inputSchema` in `model-metadata.yaml`
- custom servers: expose `/info/` and return `endpoint`, `method`, and `input_schema`

### Runtime API

Use these endpoints to manage registrations at runtime:

- `GET /registeredDeployments/` to list registered tools
- `PUT /registeredDeployments/{deployment_id}` to register a tool
- `DELETE /registeredDeployments/{deployment_id}` to remove a tool

## DRUM deployments

[DataRobot DRUM](https://pypi.org/project/datarobot-drum/) deployments usually work with little or no additional configuration.

### Zero configuration (for most cases)

For these deployment types, tag the deployment as `tool` and the server can register it automatically:

- structured predictions, including binary, regression, and multiclass models
- agentic workflows
- DataRobot native predictive models

### Unstructured models

For an `unstructured` target type, add `inputSchema` to `model-metadata.yaml`:

```yaml
name: "Fetch dataset"
description: "Fetches a dataset from DataRobot Data Registry"
type: inference
targetType: unstructured
inputSchema:
  type: object
  properties:
    json:
      type: object
      properties:
        dataset_id:
          type: string
          description: Dataset ID from Data Registry
        limit:
          type: integer
          default: 100
      required:
        - dataset_id
```

*Notes:*

- For unstructured models, define request parameters under the `json` property.
- Exposing input schemas from `model-metadata.yaml` requires `datarobot-drum` version `1.17.2` or later.

### Optional custom schema

You can override fallback schemas to give the LLM better guidance or tighter control over the request shape:

```yaml
inputSchema:
  type: object
  properties:
    data:
      type: string
      description: "CSV with columns: transaction_amount, user_age, merchant_category"
  required:
    - data
```

## Custom server deployments

For FastAPI, Flask, and similar services, expose an `/info/` endpoint that returns tool metadata.

### Required `/info/` response

```json
{
  "endpoint": "/weather/{city}",
  "method": "GET",
  "input_schema": {
    "type": "object",
    "properties": {}
  }
}
```

### FastAPI example

```python
from fastapi import FastAPI
from pydantic import BaseModel, Field

app = FastAPI()


class WeatherRequest(BaseModel):
    class PathParams(BaseModel):
        city: str = Field(description="City name")

    class QueryParams(BaseModel):
        units: str = Field(default="metric", description="metric or imperial")

    path_params: PathParams
    query_params: QueryParams | None = None


@app.get("/info/")
async def metadata():
    return {
        # Custom model deployments expose custom server routes behind directAccess/.
        "endpoint": "directAccess/weather/{city}",
        "method": "GET",
        "input_schema": WeatherRequest.model_json_schema(),
    }


@app.get("/weather/{city}")
async def get_weather(city: str, units: str = "metric"):
    return {"city": city, "temp": 22, "units": units}
```

### Request mapping

Given this tool call:

```json
{
  "path_params": {"city": "paris"},
  "query_params": {"units": "imperial"}
}
```

the MCP server generates a request like:

```text
GET <base_url>/directAccess/weather/paris?units=imperial
```

Where:

- `base_url` is derived from the DataRobot deployment URL
- `directAccess/` is the prefix used for custom server endpoints in custom model deployments

## Input schema reference

### Parameter groups

Parameters map to HTTP requests as follows:

| Group | Purpose | Example |
|---|---|---|
| `path_params` | Substitutes values into the URL path | `{city}` -> `"paris"` |
| `query_params` | Adds query-string parameters | `?units=imperial` |
| `data` | Sends a raw request body, such as CSV | Not used in the weather example |
| `json` | Sends a JSON request body | Not used in the weather example |

### Rules

- `path_params` and `query_params` must be flat objects
- `data` and `json` can contain nested structures
- every `{param}` in the endpoint must be present in `path_params`
- empty schemas are allowed only when `MCP_SERVER_TOOL_REGISTRATION_ALLOW_EMPTY_SCHEMA=true`

### What the server does

Internally, the MCP server transforms tool calls into HTTP requests. For the weather example, the request looks like this:

```python
async with session.request(
    method="GET",
    url="<base_url>/directAccess/weather/paris",
    params={"units": "imperial"},
) as response:
    return await response.json()
```

## Troubleshooting

### Tool does not register

Use these commands to inspect the deployment and, for DRUM or custom servers, test the `/info/` endpoint:

```bash
# Check that the deployment is active and tagged correctly.
curl -H "Authorization: Bearer $DATAROBOT_API_TOKEN" \
  "$DATAROBOT_ENDPOINT/api/v2/deployments/{deployment-id}/" | jq .

# Check the /info/ endpoint for DRUM and custom server deployments.
curl -H "Authorization: Bearer $DATAROBOT_API_TOKEN" \
  "$DATAROBOT_ENDPOINT/api/v2/deployments/{deployment-id}/directAccess/info/" | jq .
```

### Common errors

| Error | Fix |
|---|---|
| Missing `input_schema` | Add `input_schema` to the `/info/` response for custom servers, or add `inputSchema` to `model-metadata.yaml` for DRUM unstructured models. |
| Unsupported top-level property | Use only `path_params`, `query_params`, `data`, and `json`. |
| Nested structure in `path_params` | Flatten the structure or move it to `json`. |
| Missing path parameter | Define every path variable from the endpoint in `path_params`. |
