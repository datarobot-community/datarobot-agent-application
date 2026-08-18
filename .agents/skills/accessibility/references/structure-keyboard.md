# Structure, keyboard & focus

Outcome-phrased rules. Each is a *question about what a user experiences*, not a check for a specific
prop. Flag only with a concrete failure + the WCAG SC (evidence contract). Apply `review-scope.md`
first — judge instances/authored code, not imported internals.

## Keyboard operability

- **Every interaction is reachable and operable by keyboard.** Flag a click/pointer handler on a
  non-native-control element (`<div>`, `<span>`, `<svg>`, an SVG node, a `.on('click', …)` bound in
  imperative/D3 code) that has no keyboard path — i.e. it's not a native `<button>`/`<a>` and lacks
  `role` + `tabIndex={0}` + a key handler. *Failure:* a keyboard user cannot trigger it. (WCAG 2.1.1 A)
  - Do **not** blanket-flag `div`+`onClick`: a `<div role="button|link" tabIndex={0} onKeyDown=…>` that
    handles Enter/Space is correct — no finding.
  - **But check the handler is actually correct, not merely present.** The `onKeyDown` must key off the
    right keys — `if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); act(); }` — matching how a
    native button behaves. A handler that fires the action on **every** key (`onKeyDown={() => act()}`
    with no `e.key` check) is a bug, not a pass: it triggers on Tab/arrow/modifier keys, so a keyboard
    user can't move focus *past* the control without activating it, and unprevented Space also scrolls
    the page. Flag that as a keyboard-operability finding (WCAG 2.1.1 A). So the rule is two-sided: a
    *missing* key handler AND a *malformed* one (no key filter / no `preventDefault` on Space) are both
    findings; only a correctly-scoped Enter/Space handler passes.
- **No keyboard trap.** Flag a custom widget/overlay/editor that captures Tab with no way out (Esc or
  Tab to leave). *Failure:* focus is stuck. (WCAG 2.1.2 A)
- **A scrollable region is reachable by keyboard.** A container with `overflow-y-auto`/`overflow: auto`/
  `overflow: scroll` whose content is entirely non-focusable text (a log, a transcript, a long description,
  a rendered markdown pane) can be scrolled by mouse and by nothing else — a keyboard-only user simply
  cannot read past the first viewport. Give it `tabIndex={0}` and an accessible name, or ensure it contains
  focusable content. (WCAG 2.1.1 A)
  - **No finding when the region already holds focusable content** (links, buttons, form controls, rows with
    `tabIndex`) — arrowing/tabbing to those scrolls the container for free — or when the container itself is
    already focusable. Most scroll areas in real apps are lists of interactive things, so check what's
    inside before flagging.
- **Mouse-only affordances have keyboard equivalents.** Hover-only menus, drag-only actions, `onMouseOver`
  with no focus/keyboard path. (WCAG 2.1.1 A; dragging 2.5.7 AA)
  - **A control revealed only by CSS `:hover` (or a JS-set class) must also appear on keyboard focus.**
    If an interactive element is `visibility: hidden` / `display: none` / `opacity: 0` in its co-located
    stylesheet and revealed only via `:hover` or a JS `.focused`/`.is-active`-type class (not `:focus` /
    `:focus-within` / `:focus-visible`), a keyboard-only user can't reveal or reach it. Check the
    stylesheet, not just the JSX. (WCAG 2.1.1 A)
