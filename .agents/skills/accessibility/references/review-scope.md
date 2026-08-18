# Review scope — what to review, what to leave alone

This is the rule that keeps the skill **low-noise, agnostic, and offline**. It decides, for any piece of
UI, *what you are allowed to judge*. Read it first on every review.

The whole idea in one line: **judge the accessibility outcome of the code you can see; when you can't
see it, review how it's used and stay silent about the rest.** You trust nothing because of its name,
its import path, or its reputation as "a design-system component" — only because you can read it.

## 1. "Visible" means a file in the open repo

- **Visible** = a source file that exists in the repository you're reviewing (app code, local
  components, and *vendored/copied-in* primitives — e.g. a `components/ui/*` directory whose files are
  real source committed in the repo rather than an installed package — all count).
- **Not visible** = anything you'd have to reach into `node_modules`, `dist`, or build output for.
  **Never open those to reach a finding.** If review depth depended on whether a package happened to be
  installed, the skill would give different answers on different machines — that's the opposite of what
  we want. (In *authoring* mode the ban lifts: reading an installed package's types/source to confirm
  which prop actually supplies an accessible name is establishing the API, not judging a diff. See
  SKILL.md → Authoring safety.)
- A local re-export or barrel (`export { Button } from './button'`, `index.ts` roll-ups) is fine to
  follow **only by reading a file that's already in-repo**. The moment the trail crosses a package
  boundary (a bare/scoped `import … from '@scope/pkg'`) or the file isn't there, **stop**: review the
  call-site only and stay silent about the internals. Do not build an import-resolution algorithm.

## 2. Review instances and call-sites — not the mere existence of a component

Accessibility is an *outcome* of the rendered tree, and that outcome is assembled from three places:
the primitive's internals, any wrapper's added markup, and the call-site's props/children. Judge each
only where you can see it.

- **A passthrough is correct by default.** A file whose interactive element just forwards `{...props}`
  (or renders a `Slot`/`asChild`) to another element or an imported primitive, adding no
  semantics-breaking structure, is **fine → no finding** — *even though it doesn't itself set
  `role`/name/state.* Those legitimately come from the primitive or from the call-site. Do **not** flag
  a clean wrapper for "missing role" / "missing aria-label" / "icon size variant needs a label." That
  is the #1 false-positive trap.

- **Flag only *local* things that break an outcome.** Review what *this* file adds or overrides:
  - an extra node inserted where it breaks a required relationship (e.g. a `<div>` between a
    `role="tablist"` and its `role="tab"` children);
  - a click / pointer handler wired onto a static, non-focusable element with no keyboard path;
  - stripping or failing to forward `aria-*` / `id` / `disabled` that the consumer relies on;
  - a removed focus indicator with no visible replacement — read structure-keyboard.md's "Focus is
    visible" before flagging one; the replacement is usually not adjacent to the reset.

- **Hand-rolled interactive** (raw `div`/`span`/`svg` + roles/handlers/roving-tabindex reimplementing a
  widget) → full review, but report the **specific** missing outcome (name / keyboard operation / focus
  management / announced state), per the evidence contract — not a blanket "you reimplemented a widget."

- **Imported, source not visible** → review only the **call-site** (see checklist below) and stay
  silent about internals you cannot read. That is honesty, not trust: never fabricate a claim about
  code you can't see.
  - *But a form control's **name** is the caller's job, not the wrapper's.* If a DS/library component
    that renders an input (`<Search>`, `<Input>`, `<TextField>`, `<Combobox>`, `<Textarea>`…) is given
    only a `placeholder` (or nothing) at the call-site — no `label` / `aria-label` / `aria-labelledby` /
    associated `<label>` — that **is** a missing-name finding (3.3.2 / 4.1.2), *even though you can't see
    the wrapper's internals*: the wrapper cannot invent a meaningful name, so the absence of any
    name-supplying prop at the call-site is itself the evidence. Defer to unseen internals only for
    **behaviors** the wrapper actually implements (keyboard, focus, roles) — never for a name the caller
    is responsible for supplying. (Be consistent: an `<Input>` and a `<Search>` from the same library, both
    named only by `placeholder`, are the same finding — don't defer on one and flag the other.)
  - *Ground it when you can.* If other in-repo call-sites of that same component pass a `label`/`aria-label`
    prop, you've **proven** the prop exists and is the expected way in — the placeholder-only call-site is
    then a clean finding. If you can't find one, the finding still holds on a weaker footing: a wrapper's
    internal default can only ever be generic, and a generic name can't distinguish three filter fields on
    one screen from each other. Say which of the two you're standing on.

- **A reusable/exported component must stand on its own.** When the file you're reviewing is itself a
  reusable definition — a design-system or component-library primitive, a package's public export, or a
  clearly shared component — judge its accessibility standalone. Do **not** clear a real component-level gap (a
  mouse-only interaction, an unnamed data `<svg>`, a missing live region) just because the one in-repo
  call-site you can see happens to compensate (pairs it with an accessible sibling, adds the missing
  control). Other callers won't have that compensation. Report it as a component finding — you may note
  the in-repo mitigation and lower the severity, but don't zero it out. (This is the complement of the
  passthrough rule: a passthrough that *adds nothing* is fine; a reusable component that is *only*
  accessible when the caller bolts on accessibility is not.)

