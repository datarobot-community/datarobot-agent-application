# Get the Repo

Everything you need to clone Soul Factory, understand the branch strategy, run it locally, and submit changes.

---

## Clone

```bash
git clone git@github.com:your-org/dr-claw.git
cd dr-claw
```

If you only have HTTPS access:

```bash
git clone https://github.com/your-org/dr-claw.git
```

---

## Branch strategy

| Branch | Purpose |
|---|---|
| `main` | Production-ready; auto-deploys to staging |
| `develop` | Integration branch; all PRs target here |
| `feat/*` | Feature work |
| `fix/*` | Bug fixes |
| `soul/*` | Soul definition changes (triggers hot-swap pipeline in Cycle 2) |
| `docs/*` | Documentation only |

---

## Repo structure

```
dr-claw/
├── app/                   # FastAPI backend
│   ├── main.py            # Entry point
│   ├── routers/           # API route handlers
│   ├── services/          # Business logic (soul, session, hitl)
│   └── models/            # Pydantic schemas
├── frontend/              # Vite + React
│   ├── src/
│   │   ├── pages/         # Route-level pages
│   │   ├── components/    # Shared UI components
│   │   └── lib/           # API client, SSE, store
│   └── public/
├── souls/                 # SOUL.md definitions
│   ├── nemoclaw/
│   │   └── SOUL.md
│   └── templates/
├── skills/                # Skill handlers + manifests
├── scripts/               # gen_mcp_jwt.py, seed_mock_data.py
├── docs/                  # This documentation (MkDocs)
├── .env.example
└── README.md
```

---

## First-time setup

```bash
# Backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# fill in DATAROBOT_API_TOKEN, WORKLOAD_ID

# Frontend
cd frontend
npm install
```

See the [Quickstart](../getting-started/quickstart.md) for the full run sequence.

---

## Contributing

1. Branch from `develop`:
   ```bash
   git checkout develop && git pull
   git checkout -b feat/my-feature
   ```
2. Make changes and run tests:
   ```bash
   pytest                    # backend
   cd frontend && npm test   # frontend
   ```
3. Open a PR targeting `develop`.
4. Get one review approval.
5. Squash-merge.

---

## Long-term MCP JWT (Cycle 2)

In Cycle 2, the backend auto-rotates the MCP JWT using a service account. Until then, you need to regenerate daily:

```bash
# Add to your .zshrc / .bashrc for convenience:
alias sf-jwt='python ~/dr-claw/scripts/gen_mcp_jwt.py | tee ~/.mcp_jwt && export MCP_JWT=$(cat ~/.mcp_jwt)'
```

---

## What's next

<div class="next-steps" markdown>
<a class="next-step-card" href="../skills-pipeline/">
  <div class="next-step-card-title">Skills Pipeline</div>
  <div class="next-step-card-desc">Write, test, and publish a new skill from the repo.</div>
</a>
<a class="next-step-card" href="../../reference/file-map/">
  <div class="next-step-card-title">File Map</div>
  <div class="next-step-card-desc">Full annotated listing of every file in the repo.</div>
</a>
</div>

<div class="sf-helpful">
  <span class="sf-helpful-label">Was this page helpful?</span>
  <button class="sf-helpful-btn">👍 Yes</button>
  <button class="sf-helpful-btn">👎 No</button>
</div>
