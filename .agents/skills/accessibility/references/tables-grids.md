# Tables & data grids (WCAG 1.3.1 A; keyboard 2.1.1 A)

Outcome: **tabular data is programmatically a table, and interactive grids are operable by keyboard.**
Apply `review-scope.md` — review a hand-rolled table/grid or a wrapper that breaks structure; defer an
imported grid primitive's internals (review its call-site: does it get an accessible name, correct
column meta, etc.).

## Static/semantic tables

- **Header cells are real headers.** Flag a `<td>` styled and used as a header — the data then has no header
  to associate with, so a screen reader reads values with no idea what column they're in. (WCAG 1.3.1 A)
  - A missing `scope` is only a finding where the association is genuinely ambiguous: multi-level headers, or
    a table carrying **both** row and column headers. A simple table with one header row associates
    implicitly, so demanding `scope` on every `<th>` is high-volume noise for no user benefit.
- **An accessible name helps but isn't required.** `<caption>` / `aria-label` is worth a best-practice note
  when several tables share a page and nothing distinguishes them — no A/AA criterion mandates a caption, so
  don't report its absence as a failure.
- **Complex tables wire headers.** Multi-level headers need `headers`/`id` linkage.
- **Layout tables carry no data semantics** (no `<th>`/`scope`); and `role="presentation"` isn't slapped
  on a table that actually conveys relationships.
- **List/definition content uses the right element** (don't fake a key/value grid with bare `<div>`s).

## Interactive grids (`role="grid"`/`treegrid`)

- **`role="grid"` implies keyboard grid nav.** Flag `role="grid"` on a static data table (should be a
  plain table) — grid role promises arrow-key cell navigation you must then actually provide. Conversely
  a genuinely interactive grid needs roving tabindex / arrow keys.
- **Sortable column headers are keyboard-operable and expose sort state.** Flag a sort trigger that's a
  click-only `<div>`/`<span>` (or an inner node) with no keyboard path, or headers where only one column
  is focusable. *Failure:* keyboard users can't sort. Expose `aria-sort` on the active column (only one).
  - **Caveat (avoid a false positive):** some grids implement sort via a *custom* keyboard-nav context
    (roving focus on the `<th>` + Enter → sort) rather than a native control. If you can see that the
    header is reachable and Enter triggers sort, it's **operable → no finding**, even if the visible
    click target is a `<div>`. Only flag when there is genuinely no keyboard path to the sort action.
- **Row selection controls have names** (`aria-label="Select row {n}"` / "Select all rows"), and are
  reachable.
- **Hidden/responsive columns preserve header context** for the data that remains.
