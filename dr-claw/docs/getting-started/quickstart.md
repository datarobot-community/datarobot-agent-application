# Quickstart

Get Soul Factory running locally and launch your first agent in under five minutes.

---

## Prerequisites

- Python ≥ 3.11 and `pip`
- A DataRobot account with API access
- `node` ≥ 20 (for the frontend)
- A **Workload ID** for your nemoclaw deployment — ask your DR admin or create one from the DR Workload console

---

## Steps

<div class="sf-steps" markdown>

<div class="sf-step">
<div class="sf-step-num">1</div>

### Clone the repo

```bash
git clone git@github.com:your-org/dr-claw.git
cd dr-claw
```

</div>

<div class="sf-step">
<div class="sf-step-num">2</div>

### Set environment variables

Copy the example env file and fill in your credentials:

```bash
cp .env.example .env
```

```bash title=".env"
DATAROBOT_ENDPOINT=https://app.datarobot.com/api/v2
DATAROBOT_API_TOKEN=<your-token>
WORKLOAD_ID=<your-nemoclaw-workload-id>
```

</div>

<div class="sf-step">
<div class="sf-step-num">3</div>

### Configure the Global MCP JWT

Soul Factory talks to DR's Global MCP server using a short-lived JWT.  
Generate one and export it:

```bash
python scripts/gen_mcp_jwt.py | tee .mcp_jwt
export MCP_JWT=$(cat .mcp_jwt)
```

!!! tip "Rotate daily"
    JWTs expire. Re-run `gen_mcp_jwt.py` each dev session, or wire the [long-term JWT refresh](../advanced/get-the-repo.md) from Cycle 2.

</div>

<div class="sf-step">
<div class="sf-step-num">4</div>

### Start the backend

```bash
python -m uvicorn app.main:app --reload --port 8000
```

The API is now at `http://localhost:8000`. Health check:

```bash
curl http://localhost:8000/health
# {"status":"ok","version":"1.0.0-cycle1"}
```

</div>

<div class="sf-step">
<div class="sf-step-num">5</div>

### Start the frontend

```bash
cd frontend
npm install
npm run dev
```

Open **[http://localhost:5173](http://localhost:5173)** — you should see the Soul Factory dashboard.

!!! note "Mock data vs live"
    Cycle 1 ships with mock data for most pages. The `WORKLOAD_ID` env var enables real agent status on the Home and Fleet pages.

</div>

</div>

---

## Verify it works

1. Navigate to **My Agents** — you should see the sample `nemoclaw` agent card.
2. Click the agent → open the **Chat** tab → type `hello`.
3. The SOUL processes your message and streams a response via SSE.

---

## What's next

<div class="next-steps" markdown>
<a class="next-step-card" href="../core-concepts/">
  <div class="next-step-card-title">Core Concepts</div>
  <div class="next-step-card-desc">Soul, Packs, Domain, Session, HITL — understand the building blocks.</div>
</a>
<a class="next-step-card" href="../../build/app-flow/">
  <div class="next-step-card-title">App Flow</div>
  <div class="next-step-card-desc">See how a chat message travels through the entire stack.</div>
</a>
<a class="next-step-card" href="../../build/soul-reference/">
  <div class="next-step-card-title">Soul Reference</div>
  <div class="next-step-card-desc">Write or modify a SOUL.md to change your agent's personality.</div>
</a>
<a class="next-step-card" href="../../connect/setup/">
  <div class="next-step-card-title">Setup Guide</div>
  <div class="next-step-card-desc">Full developer environment setup including MCP JWT.</div>
</a>
</div>

<div class="sf-helpful">
  <span class="sf-helpful-label">Was this page helpful?</span>
  <button class="sf-helpful-btn">👍 Yes</button>
  <button class="sf-helpful-btn">👎 No</button>
</div>
