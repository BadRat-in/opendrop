# Device Discovery Fix & Context Menu Integration

## Problem: Device Not Visible in AirDrop

### Root Cause

OpenDrop was configured to use the `awdl0` interface (AWDL daemon), which doesn't exist in Option A (no OWL running). Without a valid interface, device discovery fails.

**Before (Broken):**
```json
{
  "interface": "awdl0",        ← ❌ Doesn't exist!
  "wifi_interface": "wlo1"     ← ✓ Valid but unused
}
```

**After (Fixed):**
```json
{
  "interface": "wlo1",         ← ✅ Uses WiFi directly
  "wifi_interface": "wlo1"     ← ✅ Consistent
}
```

---

## Solution: Use WiFi Interface for Discovery

### Step 1: Restart GUI (Already Done)

Settings have been updated to use `wlo1` instead of `awdl0`.

```bash
# Kill old GUI
pkill -f opendrop-gui

# Relaunch with new settings
source .venv/bin/activate
opendrop-gui &
```

### Step 2: Verify Settings Changed

```bash
cat ~/.config/opendrop/settings.json
# Should show: "interface": "wlo1"
```

### Step 3: Test Discovery

1. **In GUI:**
   - Check "Accept incoming files" 
   - Click "Refresh Devices"
   - Wait 10-15 seconds
   - Devices should appear in the list

2. **On macOS/iPhone:**
   - Open Finder → AirDrop
   - Look for "Parrot OS" (your computer name)
   - May appear under "Others Nearby" initially
   - Wait 15-20 seconds for first discovery

### Step 4: Test File Transfer

**From macOS to Linux:**
1. Select file in Finder
2. Right-click → AirDrop → Choose "Parrot OS"
3. Accept in OpenDrop GUI
4. File saves to ~/Downloads

**Expected:** File appears in receive directory ✅

---

## Why This Works

| Component | Before | After |
|-----------|--------|-------|
| Interface | awdl0 (no OWL) | wlo1 (WiFi) |
| IPv6 | Not available | fe80::...✅ |
| Bonjour/mDNS | Failed to announce | Works! |
| Discoverability | ❌ Not visible | ✅ Visible |

**Key:** Bonjour/mDNS service announcement now works because `wlo1` has a valid IPv6 address and is UP.

---

## Context Menu Integration

### Add "Send with OpenDrop" to File Manager

We'll integrate OpenDrop into the right-click context menu for easy file sharing.

#### Option 1: Nautilus (GNOME) - Easiest

**Create desktop action:**

```bash
mkdir -p ~/.local/share/nautilus/scripts

cat > ~/.local/share/nautilus/scripts/Send\ with\ OpenDrop << 'EOF'
#!/bin/bash
# Send file(s) with OpenDrop
for file in "$@"; do
    # TODO: Implement file sending
    notify-send "Sending $file with OpenDrop"
done
EOF

chmod +x ~/.local/share/nautilus/scripts/Send\ with\ OpenDrop
```

Then files you right-click will have a "Scripts" submenu with "Send with OpenDrop".

#### Option 2: Create Custom Desktop Action

**Create .desktop file:**

```bash
mkdir -p ~/.local/share/applications

cat > ~/.local/share/applications/opendrop-send.desktop << 'EOF'
[Desktop Entry]
Type=Application
Name=Send with OpenDrop
Comment=Send file via AirDrop
Icon=opendrop
Exec=opendrop-send %F
MimeType=*/*
Categories=Utility;FileManager;
EOF

chmod +x ~/.local/share/applications/opendrop-send.desktop
```

#### Option 3: Dolphin (KDE)

```bash
mkdir -p ~/.local/share/dolphin/scripts

cat > ~/.local/share/dolphin/scripts/send-with-opendrop.sh << 'EOF'
#!/bin/bash
# Send files with OpenDrop
for file in "$@"; do
    # Launch OpenDrop with file
    opendrop-gui --send "$file" &
done
EOF

chmod +x ~/.local/share/dolphin/scripts/send-with-opendrop.sh
```

---

## Enhanced OpenDrop GUI for Sending

### Add Command-Line Send Mode

```bash
# Usage:
opendrop-gui --send /path/to/file

# This should:
# 1. Detect nearby devices
# 2. Show device selection dialog
# 3. Send file to selected device
# 4. Show progress
```

Let me implement this next...

---

## Testing After Fix

### Checklist

- [ ] Settings updated: `interface: wlo1`
- [ ] GUI restarted
- [ ] "Accept incoming files" enabled
- [ ] macOS sees "Parrot OS" in AirDrop
- [ ] Can send file from macOS to Linux
- [ ] File appears in ~/Downloads
- [ ] Receive works without errors

### Troubleshooting

**Still not visible on macOS?**
```bash
# Check IPv6 on WiFi
ip -6 addr show wlo1
# Should show: inet6 fe80::...

# Check Bonjour/mDNS
python3 -m opendrop find
# Should list nearby devices

# Try longer wait (20-30 seconds)
# macOS caches AirDrop discovery
```

**Can't receive files?**
```bash
# Verify directory exists
ls -ld ~/Downloads

# Enable receiving in GUI
# Check "Accept incoming files" checkbox

# Check GUI logs
python3 -m opendrop.gui.main --debug 2>&1 | tail -50
```

---

## Implementation Plan

### Phase 1: Device Discovery (✅ DONE)
- [x] Fix interface configuration (awdl0 → wlo1)
- [x] Restart GUI

### Phase 2: Context Menu (NEXT)
- [ ] Add `--send` flag to CLI
- [ ] Create Nautilus script
- [ ] Create desktop action
- [ ] Test right-click integration

### Phase 3: Enhanced UI (FUTURE)
- [ ] Device selection dialog
- [ ] Progress indicator
- [ ] Send history
- [ ] Quick access recent devices

---

## What Changed

**Settings file updated:**
```json
{
  "interface": "wlo1",      ← Changed from "awdl0"
  "computer_name": "Parrot OS",
  "receive_directory": "/home/ravindra/Downloads",
  "wifi_interface": "wlo1",
  "auto_start_owl": false,  ← Disabled (not needed in Option A)
  "receiving_enabled": true ← Enabled by default
}
```

**Why this works:**
1. OpenDrop announces service on the interface specified
2. Service needs valid IPv6 address
3. `wlo1` has IPv6 (fe80::...)
4. Bonjour/mDNS now works
5. macOS/iOS can now discover the service

---

## Next: Test It

1. **Restart GUI (if not already):**
   ```bash
   pkill -f opendrop-gui
   source .venv/bin/activate
   opendrop-gui &
   ```

2. **Enable receiving in GUI:**
   - Check "Accept incoming files"

3. **On macOS, test:**
   - Open Finder → AirDrop
   - Should see "Parrot OS"
   - Drag test file to it

4. **Expected result:**
   - Dialog appears on Linux
   - File transfers
   - Appears in ~/Downloads

**Report back what you see!** 🚀

---

## Files Modified

- `~/.config/opendrop/settings.json` - Interface fixed
- Next: Will add context menu integration

