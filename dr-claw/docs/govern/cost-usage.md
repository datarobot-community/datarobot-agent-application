# Cost & Usage

Track LLM token consumption and spend across your entire Soul Factory fleet. Data flows from the **DR LLM Gateway billing ledger** into aggregated dashboards.

---

## Platform summary

```
┌─────────────┐   ┌─────────────┐   ┌─────────────┐   ┌─────────────┐
│  $42.18     │   │  1.2M       │   │  84K        │   │  3.2 s      │
│  This month │   │  Tokens     │   │  Cached     │   │  Avg Lat    │
└─────────────┘   └─────────────┘   └─────────────┘   └─────────────┘
```

---

## Cost by agent

| Agent | Tokens (in) | Tokens (out) | Cost today | Cost MTD |
|---|---|---|---|---|
| nemoclaw | 482,100 | 34,200 | $0.42 | $18.31 |
| data-analyst | 198,400 | 19,800 | $0.19 | $9.44 |
| code-review | 91,000 | 12,300 | $0.09 | $4.12 |

---

## Cost by model

| Model | Calls | Input tokens | Output tokens | Cost MTD |
|---|---|---|---|---|
| `dr-llm-70b` | 4,201 | 621,000 | 54,100 | $26.11 |
| `dr-llm-13b` | 1,832 | 150,500 | 12,200 | $6.44 |
| `gpt-4o-mini` | 341 | 28,000 | 3,000 | $0.18 |

---

## Charts

- **Hourly cost** — bar chart of spend over time (last 24h / 7d / 30d)
- **Token breakdown** — stacked area: input vs output vs cached
- **Model mix** — pie chart of token share per model

---

## Filters

| Filter | Options |
|---|---|
| Time range | Today / Last 7d / Last 30d / Custom |
| Agent | Any specific agent or ALL |
| Model | Any specific model or ALL |

---

## Cost alerts (Cycle 2)

In Cycle 2 you can set spend thresholds that trigger notifications:

```yaml
# soul-factory-config.yaml (Cycle 2)
cost_alerts:
  - threshold_usd: 10.00
    period: daily
    notify: [slack, email]
```

!!! note "Cycle 1"
    Cost page uses mock billing data. Real DR LLM Gateway billing integration arrives in [Cycle 2](../reference/cycle-2.md).

---

## What's next

<div class="next-steps" markdown>
<a class="next-step-card" href="../logs/">
  <div class="next-step-card-title">Logs</div>
  <div class="next-step-card-desc">Correlate spend spikes with specific tool call logs.</div>
</a>
<a class="next-step-card" href="../fleet/">
  <div class="next-step-card-title">Fleet</div>
  <div class="next-step-card-desc">Identify high-spend agents across the fleet.</div>
</a>
</div>

<div class="sf-helpful">
  <span class="sf-helpful-label">Was this page helpful?</span>
  <button class="sf-helpful-btn">👍 Yes</button>
  <button class="sf-helpful-btn">👎 No</button>
</div>
