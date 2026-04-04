#!/usr/bin/env python3
"""
Runtime schedule probe verification for a tracked show.

This script loads the real bot config, refreshes one schedule track, and checks
that the state is internally consistent after the latest probe run.
"""

from __future__ import annotations

import asyncio
import os
import time
from pathlib import Path

from qbt_telegram_bot import BotApp, Config

TRACK_ID = os.getenv("SCHEDULE_TRACK_ID", "46b117e6")


def format_local_ts(ts: int | None) -> str:
    if not ts:
        return "None"
    return time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime(int(ts)))


def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        os.environ.setdefault(key, value)


def check(label: str, ok: bool, detail: str) -> int:
    status = "PASSED" if ok else "FAILED"
    icon = "✅" if ok else "❌"
    print(f"{icon} {label} {status}: {detail}")
    return int(ok)


def main() -> None:
    repo_dir = Path(__file__).resolve().parent
    load_env_file(repo_dir / ".env")

    print("\n" + "=" * 70)
    print("Schedule Runtime Verification Test")
    print("=" * 70 + "\n")

    bot = BotApp(Config.from_env())
    track = bot.store.get_schedule_track_any(TRACK_ID)
    if not track:
        raise SystemExit(f"ERROR: Track {TRACK_ID} not found")

    print(f"Track: {track.get('track_id')}")
    print(f"Show: {(track.get('show_json') or {}).get('name')}")
    print(f"Season: {track.get('season')}")
    print(f"Tracking Mode: {(track.get('auto_state_json') or {}).get('tracking_mode')}")
    print(f"Next Code: {(track.get('auto_state_json') or {}).get('next_code')}")
    print()

    print("Running probe refresh...")
    updated, probe = asyncio.run(bot._schedule_refresh_track(track, allow_notify=False))

    auto_state = dict(updated.get("auto_state_json") or {})
    pending = list(updated.get("pending_json") or [])
    present = set(probe.get("present_codes") or [])
    actionable = list(probe.get("actionable_missing_codes") or [])
    tracked_missing = list(probe.get("tracked_missing_codes") or [])
    next_code = auto_state.get("next_code")

    print("\n" + "-" * 70)
    print("Updated State:")
    print("-" * 70)
    print(f"  tracking_mode: {auto_state.get('tracking_mode')}")
    print(f"  next_code: {next_code}")
    print(f"  next_auto_retry_at: {format_local_ts(auto_state.get('next_auto_retry_at'))}")
    print(f"  last_auto_code: {auto_state.get('last_auto_code')}")
    print(f"  pending_json: {pending}")
    print()

    print("-" * 70)
    print("Probe State:")
    print("-" * 70)
    print(f"  tracking_code: {probe.get('tracking_code')}")
    print(f"  tracked_missing_codes: {tracked_missing}")
    print(f"  actionable_missing_codes: {actionable}")
    print(f"  present_codes: {sorted(present)}")
    print(f"  signature: {probe.get('signature')!r}")
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
        f"pending_json contains only current next_code: {pending}",
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
        f"actionable_missing_codes={actionable}, pending_json={pending}, next_code={next_code!r}",
    )

    checks_total += 1
    checks_passed += check(
        "Check 6",
        next_code not in present if next_code else True,
        f"next_code present in Plex inventory? {next_code in present if next_code else False}",
    )

    print()
    print("=" * 70)
    print(f"Results: {checks_passed}/{checks_total} checks passed")
    print("=" * 70 + "\n")

    if checks_passed == checks_total:
        print("🎉 All checks passed! The schedule system is internally consistent.")
        if next_code in pending:
            print(f"{next_code} is already queued/pending, so no new actionable missing episode is expected.")
        else:
            print(f"{next_code} is still the next tracked episode and remains eligible for future acquisition.")
    else:
        raise SystemExit("Schedule runtime verification failed.")


if __name__ == "__main__":
    main()
