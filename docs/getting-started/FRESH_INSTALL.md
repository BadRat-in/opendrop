# OpenDrop Fresh Installation Guide

## Overview

This guide walks you through a **complete clean installation** of OpenDrop GUI (Option A).

---

## Step 1: Remove Old Installation (If Present)

### Option A: Complete Cleanup (Recommended)

```bash
cd /home/ravindra/Projects/opendrop
bash scripts/uninstall-opendrop.sh
```

**What it does:**
- Stops any running OpenDrop processes
- Removes system-wide installations
- Removes systemd service
- Removes sudoers configuration
- Removes AppArmor profiles
- Removes user config (~/.config/opendrop)
- Optionally removes venv and caches

**Follow the prompts** - some items are optional (like cache cleanup).

### Option B: Quick Cleanup (If You Trust Current State)

```bash
# Just stop the running GUI
pkill -f opendrop-gui

# Remove config
rm -rf ~/.config/opendrop
```

This skips system files and just removes user data.

---

## Step 2: Prepare Fresh Environment

```bash
cd /home/ravindra/Projects/opendrop
```

### Create Fresh Virtual Environment

```bash
# Remove old venv (if exists)
rm -rf .venv

# Create new venv
python3 -m venv .venv

# Activate it
source .venv/bin/activate

# Verify Python in venv
which python3
# Should show: /home/ravindra/Projects/opendrop/.venv/bin/python3
```

### Install uv Package Manager

```bash
# Check if uv is installed globally
which uv

# If not installed:
pip install uv

# Verify uv installation
uv --version
# Should show: uv X.X.X
```

---

## Step 3: Install OpenDrop Dependencies

```bash
# Make sure venv is activated
source .venv/bin/activate

# Install all dependencies (including PyQt6 for GUI)
uv sync --all-extras

# Verify installation
uv pip list | grep -E "PyQt6|zeroconf|requests|opendrop"
```

**Expected output:**
```
opendrop            0.14.0
PyQt6               6.11.0
zeroconf            0.148.0
requests            2.34.0
...
```

---

## Step 4: Verify Fresh Installation

```bash
# Activate venv
source .venv/bin/activate

# Run pre-flight checks
bash scripts/check-gui-ready.sh
```

**Expected output:**
```
✓ Python 3.10+
✓ uv package manager
✓ PyQt6 installed
✓ zeroconf installed
...
✓ All checks passed!
```

If you see **"✓ All checks passed!"**, proceed to Step 5.

---

## Step 5: Launch Fresh GUI

```bash
# Activate venv (if not already)
source .venv/bin/activate

# Launch GUI
opendrop-gui

# Or with debug logging to see startup messages
python3 -m opendrop.gui.main --debug
```

**Expected behavior:**
- Window appears titled "OpenDrop"
- System tray icon appears
- No errors in terminal
- Settings dialog available
- Device discovery ready

---

## Step 6: Configure Fresh Installation

### First Time Setup

1. **Click [Settings] button**

2. **Configure:**
   - **Computer Name:** How your Linux appears in macOS AirDrop
     - Example: "My Linux PC"
   - **Receive Directory:** Where files from macOS save
     - Example: ~/Downloads or ~/opendrop-receive
   - **WiFi Interface:** Your wireless interface
     - Usually auto-detected (wlan0, wlo1, eth0, etc.)

3. **Click [Save]**

### Verification

```bash
# Check config was saved
cat ~/.config/opendrop/settings.json

# Should show your settings:
{
  "computer_name": "My Linux PC",
  "receive_directory": "/home/user/Downloads",
  "wifi_interface": "wlan0",
  ...
}
```

---

## Step 7: Test Fresh Installation

### Quick Test

```bash
# 1. Keep GUI running
# 2. In another terminal:
source .venv/bin/activate

# 3. Test CLI discovery
python3 -m opendrop find

# Should find AirDrop devices on WiFi
```

