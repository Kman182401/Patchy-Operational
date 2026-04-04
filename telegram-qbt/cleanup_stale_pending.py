#!/usr/bin/env python3
"""
One-time migration script to clean up stale pending episodes from schedule_tracks.

This script removes episodes from pending_json that are no longer missing
(e.g., already downloaded or released) and are older than the stale threshold.

Usage: python3 cleanup_stale_pending.py
"""

import sqlite3
import json
from datetime import datetime, timezone, timedelta
import time

def now_ts() -> int:
    return int(time.time())

def format_local_ts(ts: int) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

def main() -> None:
    # Safety: warn if the bot service is currently running
    import subprocess
    try:
        result = subprocess.run(
            ["systemctl", "is-active", "--quiet", "telegram-qbt-bot.service"],
            capture_output=True,
        )
        if result.returncode == 0:
            print("⚠️  WARNING: telegram-qbt-bot.service is running.")
            print("   Running this script while the bot is active may cause state inconsistency.")
            resp = input("   Continue anyway? [y/N] ").strip().lower()
            if resp != "y":
                print("Aborted.")
                return
    except Exception:
        pass  # systemctl not available — skip check

    conn = sqlite3.connect("state.sqlite3")
    conn.execute("PRAGMA busy_timeout = 5000")
    cursor = conn.cursor()

    # Get all tracks
    cursor.execute("SELECT track_id, pending_json, auto_state_json FROM schedule_tracks")
    rows = cursor.fetchall()

    total_tracks = len(rows)
    total_stale_removed = 0
    tracks_modified = []

    for track_id, pending_str, auto_state_str in rows:
        if not pending_str or not isinstance(pending_str, str):
            continue

        try:
            pending = json.loads(pending_str)
            if not pending or not isinstance(pending, list):
                continue
        except json.JSONDecodeError:
            continue

        # Calculate stale threshold (3 hours)
        stale_threshold = now_ts() - (3 * 3600)

        # Load auto_state to get retry_codes
        auto_state = {}
        if auto_state_str and isinstance(auto_state_str, str):
            try:
                auto_state = json.loads(auto_state_str)
            except json.JSONDecodeError:
                pass

        retry_codes = auto_state.get("retry_codes") or {}

        # Identify stale episodes
        stale_episodes = []
        for code in pending:
            if code in retry_codes:
                # Skip if still in retry_codes (recently attempted)
                added_at = retry_codes.get(code)
                if added_at and int(added_at) >= stale_threshold:
                    continue
                stale_episodes.append(code)

        if stale_episodes:
            # Remove stale episodes from pending_json
            new_pending = [code for code in pending if code not in stale_episodes]
            updated_auto_state = auto_state.copy()
            # Remove stale episodes from retry_codes
            for code in stale_episodes:
                updated_auto_state.setdefault("retry_codes", {}).pop(code, None)

            # Update the database
            cursor.execute(
                "UPDATE schedule_tracks SET pending_json = ?, auto_state_json = ? WHERE track_id = ?",
                (json.dumps(new_pending, ensure_ascii=False), json.dumps(updated_auto_state, ensure_ascii=False), track_id),
            )

            tracks_modified.append({
                "track_id": track_id,
                "removed": stale_episodes,
                "remaining": new_pending,
            })
            total_stale_removed += len(stale_episodes)

    # Commit changes
    conn.commit()

    # Summary
    print(f"\n{'=' * 70}")
    print(f"One-time Pending Cleanup Migration")
    print(f"{'=' * 70}")
    print(f"\nTotal tracks checked: {total_tracks}")
    print(f"Tracks with stale entries: {len(tracks_modified)}")
    print(f"Total stale episodes removed: {total_stale_removed}")

    if tracks_modified:
        print(f"\n{'-' * 70}")
        print(f"Details:")
        print(f"{'-' * 70}")
        for track in tracks_modified:
            print(f"\nTrack: {track['track_id']}")
            print(f"  Removed episodes: {', '.join(track['removed'])}")
            print(f"  Remaining: {', '.join(track['remaining'])}")

    print(f"\n{'=' * 70}")
    print(f"Migration complete. Schedule runner will clean up remaining stale")
    print(f"entries automatically during normal reconciliation cycles.")
    print(f"{'=' * 70}\n")

    conn.close()

if __name__ == "__main__":
    main()