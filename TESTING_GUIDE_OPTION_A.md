# OpenDrop GUI Testing Guide (Option A)

## Pre-Testing Checklist

**Run this first:**
```bash
source .venv/bin/activate
bash scripts/check-gui-ready.sh
```

**Expected:**
```
✓ All checks passed!
OpenDrop GUI is ready to launch
```

If you see this, proceed to testing.

---

## Test 1: GUI Launches Successfully

### What to Test
Verify the GUI window appears and system tray icon shows up.

### Steps
```bash
source .venv/bin/activate
opendrop-gui &
```

### Expected Results
- [ ] Window titled "OpenDrop" appears on screen
- [ ] Window has menu bar with buttons visible
- [ ] System tray icon appears (usually in top-right corner)
- [ ] Tray icon shows a dot (color may be green/gray)
- [ ] No errors in terminal

### If It Fails
```bash
# Try with debug logging
python3 -m opendrop.gui.main --debug 2>&1 | tail -30
```

Check for:
- ImportError - missing dependencies
- X11/Display errors - X11 not running
- Qt errors - PyQt6 issues

---

## Test 2: Settings Dialog

### What to Test
Verify settings can be opened, modified, and saved.

### Steps
1. GUI is running (Test 1)
2. Look for **[Settings]** button in main window
3. Click it
4. Dialog should appear with fields:
   - Computer Name
   - Receive Directory
   - WiFi Interface

### Expected Results
- [ ] Settings dialog opens
- [ ] Can see current values
- [ ] Can change Computer Name
- [ ] Can browse and select Receive Directory
- [ ] Click [Save] works without error
- [ ] Settings persist after closing and reopening GUI

### Verification
```bash
cat ~/.config/opendrop/settings.json
# Should show your saved settings
```

### If It Fails
- Check directory permissions: `ls -ld ~/.config/opendrop`
- Try with explicit settings: `opendrop-gui --name "Test PC"`

---

## Test 3: Device Discovery (CLI Baseline)

### What to Test
Verify the core OpenDrop discovery works before GUI testing.

### Prerequisites
- Your Linux machine on WiFi
- Your macOS device on SAME WiFi network
- Both devices on same network (important!)

### Steps
```bash
source .venv/bin/activate

# Test 1: Verify IPv6 is working
python3 << 'PYTHON'
from opendrop.util import AirDropUtil
ip = AirDropUtil.get_ip_for_interface('wlan0', ipv6=True)
print(f"IPv6 Address: {ip}")
PYTHON

# Test 2: Start discovery
python3 -m opendrop find
```

### Expected Results
- [ ] IPv6 address shows (e.g., `fe80::xxxx:xxxx:xxxx:xxxx`)
- [ ] Discovery runs and shows "Discovering AirDrop devices..."
- [ ] After 5-10 seconds, macOS devices appear

**Sample Output:**
```
Discovering AirDrop devices (Ctrl+C to stop)...
Found device: MacBook-Pro (ID: 1a2b3c4d...)
Found device: iMac (ID: 5e6f7g8h...)
```

### If No Devices Found
1. **Check WiFi:**
   ```bash
   iwconfig wlan0  # or your interface
   # Should show SSID and "Access Point: XX:XX:XX:XX:XX:XX"
   ```

2. **Check IPv6:**
   ```bash
   ip -6 addr show wlan0
   # Should show inet6 address with scope link (fe80::...)
   ```

3. **Wait longer** - Bonjour discovery can take 10-15 seconds

4. **Restart Finder on macOS** - Force re-advertise AirDrop

5. **Check firewall** - No port blocking for mDNS (port 5353)

---

## Test 4: Device Discovery in GUI

### What to Test
Verify the GUI discovers devices the same way as CLI.

### Prerequisites
- CLI discovery works (Test 3)
- macOS AirDrop is enabled and visible

### Steps
1. Launch GUI: `opendrop-gui`
2. Look for **"Nearby Devices"** section
3. Wait 10-15 seconds
4. macOS device should appear

