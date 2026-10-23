# Signoff design system

## Direction

Signoff is an operational workspace for proving delivery. The interface should feel calm, precise and reviewable: clear hierarchy, meaningful density and visible state transitions. Visual decoration must never compete with the evidence or the decision a user is making.

## Typography

- Geist Sans is the only product font.
- Use 640–700 for page titles, 600 for section headings and 400–520 for supporting copy.
- Use tabular numbers for metrics, dates and percentages.
- Use JetBrains Mono only for requirement IDs, hashes and technical identifiers.
- Avoid excessive uppercase labels; reserve them for navigation groups and compact metadata.

## Iconography

- Lucide is the single icon source.
- Use 16–18px icons in controls and 20–22px icons for major empty states.
- Use a consistent stroke width between 1.5 and 1.7.
- Never use emoji, Unicode symbols or CSS drawings as interface icons.
- Every icon-only action needs an accessible label and a visible hover/focus state.

## Surfaces and spacing

- Use the navy/indigo Signoff palette in dark mode and cool white surfaces in light mode.
- Prefer one strong container with internal dividers over a grid of decorative cards.
- Shared radii are 7px for controls, 10px for cards and 14px for larger workspace sections.
- Use the spacing scale in `design-system.css`: 4, 8, 12, 16, 20 and 24px.
- Use shadows only to establish elevation or separate a drawer; borders carry most of the structure.

## Interaction

- Hover states should clarify what is actionable.
- Loading, empty, error, success and permission-denied states must be intentional.
- Motion is short and purposeful: materialize content, move a drawer, confirm an action. Respect reduced-motion preferences.
- Destructive or consequential actions require confirmation and a recoverable error message.

## Component rules

Prefer the shared workspace patterns already present in the app:

- `MetricCard` for a single decision-relevant metric;
- `StatusBadge`/`reference-pill` for state;
- `DataTable`/requirements rows for dense reviewable data;
- `SidePanel`/requirement drawer for contextual detail;
- `EmptyState` for missing data;
- `CommandSearch` patterns for global search and filters.

New pages should consume the same tokens and primitives instead of adding a parallel visual language.
