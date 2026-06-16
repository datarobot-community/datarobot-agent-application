# Backend Development Instructions

The agent application template includes a backend implementation in `fastapi_server/`.
By default it ships a backend implementing APIs endpoints for the frontend application.

## Backend Development Guidelines

- The FastAPI backend in `fastapi_server/` already serves the chat API at `/api/v1/`.
  If the user's frontend needs new data endpoints, add them in `fastapi_server/app/api/v1/`.
- The entry point for the backend can be found at `fastapi_server/app/main.py`
- For POST endpoints accepting JSON body, use Pydantic models (not function parameters). Query params go in function signature, body params go in Pydantic model.

## Application persistence

`USE_APPLICATION_MEMORY_SPACE` controls where the FastAPI backend stores application data: chats, messages, OAuth identities, and user profiles. It is separate from agent-side memory runtime parameters on the agent deployment.

> [!NOTE]
> `USE_APPLICATION_MEMORY_SPACE=true` is currently experimental.

| Setting | Persistence | Provisioned by |
|---------|-------------|--------------|
| `false` (default) | SQLite (`database_uri` in `fastapi_server/app/config.py`) | Local file at `.data/database.sqlite` |
| `true` | DataRobot Memory Space (`APPLICATION_MEMORY_SPACE_ID`) | Pulumi in `infra/infra/fastapi_server.py` |

To enable Memory Space persistence:

1. Ensure the organization has agentic memory API access (`ENABLE_AGENTIC_MEMORY_API`).
2. Set `USE_APPLICATION_MEMORY_SPACE=true` in the project `.env` (see `.env.template`).
3. Run `task deploy-dev`. Pulumi provisions a memory space and wires `USE_APPLICATION_MEMORY_SPACE` and `APPLICATION_MEMORY_SPACE_ID` on the FastAPI custom application runtime (not the agent deployment).
4. After changing this flag, rerun `task deploy-dev` before `task dev` so infrastructure and runtime parameters stay in sync with `.env`.

Repository wiring happens in `fastapi_server/app/deps.py`: when both the flag and `APPLICATION_MEMORY_SPACE_ID` are set, Memory Space repositories are used; otherwise SQLite repositories are used. API and service code should depend on the `*RepositoryLike` types in `fastapi_server/app/repo_types.py`, not concrete implementations.

### Which files to edit

**Configuration and infrastructure** (any change to the flag or provisioning):

- `.env` / `.env.template` — set `USE_APPLICATION_MEMORY_SPACE`
- `fastapi_server/app/config.py` — runtime parameter definitions
- `infra/infra/fastapi_server.py` — Pulumi Memory Space provisioning and runtime parameter wiring

**When `USE_APPLICATION_MEMORY_SPACE=false` (SQLite)** — edit SQLite-backed repositories and schema:

- `fastapi_server/app/chats/__init__.py` — `Chat` model and `ChatRepository`
- `fastapi_server/app/messages/__init__.py` — `Message` model and `MessageRepository`
- `fastapi_server/app/users/user.py` — `User` model and `UserRepository`
- `fastapi_server/app/users/identity.py` — identity model and `IdentityRepository`
- `fastapi_server/migrations/` — Alembic migrations for schema changes
- `fastapi_server/app/db.py` — database context (only if changing DB behavior)

**When `USE_APPLICATION_MEMORY_SPACE=true` (Memory Space)** — edit Memory Space-backed repositories:

- `fastapi_server/app/memory/repos.py` — `MemoryChatRepository`, `MemoryMessageRepository`
- `fastapi_server/app/memory/user_repos.py` — `MemoryUserRepository`
- `fastapi_server/app/memory/identity_repos.py` — `MemoryIdentityRepository`
- `fastapi_server/app/memory/registry.py`, `user_registry.py`, `identity_registry.py` — session registries
- `fastapi_server/app/memory/metadata_keys.py`, `participant.py` — metadata keys and participant IDs

**Shared regardless of setting** — edit when adding or changing persisted entities:

- `fastapi_server/app/deps.py` — wire the correct repository implementation
- `fastapi_server/app/repo_types.py` — union types consumed by API and services
- `fastapi_server/app/api/v1/` — use `*RepositoryLike` types from `deps`, not SQLite- or Memory-specific classes

**Tests:**

- SQLite path: `fastapi_server/tests/ag_ui/test_storage.py` and other tests using in-memory SQLite fixtures
- Memory space path: `fastapi_server/tests/memory/`
- End-to-end memory space behavior: `tests/e2e/test_memory.py` (requires `USE_APPLICATION_MEMORY_SPACE=true`)

When adding a new persisted entity, implement both a SQLite repository (with migration) and a Memory Space repository, then register both in `deps.py` and `repo_types.py`. See [docs/fastapi_server/README.md](../docs/fastapi_server/README.md) for setup details.

## Installing backend packages

Before making any changes to the backend code, install dependencies by running shell command:

```shell
dr task run fastapi_server:install
```

## Backend Testing

```shell
dr task run fastapi_server:lint
```

```shell
dr task run fastapi_server:test
```

