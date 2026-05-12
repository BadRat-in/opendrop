# OpenDrop-GUI Verification Guide

This document describes how to verify that OpenDrop-GUI is properly set up and functioning.

## Pre-Flight Checks

### 1. Dependencies Installation

```bash
# Verify uv is installed
uv --version
# Expected: uv 0.11.4 or later

# Sync dependencies with GUI extra
uv sync --extra gui

# Verify all packages are available
uv run python3 -c "import PyQt6; print(f'PyQt6 version: {PyQt6.__version__}')"
```

### 2. Python Module Imports

```bash
source .venv/bin/activate

# Test core modules
python3 -c "
from opendrop.gui.settings import OpenDropSettings
from opendrop.gui.owl_manager import OWLManager
from opendrop.gui.worker import BrowseWorker, SendWorker, ReceiveWorker
from opendrop.gui.settings_dialog import SettingsDialog
from opendrop.gui.window import MainWindow
from opendrop.gui.tray import OpenDropTray
from opendrop.gui.main import main
print('✓ All GUI modules imported successfully')
"
```

### 3. CLI Compatibility

```bash
# Verify CLI still works
opendrop --help

# Expected: Shows help for receive/find/send subcommands
```

### 4. Version Check

```bash
source .venv/bin/activate
python3 -c "import opendrop; print(f'OpenDrop version: {opendrop.__version__}')"
# Expected: OpenDrop version: 0.14.0
```

## System Setup Verification

### 5. OWL Binary Check

```bash
# Verify OWL is installed
which owl
/usr/local/bin/owl
# Expected: OWL prints its ASCII art logo

# Check OWL can detect interfaces
owl -h 2>&1 | head -10
```

### 6. Systemd Service

Before running `setup-owl.sh`:

```bash
# Check for required tools
which iw ip nmcli systemctl

# Verify WiFi interface
ip link show wlo1
# Expected: Interface with <BROADCAST,MULTICAST,UP,LOWER_UP>

# Check hardware AWDL capability
iw phy phy0 info | grep -A 20 "valid interface combinations"
```

### 7. Root User Check

```bash
# setup-owl.sh must run as root
sudo bash scripts/setup-owl.sh

# After running, verify:
cat /etc/sudoers.d/opendrop
# Should show NOPASSWD rules for systemctl owl-awdl

systemctl status owl-awdl.service
# Should show "loaded but inactive"

cat /etc/systemd/system/owl-awdl.service | head -20
# Should show the service unit file
```

## Runtime Verification

### 8. OWL Startup (Manual)

```bash
# Start OWL via systemd (as regular user, no sudo needed)
sudo systemctl start owl-awdl.service

# Verify awdl0 interface appears
ip link show awdl0
# Expected: awdl0: <POINTOPOINT,NOARP,UP,LOWER_UP>

# Check IPv6 address
ip -6 addr show awdl0
# Expected: inet6 fe80::<something> scope link

# Stop OWL
sudo systemctl stop owl-awdl.service

# Verify cleanup
ip link show mon0 2>&1 | grep -q "does not exist"
# Expected: "does not exist" message

# Verify WiFi reconnected
nmcli device status | grep wlo1
# Expected: wlo1 should be "connected"
```

### 9. GUI Basic Functionality (with DISPLAY)

```bash
# Set DISPLAY if you have X11
export DISPLAY=:0

# Start the GUI in background
opendrop-gui &
GUI_PID=$!

# Wait for startup
sleep 2

# Verify system tray icon
pgrep -f opendrop-gui
# Expected: Returns the PID

# Check logs
journalctl -u owl-awdl.service -n 20
# Should show startup messages

# Stop GUI
kill $GUI_PID
```

## CLI Testing (No GUI Needed)

### 10. Device Discovery

```bash
# Start OWL manually
sudo systemctl start owl-awdl.service
sleep 2

# Run discovery
opendrop find -i awdl0
# Expected: Will search for nearby devices
# Press Ctrl+C to stop

# Stop OWL
sudo systemctl stop owl-awdl.service
```

### 11. Self-Discovery (Loopback Test)

```bash
# This test verifies the protocol implementation without OWL
# It won't discover real devices but tests the code paths

# Start receiver in one terminal
cd /tmp && opendrop receive &
RECV_PID=$!
sleep 1

# Send in another terminal (you'll need to adjust for your system)
echo "test" > /tmp/test.txt
# opendrop send -r <receiver_id> -f /tmp/test.txt
# (requires actual device to be present)

# Cleanup
kill $RECV_PID
```

## File System Checks

### 12. Config Directory

```bash
# Verify settings persistence
ls -la ~/.config/opendrop/
# Expected: settings.json exists after GUI first run

cat ~/.config/opendrop/settings.json
# Expected: JSON with computer_name, receive_directory, etc.
```

### 13. Project Structure

```bash
# Verify all created files exist
ls -la opendrop/gui/{__init__,main,settings,owl_manager,worker,settings_dialog,window,tray}.py

# Verify resource files
ls -la opendrop/gui/resources/{icon_active,icon_inactive}.png

# Verify systemd service
ls -la systemd/owl-awdl.service

# Verify setup script
ls -la scripts/setup-owl.sh
stat --format='%A' scripts/setup-owl.sh  # Should show execute bits
```

## Linting & Quality Checks

### 14. Code Quality

```bash
# Install dev dependencies
uv sync --all-groups

# Run linters
black --check opendrop/gui/
flake8 opendrop/gui/
isort --check opendrop/gui/
pylint opendrop/gui/*.py

# Run tests (if any)
pytest tests/ -v
```

## Troubleshooting

### Issue: "No system tray available"
- Make sure you have a desktop environment with system tray support (GNOME, KDE, XFCE, etc.)
- The GUI cannot run on headless systems or minimal window managers without tray

### Issue: "OWL not found"
- Install OWL: `git clone https://github.com/seemoo-lab/owl && cd owl && make && sudo make install`
- Verify: `which owl` should return `/usr/local/bin/owl`

### Issue: "Cannot put device in monitor mode"
- Some WiFi drivers don't support monitor mode
- Check: `iw phy phy0 info | grep -i "monitor"`
- You may need a secondary USB WiFi adapter

### Issue: "PyQt6 import error"
- Make sure you ran: `uv sync --extra gui`
- Not just `uv sync`

### Issue: "Sudoers permission error"
- Run setup script with sudo: `sudo bash scripts/setup-owl.sh`
- Verify: `sudo -l` should show OWL service commands

## Success Checklist

- [ ] `uv --version` returns a version
- [ ] All GUI modules import without errors
- [ ] `opendrop --help` shows CLI options
- [ ] `opendrop-gui` starts (may fail gracefully without DISPLAY)
- [ ] OWL binary exists at `/usr/local/bin/owl`
- [ ] systemd service file installed at `/etc/systemd/system/owl-awdl.service`
- [ ] Sudoers rule installed at `/etc/sudoers.d/opendrop`
- [ ] `systemctl start owl-awdl.service` succeeds (with sudo if needed)
- [ ] `ip link show awdl0` shows the interface after OWL starts
- [ ] OWL stops cleanly with `systemctl stop owl-awdl.service`
- [ ] `mon0` interface disappears after stopping
- [ ] WiFi (`wlo1`) reconnects after stopping OWL
- [ ] `~/.config/opendrop/settings.json` exists and is valid JSON

---

**Last Updated:** 2026-05-12
**Version:** OpenDrop-GUI 0.14.0
