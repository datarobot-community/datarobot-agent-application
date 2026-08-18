---
name: accessibility
description: >-
  Reviews and authors WEB accessibility (WCAG 2.2 AA) in React/TS/JS UI code. TWO TRIGGERS.
  (1) REVIEW — use whenever accessibility is named or implied: a11y, WCAG, ARIA, screen reader,
  keyboard navigation, focus, alt text, labels, contrast, roles, "is this accessible", or a request to
  review a PR/diff/component with user-facing UI. (2) AUTHORING — use whenever you are about to write
  or edit user-facing UI, EVEN IF NOBODY MENTIONS ACCESSIBILITY: any component, button, link, icon
  control, form, input, search box, modal, drawer, popover, menu, tabs, table, list, toast, or
  streaming/async output — and stylesheets count: a .less/.css/.scss rule for focus, hover, outline,
  visibility or colour is UI work too. Never wait to be asked, and never pre-judge whether a given UI
  "has an accessibility angle" — it always does. Load it BEFORE writing the code, so names, labels,
  keyboard and focus are right first time. Skip only for code with no user-facing UI at all — backend,
  config, build scripts, docs.
---

# Accessibility — review & authoring (WCAG 2.2 AA)

You catch the **judgment-level** accessibility issues that linters and axe cannot: whether a name is
*meaningful*, whether focus/keyboard actually *work*, whether dynamic changes are *announced*, whether
ARIA matches real behavior. You are **advisory** — you never block a merge; trade-offs are allowed to
win. You are **design-system-agnostic**: you judge the accessibility *outcome* of the code you can see
and never assume a library is accessible.

## Two modes (same rules, different intent)

- **Review mode** (default when handed a diff / PR / file / "review this for a11y"): produce
  evidence-backed findings in the output format below. Read-only.
- **Authoring mode** (when writing or editing UI): apply the same rules as requirements while you
  generate code — see the **Authoring checklist** near the end of this file.

Everything below applies to both modes; the routing table and output format are review-specific.

## The four contracts (non-negotiable)

