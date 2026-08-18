# Signoff dashboard visual QA

## Comparison target

- Source visual truth: user-provided Signoff dashboard screenshot in the implementation request, captured at 1536 × 1024.
- Implementation screenshot: [`dashboard-reference-implementation.jpg`](/Users/darce/SDA/dashboard-reference-implementation.jpg)
- Route: `/dashboard`
- CSS viewport: 1536 × 1024
- Screenshot pixels: 1536 × 1024
- Device pixel ratio: 1
- Density normalization: none required
- State: dark theme, English locale, `Acme Inc.`, `Release 2.3`, Overview tab, `REQ-041` drawer open.

## Evidence

The source screenshot and the browser-rendered implementation were reviewed at the same viewport and interaction state. The full-view comparison covered the fixed 202px sidebar, 62px topbar, release header, six tabs, four metric cards, requirements/status row, lower activity and verification cards, and the 384px persistent requirement drawer.

Focused comparison regions covered:

- Sidebar logo, grouped navigation, active Dashboard state, and account footer.
- Release header, breadcrumb, status pill, search, Share button, and context menu.
- Metric cards, mini radial progress, coverage area chart, and semantic status colors.
- Requirements table selection, coverage bars, adjacent status card, and drawer proportions.
- Verification donut, legend, drawer tabs, acceptance criteria, and CTA.

## Findings

- [P2 — fixed] The Recharts donut inherited the overlay positioning rule and rendered its SVG off-center. The chart container was isolated from the center-label overlay and the center label was positioned independently.
- [P3 — accepted] The reference screenshot contains photographic avatars that were not available as source assets in the workspace. The implementation uses local, deterministic avatar tokens with initials so the layout remains stable and no external image dependency is introduced.

## Comparison history

1. Initial implementation: layout, typography, palette, sidebar, drawer, table and charts aligned; the lower donut had a vertical positioning mismatch.
2. Fix applied in `app/reference-dashboard.css`: the Recharts container now uses its own absolute layer and the label overlay is independently centered.
3. Post-fix browser capture: donut is fully visible and centered within the verification card; drawer and lower cards remain within the 1536 × 1024 viewport.

## Interaction QA

- Selected `REQ-057`, closed the drawer, reopened `REQ-041`, and verified drawer navigation.
- Switched Overview/Requirements tabs and verified active-tab state.
- Filtered with the global search input and restored the full list.
- Opened and closed the release context menu.
- Switched English → Spanish → English and verified `html[lang]` and translated content.
- Switched dark → light → dark and verified the global theme token and surface change.
- Used the new topbar theme icon beside the notification bell; light mode selected the transparent light-background wordmark and preserved the 1536 × 1024 drawer geometry.
- Loaded `/`, `/dashboard`, and `/review/demo-review-token` in fresh browser tabs without runtime errors.
- Fresh dashboard browser session reported zero console errors.
- Recharts charts use measured container dimensions and reported no zero-size warnings during dashboard reloads and project switches.

Responsive validation:

- 1280 × 900: full sidebar, persistent right drawer, no horizontal overflow.
- 1024 × 900: compact icon sidebar, drawer moves below the workspace, no horizontal overflow.
- 768 × 900: compact icon sidebar, two-row topbar, reduced table columns, no overlap or horizontal overflow.
- 390 × 844: mobile navigation strip, two-row topbar, two-column metric cards, stacked content and drawer, no horizontal overflow.

## Technical checks

- `npx tsc --noEmit`: passed
- `npx eslint app components --quiet`: passed
- `npm run build`: passed
- `/usr/bin/python3 -m pytest -q` in `apps/api`: passed (11 tests)
- Transparent brand assets: alpha channel verified; favicon and Apple icon use the transparent mark.

## Follow-up polish

- Replace initials avatars with approved portrait assets if the original reference portraits become available.

final result: passed
