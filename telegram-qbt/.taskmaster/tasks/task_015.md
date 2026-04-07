# Task ID: 15

**Title:** Command Center manage downloads sub-page

**Status:** done

**Dependencies:** None

**Priority:** medium

**Description:** Replace individual per-download cancel buttons on Command Center with single Manage Downloads button linking to a dedicated sub-page.

**Details:**

Changed command_center_keyboard() to show count button. Added manage_downloads_keyboard() and dl:manage callback handler. Increased download tuple limit from 5 to 10. Updated 5 DummyBot classes in tests.

**Test Strategy:**

All 462 existing tests pass after adding _on_cb_dl_manage to DummyBot classes.