- **No positive tabindex.** Flag `tabIndex={1+}` — it scrambles focus order. (WCAG 2.4.3 A)
- **A roving `tabIndex={-1}` needs a mechanism that actually moves focus — verify it exists.** When a widget
  makes its inactive items `tabIndex={-1}` and only the active one `0` (the roving-tabindex pattern: tabs,
  menus, toolbars, grids, radio groups), find the thing that moves focus *between* items. It is one of two
  things: an explicit arrow-key handler, or a **native grouping the browser drives for you**. If neither is
  in the code you can see, the pattern has *removed* keyboard access rather than organised it — Tab skips
  the inactive items because of the `-1`, and nothing else ever focuses them. *Failure:* a keyboard user can
  reach the currently-selected item and no other, so a tab/menu/toolbar cannot be operated at all. Strictly
  worse than plain `tabIndex={0}` on every item. (WCAG 2.1.1 A)
  - **The native case is the one that looks correct and isn't:** `<input type="radio">` elements form a group
    — and get arrow-key navigation — only when they share a **`name`**. A tablist or segmented control built
    from radios that have `id` and `checked` but no `name` renders and clicks perfectly, and is keyboard-dead.
    Compare against any correctly-grouped radio component in the same repo before concluding either way.
  - **No finding when the mechanism is present** — an `onKeyDown` handling Arrow keys, a roving-tabindex hook
    or context, or a shared `name`. Most roving implementations are correct; look for the mover, don't flag
    the `-1` on sight.
- **Single-character shortcuts can be disabled, remapped, or fire only when a control has focus.** Flag a
  `document`/`window`-level key handler that acts on a bare printable character (`e.key === '/'`, `'j'`,
  `'?'`, a `useHotkeys('k')`) with no modifier requirement, no setting to turn it off, and no scoping to a
  focused element. *Failure:* speech-input users trigger it mid-dictation, and so does anyone whose device
  emits stray keystrokes. A handler that requires `metaKey`/`ctrlKey`/`altKey`, or that's bound to an
  element rather than the document, is correct → no finding. (WCAG 2.1.4 A)
- **Content revealed on hover or focus is reachable, readable, and dismissable.** A tooltip/popover/
  truncated-text reveal must be (a) dismissable without moving the pointer or focus (Esc), (b) *hoverable* —
  it stays up when the pointer moves onto it, so long text can be read or copied, and (c) persistent until
  the trigger is left or it's dismissed. (WCAG 1.4.13 AA)
  - The everyday failure: text clamped with `truncate`/`line-clamp` whose full value appears only via
    `onMouseOver`/`:hover` with **no `onFocus`/`:focus-within`**. Keyboard users can't reach it and touch
    users can't hover, so the content is simply unavailable to them — and if the truncated thing is an
    error message, the information they most need is the part they can't get. Check for a focus path
    alongside every hover path, not just on controls but on *content* reveals too.
  - A native `title` tooltip cannot satisfy this (not dismissable, not hoverable) — one more reason
    `title` is a weak mechanism, see names-forms.md.

## Pointer input

- **The action happens on release, not on press.** Flag a control whose function fires from `onMouseDown` /
  `onPointerDown` / `onTouchStart` instead of `onClick`/`onMouseUp`. *Failure:* there is no way to abort —
  a user who presses the wrong target, or whose tremor lands a press early, has already committed the
  action, and it's worst on destructive ones. Using `onMouseDown` merely to *begin* something the user can
  still abandon (starting a drag, focusing, opening a menu that Esc closes) is fine; the finding is a
  committed, non-reversible action on press. (WCAG 2.5.2 A)
- **Path-based and multi-point gestures have a single-pointer alternative.** A swipe, pinch, two-finger
  rotate, or drag-along-a-track built from `onTouchMove`/`onPointerMove` needs an equivalent tap/click path
  (buttons, a stepper, a menu item) unless the gesture is essential to the function. (WCAG 2.5.1 A) — the
  same goes for anything driven by *device* motion (shake, tilt, `devicemotion`): it needs a UI control too,
  and a way to switch the motion trigger off. (WCAG 2.5.4 A)
- **Drag-and-drop has a non-dragging route to the same outcome.** Reordering, kanban moves, drag-to-resize
  and slider handles need a click or keyboard equivalent — move-up/move-down buttons, a "move to…" menu,
  arrow keys, a numeric input. Flag a reorder or resize whose *only* implementation is a pointer drag.
  (WCAG 2.5.7 AA; the keyboard side is also 2.1.1 A)

## Pointer target size (new in WCAG 2.2)

