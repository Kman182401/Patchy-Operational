# Task ID: 7

**Title:** Extract the remove handler

**Status:** done

**Dependencies:** 2 ✓, 3 ✓

**Priority:** high

**Description:** Move all _remove_* methods (~45 methods, lines 3257-4121) plus _cleanup_qbt_for_path, _delete_remove_candidate, _delete_remove_candidates, _remove_runner_job, _remove_build_job_verification, _remove_attempt_plex_cleanup into patchy_bot/handlers/remove.py. Register all rm:* callback prefixes (18 prefixes). Update bot.py on_text remove flow branches to delegate.

**Details:**

The remove system handles: fuzzy search matching against Plex library, hierarchical browse (root -> show -> season -> episode), multi-select with toggle, path safety validation (traversal guard, symlink rejection, depth validation), disk deletion, qBT torrent cleanup, Plex metadata cleanup with retry, and the background remove runner job. Methods span approximately lines 3257-4121 (~865 lines) plus the runner at lines 2316-2405. The _remove_runner_job processes due remove_jobs from the store with exponential backoff retry.

**Test Strategy:**

All 20 delete-safety tests must pass. All existing remove UI tests must pass. Deploy and test: /remove search flow, browse library, multi-select, confirm delete, Plex cleanup notification.

## Subtasks

### 7.1. Extract remove search and candidate matching

**Status:** pending  
**Dependencies:** None  

Move _remove_roots, _path_size_bytes, _remove_match_score, _find_remove_candidates (~L3257-3369) into handlers/remove.py.

### 7.2. Extract remove selection state management

**Status:** pending  
**Dependencies:** None  

Move _remove_selected_path through _remove_effective_candidates (~L3394-3464) — toggle, count, total size, effective candidates.

### 7.3. Extract remove UI builders

**Status:** pending  
**Dependencies:** None  

Move all remaining _remove_*_keyboard and _remove_*_text methods not already in ui/ from task 3.

### 7.4. Extract remove library browse system

**Status:** pending  
**Dependencies:** None  

Move _remove_library_items, _remove_show_children, _remove_season_children, _extract_movie_name, _extract_show_name, _remove_group_tv_items, _remove_show_group_children (~L3636-3907).

### 7.5. Extract remove execution and runner

**Status:** pending  
**Dependencies:** None  

Move _cleanup_qbt_for_path, _delete_remove_candidate, _delete_remove_candidates, _remove_runner_job, _remove_build_job_verification, _remove_attempt_plex_cleanup. Register rm:* callbacks.

### 7.6. Wire remove handler and verify all delete-safety tests pass

**Status:** pending  
**Dependencies:** None  

Replace bot.py remove methods with delegation. Run full test suite — all 20 delete-safety tests and remove UI tests must pass.
