# Task ID: 5

**Title:** Extract the download tracking handler

**Status:** done

**Dependencies:** 2 ✓, 3 ✓

**Priority:** medium

**Description:** Move download/progress methods into patchy_bot/handlers/download.py: _progress_bar, _completed_bytes, _is_complete_torrent, _format_eta, _state_label, _eta_label, _render_progress_text, _start_progress_tracker, _start_pending_progress_tracker, _attach_progress_tracker_when_ready, _stop_download_keyboard, _tracker_send_fallback, _safe_tracker_edit, _track_download_progress, _completion_poller_job, _is_direct_torrent_link, _result_to_url, _extract_hash, _resolve_hash_by_name, _vpn_ready_for_download, _do_add. Register stop: callback prefix.

**Details:**

The download handler manages: VPN readiness checks, torrent addition via QBClient, per-download progress tracking asyncio Tasks, the completion poller job (60s interval), and the stop: callback. Methods span approximately lines 567-987 in bot.py (~420 lines) plus download helpers at lines 4781-4963. The _completion_poller_job is registered as a repeating job in _post_init and calls plex_organizer.organize_download on completion.

**Test Strategy:**

Add at least 5 new unit tests for _progress_bar, _format_eta, _is_complete_torrent with known inputs. Deploy and test: start a download, verify progress bar updates, verify completion notification fires.
