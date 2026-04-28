---
description: Full Patchy Bot stack health check (service, qBT, Plex, VPN, resources)
allowed-tools: Bash
---

Check the entire Patchy stack without restarting anything. Read-only diagnostics.

Defaults (from `patchy_bot/config.py`):
- qBT: `http://127.0.0.1:8080`
- VPN interface: `tun0`
- VPN service: `surfshark-vpn.service`
- Plex base URL: from `PLEX_BASE_URL` env var (may be unset)

Run these checks (parallel where safe):

1. **Bot service**
   !`systemctl is-active telegram-qbt-bot.service`
   !`journalctl -u telegram-qbt-bot.service -p err -n 3 --no-pager -o short-iso 2>/dev/null || echo "(no recent errors)"`

2. **qBittorrent WebUI**
   !`curl -s -o /dev/null -w 'http=%{http_code} time=%{time_total}s\n' --max-time 5 http://127.0.0.1:8080`

3. **Plex** (read URL from systemd env, fall back to skip if unset)
   !`PLEX_URL=$(systemctl show telegram-qbt-bot.service -p Environment --value | tr ' ' '\n' | grep '^PLEX_BASE_URL=' | cut -d= -f2-); if [ -n "$PLEX_URL" ]; then curl -s -o /dev/null -w 'http=%{http_code} time=%{time_total}s url='"$PLEX_URL"'\n' --max-time 5 "$PLEX_URL/identity" 2>&1; else echo "PLEX_BASE_URL unset — skipping"; fi`

4. **VPN (Surfshark)**
   !`systemctl is-active surfshark-vpn.service 2>/dev/null || echo "(service not present)"`
   !`ip -4 addr show tun0 2>/dev/null | grep -oP 'inet \K[\d.]+' || echo "(tun0 has no IPv4)"`
   !`getent hosts api.surfshark.com >/dev/null && echo "DNS ok" || echo "DNS FAIL"`

5. **Disk**
   !`df -h /home/karson/Patchy_Bot 2>&1 | tail -1`
   !`df -h /mnt 2>&1 | tail -n +2 || true`

6. **Memory**
   !`free -h | head -2`

Now build a single status table:

| Component | Status | Detail |
|---|---|---|
| Bot service | ✅/⚠️/🔴 | active state + last err |
| qBittorrent | ✅/⚠️/🔴 | http code |
| Plex | ✅/⚠️/🔴/⏭️ | http code or "skipped" |
| VPN (tun0) | ✅/⚠️/🔴 | iface + IP + DNS |
| Disk | ✅/⚠️/🔴 | % used |
| Memory | ✅/⚠️/🔴 | % used |

Status rules:
- ✅ green for: service active / 2xx HTTP / VPN up with IP+DNS / disk <85% / mem <85%
- ⚠️ yellow for: degraded but functional (e.g. disk 85-95%, 401 from Plex with token issues)
- 🔴 red for: service inactive / connection refused / no IP on tun0 / disk ≥95%

If anything is degraded or red, append a "Next diagnostic step" line per failing component (e.g. "qBT down → check `qbittorrent-nox.service` and `journalctl -u qbittorrent-nox.service -n 50`").