## 3. Accessible names can be computed — don't mistake them for missing

A control has an accessible name if a name is provided by **any** means, including:
- `aria-label={t('Delete')}`, a variable, a `useMemo`/template string, or any expression — a name that isn't
  a string literal is still a name. **But the test isn't "an expression is present", it's "every value it can
  take is a real name."** `aria-label={label}` on an optional prop with no default,
  `aria-label={cond ? 'Delete' : ''}`, or `aria-label={row.title}` where the data can be empty each leave a
  reachable path with no name — still a missing-name finding, and the fix is a fallback. Clear it only when
  the expression cannot evaluate to empty;
- an associated `<label htmlFor>` / `aria-labelledby` / wrapping label;
- visible child text, **or** visually-hidden child text (`className="sr-only"`, a `VisuallyHidden`
  component, or a library's hidden dialog title) — these are real accessible names, common in icon
  buttons and dialogs.

Conversely: `title` as the **sole** name on an icon-only control is **not a finding** — `title` feeds the
accessible-name computation, so the control *is* named and 4.1.2 is met. What's wrong with it is
discoverability (hover-only, unreliable on touch and speech input), and that's best practice rather than an
A/AA criterion: recommend an `aria-label` as a best-practice note, severity slot empty. Only a control with
**no** name at all (no text, `aria-label`, or `title`) is **Blocks a task**. And `placeholder` is **never** a
label (WCAG 3.3.2) — that one *is* a finding.

## 4. "Reviewing inside a design system" needs no special mode

There is no app-vs-library switch. When you're inside the design system / component library itself, the
primitive's implementation is simply *visible authored code*, so you review it (that's where the real
primitive bugs live). When you're in an app consuming that primitive by package import, its internals are
*not visible*, so you review the call-site. Same rule, different visibility — and it holds whichever
component library the repo happens to use, or several at once. If a vendored/copied primitive has a bug, note
that it's a shared/copied file — the fix may belong upstream — but you may still flag it.

## 5. When unsure — stay silent

If you can't resolve what a symbol renders, can't tell whether a name is provided, or can't establish a
concrete failure, **say nothing about it**. The skill is advisory and low-noise; a missed issue is far
cheaper than a false one, which erodes trust and gets the whole skill muted.

## 6. Criteria source review can't settle — name them, don't guess either way

A handful of AA criteria need rendered pixels, real media, a device, or the whole site's architecture. Silence
implies "checked and fine", and an asserted finding would be fabricated, so when the diff plainly touches one
of these the honest output is a single `[advisory — verify]` line naming what a human or a browser tool has to
check:

- **Contrast ratios (1.4.3, 1.4.11)** — no pixels here. See `contrast-advisory.md`.
- **Reflow at 320px (1.4.10) and text spacing (1.4.12)** — need a layout engine. A hardcoded wide
  `width`/`min-width` on a container, or a fixed `height` on a text block that could clip at larger
  line-height, is worth one advisory line. The zoom lock in the viewport meta is the one part you *can*
  assert outright (1.4.4).
- **Caption / audio-description accuracy (1.2.2–1.2.5)** — you can see whether a track or transcript exists,
  never whether it's correct.
- **Flashing (2.3.1), orientation lock (1.3.4), images of text (1.4.5), multiple ways to find a page
  (2.4.5)** — need rendering, a device, or the full site map. Don't manufacture findings here; if the diff
  raises one, say plainly that it needs a manual check.

This is the same discipline as the rest of the file: report what you can prove, disclose what you can't
reach, and never let the two blur.

## Call-site checklist (apply at EVERY usage, library component or not)

Even when you defer a component's internals, always check how it's *used*:

- **Name:** does every interactive element (button, link, input, icon-only control) end up with an accessible
  name — via text, `aria-label`, `aria-labelledby`, associated `<label>`, or hidden child text? Icon-only with
  **none** → a *Blocks a task* finding; `title`-**only** → the control is named, so a best-practice note, not
  a finding (§3). For an `<img>` the question is *informative or decorative*: informative needs a meaningful
  `alt`, decorative needs `alt=""` — an empty `alt` on a decoration is **correct**, never a missing name.
- **Label association:** is each form control tied to a label (`htmlFor`/`id`, wrapping label, or
  `aria-label`)? `placeholder` alone doesn't count.
- **Keyboard:** does any custom `onClick`/handler on a non-native-control element have a *working* keyboard
  equivalent — a native element, or `role` + `tabIndex` + an `onKeyDown` that actually filters on Enter/Space
  and calls `preventDefault()`? A present-but-unfiltered handler that fires on every key is a finding, not a
  pass (see structure-keyboard.md).
- **State:** are toggle/expanded/selected/checked states expressed (`aria-expanded`, `aria-pressed`,
  `aria-selected`, `aria-checked`) and updated on interaction?
- **Required props:** if the visible types/usages show a component *requires* a name prop for icon-only
  use, is it passed?
- **Announcements:** if this usage produces async/dynamic output, is it in (or routed to) a live region
  (see `feedback-live.md`)?
