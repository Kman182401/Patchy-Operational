---
name: sync-parity
description: Check that Movie and TV search features have matching functionality. Use when the user says "check parity", "sync parity", "movie tv parity", "compare movie and tv", or after making changes to search, callback, navigation, or add-flow code that touches either movie or TV paths.
---

# Movie / TV Feature Parity Audit

Compare the Movie and TV code paths across the bot and flag any feature that exists in one but not the other. This is a critical check — the project rule is that any change to Movie Search must also be applied to TV Search and vice versa.

## What to compare

Read these files and trace both the movie and TV paths through each:

1. **`/home/karson/Patchy_Bot/telegram-qbt/patchy_bot/handlers/_search.py`** — Search command handling
2. **`/home/karson/Patchy_Bot/telegram-qbt/patchy_bot/handlers/_callbacks.py`** — Callback routing for add flows, media choice
3. **`/home/karson/Patchy_Bot/telegram-qbt/patchy_bot/handlers/_navigation.py`** — Pagination and result display
4. **`/home/karson/Patchy_Bot/telegram-qbt/patchy_bot/search_chat.py`** — Natural language search intent parsing
5. **`/home/karson/Patchy_Bot/telegram-qbt/patchy_bot/common.py`** — Shared utilities (quality detection, formatting)
6. **`/home/karson/Patchy_Bot/telegram-qbt/patchy_bot/ui.py`** — UI state and keyboard building
7. **`/home/karson/Patchy_Bot/telegram-qbt/qbt_telegram_bot.py`** — Legacy monolith (runtime file)

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
- **Natural language parsing** — does search_chat handle both "find movie X" and "find show X" equivalently?

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
