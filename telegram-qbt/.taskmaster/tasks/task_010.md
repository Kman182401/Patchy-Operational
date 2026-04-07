# Task ID: 10

**Title:** Move plex_organizer.py into the package

**Status:** done

**Dependencies:** None

**Priority:** medium

**Description:** Move plex_organizer.py from the telegram-qbt/ root into patchy_bot/plex_organizer.py. Update the import in bot.py from 'from plex_organizer import organize_download' to 'from .plex_organizer import organize_download'. Update the backward-compat shim in qbt_telegram_bot.py if it re-exports anything from plex_organizer.

**Details:**

plex_organizer.py (336 lines) currently lives outside the patchy_bot/ package at the telegram-qbt/ root. bot.py imports it via bare 'from plex_organizer import organize_download' which only works when the working directory is telegram-qbt/. Moving it into the package makes the import path-independent and consistent with the rest of the codebase. The file contains the organize_download function that moves completed downloads into the Plex folder structure (Movies/ or TV/ShowName/Season XX/).

**Test Strategy:**

Run existing test suite — must pass. Import patchy_bot.plex_organizer from any directory and verify it loads without error. Deploy and verify a completed download gets organized into Plex folders.
