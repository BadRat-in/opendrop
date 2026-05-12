# Next Actions: Device Discovery Fix & Context Menu Setup

## 🔍 What We Fixed

### Problem 1: Device Not Visible in AirDrop ✅ FIXED
- **Issue:** OpenDrop configured to use `awdl0` (doesn't exist without OWL)
- **Fix:** Changed settings to use `wlo1` (your active WiFi interface)
- **Result:** Bonjour/mDNS discovery should now work

### Problem 2: No Context Menu Integration ✅ IMPLEMENTED
- **Feature:** Right-click files → "Send with OpenDrop"
- **Support:** Nautilus (GNOME), Dolphin (KDE), Thunar (Xfce)
- **Status:** Ready to install

---

## 🚀 Step 1: Test Device Discovery (5 minutes)

### Kill old GUI and restart with new settings:

```bash
# Kill old process
pkill -f opendrop-gui
sleep 2

# Verify settings are fixed
cat ~/.config/opendrop/settings.json
# Should show: "interface": "wlo1"

# Restart GUI
source .venv/bin/activate
opendrop-gui &
sleep 3
```

### In the GUI:

1. **Check "Accept incoming files"** checkbox
2. **Click "Refresh Devices"** button
3. **Wait 15-20 seconds** for discovery
4. **Check if devices appear** in the list

### On macOS/iPhone:

1. Open **Finder** → **AirDrop**
2. Look for **"Parrot OS"** (your computer name)
3. May appear under "Others Nearby"
4. Wait 15-20 seconds if not immediate

### Expected Result:
- ✅ macOS sees "Parrot OS" in AirDrop
- ✅ Linux GUI shows nearby devices in list
- ✅ Can drag file from macOS to Linux

**Test this first before proceeding to context menu setup!**

---

## 📋 Step 2: Install Context Menu Integration (2 minutes)

### Run the setup script:

```bash
bash scripts/setup-context-menu.sh
```

This will:
- ✓ Detect your file manager (Nautilus, Dolphin, Thunar, etc.)
- ✓ Install "Send with OpenDrop" option
- ✓ Create desktop actions
- ✓ Update desktop database

### After setup, restart file manager:

```bash
# GNOME Nautilus
nautilus &

# KDE Dolphin
dolphin &

# Xfce Thunar
thunar &

# Or just restart from application menu
```

---

## 🧪 Step 3: Test Context Menu (1 minute)

### Right-click any file:

1. Open file manager
2. Select any file
3. Right-click
4. Look for **"Send with OpenDrop"** option
   - Nautilus: Under "Scripts" submenu
   - Dolphin: Under "Scripts" submenu
   - Thunar: Under "Edit" menu
5. Click it

### Expected Dialog:

1. Device selection dialog appears
2. Nearby devices shown in list
3. Select a device
4. Click "Send"
5. File sends to that device

---

## ✅ Full Testing Workflow

### Complete Test (20 minutes):

```bash
# 1. Fix device discovery (already done)
# Settings: interface = wlo1 ✓

# 2. Restart GUI
pkill -f opendrop-gui
source .venv/bin/activate
opendrop-gui &

# 3. In GUI:
#    - Check "Accept incoming files"
#    - Click "Refresh Devices"
#    - Wait 15-20 seconds
#    - Verify devices appear

# 4. Install context menu
bash scripts/setup-context-menu.sh

# 5. Restart file manager
nautilus &  # or dolphin, thunar, etc.

# 6. Test sending:
#    - Right-click file
#    - Select "Send with OpenDrop"
#    - Choose device
#    - Send file
```

### Expected Results:

| Test | Expected | Status |
|------|----------|--------|
| Device appears in GUI list | ✓ Yes | Test it! |
| macOS sees "Parrot OS" | ✓ Yes | Test it! |
| Can send from macOS | ✓ Works | Test it! |
| Can send from context menu | ✓ Works | Test it! |
| File appears in Downloads | ✓ Yes | Test it! |

---

## 🔧 Troubleshooting

### Device still not visible?

```bash
# Check IPv6 on WiFi
ip -6 addr show wlo1
# Should show: inet6 fe80::...

# Check if settings loaded correctly
cat ~/.config/opendrop/settings.json
# Should show: "interface": "wlo1"

# Verify Bonjour/mDNS works
python3 -m opendrop find
# Should list nearby devices

# Try longer wait (30+ seconds)
# macOS sometimes caches discovery
```

### Context menu doesn't appear?

```bash
# Clear file manager cache
rm -rf ~/.cache/nautilus  # Nautilus
rm -rf ~/.cache/dolphin   # Dolphin
rm -rf ~/.cache/Thunar    # Thunar

# Restart file manager completely
pkill nautilus  # or dolphin, thunar
nautilus &
```

### Send dialog won't open?

```bash
# Test send script directly
source .venv/bin/activate
python3 scripts/opendrop-send.py ~/Downloads/test.txt

# Should show device selection dialog
```

---

## 📊 Success Checklist

- [ ] Settings show: `"interface": "wlo1"`
- [ ] GUI restarts without errors
- [ ] "Accept incoming files" checkbox works
- [ ] "Refresh Devices" button works
- [ ] Devices appear in GUI list after 15-20 seconds
- [ ] macOS sees "Parrot OS" in AirDrop
- [ ] Context menu setup runs successfully
- [ ] "Send with OpenDrop" appears in right-click menu
- [ ] Can send file from context menu
- [ ] Device selection dialog appears
- [ ] File transfers successfully
- [ ] File appears in ~/Downloads

**All checked = Success!** ✅

---

## 📚 Documentation

Read these for more details:

1. **[docs/DEVICE_DISCOVERY_FIX.md](docs/DEVICE_DISCOVERY_FIX.md)**
   - Explains the device discovery problem and fix
   - Shows what changed in settings
   - Detailed troubleshooting

2. **[docs/getting-started/QUICK_REFERENCE.md](docs/getting-started/QUICK_REFERENCE.md)**
   - Quick command reference
   - Useful one-liners

3. **[docs/troubleshooting/TROUBLESHOOTING.md](docs/troubleshooting/TROUBLESHOOTING.md)**
   - Common issues and solutions
   - Detailed debugging steps

---

## 🎯 Next Priority

**Immediate (do these now):**
1. ✅ Device discovery fix applied (already done)
2. ⏳ Restart GUI and test device visibility
3. ⏳ Install context menu integration
4. ⏳ Test sending files

**After that works:**
1. File transfer stability testing
2. Performance optimization
3. UI improvements
4. Additional features (history, favorites, etc.)

---

## Quick Command Reference

```bash
# Fix device discovery (ALREADY DONE)
# Settings changed: awdl0 → wlo1

# Restart GUI
pkill -f opendrop-gui
source .venv/bin/activate
opendrop-gui &

# Install context menu
bash scripts/setup-context-menu.sh

# Test send from CLI
python3 scripts/opendrop-send.py ~/Downloads/test.txt

# Check settings
cat ~/.config/opendrop/settings.json

# Debug discovery
python3 -m opendrop find

# View logs
python3 -m opendrop.gui.main --debug 2>&1 | tail -50
```

---

## Summary

✅ **Device discovery fixed** - Settings changed to use wlo1 instead of awdl0
✅ **Context menu ready** - Scripts created for file manager integration
⏳ **Next: Test it** - Restart GUI, verify device visibility, install context menu

**Report back after testing!** Let me know:
- Can you see devices in GUI?
- Does macOS see your Linux?
- Does context menu appear?
- Can you successfully send files?

🚀 **You're almost there! Test it now and let me know!**