### Full Testing

Follow **TESTING_GUIDE_OPTION_A.md** for comprehensive 10-test procedure.

---

## Clean Install Verification Checklist

- [ ] Old installation uninstalled (`scripts/uninstall-opendrop.sh`)
- [ ] Fresh venv created (`python3 -m venv .venv`)
- [ ] venv activated (`source .venv/bin/activate`)
- [ ] uv installed (`pip install uv`)
- [ ] Dependencies installed (`uv sync --all-extras`)
- [ ] Pre-flight checks pass (`bash scripts/check-gui-ready.sh`)
- [ ] GUI launches (`opendrop-gui`)
- [ ] Settings configured
- [ ] Config file exists (`~/.config/opendrop/settings.json`)
- [ ] CLI discovery works (`python3 -m opendrop find`)

**All checked = Clean install successful!** ✅

---

## Troubleshooting Fresh Install

### Issue: "command not found: python3"

**Solution:**
```bash
# Check available Python
python --version
python3.10 --version
python3.11 --version

# Use the available version (3.10+)
/usr/bin/python3.10 -m venv .venv
```

### Issue: "command not found: uv"

**Solution:**
```bash
# Install uv with pip
source .venv/bin/activate
pip install uv

# Or install system-wide
sudo pip install uv
```

### Issue: "PyQt6 not found after uv sync"

**Solution:**
```bash
# Make sure you used --all-extras
source .venv/bin/activate
uv sync --all-extras

# Verify it installed
python3 -c "import PyQt6; print('PyQt6 OK')"
```

### Issue: venv activation not working

**Solution:**
```bash
# Check if .venv/bin/activate exists
ls -la .venv/bin/activate

# Try absolute path
source /home/ravindra/Projects/opendrop/.venv/bin/activate

# Or use alternate syntax
. .venv/bin/activate
```

### Issue: GUI won't launch

**Solution:**
```bash
# Check with debug mode
source .venv/bin/activate
python3 -m opendrop.gui.main --debug 2>&1 | head -50

# Check for X11/Display issues
echo $DISPLAY
# Should show something like: :0 or :0.0
```

---

## Optional: System-Wide Setup

After fresh install works, optionally set up system-wide (one-time):

```bash
# Install wrapper script to /usr/local/bin
sudo cp scripts/opendrop-gui-wrapper.sh /usr/local/bin/opendrop-gui
sudo chmod 755 /usr/local/bin/opendrop-gui

# Create desktop launcher
sudo cp assets/opendrop-gui.desktop /usr/share/applications/

# Update desktop database
sudo update-desktop-database

# Now you can launch from application menu or terminal:
opendrop-gui
```

---

## Fresh Install Recovery

If something goes wrong, you can always start over:

```bash
# Complete reset
rm -rf .venv ~/.config/opendrop ~/.cache/opendrop

# Then follow Step 2 onwards
python3 -m venv .venv
source .venv/bin/activate
pip install uv
uv sync --all-extras

# Test
bash scripts/check-gui-ready.sh
opendrop-gui
```

---

## Next: Testing After Fresh Install

Once fresh install is complete, follow:

**TESTING_GUIDE_OPTION_A.md**

Which includes:
- 10 comprehensive tests
- Expected results for each
- Troubleshooting for failures
- Success criteria

---

## Summary

**Fresh install = Clean slate** ✅

- All old configs removed
- New venv created
- All dependencies fresh
- Clean configuration
- Ready for testing

**Next step: Run TESTING_GUIDE_OPTION_A.md**

---

## Quick Commands Reference

```bash
# Complete fresh install (from project root)
rm -rf .venv ~/.config/opendrop
python3 -m venv .venv
source .venv/bin/activate
pip install uv
uv sync --all-extras
bash scripts/check-gui-ready.sh
opendrop-gui
```

Copy-paste the above commands in sequence for a complete fresh installation.

