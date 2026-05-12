# OpenDrop GUI - Quick Reference Card

## Launch Commands

```bash
# Setup (first time)
source .venv/bin/activate
uv sync --all-extras

# Launch GUI
opendrop-gui

# Launch with debug logging
python3 -m opendrop.gui.main --debug

# Run pre-flight checks
bash scripts/check-gui-ready.sh
```

## Quick Tests (CLI)

```bash
# Test IPv6
python3 -c "from opendrop.util import AirDropUtil; print(AirDropUtil.get_ip_for_interface('wlan0', ipv6=True))"

# Test device discovery
python3 -m opendrop find

# Test receive mode
python3 -m opendrop receive
```

## Configuration

**Location:** `~/.config/opendrop/settings.json`

**Reset to defaults:**
```bash
rm ~/.config/opendrop/settings.json
# GUI will recreate on next launch
```

**Manual config:**
```json
{
  "computer_name": "My Linux PC",
  "receive_directory": "/home/user/Downloads",
  "wifi_interface": "wlan0",
  "receiving_enabled": true
}
```

## Troubleshooting Commands

```bash
# Check WiFi
iwconfig wlan0
# Should show: SSID and Access Point

# Check IPv6
ip -6 addr show wlan0
# Should show: inet6 fe80::... or 2xxx:...

# Check mDNS
avahi-browse -r _airdrop._tcp
# Should find AirDrop devices

# Check firewall
sudo ufw status
# Port 5353 (mDNS) and 443 (HTTPS) must be open

# View config
cat ~/.config/opendrop/settings.json

# View logs
journalctl -f  # system logs
# Or check terminal where GUI was launched
```

## Expected Behavior

| Action | Expected Result | Time |
|--------|-----------------|------|
| Launch GUI | Window appears, tray icon shows | Instant |
| Discovery starts | "Nearby Devices" shows devices | 5-15 sec |
| macOS sees Linux | Linux appears in AirDrop | 5-15 sec |
| Send file | Dialog appears, file transfers | Varies |
| Receive file | File appears in directory | Varies |

## Quick Checklist

- [ ] GUI launches (`opendrop-gui`)
- [ ] Settings dialog opens
- [ ] Devices appear after 15 seconds
- [ ] macOS sees your Linux
- [ ] Can send test file
- [ ] Can receive test file
- [ ] Settings persist after restart

## File Locations

| Item | Location |
|------|----------|
| Config | `~/.config/opendrop/settings.json` |
| Logs | Terminal output or `journalctl` |
| Certs | `opendrop/certs/*.pem` |
| GUI Code | `opendrop/gui/*.py` |

## Common Issues & Fixes

| Issue | Fix |
|-------|-----|
| GUI won't launch | Check: `python3 -m opendrop.gui.main --debug` |
| No devices found | Wait 15 sec, check IPv6: `ip -6 addr show` |
| File won't send | Check receive directory exists and is writable |
| Settings don't save | Check: `ls -la ~/.config/opendrop` (must be writable) |
| macOS doesn't see Linux | Check receive mode enabled, wait 20 sec |

## Useful Aliases

```bash
# Add to ~/.bashrc
alias opendrop-check='bash ~/Projects/opendrop/scripts/check-gui-ready.sh'
alias opendrop-discover='python3 -m opendrop find'
alias opendrop-receive='python3 -m opendrop receive'
```

## Network Requirements

✅ Requirements Met (Option A)
- IPv6 enabled on both devices
- Same WiFi network
- Port 5353 (mDNS) open
- Port 443 (HTTPS) open
- No proxy blocking services

❌ Not Required
- OWL/AWDL daemon
- Bluetooth AirDrop
- Cross-network setup

## Performance Tips

- **Faster discovery:** Enable receive mode before looking
- **Larger files:** Use WiFi 5/6, not 2.4GHz
- **Battery:** GUI uses ~50-100 MB RAM when idle
- **Network:** Hardwired Ethernet also works (needs IPv6)

## Getting Help

1. **Check logs:** Terminal output from `opendrop-gui --debug`
2. **Run pre-checks:** `bash scripts/check-gui-ready.sh`
3. **Test CLI:** `python3 -m opendrop find`
4. **Review guide:** See TESTING_GUIDE_OPTION_A.md for 10 detailed tests

## Success = All Green ✅

```
Pre-flight checks: ✅ All passed
GUI launches: ✅ Yes
Discovery works: ✅ Devices visible
File transfer works: ✅ Can send/receive
Settings persist: ✅ Save/load works
Stability: ✅ No crashes
```

**Option A Complete!** 🎉

---

## Testing Workflow

```
1. Setup
   ↓ uv sync --all-extras
   ↓ bash scripts/check-gui-ready.sh
   
2. Launch
   ↓ opendrop-gui
   
3. Test (follow TESTING_GUIDE_OPTION_A.md)
   ↓ Test 1: GUI launches
   ↓ Test 2: Settings
   ↓ Test 3: CLI discovery
   ↓ Test 4: GUI discovery
   ↓ Test 5: macOS sees Linux
   ↓ Test 6: Transfer file
   ↓ Test 7: Drag-drop
   ↓ Test 8: Receive mode
   ↓ Test 9: Persistence
   ↓ Test 10: Stability
   
4. Success
   ✅ All tests pass
   → Option A COMPLETE
```

