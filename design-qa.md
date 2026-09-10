# Discover redesign QA

## Comparison target

- Source visual truth: `C:\Users\Halal\.codex\generated_images\01a08846-44f3-7a93-8050-0d8fa4efdf38\exec-2bdf49bf-7cab-42ea-ab60-2e55ca9c97b4.png`
- Implementation: browser-rendered Discover view at `http://localhost:8091/`.
- Viewport/state: desktop, unauthenticated Discover view; hero, three entry choices, privacy boundary and process visible.
- Browser evidence: captured in the active in-app-browser verification turn after the hero asset route was fixed. No console warnings or errors were recorded.

## Findings and fixes

- [P1, fixed] The approved hero asset initially rendered as alternate text because the static-file allowlist did not include it. Added the exact image route in `server.py`; a second browser capture displayed the Toronto image correctly.
- [P2, fixed] A public binary image was initially blocked by the publication scanner. The scanner now permits only this specifically reviewed file at its pinned SHA-256 digest; altered or unreviewed binary assets still fail the release gate.
- [P2, fixed] The old Discover page made the product read as generic property research. The new hierarchy leads with deal introduction, then gives three role-specific paths and a four-step controlled workflow.

## Fidelity surfaces

- Fonts and typography: retained the existing editorial serif for product hierarchy and compact sans-serif UI text; the new hero remains readable without crowding.
- Spacing and layout rhythm: desktop uses a split hero and three equal decision columns; the responsive CSS stacks the hero, cards and process sequence below 740px.
- Colors and visual tokens: retained the existing forest green, warm ivory, muted teal, line, and focus-ring tokens.
- Image quality and asset fidelity: generated Toronto/GTA hero photograph is public-approved by digest and correctly served; no private property imagery is used.
- Copy and content: removed generic “property intelligence” framing and replaced it with mandate, counterparty, consent and evidence-room language. No claims of returns, custody, live capital movement or legal clearance were added.

## Primary interactions tested

- `Submit a mandate` routes an unauthenticated visitor to workspace creation.
- The page fetches public passports, filters them by search/type/city, and keeps the existing controlled data-room route intact.
- Browser console check: no errors or warnings.

## Follow-up polish

- Run a device-specific mobile browser capture on a physical/mobile-emulation surface before a broad public campaign.

final result: passed
