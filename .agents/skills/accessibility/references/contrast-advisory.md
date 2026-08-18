# Contrast & color

**Contrast *ratio* is advisory; color-*only* meaning is a real finding.** Keep those apart — collapsing
them either hedges away a criterion you can actually prove, or asserts a number you can't.

You review source, not rendered pixels, so you **cannot** compute a contrast ratio and **must not**
assert one or block on it: every ratio concern is raised as `[advisory — verify]` with a pointer to
check in-browser (axe DevTools, the WebAIM contrast checker, or the design tokens' documented pairs),
and a contrast advisory can never be the sole reason to request changes. **Use of Color (1.4.1) is the
exception** — whether a second, non-color cue exists is plainly visible in the source, so that one is
reported as an ordinary finding with a severity.

## When to raise an advisory (only on VISIBLE evidence)

- **Text over a variable background.** Text placed over a `background-image`, gradient, video, or a
  semi-transparent overlay with no solid scrim. *Why:* the effective contrast depends on pixels behind
  the text; likely-risky. (WCAG 1.4.3 AA)
- **A foreground+background pair set together that look close** — e.g. a muted foreground on a light
  surface both specified in the same rule/props. Advise a check; give the two colors you see.
  (WCAG 1.4.3 AA)
- **Non-text contrast** of essential UI — a focus ring, input border, icon, or chart boundary that looks
  faint against its neighbor. Advisory. (WCAG 1.4.11 AA)
- **Focus-ring visibility** — pairs with structure-keyboard.md's "focus is visible": if a custom focus
  style looks like it may be too subtle, advise verifying it's perceptible (advisory on the *quality*;
  the *removal* with no replacement is a real 2.4.7 finding).

## The one real finding here: color as the *only* cue (WCAG 1.4.1 A)

Report this normally — severity, no `[advisory]` tag — because you can prove it from source without
measuring anything: the question is only whether a **second, non-color cue exists**, and its absence is
visible in the code.

- Status / required / error signalled solely by a color: a red border, a colored dot, a
  `.status--error` class, a `background: green` row, a legend-less colored badge — with no text, icon,
  shape, or pattern alongside it.
- Chart or data-viz series distinguished only by hue (no direct labels, markers, dash patterns).
- Fix line: add the second cue (text, icon, shape, pattern, or a direct label) — don't just darken it.
- Not this: a color that merely *decorates* something already named in text, or a hover/active tint that
  carries no meaning of its own. Those are fine.
- **Not this either: a selected / active state that *fills* one item among unfilled siblings** — a
  `background` or `fill` token, or a border/underline going from absent to present. Tab, pill, segmented
  control, nav item, list row, table cell: the widget doesn't matter, the mechanism does. The shape you
  can prove is a cue *added to one item among otherwise-identical siblings, differing in hue alone* —
  the required field that is the only red-bordered one, the error text that is the only red text. Filled
  against unfilled isn't that: it differs in area and lightness too, and position in the group carries
  meaning of its own. Whether the separation is *strong enough* is a ratio question — advisory
  (1.4.11), never a 1.4.1 finding.
  - **What keeps `background: green` above a finding:** when *every* item is filled and only the **hue**
    separates them — a green row for pass, a red row for fail — that is hue-alone again, and real.
    Filled-vs-unfilled is fine; green-vs-red is not.
  - Still a finding: a state that only **recolours something the siblings already have** — the label
    text, or a border every item carries — and every error / warning / status state. One caveat, the
    same one as above: if the two tokens plainly differ in hue, report it; if you cannot tell whether
    lightness alone already separates them, that is the ratio question — advisory, not a finding.
  - A group that exposes its selected state to assistive tech by **no mechanism at all** — neither a
    native one (`<input type="radio" checked>`, `<option selected>`) nor an ARIA attribute
    (`aria-selected` / `-current` / `-pressed` / `-checked`) — is a **4.1.2** finding (see
    names-forms.md), not a 1.4.1 one. Native state needs no ARIA on top; don't ask for both.

## What is NOT evidence (do not flag)

- **Hardcoded hex is not a failure** and **a design-token is not a success.** Neither tells you the
  actual ratio. Don't flag `#767676` as "low contrast", and don't assume `text-token-muted` passes.
  Judge only a *visible pairing* or a *color-only cue*, as above.
- A single foreground color with no visible background in the same code → at most a light advisory
  ("verify the inherited background still meets contrast"), not a finding.

## Phrasing
> `[advisory — verify] Button.tsx:40 — text and background are set together and look close; I can't
> measure the ratio — verify ≥ 4.5:1 (3:1 for large text) in-browser or with axe. (WCAG 1.4.3 AA)`
