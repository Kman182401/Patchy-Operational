---
name: visual-regression-reviewer
description: Reviews Playwright screenshot diffs, Chromatic visual diffs, and Storybook snapshot changes — decides whether each change is intentional or a regression. Invoke this skill whenever Claude finishes editing UI code and screenshots have changed, when a Playwright visual test fails, when the user wants to review a Chromatic build, when deciding whether to update baseline snapshots, or when something "looks off" after a merge. Even if the user says "check the screenshots" or "are these visual changes OK" or "Playwright is failing", invoke this skill to do the review systematically.
---

# Visual Regression Reviewer

Your job is to look at visual diffs and make a clear call: **intentional change** or **regression**. Don't hedge. Give a verdict with a reason and a specific action.

## Decision process

For each changed screenshot:

1. **Identify what changed** — layout shift, color change, size/spacing, missing element, new element, text change
2. **Match to a code change** — was this change made intentionally by the current PR/commit?
3. **Apply the regression signals** — check the list below
4. **Verdict** — PASS, FAIL, or REVIEW

## Output format

For each file, output:

```
File: path/to/screenshot.png
Status: PASS | FAIL | REVIEW
Change: <one-line description of what visually changed>
Reason: <why it's pass/fail/review>
Action: Accept baseline | Fix before merge | Needs human judgment
```

Bundle multiple PASS items together if they share the same reason (e.g., "all PASS — reflects intentional button label update").

## PASS — intentional change

A change is PASS when:
- It directly corresponds to a code change in the current branch (new component, edited text, updated color via theme variable)
- It improves visual hierarchy, spacing, or readability
- It aligns with Telegram's design system (uses `--tg-theme-*` variables, respects safe areas, correct typography)
- It's a pixel-level anti-aliasing or subpixel rendering difference between OS/browser versions — these are not meaningful

## FAIL — regression

A change is FAIL when any of these are true:

**Color issues**
- A hardcoded hex color is now visible where a theme variable should be used
- White or light background appears in dark colorScheme (dark mode broken)
- Text is invisible or very low contrast against background
- Button color doesn't match `--tg-theme-button-color`

**Layout issues**
- Content touches the screen edge without padding (safe-area inset missing)
- An element is clipped or partially hidden under status bar / home indicator
- Elements overlap unexpectedly
- A previously visible element is now gone (not hidden intentionally)
- Layout breaks below 390px viewport width

**Touch target issues**
- A button or tappable row is visually shorter than 44px

**Typography issues**
- Text truncates without ellipsis where it should wrap or use ellipsis
- Text overflows its container
- Font appears as a fallback/system serif where sans-serif is expected

**Navigation issues**
- A back button, close button, or primary action button is missing from a screen where it was present before
- The MainButton (Telegram native) is hidden when it should be shown

## REVIEW — needs human judgment

Mark as REVIEW when:
- The change is significant but not clearly tied to a specific code change you can identify
- The animation or transition behavior changed (screenshots can't capture this)
- A component looks different but you can't tell if it was intended without context from the developer

## Telegram-specific regression signals

These are the most common ways Mini App UI breaks in Telegram — check these first:

| Signal | Symptom | Verdict |
|---|---|---|
| Hardcoded color | White/gray element in dark mode | FAIL |
| Missing `viewport-fit=cover` | Content clipped on iOS notch | FAIL |
| Missing `env(safe-area-inset-bottom)` | Content behind home indicator | FAIL |
| Missing `var(--tg-content-safe-area-inset-bottom)` | Content under Telegram's bottom bar | FAIL |
| Touch target < 44px | Tiny tappable area | FAIL |
| System font not loading | Serif fallback rendered | FAIL |
| Text overflow without ellipsis | Overflowing text | FAIL |
| >3 buttons in one row at 390px | Buttons cramped/misaligned | FAIL |

## Playwright workflow

```bash
# View the HTML report (most useful — side-by-side diff viewer)
npx playwright show-report

# Re-run failed tests only
npx playwright test --last-failed

# Accept ALL screenshot changes (only after reviewing — don't do this blindly)
npx playwright test --update-snapshots

# Update snapshots for one specific test file
npx playwright test path/to/test.spec.ts --update-snapshots
```

When a Playwright visual test fails, the HTML report shows three images: **Expected** (baseline), **Actual** (current run), **Diff** (highlighted pixels). Always look at all three — the diff alone doesn't tell you if the change is acceptable.

## Chromatic workflow

- Go to the Chromatic build URL in the PR
- Review diffs in the "Changes" tab — each story shows baseline vs. current
- **Accept** = intentional, updates baseline for future runs
- **Deny** = regression, blocks merge
- Stories to always keep in Storybook for reliable coverage:
  - Default state
  - Dark mode (`colorScheme: 'dark'`)
  - Light mode (`colorScheme: 'light'`)
  - Mobile viewport (390×844)
  - Long content / edge case (overflow, empty state, loading state)

## Storybook snapshot conventions

For this project, each new UI component should have at minimum these stories:

```ts
export const Default: Story = {};
export const DarkMode: Story = {
  parameters: { tgColorScheme: 'dark' }
};
export const LightMode: Story = {
  parameters: { tgColorScheme: 'light' }
};
export const MobileViewport: Story = {
  parameters: { viewport: { defaultViewport: 'iphone14' } }
};
```

A visual regression caught in Storybook is infinitely cheaper than one found in production.

## When all screenshots pass

After a clean visual review, state:

```
Visual review: PASS — N files checked, no regressions found.
Baseline update recommended for: [list any intentional changes that need snapshot updates]
```

And explicitly confirm the Playwright baseline is up to date before marking the task done.
