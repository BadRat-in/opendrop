# 🔧 Troubleshooting Guide: OpenDrop-GUI

This guide helps you fix common issues encountered while setting up and running OpenDrop-GUI.

---

## 🚨 Issue 1: OWL Service Fails to Start

### **Symptoms**
```
Failed to start OWL: Job for owl-awdl.service failed because the control process exited with error code.
See "systemctl status owl-awdl.service"
```

### **Root Cause**
The systemd service was configured with `Type=forking`, but OWL runs in the **foreground** (doesn't fork into background). This mismatch causes systemd to think the service failed immediately.

### **Fix**

1. **Reload the fixed systemd service** (the code has been updated):
   ```bash
   sudo systemctl daemon-reload
   ```

2. **Stop any running OWL service**:
   ```bash
   sudo systemctl stop owl-awdl.service
   ```

3. **Verify the service file is updated**:
   ```bash
   cat /etc/systemd/system/owl-awdl.service | grep "^Type="
   # Should show: Type=simple
   ```
   
   If it still shows `Type=forking`, manually update it:
   ```bash
   sudo nano /etc/systemd/system/owl-awdl.service
   # Change "Type=forking" to "Type=simple"
   # Then press Ctrl+O, Enter, Ctrl+X to save
   ```

4. **Reload and test**:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl start owl-awdl.service
   sudo systemctl status owl-awdl.service
   ```

5. **Check if awdl0 appeared**:
   ```bash
   ip link show awdl0
   ip -6 addr show awdl0
   # Should show awdl0 interface with IPv6 address
   ```

---

## 🚨 Issue 2: WiFi Disconnects When Starting OWL

### **Symptoms**
- WiFi disconnects when you start OWL
- Takes 10-20 seconds to reconnect
- This is **normal on single-radio systems**

### **Why It Happens**
OWL needs the WiFi adapter in **monitor mode** to capture AWDL frames. On most laptops (single-radio systems), this requires:
1. Taking the interface offline
2. Switching to monitor mode
3. WiFi temporarily disconnects
4. Reconnection happens automatically

### **Is This Expected?**
✅ **YES, this is normal and expected behavior** on single-radio systems.

**Hardware check**:
```bash
# Check if your hardware supports concurrent modes
iw phy phy0 info | grep -A 20 "valid interface combinations"

# If you see "managed" and "monitor" together, you have concurrent support
# (WiFi won't disconnect)

# If you only see them separately, WiFi will disconnect briefly
# (This is your case - totally normal)
```

### **How to Avoid WiFi Disruption**
✅ **Solution: Use a secondary USB WiFi adapter**

1. Plug in a USB WiFi adapter
2. Find its interface name:
   ```bash
   ip link show
   # Look for something like "wlan1" or "wlx..."
   ```

3. Update the systemd service to use the USB adapter:
   ```bash
   sudo nano /etc/systemd/system/owl-awdl.service
   ```
   
   Change this line:
   ```
   ExecStartPre=/usr/sbin/iw dev wlo1 interface add mon0 type monitor
   ```
   
   To (replace `wlan1` with your USB adapter name):
   ```
   ExecStartPre=/usr/sbin/iw dev wlan1 interface add mon0 type monitor
   ```
   
   And change this line:
   ```
   ExecStopPost=/usr/sbin/ip link set wlo1 up
   ExecStopPost=/usr/bin/nmcli device connect wlo1
   ```
   
   To:
   ```
   ExecStopPost=/usr/sbin/ip link set wlan1 up
   ExecStopPost=/usr/bin/nmcli device connect wlan1
   ```

4. Reload and restart:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl restart owl-awdl.service
   ```

---

## 🚨 Issue 3: Desktop Launcher Not Showing Exec Field

### **Symptoms**
Opening from Application Menu shows:
```
No Exec field in /usr/share/applications/opendrop-gui.desktop
```

### **Root Cause**
Desktop environment is caching the old .desktop file before the Exec field was added.

### **Fix**

1. **Clear desktop cache**:
   ```bash
   # GNOME
   rm -rf ~/.cache/application-state/
   
   # KDE Plasma
   rm -rf ~/.cache/ksycoca5_* ~/.config/mimeapps.list
   
   # XFCE
   rm -rf ~/.cache/xfce4/
   ```

2. **Force cache rebuild** (KDE):
   ```bash
   kbuildsycoca5 --noincremental
   ```

3. **Restart desktop environment** (simplest method):
   - Log out and log back in, OR
   - Press Super (Windows key) and search for "OpenDrop" again

4. **Verify the file is correct**:
   ```bash
   cat /usr/share/applications/opendrop-gui.desktop | grep "Exec="
   # Should show: Exec=/usr/local/bin/opendrop-gui
   ```

---

## 🚨 Issue 4: Command Not Found: opendrop-gui

### **Symptoms**
```bash
$ opendrop-gui
zsh: command not found: opendrop-gui
```

### **Root Cause**
The wrapper script wasn't installed to `/usr/local/bin/` (setup script didn't run as root).

