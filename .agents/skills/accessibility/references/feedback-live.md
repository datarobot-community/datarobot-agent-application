# Live regions, status & async feedback (WCAG 4.1.3 AA)

The outcome: **when something changes without a page navigation, a screen-reader user is told.** This
is the most-missed criterion in dynamic React UIs (chat, toasts, search results, save/validation,
loading). Apply `review-scope.md`: review the component that *produces* the update.

**This is not only about async.** A *synchronous* change — a click that updates a selection count, a
keystroke that changes a result count, a validation message appearing on blur — is just as invisible to a
screen-reader user, and is missed far more often precisely because nothing about it feels like "loading".

## First, is it actually a status message? (most changes are not)

4.1.3 is narrower than "the DOM changed", and treating every re-render as a missing live region is the single
fastest way to make this skill unusable: ordinary correct React UI would collect a live-region finding on
every tab, accordion, and menu. A **status message** tells the user the *success or result of an action*, a
*waiting state*, *progress*, or *the existence of an error* — and it does so **without moving focus**. Ask
those two questions before you flag anything.

**Not a status message → no finding:**
- The change is already carried by a **state attribute on the control the user just operated** —
  `aria-expanded` on a disclosure, `aria-selected` on a tab, `aria-pressed` on a toggle, `aria-checked`,
  `aria-sort` on the header that was just activated. AT announces the new state from the thing under focus.
  (If that attribute is *missing*, the finding is 4.1.2 state — see names-forms.md — not 4.1.3.)
- **Focus moves into the new content** (a dialog opens and takes focus, the user is sent to the first invalid
  field). The user is now reading it; a live region would double-announce.
- The user **navigated to it** — content arriving because the route changed, or an accordion revealing its
  own panel. (Careful with "load more": if rows are appended in place and focus stays on the button, the user
  has no idea anything arrived — that one *is* a status message.)
- Content the user is **actively typing into or directly manipulating**, where the change is the direct
  echo of their own keystroke.

**Is a status message → the rules below apply:** save/submit succeeded or failed, validation errors appeared,
a background operation started/finished, progress advanced, a search or filter produced N results,
"3 of 40 selected" after a select-all, an async list finished loading, streamed text arriving.

- **Dynamic result → announced.** Flag async results, search-result counts, save/success confirmations,
  validation summaries, and **streaming/chat output** that are inserted into the DOM with no live
  region (`aria-live` / `role="status"` / `role="alert"` / `role="log"`). *Failure:* the update is
  visually there but silent to AT.
  - Chat/streaming specifically: the message list that receives streamed assistant text needs
    `role="log"` (or an `aria-live="polite"` container). A silent `<div>` that only auto-scrolls is a
    finding.
- **Loading/progress over a couple of seconds is announced.** A spinner with no `role="status"`/
  `aria-label`, or a long operation with no polite announcement of start/finish. (Determinate progress
  → `role="progressbar"` with value attrs.)
- **Right politeness.** Routine updates → `polite` (`role="status"`); only genuine errors/interruptions
  → `assertive` (`role="alert"`). Flag `aria-live="assertive"` on non-urgent updates (it interrupts).
- **The live region pre-exists.** In React, render the live-region element unconditionally and change
  its *content*; a region that's mounted at the same moment its content appears often isn't announced.
  - **Watch the container, not just the region.** The usual way this breaks is that the `role="status"`
    is written correctly but sits inside a wrapper that itself unmounts at zero state — a toolbar that
    does `if (!count) return null`, or a parent rendering `{count > 0 && <Toolbar/>}`. The region then
    mounts *with* its first content, so the **first** change — the most important one — is silent, while
    later ones announce fine and make it look like it works. Keep the region mounted outside whatever
    appears and disappears, and let its text go empty instead. Repeating identical text won't re-announce
    either, so clear it between messages if the same value can occur twice in a row.
- **Don't move focus to a toast/alert.** Flag `.focus()` on a transient notification — announce via the
  live region instead; moving focus is disorienting.
- **Auto-dismiss has a control.** A toast that disappears on a timer with no pause/dismiss can be missed
  (also 2.2.1).

## Deferral note
Toast/notification libraries and `Toast`/`Alert`/`Message`/`FieldError`-style components from any
component library usually manage their own `aria-live`/`role` internally. Per review-scope: if the
announcement is delegated to such an imported/visible-clean primitive, **don't** demand a second live
region — that's a false positive. Flag only ad-hoc `setState`-driven updates with no live region, or a
wrapper that strips the primitive's role.