### Expected Results
- [ ] After 10-15 seconds, see device list updating
- [ ] macOS device appears with name (e.g., "MacBook Pro")
- [ ] Device shows [Send File] button
- [ ] List updates every 2-3 seconds

### Sample Screen
```
Nearby Devices:
[Loading devices...]

After 10-15 seconds:
[✓] MacBook Pro    [Send File]
[✓] iMac           [Send File]
```

### If Devices Don't Appear
1. Check Test 3 (CLI discovery) works first
2. Check logs in terminal (scroll up)
3. Verify "Receive Mode" is enabled
4. Try restarting GUI

---

## Test 5: Verify Visibility on macOS

### What to Test
Verify macOS can see your Linux machine in AirDrop.

### Prerequisites
- GUI is running
- "Enable Receive Mode" is checked in GUI
- macOS AirDrop is open

### Steps
1. On macOS, open Finder
2. In sidebar, click **AirDrop**
3. Look for your computer name (e.g., "My Linux PC")
4. It may be under "Others Nearby" if you just started

### Expected Results
- [ ] Linux computer appears in AirDrop window
- [ ] Shows your configured computer name
- [ ] Icon or name is clearly visible
- [ ] Can click to select it

### If Not Visible
1. Wait 15-20 seconds (first discovery takes time)
2. Restart Finder on macOS: Cmd+Q then reopen
3. Check "Receive Mode" is enabled in Linux GUI
4. Verify both on same WiFi: `ifconfig` on macOS, `ip addr` on Linux

---

## Test 6: Send File from macOS to Linux

### What to Test
Verify file transfer from macOS → Linux works.

### Prerequisites
- Tests 4 and 5 pass (discovery works both ways)
- Have a test file on macOS (e.g., test.txt)
- Receive directory exists on Linux

### Steps
1. **On macOS:**
   - Open Finder
   - Select a test file
   - Right-click → AirDrop
   - Click on your Linux computer

2. **On Linux GUI:**
   - Accept dialog appears
   - Click "Accept" or "Yes"
   - Watch file save to receive directory

### Expected Results
- [ ] Dialog appears on Linux asking "Accept from MacBook?"
- [ ] Accept button works
- [ ] File appears in receive directory
- [ ] File has correct name and size

### Verification
```bash
ls -lah ~/Downloads  # or your receive directory
# File should be there with today's date
```

### If Transfer Fails
1. **Check receive directory:**
   ```bash
   ls -ld ~/Downloads  # must be writable
   ```

2. **Check logs** - GUI shows errors if transfer fails

3. **Try smaller file** - Large files may timeout

4. **Check firewall** - HTTPS port 443 must be open on localhost

---

## Test 7: Receive File from macOS via Finder Drag-Drop

### What to Test
Verify alternative file send method works.

### Prerequisites
- Test 6 passes (basic send works)
- Have a test file on macOS
- Receive Mode enabled on Linux

### Steps
1. **On macOS:**
   - Open Finder
   - Open AirDrop window
   - Find your Linux computer
   - Drag file onto it

2. **On Linux:**
   - Dialog appears
   - Accept the transfer

### Expected Results
- [ ] Drag-drop initiates transfer
- [ ] File appears in receive directory
- [ ] Size is correct

---

## Test 8: Enable Receive Mode

### What to Test
Verify Linux can receive files from macOS.

### Steps
1. In GUI, check **"Enable Receive Mode"**
2. Verify receive directory is set
3. On macOS, try sending file

### Expected Results
- [ ] Checkbox toggles receive mode
- [ ] Receive directory path shows correct location
- [ ] Can create files in that directory
- [ ] Can receive from macOS

### Verification
```bash
touch ~/opendrop-test.txt
# If this works, receive directory is writable
```

---

## Test 9: Settings Persistence

### What to Test
Verify settings save and load correctly.

### Steps
1. Open Settings
2. Change Computer Name to "Test PC"
3. Click Save
4. Close GUI completely
5. Reopen GUI
6. Open Settings again

