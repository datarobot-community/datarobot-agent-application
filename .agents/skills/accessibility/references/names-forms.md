# Names, roles, ARIA, images, forms & links

Outcome-phrased. Remember (from review-scope.md): **names can be computed** (`aria-label={t()}`,
variables, `sr-only` child text, associated `<label>`) — those are NOT missing. `placeholder`-as-label
IS a finding; `title`-only is **not** — the control is named, so it's a best-practice note (see below).

## Accessible name / role / value (WCAG 4.1.2 A)

- **Every interactive control has an accessible name.** Flag an icon-only button/link/menu-trigger with
  no text, `aria-label`, `aria-labelledby`, or hidden child text. *Failure:* screen reader announces
  only "button". (WCAG 4.1.2 A — for a *link*, also 2.4.4 Link Purpose; 2.4.4 is about links, so don't
  attach it to a button.)
  - A `title`-**only** name is **not a finding.** The control *is* named — `title` feeds the accessible-name
    computation, so 4.1.2 is satisfied. What's wrong with it is discoverability: hidden until hover,
    unreliable on touch and speech input. That's real but it is best practice, not an A/AA criterion, so
    recommend an explicit `aria-label` as a *best-practice note* (SKILL.md → Best-practice notes) with the
    severity slot empty. Keep the finding for a control with no name at all.
- **ARIA is valid and honest.** Flag: `aria-*` referencing a non-existent id (`aria-labelledby`/
  `-controls`/`-describedby`); invalid role or attribute value; a required parent/child role missing
  (`role="tab"` with no `tablist` ancestor, `option` with no `listbox`). *Failure:* AT gets a broken or
  contradictory tree. (also 1.3.1)
- **State is expressed and updated.** A custom toggle/disclosure/tab that never sets or never updates
  `aria-expanded`/`-pressed`/`-selected`/`-checked`. *Failure:* state changes are silent.
- **Name doesn't wipe content / duplicate the role.** `aria-label` on a name-from-content element that
  hides meaningful child text; redundant `role="button"` on a `<button>`.
- **The name doesn't repeat the role in words** — *best-practice note, not a finding.*
  `aria-label="Delete button"`, `alt="Search icon"`, `aria-label="Settings link"`. AT announces the role
  itself, so the user hears "Delete button, button" — noise on every pass over the control. Recommend
  dropping the role word, with the severity slot empty and **no SC cited as failed**: 2.4.6 asks that a
  label describe topic or purpose, and "Delete button" does. (A functional image whose `alt` describes
  the *picture* instead of the *action* is a different thing and stays a 1.1.1 A finding — see Images.)
- **Nothing is announced twice.** The finding is a *named* decoration inside an already-named control: an
  `<img alt="Delete">` or `<svg role="img" aria-label="Delete">` (or an icon component whose props give it a
  `title`/`alt`) sitting inside a `<button>` that also has text or an `aria-label` — the user hears "Delete
  Delete, button". Same for an `alt` that repeats the visible caption or link text right beside it. The fix
  is to silence the decoration (`alt=""` / `aria-hidden="true"`), not to rename the control. (WCAG 1.1.1 A)
  - **Do not flag a bare `<svg>`/icon component with no name of its own.** It contributes nothing to the
    accessible name in the first place, so there is no double announcement — adding `aria-hidden="true"` is
    defensive best practice, not a WCAG failure, and flagging every icon inside every labelled button is the
    fastest way to get this skill muted.
- **Nothing nested-interactive:** button-in-button, link-in-button, a link wrapping a button. Not
  `<h3><button>` — a heading *containing* a button is the standard accordion pattern and is correct.

## Images & non-text content (WCAG 1.1.1 A)

