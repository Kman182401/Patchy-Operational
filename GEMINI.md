# Telegram Bot + Mini App Rules

## Product direction
- Use native bot chat only for quick actions, confirmations, alerts, and compact navigation.
- Use the Mini App for any flow that benefits from richer layout, previews, filtering, settings, dashboards, or visual hierarchy.
- Prefer editing existing bot messages/keyboards over sending replacement messages when navigating settings or paginated results.

## Telegram UX rules
- Default to mobile-first layouts.
- Respect Telegram theme colors and safe-area variables.
- Avoid dense layouts.
- Prefer obvious primary actions and very few competing buttons.
- Keep button labels short and action-oriented.
- Always design for dark mode first and verify light mode second.
- Avoid decorative motion unless it improves clarity.

## Design system rules
- Use one spacing scale consistently.
- Use one card style consistently.
- Use one button hierarchy consistently.
- Use one icon set consistently.
- Keep all screens visually aligned with Telegram-native tone rather than trying to mimic iOS/Material exactly.

## Implementation rules
- Build Mini App UI as components first, pages second.
- Never merge visual work without Playwright screenshot checks.
- Prefer Storybook stories for reusable UI states.
- Treat visual regressions as real failures.
- Never read secrets or env files unless explicitly needed.
