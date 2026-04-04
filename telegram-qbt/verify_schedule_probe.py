#!/usr/bin/env python3
"""
Database-only verification for a tracked schedule entry.

This is a lightweight consistency check that does not hit qBittorrent or
metadata providers. It validates whether the persisted schedule state matches
the expected post-probe behavior for the current next episode.
"""

from __future__ import annotations

import json
import os
import sqlite3
import time
from pathlib import Path

TRACK_ID = os.getenv("SCHEDULE_TRACK_ID", "46b117e6")


def now_ts() -> int:
    return int(time.time())


def get_local_time() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())


def check(label: str, ok: bool, detail: str) -> int:
    status = "PASSED" if ok else "FAILED"
    icon = "✅" if ok else "❌"
    print(f"{icon} {label} {status}: {detail}")
    return int(ok)


def main() -> None:
    print(f"\n{'=' * 70}")
    print("Schedule Database Verification Test")
    print(f"{'=' * 70}")
    print(f"Run time: {get_local_time()}")
    print(f"Timestamp: {now_ts()}")
    print(f"{'=' * 70}\n")

    db_path = Path(__file__).resolve().parent / "state.sqlite3"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT track_id, pending_json, auto_state_json, last_probe_json "
        "FROM schedule_tracks WHERE track_id = ?",
        (TRACK_ID,),
    )
    row = cursor.fetchone()
    conn.close()

    if not row:
        raise SystemExit(f"ERROR: Track {TRACK_ID} not found")

    track_id, pending_str, auto_state_str, last_probe_str = row
    pending = json.loads(pending_str) if pending_str else []
    auto_state = json.loads(auto_state_str) if auto_state_str else {}
    probe = json.loads(last_probe_str) if last_probe_str else {}

    next_code = auto_state.get("next_code")
    present = set(probe.get("present_codes") or [])
    actionable = list(probe.get("actionable_missing_codes") or [])
    tracked_missing = list(probe.get("tracked_missing_codes") or [])

    print(f"Track: {track_id}")
    print(f"Show: {(probe.get('show') or {}).get('name', 'Unknown')}")
    print(f"Season: {probe.get('season', 'Unknown')}")
    print()

    print("-" * 70)
    print("Current State:")
    print("-" * 70)
    print(f"  tracking_mode: {auto_state.get('tracking_mode')}")
    print(f"  next_code: {next_code}")
    print(f"  enabled: {auto_state.get('enabled')}")
    print(f"  pending_json: {pending}")
    print()

    print("-" * 70)
    print("Probe State:")
    print("-" * 70)
    print(f"  tracking_code: {probe.get('tracking_code')}")
    print(f"  tracked_missing_codes: {tracked_missing}")
    print(f"  actionable_missing_codes: {actionable}")
    print(f"  present_codes: {sorted(present)}")
    print(f"  unreleased_codes: {probe.get('unreleased_codes')}")
    print()

    print("=" * 70)
    print("Verification Checks:")
    print("=" * 70 + "\n")

    checks_total = 0
    checks_passed = 0

    checks_total += 1
    checks_passed += check(
        "Check 1",
        auto_state.get("tracking_mode") == "upcoming",
        f"tracking_mode={auto_state.get('tracking_mode')!r}",
    )

    checks_total += 1
    checks_passed += check(
        "Check 2",
        bool(next_code),
        f"next_code={next_code!r}",
    )

    checks_total += 1
    checks_passed += check(
        "Check 3",
        set(pending).issubset({next_code} if next_code else set()),
        f"pending_json={pending}",
    )

    checks_total += 1
    tracked_ok = tracked_missing == [next_code] if next_code and next_code not in pending else tracked_missing == []
    checks_passed += check(
        "Check 4",
        tracked_ok,
        f"tracked_missing_codes={tracked_missing}, pending_json={pending}, next_code={next_code!r}",
    )

    checks_total += 1
    actionable_ok = not actionable if next_code in pending else actionable in ([], [next_code])
    checks_passed += check(
        "Check 5",
        actionable_ok,
        f"actionable_missing_codes={actionable}, pending_json={pending}",
    )

    checks_total += 1
    checks_passed += check(
        "Check 6",
        next_code not in present if next_code else True,
        f"next_code present in inventory? {next_code in present if next_code else False}",
    )

    print()
    print("=" * 70)
    print(f"Results: {checks_passed}/{checks_total} checks passed")
    print("=" * 70 + "\n")

    print("-" * 70)
    print("Interpretation:")
    print("-" * 70)
    if next_code in pending:
        print(
            f"{next_code} is already pending/queued, so the persisted probe correctly shows no new actionable missing episode."
        )
    else:
        print(
            f"{next_code} is still the next tracked episode, so the persisted probe should point to it directly."
        )

    if checks_passed == checks_total:
        print("🎉 All checks passed! The stored schedule state is internally consistent.")
    else:
        raise SystemExit("Schedule database verification failed.")


if __name__ == "__main__":
    main()