- **Informative images have meaningful `alt`;** decorative images have `alt=""`. Flag: missing `alt`;
  `alt` that is a filename / "image" / "photo"; `alt=""` on an image that is actually a link/button or
  conveys info; a functional image whose alt describes the picture instead of the action ("magnifying
  glass" vs "Search").
- **Complex images** (charts, diagrams, data-viz `<svg>`) need a text alternative / accessible name
  (`role="img"` + `aria-label`, or an adjacent description). Flag a data `<svg>` with no name.
- **Media has a text alternative.** Prerecorded speech in `<video>` needs captions (`<track kind="captions">`)
  (1.2.2 A) and an audio description or full text alternative (1.2.3 A); audio-only content needs a transcript
  and video-only content a transcript or described audio (1.2.1 A). Flag a media element shipped with no
  `<track>` and no adjacent transcript/description. You can only see whether an alternative *exists* — never
  claim an existing caption file is accurate or complete.
  - **At AA the transcript escape closes.** 1.2.3 lets a full text alternative stand in for audio
    description, but **1.2.5 AA requires the audio description itself** for prerecorded video. Don't clear
    a video that ships a transcript and no AD — that passes A and fails AA. (WCAG 1.2.5 AA)
- **Autoplaying sound has its own control.** Flag `autoPlay` on `<audio>`/`<video>` that is not `muted` and
  plays longer than 3 seconds without a pause/stop/volume control independent of the system volume.
  *Failure:* it talks over a screen reader, which is the one thing the user can't work around. (WCAG 1.4.2 A)

## Forms, labels & errors

- **Every input is labeled.** Flag an `<input>/<select>/<textarea>` with no associated `<label htmlFor>`,
  wrapping label, `aria-label`, or `aria-labelledby`. `placeholder` alone is not a label. (WCAG 3.3.2 A;
  4.1.2 A)
  - This applies **through a design-system/library wrapper** too (`<Search>`, `<Input>`, `<TextField>`,
    `<Combobox>`…): the control's *name* is the caller's responsibility, so a call-site that passes only
    `placeholder` and no name-supplying prop/label is a finding even when the wrapper's internals aren't
    visible — you don't need to see them to know the caller supplied no name. (See review-scope.md §2.)
- **Grouped controls are grouped.** Related radios/checkboxes need `<fieldset>`+`<legend>` (or
  `role="radiogroup"` + a group name). (WCAG 1.3.1 A)
- **Errors are identified in text and tied to the field.** Flag an error shown only by color/border, or
  error text not linked via `aria-describedby` + `aria-invalid`. *Failure:* SR users hear no error, or
  can't tell which field. (WCAG 3.3.1 A; 1.4.1 A; error suggestion 3.3.3 AA)
- **On submit-with-errors the user is told, one way or another.** Either focus moves to an error summary or
  the first invalid field, **or** the errors land in a live region. Flag only when *neither* exists — errors
  rendering silently below the fold while focus stays on the button are never perceived at all. Moving focus
  is the usual fix but isn't itself mandated by a criterion, so don't report "focus didn't move" as the
  failure. (WCAG 3.3.1 A; 4.1.3 AA)
- **Identity/payment/auth fields have `autocomplete`.** (WCAG 1.3.5 AA)
- **Consequential submissions are reversible, checked, or confirmed.** When a submit has legal, financial, or
  data-destroying consequences — deleting an account/dataset/deployment, placing an order, signing an
  agreement — at least one of these has to exist: an undo path, a validation/review step before commit, or an
  explicit confirmation the user must act on. Flag a destructive action wired straight to a single click with
  none of the three. *Failure:* one mis-hit destroys work with no recovery, and mis-hits are exactly what
  motor and low-vision users are more exposed to. (WCAG 3.3.4 AA)
  - Only when you can *see* that nothing guards it. The confirm step usually lives in the handler, a mutation
    hook, or a parent that opens a dialog — if that code isn't in front of you, this is unresolvable and the
    evidence contract says stay silent. Never flag a `onClick={handleDelete}` whose `handleDelete` you didn't
    read.
- (2.2) **Don't ask for the same information twice in one process.** Within a multi-step flow (wizard,
  checkout, onboarding), data the user already entered should be auto-populated or offered for selection
  rather than re-typed. Flag a later step that re-asks for something an earlier step in the same flow
  captured. *Failure:* users with memory or dexterity difficulties have to re-derive and re-key it.
  Exceptions: re-entry that is essential (password confirmation), a security check, or information no
  longer valid. (WCAG 3.3.7 A)
- (2.2) **Accessible authentication** — don't require memorization/transcription with no alternative;
  allow paste in code fields. (WCAG 3.3.8 AA)

## Link purpose & label-in-name

- **Link/button purpose is clear from its text (± context).** Flag "click here", "read more",
  "learn more", bare URLs, or identical link text pointing to different destinations with no
  distinguishing `aria-label`. (WCAG 2.4.4 A)
  - **2.4.4 is Link Purpose *In Context*, so check the context before flagging.** A "Read more" whose
    naming heading, list item, paragraph or table cell is programmatically its ancestor already conveys
    the purpose and conforms — the finding is a vague link with *no* such context, or several identical
    ones going to different places. (Requiring the link text to stand alone is 2.4.9, AAA.)
- **Visible label is in the accessible name.** If `aria-label` overrides visible text, it must contain
  that visible text (so speech-input users can activate it). (WCAG 2.5.3 A)
- **`<a>` vs `<button>`:** navigation → `<a href>`; action → `<button>`. Flag an `<a>` with no `href`
  used as a button, or a `<div onClick>` used as a submit. (WCAG 4.1.2 A)