### 1. Evidence — report only what you can prove
Report a finding only when there is a **concrete, user-facing failure** you can point to in the code,
tied to a **specific WCAG 2.2 success criterion**. If you cannot name the SC *and* say who is blocked
and how, **stay silent**. No speculation, no "might", no style opinions. Every finding cites the WCAG
SC (required). An axe rule-id / WCAG "F"-number is an optional hint, never required. Prefer a
declarative one-line fix over hedged suggestions. A brief "what's done well" note is optional (nice in
authoring/coaching; skip it if it dilutes a review's signal).

### 2. Scope — verify VISIBLE code, trust nothing by reputation
See `references/review-scope.md`. In short:
- **Visible = a file that exists in the open repo.** For *review* reasoning, never open `node_modules`,
  `dist`, or build output — if review depth tracked install state, the same diff would get different
  findings on different machines. Resolve a local re-export/barrel only by reading a file already
  in-repo; the moment it crosses a package boundary or the file isn't there → **review the call-site
  only, stay silent about internals you can't see**. No import-tracing pipeline.
  *Authoring is the one exception* — see Authoring safety: to avoid inventing a prop you may read an
  installed package's types/source, because you're establishing what the API **is**, not what a diff
  gets judged on.
- **Review rendered JSX *instances* and call-sites — not the mere existence of a component.** A
  primitive/wrapper that only forwards `{...props}` and adds no semantics-breaking local structure is
  **correct → no finding**, even though it doesn't itself set role/name/state. Only flag **local**
  structure/handlers/overrides that break an outcome.
- Reviewing *inside* a component library or design system is the same rule — the primitive is just
  visible authored code, so you review it.
- Can't resolve / unsure → **stay silent**.

### 3. Contrast is advisory — but color-*only* meaning is a real finding
Two different things live here; don't collapse them into one hedge.
- **Contrast ratio → advisory, always.** You cannot measure rendered pixels, so you **never assert a
  ratio and never block on one.** Raise `[advisory — verify]` only when the code visibly shows a risky
  pairing: a foreground AND background set together that look close, or text over an
  image/gradient/video. Hardcoded hex is **not** evidence of failure; a token is **not** evidence of
  success. Point at an in-browser / axe check.
- **Information carried by color alone → a normal 1.4.1 A finding**, with a severity, not an advisory.
  Nothing needs measuring here: when a status / required / error state (or a chart series) is signalled
  only by a color, with no accompanying text, icon, shape, or pattern, the *absence of the second cue*
  is right there in the source. That's evidence, so report it as a finding. A **selected or active**
  state that fills one item among unfilled siblings is the exception — see contrast-advisory.md first.

See `references/contrast-advisory.md`.

### 4. Judge the outcome, not the pattern
Every rule in the bundles names a source pattern, because a pattern is the thing you can search for. The
pattern is only the **lead**; the finding is the **outcome**. Before reporting, restate the rule as the
question a user would ask — *does anything visibly change when this is focused? could someone who can't
see colour tell these apart? can a keyboard get here?* — and answer it from the whole file: later blocks,
the cascade, ancestor / sibling / descendant selectors, and whatever this stack uses **instead of** CSS
(a utility class in `className`, a styled-component, an inline style). A repo that writes no stylesheets
is not a repo without focus styles.
- A pattern that matches while the outcome is fine is a **false positive** — the commonest way this skill
  fails, and the one that gets it muted.
- An outcome that fails while the pattern is absent is **still a finding** — a literal string is never
  the gate.

## Default scope of a review
The task / diff / named files first. Open a dependency's in-repo source only to confirm a *suspected*
structural break. **Never crawl the whole repo for a11y unless explicitly asked.**

## Severity (local user-harm scale — NOT axe impact)
- **Blocks a task** — a keyboard/screen-reader user cannot complete a core action (no accessible name
  on the only control, keyboard trap, unlabeled required input, interactive element unreachable).
- **Serious barrier** — major friction with a workaround (illogical focus order, unannounced status,
  weak/duplicated names, broken heading structure).
- **Nuisance** — degraded but usable (verbose alt, minor landmark/heading polish).
Pair every finding with its WCAG SC. When the evidence genuinely can't establish impact, put
`[advisory — verify]` in the severity slot rather than guessing a level — the slot is never left empty.
**Calibrate by real harm:** a semantic/role mismatch where the control is still reachable and operable
(e.g. `role="link"` on something that performs an action) is usually a **Nuisance** — reserve **Blocks a
task** for genuinely unreachable/unusable/unnamed controls. Don't inflate operable-but-imperfect code. A
genuinely unnamed icon control (no text, `aria-label`, or `title`) is **Blocks a task**; one named *only* by
`title` is named-but-fragile — not a finding at all, but a best-practice note (see below).

## Routing — consult the reference for what changed (do this every review)
**Default to loading a bundle, not to skipping it.** The keyword lists below are prompts, not an
exhaustive taxonomy — if what changed is *near* a category, or you're unsure which bundle owns it, load
it. Skip only what is plainly irrelevant (no table in the diff → skip tables-grids). Deciding a bundle
"probably doesn't apply" before reading it is how real issues get missed: that judgment is the bundle's
job, not the precondition for opening it. When nothing obviously matches but the diff touches UI, load
`structure-keyboard.md` and `names-forms.md` — they cover the majority of real findings.
- interactive elements, `onClick`/handlers, `div`/`span` as controls, tabindex, focus, **any custom widget** (dialog, menu, tabs, accordion, disclosure/expand-collapse, tooltip, popover, combobox, tree, carousel), headings, landmarks, lists, sticky/fixed overlays, **drag-and-drop or reordering**, **small tap/click targets of any kind**, **mouse-down/pointer-down/touch handlers & gestures**, **keyboard shortcuts/hotkeys**, **the app shell — `index.html`, a root layout, `<html lang>`, viewport meta, skip links**, **timeouts/auto-refresh/countdowns**, **CSS that reorders content (`order`, `*-reverse`, `grid-area`)**, animation/motion → `references/structure-keyboard.md`
- accessible names, `aria-*`, roles, icon-only buttons, images/`alt`, **`<svg>`/charts needing a name**, **audio/video, captions & autoplay**, **links and link text**, form inputs, labels, errors, multi-step forms, **destructive or irreversible submits**, nested interactive elements → `references/names-forms.md`
- **anything on screen that changes without a page navigation** → `references/feedback-live.md`. Not just the async cases (toasts, loading, streaming, save/validation results) — *synchronous* ones count too and are the ones most often missed: a selection count, a filter/search result count, an "N of M" indicator. Routing here is deliberately broad and the bundle then narrows hard: 4.1.3 is about *status messages*, so a change already conveyed by a state attribute on the control the user just operated (`aria-expanded`/`-selected`/`-pressed`) or by focus moving into the new content needs **no** live region. Read the bundle before flagging one.
- `<table>`, `role="grid"`, sortable/selectable data grids, **any tabular or key/value data — including one built from `div`s**, virtualized/paginated rows → `references/tables-grids.md`
- color, contrast, gradients, color-only status, **selected / active / current states on tabs, pills, segmented controls, nav items and rows**, focus-ring *contrast* (its *presence* is structure-keyboard.md), **charts/data-viz series colour**, **status badges/pills/dots**, **theming or dark mode**, **disabled styling** → `references/contrast-advisory.md`
Always also apply `references/review-scope.md` (visibility/instance rule + call-site checklist).

## Output format (review mode)
Group findings by severity, most-severe first. One finding per line:

```
[severity] file:line — <the concrete failure, one sentence> → <declarative fix> (WCAG <SC> <level>)
```

Example:
```
[Blocks a task] MessageHeader.tsx:207 — the delete icon-button has no accessible name, so a screen-reader user hears only "button" → add aria-label="Delete message" (WCAG 4.1.2 A)
```

If there are no evidence-backed findings, say so plainly (do not invent issues to look thorough).

### Best-practice notes — the things that are NOT findings
Some habits are worth a word but are **not** WCAG A/AA failures. Reporting them with a severity and an SC is
the fastest way to lose credibility: the one reviewer who checks the spec discovers you cited a criterion
that doesn't say what you claimed, and then nothing you report gets trusted. Put them in a short separate
list after the findings — one line each, no severity, no SC-as-failure, and skip the list entirely if it
would bury real findings:

```
note — file:line — <what's fragile and why> (best practice, not an A/AA failure)
```

Standing members of this bucket. **Do not promote these into findings**, however tempting:
- **`title` as an icon control's only name.** `title` *does* feed the accessible-name computation, so 4.1.2
  is met — the weakness is discoverability (hidden until hover, unreliable on touch and speech input).
  Recommend an `aria-label`; don't call it a failure. A control with **no** name at all is a completely
  different thing: that's a real 4.1.2 **Blocks a task** finding.
- **A name that echoes the role in words** (`aria-label="Delete button"`). Verbose, not non-conformant —
  2.4.6 asks a label to describe topic or purpose, and it does.
- **A missing `prefers-reduced-motion` guard** — that's 2.3.3, level AAA.
- **A `div role="button"` that is fully and correctly implemented** — ARIA's first rule is guidance, not an SC.
- **Skipped heading levels, or more than one `<h1>`** — no A or AA criterion requires either.
- **`aria-hidden` on a bare decorative icon that has no name of its own** — it was never announced, so
  nothing was announced twice.

## Authoring checklist — the reference bundles, inverted
The bundles are written for review ("flag X"); while authoring, read them as requirements ("build so X
can't happen"). Getting these five right *as you type* removes most of what a review would later find:
1. **Native first.** `<button>` / `<a href>` / `<label>` / `<table>`, or whatever primitive the repo's own
   component library already provides, before any `div` + `role` — the name, focus behavior, and keyboard
   handling come for free instead of becoming yours to own.
   - **But reuse doesn't transfer responsibility.** When you pick an existing component *specifically to
     deliver an accessibility outcome* — a tooltip that has to be readable, a truncation whose full text
     has to be reachable, a dialog that has to trap focus, a toast that has to announce — and that
     component's source is visible in-repo, open it and confirm it actually does. "Trust nothing by
     reputation" is not just a review rule: a primitive with a hover-only reveal or a missing focus path
     hands its defect to every feature that reuses it, and your feature ships broken for reasons that
     aren't in your diff. If the source isn't visible, say what outcome you're depending on so a human
     can check it.
2. **Name the control in the same keystroke as the icon.** Icon-only buttons/links get `aria-label` or
   visually-hidden text; every input gets a real associated `<label>`. A placeholder is not a name.
3. **Anything clickable is Tab-reachable and key-operable.** If you do reach for `div` + `onClick`, add
   `role`, `tabIndex={0}`, and an Enter/Space handler with `preventDefault()` in the same edit — the gap
   is nearly never closed "later".
4. **Anything that appears without a navigation gets announced.** Streamed/async/validation output lands
   in a live region that is *already mounted* (`role="status"` / `role="log"`); state changes flip
   `aria-expanded` / `-pressed` / `-selected` / `-checked`.
5. **Focus always has somewhere to go.** Into the surface on open, back to the trigger on close, to a
   sibling when the focused item is deleted — and never remove the focus indicator, however it is spelled,
   without a visible replacement.

**Authoring safety:** only use component APIs you can prove. Existing in-repo usages and the package's
types or source both count as proof — and here, unlike in review, **reading the installed package under
`node_modules` is allowed and encouraged**, because you're establishing what the API *is* rather than
judging someone's diff by it. Do check: a library may already name its own elements internally in a way
that defeats the obvious fix (a component that points its input at a hidden label via `aria-labelledby`
will *shadow* an `aria-label` you pass, so the accessible name has to be supplied through whatever prop
that library actually exposes). If you cannot prove a prop exists, use native HTML semantics or state the
intent — **never invent a component-library prop name.** If you add a `jest`/`vitest`-axe assertion, check the
repo's harness actually runs it — an axe call sitting inside a suite-level opt-out passes vacuously, which is
documentation, not a gate.

## What this skill is NOT
- Not a blocking gate. Not a contrast measurer. Not a WCAG conformance certificate (it surfaces
  judgment issues for a human; it does not certify AA).
- It does not maintain a per-component catalog, and its *review* judgments never depend on any design system
  being installed, on `node_modules`, or on network access (authoring may read an installed package to
  confirm an API — that's the one exception). It rests only on WCAG 2.2 AA + this evidence contract + your
  judgment over the code you can see.
