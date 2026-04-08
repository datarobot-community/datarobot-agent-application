DRAgentCore  ·  Vision & Feature Spec
deepagents + LangGraph + SOUL + DRSkillsMiddleware on the DR agent-app template

Hackathon context (Soul Inc.)
The Soul Inc. hackathon built a domain-swappable agent runtime integrating NVIDIA's NemoClaw/OpenShell with the DataRobot platform. The core insight: a single persistent agent runtime (the body) comes alive when given a SOUL — a persona definition — and can swap domains without rebuilding or redeploying.
The hackathon validated the SOUL concept and the domain-swap demo. It hit two blockers: (1) Path B (OpenShell local) failed — /opt/start.sh never runs, nothing listens on port 8080 — so Path A (Workload API) was used; (2) the container/sandbox model means users receive a deployed agent, not a repo they can develop further.
DRAgentCore addresses the second blocker directly: same SOUL concept, same domain-swap capability, but built on deepagents + LangGraph as a lightweight Python harness — no container, no daemon, a repo the user owns.





Vision
Build a long-horizon agent harness on top of the DR agent-app template that replaces the current request-response agent loop with deepagents, adds the SOUL concept for domain swapping, and wraps everything in a composable DR middleware stack.
The user receives a repo they own: a souls/ directory to define personas, a skills/ directory for domain knowledge, and middleware they can extend. One runtime. Load a SOUL and it becomes a supply chain analyst. Load another and it becomes a data analyst. No rebuild, no restart, no container.





Features
1. Runtime — deepagents + LangGraph replacing the agent loop
Planning tool: deepagents as the harness
built-in todo list — agent decomposes complex tasks and tracks progress
virtual filesystem — offloads large tool results; prevents context overflow
sub-agent spawning — delegates to specialists with clean context isolation
context compaction — auto-summarizes history when approaching token limits
Underneath deepagents: LangGraph as the execution graph
HITL gates — interrupt_before=['write_node'] for any destructive operation
checkpointing — long-horizon runs survive failures, resume exactly where stopped
stateful multi-step workflows with conditional routing
Replaces the inner agent loop in the existing DR agent-app FastAPI backend. Same FastAPI, same React UI, same Workload API deploy. No new infrastructure.
No container, no daemon, no sandbox — pure Python process. The repo is the artifact.

2. SOUL — domain swapping at runtime
Format: A SOUL is two files:
SOUL.md — system prompt, persona, routing rules, domain context
mcp-tools.json — which MCP servers connect for this domain
souls/ directory in the repo root — supply-chain, finance, data-analyst, engineering-productivity, docs-rag
POST /swap-soul/{name} — swaps the active domain at runtime. No restart. No rebuild. Same agent body.
Each soul defines its MCP server list: DR platform API, DuckDB, Perplexity, domain-specific tools
souls/__template__/ — blank scaffold showing the format for users to create their own

3. Search + Execute — the headline capability from the hackathon
Agent reads the DR OpenAPI spec live, finds the right endpoints, writes Python, executes it — inside the FastAPI process with DR API token scoping
The demo moment: 'Pull deployment health for our top 5 forecast models and tell me which need retraining' — agent has never seen this query, figures it out entirely autonomously
execute_python MCP tool — takes code string, returns stdout/stderr — same as hackathon but runs in process rather than Docker sandbox
This is what replaces the NemoClaw sandbox for code execution — DR governance middleware provides the trust layer instead

4. Middleware stack — composable, ordered, DR-native
DRSkillsMiddleware: DRSkillsMiddleware — what was missing from the hackathon entirely
auto-discovers SKILL.md files from datarobot-agent-skills on startup (30-50 tokens each)
lazily loads full skill content when agent task matches skill description
this is the 'Thermos agent' capability — runtime gets smarter as skills library grows without touching core code
supply chain soul auto-loads forecast-analysis, anomaly-detection skills when relevant
DRGovernanceMiddleware: DRGovernanceMiddleware — replaces partial proxy-layer governance from hackathon
OTel tracing wired to DR platform — every tool call, every LLM call, traced
cost budget enforcement — configurable per-session token limit
Okta agent identity — agent has a first-class identity in the DR ecosystem
audit log on all write operations
DRContextMiddleware: DRContextMiddleware — new capability not in hackathon
auto-evicts tool results over threshold to DR Store
conversation compaction trigger at configurable token count
cross-session persistence via LangGraph Store
DRSubAgentMiddleware: DRSubAgentMiddleware — new capability not in hackathon
spawns specialized sub-agents as DR deployments
context isolation — orchestrator sees only summarized results
supply chain example: data-analyst sub-agent + variance-reporter sub-agent
DomainMiddleware: DomainMiddleware (user extension point) — override for custom routing logic, anomaly thresholds, business rules per SOUL. The class a customer extends per vertical without touching governance.