- **Interactive targets are at least 24×24 CSS px**, or spaced far enough apart that a 24px circle
  centred on each doesn't overlap a neighbour's. *Failure:* users with tremor, low dexterity, or a touch
  screen mis-hit the control — and the denser the row of icon buttons, the worse it gets. (WCAG 2.5.8 AA)
  - Judge the **control**, not the glyph inside it: `size-4`/`h-5 w-5` on an `<svg>` inside a padded
    button is fine; the same class on the `<button>`/`role="button"` element itself is not.
  - Exceptions that are **not** findings: links inline in a sentence, targets whose size the browser
    controls (a native `<select>`), a target whose size is legally/essentially fixed, and a case where an
    equivalent larger control for the same action exists elsewhere on the same page.
  - You're reading source, not layout. Only assert when the code plainly pins the control under 24px
    (explicit height/width classes or CSS on the control). If padding, `min-height`, line-height, or a DS
    default could plausibly carry it over the line, say `[advisory — verify]` instead of asserting.

## Focus management

- **Focus is visible.** Flag a focus-outline reset (`outline: none` / `outline: 0`, CSS or inline, and
  the longhands that do the same) when **focusing that control changes nothing visible, anywhere**.
  *Failure:* keyboard users can't see where they are. (WCAG 2.4.7 AA) — ring *quality* (contrast) is
  advisory, see contrast-advisory.md. Over-firing is this rule's commonest false positive, so resolve
  the replacement before flagging:
  - **Counts, wherever it lands — and however the stack spells it.** A `:focus` or `:focus-visible`
    block anywhere in the file, not only beside the reset; **or utility classes in a `className`.**
    `focus-visible:outline-none focus-visible:ring-2` is a *complete* focus style, not a bare reset —
    read the whole class string before concluding anything, in either direction. Anything that paints
    counts: `box-shadow`, `border`, `background`, a `::before` carrying `content`, a `ring-*` utility.
    In a text field the **caret** is itself an indicator, so a bare `focus:outline-none` on an `<input>`
    is not automatically a finding.
    - On a **sibling** or **descendant** (`&:focus-visible + label`): a visually-hidden native input
      styled through its label is *meant* to ring somewhere other than itself.
    - On an **ancestor** (`:focus-within`, the card / field-shell pattern) — provided it still says
      *which* control has focus. One focusable child is the clean case. With several, the ancestor ring
      only covers the ones that have no indicator of their own; a shell whose input leans on the
      wrapper ring while its clear button carries `focus-visible:ring-2` is correct, because each
      focused control still looks different. It fails only when focus can move between two controls
      that both depend on that one ring and nothing visibly changes.
  - **Doesn't count.** A style keyed off a **different** control — 2.4.7 is per focused element, so a
    ring elsewhere in the file does not rescue this one. Anything already in the **base state**, such as
    a `box-shadow` a line or two above the reset and worn at all times; only a declaration reached
    *because* the control is focused is a change. `:hover`, ever. A ring the reset then overrides —
    equal specificity and later in source wins, so check order, not just presence. A block that paints
    nothing: an empty `:focus-visible {}`, one that only re-declares the reset, a zero-width ring, a
    `::before` with no `content`, `border-color` under `border: 0`. A JS-toggled `.focused` class that
    isn't really wired — see "Styles usually aren't in the JSX" below.
  - **Styles usually aren't in the JSX — read the co-located stylesheet.** Tailwind repos put focus
    classes right in `className`, but non-Tailwind repos keep them in a sibling
    `.less`/`.css`/`.scss` (`button.tsx` ↔ `button.less`). When a component has such a file, open it and
    check for `outline: none`/`outline: 0` on the control (or a blanket `.foo * { outline: none }`) whose
    only focus indicator is a *class* toggled by JS (`.focused`, `.is-active`). If that class is set by
    `onFocus`/`onBlur`/arrow handlers that aren't actually wired onto the element (e.g. a hook returns
    them but only `onKeyDown` is spread), then Tab/click focus shows **no** ring → a real 2.4.7 finding,
    not a maybe. Same discipline as following an animation into the in-repo CSS: the stylesheet is
    in-repo, so read it before concluding focus is fine.
