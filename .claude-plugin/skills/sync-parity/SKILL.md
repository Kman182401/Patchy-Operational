---
name: sync-parity
description: Audit movie/TV parity across Patchy's search and add flows. Use after changing shared search UX, result rendering, callback routing, or add/download flows that should stay aligned across movie and TV behavior. Do not use when the difference is intentionally domain-specific, such as TV episode scheduling versus movie release gating.
---

# Movie / TV Feature Parity Audit

Compare the Movie and TV code paths across the bot and flag any feature that exists in one but not the other. This is a critical check — the project rule is that any change to Movie Search must also be applied to TV Search and vice versa.

## Agent Delegation

This skill delegates to the following agents during execution. Always use these agents — do not implement inline what an agent can handle.

- **Primary:** Delegate search pipeline parity analysis (filters, sorting, result formatting) to the `search-download-agent` (parallel with UI review).
- **Secondary:** Delegate UI parity analysis (keyboards, buttons, callbacks, navigation) to the `ui-agent` in parallel with the search analysis.

## What to compare

Read these files and trace both the movie and TV paths through each:

1. **`/home/karson/Patchy_Bot/telegram-qbt/patchy_bot/handlers/search.py`** — shared search filtering, ranking, rendering
2. **`/home/karson/Patchy_Bot/telegram-qbt/patchy_bot/handlers/download.py`** — add/download completion flow
3. **`/home/karson/Patchy_Bot/telegram-qbt/patchy_bot/handlers/commands.py`** — command-surface entry points and active/status UI
4. **`/home/karson/Patchy_Bot/telegram-qbt/patchy_bot/handlers/schedule.py`** — TV schedule acquisition and movie release-track differences
5. **`/home/karson/Patchy_Bot/telegram-qbt/patchy_bot/ui/text.py`** — shared user-facing wording
6. **`/home/karson/Patchy_Bot/telegram-qbt/patchy_bot/ui/keyboards.py`** — inline keyboard layout patterns
7. **`/home/karson/Patchy_Bot/telegram-qbt/patchy_bot/bot.py`** — callback dispatch and flow wiring

## What to look for

For each feature area, check if movie and TV paths have equivalent:

- **Search filters** — same filter flags available for both?
- **Result formatting** — same display format (size, seeds, quality badge)?
- **Add flow** — same confirmation steps, same keyboard layout?
- **Category routing** — correct save paths for each media type?
- **Quality detection** — same regex patterns applied to both?
- **Pagination** — same page size, same navigation buttons?
- **Error handling** — same error messages and fallback behavior?
- **Keyboard buttons** — same button labels and layout patterns?
- **Intent boundaries** — are differences intentional because TV uses episodic schedule logic while movies use release tracking?

## Intentional differences

Do not flag these as parity bugs by default:

- TV episode auto-tracking in `schedule_tracks`
- Movie release-date tracking in `movie_tracks`
- Plex inventory logic that is inherently TV-episode-specific

## Report format

### Parity matches (brief)
List features that are correctly mirrored — just the feature name, one line each.

### Parity gaps (detailed)
For each gap found:
- **Feature**: what's different
- **Movie path**: what the movie side does (file:line)
- **TV path**: what the TV side does (or "missing")
- **Impact**: what a user would experience
- **Fix**: specific code change needed

### Verdict
- **In sync** — no gaps found
- **N gaps found** — list them with severity (cosmetic / functional / broken)