5. Customer-facing domain packs — one runtime replaces a portfolio of apps
The hackathon team noted this explicitly: 'We can replace all apps with tools.' Each pack is a SOUL that makes the runtime behave like a specific DR application — but with the full long-horizon agent capability underneath.
supply-chain — autonomous forecasting, anomaly detection, variance reporting, shipment rerouting
data-analyst — replaces Talk to My Data. execute_code + DR API. DuckDB for data. Self-healing SQL.
docs-rag — replaces Talk to My Docs. Markdown-indexed files, no vector DB required (Karpathy's approach).
deep-coder — architect + coder + QA in one SOUL. Multi-agent internally, single interface externally.
agent-deployer — meta-play: an agent that deploys other agents. Most impressive demo moment for technical audiences.

6. Available MCP Tools — NemoClaw staging server (beta-global-mcp.stg.ue1.aws.int.datarobot.com)
Verified live against staging MCP server. 49 tools across 6 categories. Auth: Bearer JWT (short-lived OAuth token).

DR Platform — deployments, models, predictions
  list_deployments              List all DR deployments for the authenticated user
  get_deployment_info           Deployment health, features needed to make predictions
  get_deployment_features       Features list for a deployment as JSON
  get_model_info_from_deployment Model info associated with a given deployment ID
  get_model_details             Detailed model info with feature impact and ROC
  get_model_roc_curve           ROC curve for a specific model
  get_model_feature_impact      Feature impact for a specific model
  get_model_lift_chart          Lift chart for a specific model
  get_prediction_history        Recent prediction results from a deployment
  get_best_model                Best model for a project, optionally by metric
  list_models                   All models in a project
  deploy_model                  Deploy a model — create a new DR deployment
  deploy_custom_model           Deploy a custom inference model (.pkl) to DR MLOps
  predict_realtime              Real-time predictions using a deployment + local CSV or dataset
  predict_by_file_path          Predictions using a deployment + local CSV (Python SDK)
  predict_by_ai_catalog         Predictions using a deployment + AI Catalog dataset (SDK)
  predict_by_ai_catalog_rt      Real-time predictions using a deployment + AI Catalog dataset
  predict_from_project_data     Predictions using training data associated with the project
  generate_prediction_data_template  Template CSV with correct structure for predictions
  validate_prediction_data      Validate if a CSV is suitable for predictions
  is_eligible_for_timeseries_training Check if dataset is eligible for time series training
  score_dataset_with_model      Score a dataset using a specific DR model
  start_autopilot               Start automated model training (Autopilot) for a project

DR Data — AI Catalog, datastores, projects
  upload_dataset_to_ai_catalog  Upload a dataset to the DR AI Catalog / Data Registry
  list_ai_catalog_items         All AI Catalog items (datasets)
  get_dataset_details           Dataset metadata and optional sample rows
  list_datastores               Available DR data connections (datastores)
  browse_datastore              Browse a datastore — catalogs, schemas, tables
  query_datastore               Execute SQL against a DR datastore (DML only)
  list_projects                 All DR projects for the authenticated user
  get_project_dataset_by_name   Dataset ID by name for a given project
  analyze_dataset               Analyze dataset structure and potential use cases
  suggest_use_cases             Suggest ML use cases from a dataset
  get_exploratory_insights      Exploratory data insights for a dataset

Web Search & Research
  perplexity_search             Multi-query research + content extraction (Perplexity)
  perplexity_think              Conversational AI for reasoning and structured data extraction
  tavily_search                 Real-time web search (Tavily, optimized for AI agents)
  tavily_extract                Extract content from web pages
  tavily_map                    Generate structured map of a website
  tavily_crawl                  Crawl a website for RAG workflows

API Discovery (Feature 3 — Search + Execute)
  search_service_api            Search an external service's OpenAPI spec for matching endpoints
  list_services                 List services available for search_service_api

Skills Management (Feature 4 — DRSkillsMiddleware)
  list_skills                   List available skills filtered by category, tag, or service
  create_skill                  Create a new skill by writing a SKILL.md to the skills directory
  validate_skill                Validate a skill's SKILL.md for correctness
  update_skill_status           Update a skill's status in its SKILL.md frontmatter

Token Management
  list_tokens                   List services for which you have stored API tokens
  store_token                   Store a personal API token via secure web form
  delete_token                  Remove a stored token for a service

SOUL → tool mapping (which tools each SOUL activates)
  supply-chain    list_deployments, get_deployment_info, get_prediction_history, get_model_details,
                  get_model_feature_impact, is_eligible_for_timeseries_training, predict_realtime,
                  predict_by_ai_catalog, start_autopilot, perplexity_search, tavily_search,
                  list_skills, search_service_api
  data-analyst    query_datastore, browse_datastore, list_datastores, analyze_dataset,
                  get_exploratory_insights, suggest_use_cases, upload_dataset_to_ai_catalog,
                  list_ai_catalog_items, get_dataset_details, search_service_api, tavily_search,
                  tavily_extract, list_skills
  docs-rag        tavily_search, tavily_extract, tavily_crawl, tavily_map, perplexity_search,
                  perplexity_think, list_skills, search_service_api
  deep-coder      search_service_api, list_services, list_skills, create_skill, validate_skill,
                  tavily_search, tavily_extract, store_token, list_tokens
  agent-deployer  deploy_model, deploy_custom_model, list_deployments, get_deployment_info,
                  get_model_details, start_autopilot, list_skills, search_service_api,
                  list_services, list_ai_catalog_items


7. Repo structure — what the user receives
souls/  — domain pack directories (SOUL.md + mcp-tools.json per domain)
skills/  — symlink to datarobot-agent-skills repo (auto-discovered by DRSkillsMiddleware)
middleware/  — DRSkillsMiddleware, DRGovernanceMiddleware, DRContextMiddleware, DRSubAgentMiddleware, DomainMiddleware base class
core/runtime.py  — AgentRuntime wrapping create_deep_agent(), ~50 lines
app/  — unchanged FastAPI backend from DR agent-app template
frontend/  — unchanged React UI from DR agent-app template
infra/  — unchanged Workload API / Pulumi deploy



8. Hackathon vs DRAgentCore — what changes, what carries over





What this is not
Not a new framework — deepagents and LangGraph are the frameworks. This is the DR-opinionated harness layer above them.
Not a fifth template alongside CrewAI/LangGraph/LlamaIndex/NAT — it uses LangGraph underneath but abstracts it away from the user.
Not a container or daemon — the agent runs in the existing FastAPI process.
Not a replacement for NemoClaw — NemoClaw is infrastructure security. DRGovernanceMiddleware is behavioral governance. They're complementary layers.




DRAgentCore · Internal Vision Doc · April 2026