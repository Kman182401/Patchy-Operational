# ClamAV Operations Guide

Operational reference for the ClamAV integration used by Patchy Bot's malware engine.

## 1. Signature Updates (freshclam daemon)

The `clamav-freshclam` systemd service keeps virus signatures current. Default cadence is **every 2 hours (12x/day)**.

```bash
sudo systemctl status clamav-freshclam
sudo systemctl enable --now clamav-freshclam
```

## 2. Manual Update

Force an immediate signature refresh:

```bash
sudo freshclam
```

## 3. Verify Database Currency

Check installed ClamAV version and loaded signature database:

```bash
clamscan --version
```

## 4. Patchy Bot Integration

- Scans run at download completion via `_apply_completion_security_gate` in
  [`patchy_bot/handlers/download.py`](../patchy_bot/handlers/download.py).
- If ClamAV is missing or unreachable, the gate falls back to **heuristic-only**
  scanning defined in [`patchy_bot/malware.py`](../patchy_bot/malware.py).
- A **circuit breaker** trips after **3 consecutive ClamAV errors** and stays
  open for a **600-second** cooldown before a single probe attempt
  (Session 4 addition).
- The **heuristic scanner is always active**, independent of ClamAV status.

## 5. Troubleshooting

| Symptom | Action |
|---|---|
| `No supported database files found` | Run `sudo freshclam` to populate the signature database. |
| Scan timeouts | Tune `MALWARE_SCAN_TIMEOUT_SECONDS` (default `300`, minimum `30`). |
| Circuit breaker tripped | Inspect ClamAV daemon logs: `journalctl -u clamav-daemon` |
| `clamav_breaker_tripped` event in `download_health_events` | The breaker fired; it auto-probes after 600s. No manual reset required unless errors persist. |