- **Focus moves sensibly on dynamic UI.** For hand-rolled dialogs/drawers/popovers: focus moves into
  the surface on open, is trapped while open, returns to the trigger on close, background is inert/
  `aria-hidden`. Flag a missing piece. (WCAG 2.4.3 A; 4.1.2 A) — defer this for an imported dialog
  primitive; review it for a hand-rolled one or a wrapper that breaks it.
- **Focus isn't lost.** Deleting the focused item / removing content with no focus re-home dumps focus
  to `<body>`. On SPA route change, focus should move to the new view/heading, not stay on the link.
  (WCAG 2.4.3 A)
- **Nothing focusable is `aria-hidden`.** Flag `aria-hidden="true"` on a focusable element or an
  ancestor of one — it creates a "phantom" focus stop. (WCAG 4.1.2 A)
- **The focused element isn't hidden behind sticky chrome.** A `position: sticky`/`fixed` header, toolbar,
  action bar, footer or cookie banner that overlays a scrolling region can leave a Tab-focused control
  *entirely* covered — the user is typing into something they can't see. Flag a sticky/fixed overlay above
  a focusable list/table/form where nothing compensates (`scroll-margin-top`/`scroll-padding-top` on the
  scroll container, or a layout that reserves the space). New in 2.2 and easy to miss. (WCAG 2.4.11 AA)

## Semantic structure

- **Native element for the job.** Prefer `<button>`/`<a href>`/`<nav>`/`<ul>`. Flag a generic element
  standing in for a native control **only when the substitution causes an actual gap** — a
  missing/incorrect role, no keyboard path, lost focus, or an `<a>` without `href` used as a button. A
  generic element that reimplements the native semantics **completely and correctly** (`role` +
  `tabIndex` + a correct Enter/Space handler + an accessible name) is already accessible: there is no
  concrete user-facing failure, so under the evidence contract that is **not a finding** — suggesting the
  native element there is a code-quality note, not a WCAG issue, so don't report it. ARIA's first rule is
  best practice, not an AA success criterion. (WCAG 4.1.2 A only when a real gap exists.)
- **Text that looks like a heading IS a heading.** The real failure is a visually-styled "heading" built
  from a `<div>`/`<p>`/`<span>` — bold, large, titling a section — with no `<h*>` or `role="heading"`: the
  page then offers a screen reader no outline to navigate by. A heading that does exist also has to describe
  its section. (WCAG 1.3.1 A; 2.4.6 AA)
  - **Not findings:** a skipped level (`h1`→`h3`), two `<h1>`s, or no `<h1>`. These are widely recommended
    practice, but no A or AA criterion requires either — and a component reviewed on its own genuinely
    cannot know what level it will sit at in the page that renders it. Best-practice note at most.
- **Landmarks & lists are real.** One `<main>`; content in landmarks; multiple `<nav>` distinguished by
  `aria-label`; list content in `<ul>/<ol>/<dl>` not stacked `<div>`s. (WCAG 1.3.1 A)
- **Custom composite widgets follow their ARIA APG pattern** (tabs, menu, combobox, tree, accordion):
  correct roles, states, and arrow-key/roving-tabindex behavior. Flag a hand-rolled one that's missing
  the pattern; recommend the repo's existing primitive. (WCAG 4.1.2 A; 2.1.1 A) — reference APG *behavior*, not its
  code examples.

## Document & page level

