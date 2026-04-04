---
name: telegram-miniapp-builder
description: Builds and edits Telegram Mini App UI — components, pages, layout systems, theme integration, and WebApp API calls. Invoke this skill whenever you're creating or editing any screen or component inside the Mini App, implementing Telegram theme variables, handling safe-area insets, calling the WebApp JS API, wiring up MainButton/BackButton, making a layout mobile-first, or fixing dark mode. Even if the user says "add a screen for X" or "the Mini App looks broken on iPhone", invoke this skill before writing any frontend code — it prevents the most common Telegram-specific pitfalls.
---

# Telegram Mini App Builder

Building a Telegram Mini App requires three things that don't apply to regular web dev: **theme awareness**, **safe-area respect**, and **WebApp API integration**. Get any one wrong and the app looks broken or off-brand inside Telegram's shell.

## Project setup baseline

```html
<!-- Required in <head> -->
<script src="https://telegram.org/js/telegram-web-app.js"></script>
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
```

```js
// Required on app mount — tells Telegram the app is ready
window.Telegram.WebApp.ready();
window.Telegram.WebApp.expand(); // full-height by default
```

## Theme variables — never hardcode colors

Every color must come from Telegram's CSS variables. These update automatically when the user switches light/dark or applies a custom theme.

```css
/* Core palette */
background-color: var(--tg-theme-bg-color);
color: var(--tg-theme-text-color);
color: var(--tg-theme-hint-color);         /* secondary/muted text */
color: var(--tg-theme-link-color);

/* Buttons */
background-color: var(--tg-theme-button-color);
color: var(--tg-theme-button-text-color);

/* Surfaces */
background-color: var(--tg-theme-secondary-bg-color);   /* cards, input bg */
background-color: var(--tg-theme-section-bg-color);     /* grouped sections */
background-color: var(--tg-theme-header-bg-color);      /* top bars */

/* Semantic */
color: var(--tg-theme-accent-text-color);
color: var(--tg-theme-section-header-text-color);
color: var(--tg-theme-subtitle-text-color);
color: var(--tg-theme-destructive-text-color);          /* delete/danger */
```

**Never** use a hardcode like `color: #ffffff` or `background: #1c1c1e`. A user running a custom Telegram theme or light mode will get a broken, unreadable UI.

## Safe area layout — required for iOS notch/home-bar

```css
/* Global layout wrapper */
.app {
  padding-top: env(safe-area-inset-top);
  padding-left: env(safe-area-inset-left);
  padding-right: env(safe-area-inset-right);
  /* Bottom: compound inset for Telegram's content zone + OS home bar */
  padding-bottom: calc(
    env(safe-area-inset-bottom) +
    var(--tg-content-safe-area-inset-bottom, 0px)
  );
}

/* Sticky footers / fixed bottom bars */
.bottom-bar {
  padding-bottom: calc(
    env(safe-area-inset-bottom) +
    var(--tg-content-safe-area-inset-bottom, 0px) +
    12px
  );
}
```

Missing safe-area insets = elements hidden behind the iOS home indicator or clipped under the status bar.

## WebApp API reference

```js
const tg = window.Telegram.WebApp;

// Lifecycle
tg.ready();                        // signal app loaded
tg.expand();                       // request full height
tg.close();                        // dismiss mini app
tg.enableClosingConfirmation();    // ask before close if unsaved

// Send data back to the bot
tg.sendData(JSON.stringify({ action: 'add', id: 42 }));

// Theme & appearance
tg.colorScheme;                    // "dark" | "light"
tg.themeParams;                    // object with all theme values
tg.setHeaderColor('secondary_bg_color');
tg.setBackgroundColor('secondary_bg_color');

// Main button (primary CTA — bottom of screen)
tg.MainButton.setText('Add Torrent');
tg.MainButton.show();
tg.MainButton.onClick(() => handleSubmit());
tg.MainButton.showProgress();      // spinner while loading
tg.MainButton.hideProgress();
tg.MainButton.hide();

// Back button (top-left nav)
tg.BackButton.show();
tg.BackButton.onClick(() => router.back());
tg.BackButton.hide();

// Haptic feedback
tg.HapticFeedback.impactOccurred('light');    // light tap
tg.HapticFeedback.impactOccurred('medium');   // confirm
tg.HapticFeedback.notificationOccurred('success');
tg.HapticFeedback.notificationOccurred('error');

// User data (available without extra permission)
tg.initDataUnsafe.user;            // { id, first_name, username, ... }
```

Always prefer `MainButton` for primary actions rather than an in-app button at the bottom — it's native, theme-aware, and has built-in loading state.

## Mobile-first layout rules

- **Min touch target**: 44×44px for every interactive element. Use `min-height: 44px` on buttons and list rows.
- **Max content width**: 390px (iPhone 14 safe). Center content with `max-width: 390px; margin: 0 auto` if building for desktop fallback.
- **Spacing scale**: 4px base. Use 4, 8, 12, 16, 24, 32px. Nothing else.
- **Typography**: `font-family: system-ui, -apple-system, sans-serif`. Never import external fonts — they add latency and may not render in Telegram's WebView.
- **No hover-only interactions**: every action must be reachable by tap.
- **Bottom sheets > modals**: use `position: fixed; bottom: 0` slide-up patterns for overlays, not centered modals that break on small screens.

## Component standards

### Card
```css
.card {
  background: var(--tg-theme-secondary-bg-color);
  border-radius: 12px;
  padding: 12px 16px;
  /* No border — cards use bg contrast, not borders, in Telegram style */
}
```

### List row (for results, settings items)
```css
.list-row {
  display: flex;
  align-items: center;
  min-height: 44px;
  padding: 8px 16px;
  background: var(--tg-theme-bg-color);
  border-bottom: 0.5px solid var(--tg-theme-hint-color);
  opacity: 0.25; /* hint-color border at low opacity looks Telegram-native */
}
```

### Section header
```css
.section-header {
  font-size: 13px;
  font-weight: 400;
  color: var(--tg-theme-section-header-text-color);
  text-transform: uppercase;
  letter-spacing: 0.04em;
  padding: 8px 16px 4px;
}
```

## Dark mode: build dark first

Telegram users are majority dark-mode. Design the dark layout first, then verify light mode.

To test light mode during development:
```js
// Force light mode for testing (Telegram WebApp doesn't let you switch from within the app)
// Override CSS vars in a test build:
document.documentElement.style.setProperty('--tg-theme-bg-color', '#ffffff');
document.documentElement.style.setProperty('--tg-theme-text-color', '#000000');
```

Or use Telegram's test environment to launch the Mini App with a light theme.

## Playwright screenshot requirement

Per project rules, **never merge visual work without Playwright screenshot checks**.

Minimum coverage per screen:
1. Dark mode, default state
2. Light mode, default state
3. Mobile viewport (390×844 — iPhone 14)
4. Any edge-case state (empty list, loading, error)

```js
// playwright.config.js
use: {
  viewport: { width: 390, height: 844 },
}
```

Flag any screenshot where:
- A white element appears on a dark background (hardcoded color)
- Content is clipped at screen edges (missing safe-area)
- Any element's height is visually under 44px (tap target too small)
