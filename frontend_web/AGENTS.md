# Frontend Development Instructions

The agent application frontend MUST be implemented in the following location withing the `frontend_web/`.
The technology stack is TypeScript + React + Vite + Tailwind CSS + shadcn/ui.
By default it ships a chat UI, but it can reimplemented to contain dashboards, multi-page apps, or other custom UIs.

## Frontend Development Guidelines

IMPORTANT: Do NOT replace this stack with a different framework (e.g. Next.js, Vue, Angular, Svelte). If the user asks to switch frameworks, because deployment pipeline and infrastructure depend on the current stack.
IMPORTANT: The frontend depends on backend API endpoints and agent tool outputs being in place.

- You may modify files ONLY inside `frontend_web/` and `fastapi_server/` for the frontend work.
- The frontend is a standard Vite + React + TypeScript project:
  * Pages live in `frontend_web/src/pages/`
  * Routes are defined in `frontend_web/src/routesConfig.tsx`
  * Reusable components are in `frontend_web/src/components/`
  * UI primitives (shadcn/ui) are in `frontend_web/src/components/ui/`
  * API hooks and requests are in `frontend_web/src/api/`
  * Theming is in `frontend_web/src/theme/`
- Read `frontend_web/README.md` to further understand the existing structure.

### API Architecture

The frontend uses a three-layer architecture for API calls:

1. **API Client** (`src/api/apiClient.ts`): Pre-configured axios instance with base URL
2. **API Requests** (`src/api/{feature}/api-requests.ts`): Functions that make HTTP calls using `apiClient`
3. **React Query Hooks** (`src/api/{feature}/hooks.ts`): Hooks that wrap requests with React Query for caching/state
4. **Pages**: Import and use the hooks

**When adding new API endpoints:**
- Create request functions in `src/api/{feature}/api-requests.ts` using `apiClient` (MUST use default import: `import apiClient from '@/api/apiClient'`)
- Wrap them in React Query hooks in `src/api/{feature}/hooks.ts`
- Import and use the hooks in your pages/components
- Never call `fetch()` or create new axios instances - always use the configured `apiClient`

**CRITICAL - API Path Requirements:**

`apiClient` is already configured with `baseURL` that includes `/api`. Therefore:

Including `/api` in the path will cause **double `/api/api/` URLs** and result in 404/405 errors.

## Frontend  Security
- NEVER embed API keys, secrets, or credentials in frontend code. If the frontend needs to call
  external services, route those calls through `fastapi_server/` endpoints. Do not make direct external API
  calls from browser-side code as this exposes secrets and creates CORS issues.

## Installing frontend packages

Before making any changes to the frontend code, install dependencies (npm packages) by running shell command:

```shell
dr run frontend_web:install
```

- To install new npm packages, use shell to run `npm install <package>` from the `frontend_web/` directory.

## Installing shadcn/ui components

**CRITICAL**: Before writing ANY code that imports a shadcn/ui component, you MUST first verify the component file exists.

**MANDATORY WORKFLOW:**
1. **BEFORE** writing any import statement for a shadcn/ui component (e.g. `Select`, `Tabs`, `Table`, `Popover`, `DatePicker`, `Dialog`, `Accordion`, etc.)
2. Check if the file exists: `frontend_web/src/components/ui/{component}.tsx`
3. If the file does NOT exist, you MUST run: `npx --yes shadcn@latest add {component} --overwrite` from the `frontend_web/` directory
4. Wait for the installation to complete
5. ONLY THEN write code that imports the component

## Frontend Testing

```shell
dr run frontend_web:lint
```

```shell
dr run frontend_web:test
```