### **Fix**

1. **Check if wrapper exists**:
   ```bash
   ls -la /usr/local/bin/opendrop-gui
   ```

2. **If missing, install it manually**:
   ```bash
   sudo cp scripts/opendrop-gui-wrapper.sh /usr/local/bin/opendrop-gui
   sudo chmod 755 /usr/local/bin/opendrop-gui
   ```

3. **Verify it works**:
   ```bash
   which opendrop-gui
   opendrop-gui  # Should launch the GUI
   ```

---

## 🚨 Issue 5: WiFi Won't Reconnect After Stopping OWL

### **Symptoms**
- OWL stops but WiFi stays disconnected
- `nmcli` command asks for password that can't be provided

### **Root Cause**
The systemd service can't reconnect to WiFi because NetworkManager needs the password for secured networks, which can't be provided in an automated script.

### **Workaround**

The service will try to reconnect, but if it fails, manually reconnect:

```bash
# Method 1: Manual reconnect
nmcli device connect wlo1

# If that fails, reconnect to the network:
nmcli device wifi connect "rb_alderson"

# Method 2: Use your password
nmcli device wifi connect "rb_alderson" password YOUR_PASSWORD

# Method 3: Click WiFi in system tray and reconnect manually
```

**Better Solution**: Store WiFi password in NetworkManager
```bash
# The password should already be saved, but if not:
nmcli connection modify "rb_alderson" wifi-sec.psk "YOUR_PASSWORD" wifi-sec.psk-flags 0
nmcli device connect wlo1
```

---

## 🚨 Issue 6: GUI Icon Is Just a Dot

### **Status**
✅ This is **cosmetic and can be improved later**

### **Current Behavior**
The system generates a simple green/gray circle icon when the icon file isn't found.

### **Future Improvement**
We'll replace with a proper OpenDrop icon from the SEEMOO Lab or create a professional icon.

---

## ✅ Verification Checklist

After applying fixes, verify everything works:

```bash
# 1. Service file is updated
sudo systemctl status owl-awdl.service
# Should show: Type=simple

# 2. CLI command works
opendrop --help

# 3. GUI wrapper is installed
which opendrop-gui
/usr/local/bin/opendrop-gui --help

# 4. Desktop launcher works
# Check: Settings → Applications → OpenDrop
# Or click "OpenDrop" in app menu

# 5. OWL starts without error
sudo systemctl start owl-awdl.service
sleep 3
ip link show awdl0
# Should show awdl0 interface

# 6. WiFi status
nmcli device status | grep wlo1
# Should show connected (after OWL fully starts)

# 7. Stop OWL cleanly
sudo systemctl stop owl-awdl.service
sleep 2
ip link show awdl0
# Should show error: Device "awdl0" does not exist

# 8. WiFi reconnected
nmcli device status | grep wlo1
# Should show connected
```

---

## 📞 Getting Help

If issues persist:

1. **Check systemd logs**:
   ```bash
   sudo journalctl -xeu owl-awdl.service | tail -50
   ```

2. **Run OWL manually to see errors**:
   ```bash
   sudo iw dev wlo1 interface add mon0 type monitor
   sudo ip link set mon0 up
   sudo /usr/local/bin/owl -i mon0
   # Press Ctrl+C to stop
   sudo iw dev mon0 del
   ```

3. **Check if OWL binary works**:
   ```bash
   /usr/local/bin/owl
   # Should show the OWL ASCII art logo
   ```

4. **Check interface capabilities**:
   ```bash
   iw phy phy0 info | grep -i "monitor\|managed"
   ```

---

## 📝 Summary of Changes Made

These fixes have been applied to the repository:

| Issue | Fix |
|-------|-----|
| OWL service fails | Changed `Type=forking` → `Type=simple` |
| WiFi reconnect fails | Added `ip link set wlo1 up` before nmcli |
| Command not found | Created and installed `/usr/local/bin/opendrop-gui` wrapper |
| Desktop cache | Clear cache and restart environment |
| Icon is a dot | Cosmetic - to be improved later |

**Next commit**: All fixes will be committed with updated systemd service.

---

**Last Updated**: 2026-05-12
**Version**: 0.14.1 (fixes)