These live in the app shell (`index.html`, a root layout/document component, the router's page wrapper) —
easy to miss because they're nobody's feature, and they affect every screen at once. Only raise them when
the diff actually touches that shell or adds a new one.

- **The document declares its language.** `<html lang="en">` wherever the root element is authored. Flag a
  missing or empty `lang`: a screen reader then falls back to the OS voice and reads the UI with the wrong
  pronunciation rules. A passage in a different language needs its own `lang` on the wrapping element.
  (WCAG 3.1.1 A; 3.1.2 AA)
- **Zoom isn't disabled.** Flag `user-scalable=no`, `maximum-scale=1`, or `minimum-scale=maximum-scale` in
  the viewport `<meta>`. *Failure:* low-vision users on touch devices can't zoom at all. (WCAG 1.4.4 AA)
- **Repeated blocks can be bypassed.** A layout with a persistent header/nav ahead of the main content needs
  either a skip link among the first focusable elements or real landmarks (`<nav>` + `<main>`) to jump by.
  Flag a new page shell/layout that has neither — not the individual pages inside a shell that already
  provides one. (WCAG 2.4.1 A)
- **Reading order matches meaningful visual order.** DOM sequence is what a screen reader reads and what Tab
  follows, so co-located CSS that reorders content — `order:`, `flex-direction: row-reverse`/`column-reverse`,
  explicit `grid-area`/`grid-row` placement, absolute positioning — can put them out of step. Flag it only
  when the visual order carries *meaning* the DOM then contradicts: a label rendered after its control,
  numbered steps out of sequence, an action above the content it acts on. Purely visual arrangement of
  independent blocks is not a finding. (WCAG 1.3.2 A)

## Content & behavior (light)

- **Instructions don't rely on sensory characteristics alone** ("click the green button on the right").
  (WCAG 1.3.3 A; 1.4.1 A)
- **Page/route has a meaningful, unique title** (`<title>` / SPA route updates it). (WCAG 2.4.2 A)
- **Focus alone doesn't change context.** Flag `onFocus` that navigates, submits, or opens a modal/popup
  that takes focus. *Failure:* a keyboard user Tabbing *through* the page gets thrown somewhere they didn't
  choose to go. Revealing a hint or a panel in place is not a change of context — no finding. (WCAG 3.2.1 A)
- **Changing a value doesn't change context unannounced.** Flag a `<select onChange>` (or radio/checkbox
  handler) that immediately navigates, submits, or replaces the view with no apply control and no advance
  warning. *Failure:* a keyboard user arrowing through the options fires whichever one they land on.
  Filtering a list in place is fine — the finding is navigation or submission. (WCAG 3.2.2 A)
- **Time limits can be extended, adjusted, or turned off.** Flag a session timeout, auto-logout,
  auto-refresh, countdown, or carousel auto-advance that expires content with no way to extend or disable it
  (exceptions: real-time events, and limits longer than 20 hours). (WCAG 2.2.1 A)
- **Navigation & component naming are consistent across pages.** (WCAG 3.2.3 / 3.2.4 AA)
- **Help sits in the same place on every page.** If a help affordance (support link, contact details, a
  chat launcher, a help menu) appears across multiple pages, it must keep the same relative position in
  the layout each time. Only flag when the diff actually shows the inconsistency — e.g. one page puts the
  launcher in the header and another drops it into the footer. (WCAG 3.2.6 A, new in 2.2)
- **Motion that runs on its own can be stopped.** Content that moves/blinks/scrolls automatically, runs
  longer than 5s, and is presented in parallel with other content needs a pause / stop / hide control.
  (WCAG 2.2.2 A) — mind the criterion's **essential exception**: a loading spinner or progress animation
  that *is* the status indication is generally essential, so don't report it under 2.2.2.
  - **Keep the two motion criteria apart.** Honoring `prefers-reduced-motion` is **2.3.3 Animation from
    Interactions, level AAA** — above this skill's AA bar. A missing reduced-motion guard earns a
    one-line best-practice note at most; do **not** cite it as an A/AA failure. What 2.2.2 actually asks
    for is a *control*, not a media query — so don't let a `@media (prefers-reduced-motion)` block talk
    you out of a genuine 2.2.2 finding either.
  - **Confirm it from the source when the source is in-repo.** A `className` referencing an animation
    (`animate-*`, a CSS var like `--animation-*`, a keyframes name) is only a *lead*. If the keyframes are
    defined in an in-repo CSS/LESS file, open it and read the iteration-count and duration — then you can
    report a concrete finding instead of a hedge: decorative/ambient motion looping `infinite` (or >5s)
    alongside other content, with no way to pause it, IS a 2.2.2 A failure, not a maybe. Reserve
    `[advisory — verify]` for keyframes that genuinely aren't in the repo (e.g. a third-party
    stylesheet). Don't settle for advisory on motion you could have confirmed with one more in-repo read.
