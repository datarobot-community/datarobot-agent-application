# MCP Tools

49 tools live on the Global MCP server. Verified against the staging server (`beta-global-mcp.stg.ue1.aws.int.datarobot.com`).

**Auth:** Bearer JWT (short-lived OAuth token via nginx patch).

---

## DR Platform — Deployments, Models, Predictions

| Tool | Description |
|------|-------------|
| `list_deployments` | List all DR deployments for the authenticated user |
| `get_deployment_info` | Deployment health, features needed to make predictions |
| `get_deployment_features` | Features list for a deployment as JSON |
| `get_model_info_from_deployment` | Model info associated with a given deployment ID |
| `get_model_details` | Detailed model info with feature impact and ROC |
| `get_model_roc_curve` | ROC curve for a specific model |
| `get_model_feature_impact` | Feature impact for a specific model |
| `get_model_lift_chart` | Lift chart for a specific model |
| `get_prediction_history` | Recent prediction results from a deployment |
| `get_best_model` | Best model for a project, optionally by metric |
| `list_models` | All models in a project |
| `deploy_model` | Deploy a model — create a new DR deployment |
| `deploy_custom_model` | Deploy a custom inference model (.pkl) to DR MLOps |
| `predict_realtime` | Real-time predictions using a deployment + local CSV or dataset |
| `predict_by_file_path` | Predictions using a deployment + local CSV (Python SDK) |
| `predict_by_ai_catalog` | Predictions using a deployment + AI Catalog dataset (SDK) |
| `predict_by_ai_catalog_rt` | Real-time predictions using a deployment + AI Catalog dataset |
| `predict_from_project_data` | Predictions using training data associated with the project |
| `generate_prediction_data_template` | Template CSV with correct structure for predictions |
| `validate_prediction_data` | Validate if a CSV is suitable for predictions |
| `is_eligible_for_timeseries_training` | Check if dataset is eligible for time series training |
| `score_dataset_with_model` | Score a dataset using a specific DR model |
| `start_autopilot` | Start automated model training (Autopilot) for a project |

---

## DR Data — AI Catalog, Datastores, Projects

| Tool | Description |
|------|-------------|
| `upload_dataset_to_ai_catalog` | Upload a dataset to the DR AI Catalog / Data Registry |
| `list_ai_catalog_items` | All AI Catalog items (datasets) |
| `get_dataset_details` | Dataset metadata and optional sample rows |
| `list_datastores` | Available DR data connections (datastores) |
| `browse_datastore` | Browse a datastore — catalogs, schemas, tables |
| `query_datastore` | Execute SQL against a DR datastore (DML only) |
| `list_projects` | All DR projects for the authenticated user |
| `get_project_dataset_by_name` | Dataset ID by name for a given project |
| `analyze_dataset` | Analyze dataset structure and potential use cases |
| `suggest_use_cases` | Suggest ML use cases from a dataset |
| `get_exploratory_insights` | Exploratory data insights for a dataset |

---

## Web Search & Research

| Tool | Description |
|------|-------------|
| `perplexity_search` | Multi-query research + content extraction (Perplexity) |
| `perplexity_think` | Conversational AI for reasoning and structured data extraction |
| `tavily_search` | Real-time web search (Tavily, optimized for AI agents) |
| `tavily_extract` | Extract content from web pages |
| `tavily_map` | Generate structured map of a website |
| `tavily_crawl` | Crawl a website for RAG workflows |

---

## API Discovery

| Tool | Description |
|------|-------------|
| `search_service_api` | Search an external service's OpenAPI spec for matching endpoints |
| `list_services` | List services available for `search_service_api` |

---

## Skills Management

| Tool | Description |
|------|-------------|
| `list_skills` | List available skills filtered by category, tag, or service |
| `create_skill` | Create a new skill by writing a SKILL.md to the skills directory |
| `validate_skill` | Validate a skill's SKILL.md for correctness |
| `update_skill_status` | Update a skill's status in its SKILL.md frontmatter |

---

## Token Management

| Tool | Description |
|------|-------------|
| `list_tokens` | List services for which you have stored API tokens |
| `store_token` | Store a personal API token via secure web form |
| `delete_token` | Remove a stored token for a service |

---

## SOUL → Tool Mapping

Which tools each domain pack activates by default.

=== "supply-chain"
    ```
    list_deployments
    get_deployment_info
    get_prediction_history
    get_model_details
    get_model_feature_impact
    is_eligible_for_timeseries_training
    predict_realtime
    predict_by_ai_catalog
    start_autopilot
    perplexity_search
    tavily_search
    list_skills
    search_service_api
    ```

=== "data-analyst"
    ```
    query_datastore
    browse_datastore
    list_datastores
    analyze_dataset
    get_exploratory_insights
    suggest_use_cases
    upload_dataset_to_ai_catalog
    list_ai_catalog_items
    get_dataset_details
    search_service_api
    tavily_search
    tavily_extract
    list_skills
    ```

=== "docs-rag"
    ```
    tavily_search
    tavily_extract
    tavily_crawl
    tavily_map
    perplexity_search
    perplexity_think
    list_skills
    search_service_api
    ```

=== "deep-coder"
    ```
    search_service_api
    list_services
    list_skills
    create_skill
    validate_skill
    tavily_search
    tavily_extract
    store_token
    list_tokens
    ```

=== "agent-deployer"
    ```
    deploy_model
    deploy_custom_model
    list_deployments
    get_deployment_info
    get_model_details
    start_autopilot
    list_skills
    search_service_api
    list_services
    list_ai_catalog_items
    ```