### Expected Results
- [ ] Computer name is still "Test PC"
- [ ] Receive directory unchanged
- [ ] WiFi interface unchanged
- [ ] Settings file shows correct values:

```bash
cat ~/.config/opendrop/settings.json
# Should show: "computer_name": "Test PC"
```

---

## Test 10: GUI Stability

### What to Test
Verify GUI is stable during normal use.

### Steps
1. Run GUI for 5 minutes
2. Open/close settings dialog 5 times
3. Toggle receive mode 5 times
4. Let device discovery run
5. Send/receive a file
6. Close GUI properly

### Expected Results
- [ ] No crashes
- [ ] No memory leaks (RAM stays constant)
- [ ] No hung UI (buttons respond immediately)
- [ ] Proper shutdown without errors

### Monitor Resource Usage
```bash
# In another terminal
watch -n 1 'ps aux | grep opendrop'
# Memory (%MEM) should not grow over time
```

---

## Full Testing Checklist

Print this and check off as you test:

### Basic Functionality
- [ ] GUI launches without errors
- [ ] Settings dialog opens and saves
- [ ] Device discovery works (CLI baseline)
- [ ] Devices appear in GUI after 10-15 seconds
- [ ] Linux visible on macOS AirDrop

### File Transfer
- [ ] Can receive file from macOS
- [ ] Can drag-drop file from macOS
- [ ] Files save to correct directory
- [ ] File permissions correct
- [ ] Multiple files transfer successfully

### Stability & Usability
- [ ] Settings persist after restart
- [ ] GUI stable during extended use
- [ ] No memory leaks
- [ ] Error messages are clear
- [ ] Proper shutdown/cleanup

### Edge Cases
- [ ] Large files transfer correctly
- [ ] Special characters in filenames work
- [ ] Receive directory with spaces in path works
- [ ] Multiple transfers simultaneously
- [ ] Transfer with network interruption (USB network suspend/resume)

---

## Success Criteria

**Option A is WORKING if:**
- ✅ GUI launches and runs
- ✅ Discovery works (see devices both ways)
- ✅ Can transfer files from macOS to Linux
- ✅ Settings persist
- ✅ No crashes during normal use

**If all boxes are checked, Option A is COMPLETE** 🎉

---

## Troubleshooting During Testing

### GUI Won't Launch
```bash
# Check for errors
python3 -m opendrop.gui.main --debug 2>&1 | head -50

# Check dependencies
python3 -c "import PyQt6; print('PyQt6 OK')"
```

### No Devices Found
```bash
# Check network
ip -6 addr show  # IPv6 required
iwconfig wlan0   # WiFi must be connected

# Test CLI first
python3 -m opendrop find
```

### File Transfer Fails
```bash
# Check receive directory
ls -ld ~/opendrop-test
# Must be writable by your user

# Check logs in GUI terminal
# Should show detailed error
```

### Settings Don't Save
```bash
# Check config directory
ls -la ~/.config/opendrop/

# Try manual reset
rm ~/.config/opendrop/settings.json
# GUI will recreate on next launch
```

---

## Next Steps After Testing

If all tests pass:
1. Document any issues found
2. Create a PR if changes needed
3. Consider add additional features (v0.16+)
4. Package for distribution

If any tests fail:
1. Report specific test number
2. Include error messages
3. Include terminal output
4. We'll debug and fix

---

## Test Report Template

```
## Test Report - Option A

Date: YYYY-MM-DD
System: [Linux distro/version]
macOS: [version]
WiFi: [network name]

### Passed Tests
- [ ] Test 1: GUI Launches
- [ ] Test 2: Settings
- [ ] Test 3: CLI Discovery
- [ ] Test 4: GUI Discovery
- [ ] Test 5: macOS Visibility
- [ ] Test 6: File Transfer
- [ ] Test 7: Drag-Drop
- [ ] Test 8: Receive Mode
- [ ] Test 9: Persistence
- [ ] Test 10: Stability

### Issues Found
[Describe any failures or unexpected behavior]

### Notes
[Any additional observations]
```

---

Good luck! Let me know how the testing goes! 🚀

