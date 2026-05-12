# OpenDrop-GUI User Support Strategy

## Overview
Strategy for handling common issues when OpenDrop-GUI is released to the public. Focus on **automatic detection**, **easy fixes**, and **clear guidance**.

---

## 1. Automated Issue Detection

### 1.1 System Requirements Check Script
**File**: `scripts/check-system.sh`

Run at installation or first launch to detect:
- ✅ Python version (3.10+)
- ✅ Required packages (libarchive, openssl, iw, ip, nmcli)
- ✅ OWL binary installed
- ✅ WiFi adapter present
- ✅ Monitor mode support
- ✅ AppArmor/SELinux restrictions
- ✅ Kernel modules loaded

**Output**: Green/yellow/red status report with fixes

---

### 1.2 Pre-Launch Diagnostic

Run automatically when GUI starts:

```python
# In opendrop/gui/main.py
def check_system_requirements():
    checks = {
        'owl_binary': check_owl_installed(),
        'wifi_interface': check_wifi_available(),
        'monitor_mode': check_monitor_mode_support(),
        'apparmor': check_apparmor_restrictions(),
        'permissions': check_sudo_permissions(),
    }
    
    if any_critical_issue(checks):
        show_setup_wizard(checks)
    else:
        proceed_to_main_window()
```

---

## 2. Automatic Issue Resolution

### 2.1 AppArmor Profile Auto-Fix

**Trigger**: On first launch or when AppArmor blocks OWL

```python
# In opendrop/gui/owl_manager.py
def start(self):
    try:
        systemctl('start', 'owl-awdl.service')
    except OWLStartFailed as e:
        if 'Operation not permitted' in str(e):
            if self.try_fix_apparmor():
                self.start()  # Retry
            else:
                show_apparmor_dialog()
```

**What it does:**
1. Detects AppArmor is blocking
2. Offers to install the profile
3. Requests password via GUI dialog (cleaner than terminal)
4. Retries OWL startup
5. Shows success/failure message

---

### 2.2 Missing Dependency Auto-Install

**For Linux package managers:**

```bash
# Debian/Ubuntu/Parrot
if ! command -v iw &>/dev/null; then
    apt-get install iw
fi

# Fedora
if ! command -v iw &>/dev/null; then
    dnf install wireless-tools
fi

# Arch
if ! command -v iw &>/dev/null; then
    pacman -S wireless_tools
fi
```

**Triggered by**: Missing packages detected at startup

---

## 3. Smart Error Messages

### 3.1 User-Friendly Error Dialog

Instead of:
```
Failed to start OWL: Job for owl-awdl.service failed because the control 
process exited with error code. See "systemctl status owl-awdl.service" 
and "journalctl -xeu owl-awdl.service" for details.
```

Show:
```
🔴 AWDL Startup Failed

Issue: Your WiFi adapter doesn't support monitor mode
(or security settings are blocking it)

What you can do:
1. Temporarily disable AppArmor: sudo systemctl stop apparmor
2. Use a secondary USB WiFi adapter
3. Check system requirements: opendrop-check

Need help? View troubleshooting guide
[View Guide]  [Troubleshoot]  [Advanced Options]
```

---

### 3.2 Contextual Help Links

Link to specific documentation based on error:
- AppArmor issue → APPARMOR_TROUBLESHOOTING.md
- Monitor mode not supported → HARDWARE_REQUIREMENTS.md
- WiFi won't reconnect → WIFI_TROUBLESHOOTING.md
- Permission denied → PERMISSIONS.md

---

## 4. Guided Setup Wizard

### 4.1 First-Time Setup

When any issue detected:

```
Step 1: Checking System Requirements...
  ✓ Python 3.13.5
  ✓ libarchive
  ✓ OWL binary
  ⚠ AppArmor (blocking monitor mode)
  
Step 2: What Would You Like To Do?
  [A] Fix AppArmor automatically (requires password)
  [B] Disable AppArmor temporarily
  [C] Use secondary USB WiFi adapter
  [D] Show detailed troubleshooting guide
  [E] Skip for now (OWL won't work)
```

### 4.2 Post-Fix Verification

After attempting fix:
```
Verifying fix...
  Creating test mon0 interface... ✓
  Starting OWL... ✓
  Creating awdl0... ✓
  
✅ System is ready! You can now use OpenDrop.
```

---

## 5. Built-In Diagnostic Tools

### 5.1 Help Menu in GUI

**Menu → Help → System Diagnostics**

Opens dialog showing:
- ✅ System status (green/yellow/red)
- 🔧 Available fixes (with one-click apply)
- 📋 Detailed info (for advanced users)
- 🐛 Export diagnostics (for bug reports)

### 5.2 Command-Line Tools

```bash
# Quick system check
opendrop-check

# Detailed diagnostics
opendrop-check --verbose

# Export for debugging
opendrop-check --export-report > report.txt

# Run specific test
opendrop-check --test monitor-mode
opendrop-check --test apparmor
opendrop-check --test wifi-driver
```

---

## 6. Fallback Solutions

### 6.1 When Monitor Mode Unavailable

**Show options:**

```
Your WiFi adapter doesn't support monitor mode.

Options:

1. ✅ Use a secondary USB WiFi adapter (RECOMMENDED)
   - Buy: Amazon, eBay (~$15-30)
   - Models: TP-Link TL-WN722N, Alfa AWUS036, etc.
   - Configure: Scripts > Use Secondary Adapter
   
2. ⚠️ Try on different interface (might not discover devices)
   - opendrop-gui --interface=wlan0
   
3. ❌ Use virtual machine with passthrough WiFi
   - Advanced option for VirtualBox/KVM users

[Learn More]  [Shop for Adapters]  [Community Forum]
```

---

### 6.2 When AppArmor Can't Be Fixed

**Fallback sequence:**
1. Try auto-fix AppArmor profile
2. If fails: Offer to disable AppArmor temporarily
3. If user refuses: Explain limitations
4. Suggest: Use secondary USB adapter instead

---

## 7. Documentation Strategy

### 7.1 Tiered Documentation

**Level 1: GUI Help** (most users)
- Built into the application
- Contextual (shows help for the current issue)
- Plain English, no jargon

**Level 2: User Guide** (technical users)
- Installation.md
- Troubleshooting.md
- FAQ.md

**Level 3: Advanced** (power users/developers)
- ARCHITECTURE.md
- APPARMOR_PROFILE.md
- KERNEL_MODULES.md

**Level 4: Source Code** (contributors)
- Inline code comments
- Design docs
- API documentation

### 7.2 Auto-Update Documentation

When new issues found:
```python
# Fetch latest docs from GitHub
if outdated_documentation():
    download_latest_docs()
    show_notification("Updated troubleshooting guides available")
```

---

## 8. Feedback & Telemetry

### 8.1 Anonymous Error Reporting

**With user permission:**
```python
if error_occurs():
    show_dialog("""
    OpenDrop encountered an issue:
    {error_message}
    
    Would you like to help us improve?
    [Send Anonymous Report]  [No Thanks]
    """)
    
    if user_agrees():
        send_telemetry({
            'error': error_type,
            'system': os_info,
            'app_version': version,
            'timestamp': now(),
        })
```

**No sensitive data** - just error type, OS, version

### 8.2 User Survey

After successful setup:
```
✅ OpenDrop is working!

Quick feedback (30 seconds):
  How did you set it up?
  □ Automatic AppArmor fix
  □ Manual AppArmor fix
  □ Secondary USB adapter
  □ Disabled AppArmor
  
Any issues during setup?
  □ Yes (describe)
  □ No
  
[Submit Feedback]
```

---

## 9. Community Support

### 9.1 Help Resources

- **GitHub Issues**: Bug reports & feature requests
- **Discussions Board**: General help & troubleshooting
- **Discord/Slack**: Real-time community chat
- **Reddit**: r/linux, r/airdrop communities
- **Wiki**: Community-maintained troubleshooting

### 9.2 Support Bot

Auto-response for common issues:

```
User: "OWL won't start"

Bot: Found 47 similar issues. Most common solutions:
  1. AppArmor blocking (73% of cases)
     → Run: sudo bash scripts/fix-apparmor-owl.sh
     
  2. Monitor mode not supported (18% of cases)
     → Buy USB WiFi adapter
     
  3. WiFi driver issue (9% of cases)
     → Try: sudo modprobe -r iwlwifi && sudo modprobe iwlwifi

[Detailed Guide]  [Still Stuck? Create Issue]
```

---

## 10. Installation Installer

### 10.1 GUI Installer for Easy Setup

Create graphical installer (`opendrop-installer.py`):

```
┌─────────────────────────────────┐
│ OpenDrop Installer              │
├─────────────────────────────────┤
│ Step 1: Check Requirements      │
│ ✓ Python                        │
│ ✓ Dependencies                  │
│ ⚠ AppArmor (fixable)           │
│                                 │
│ [Next]                          │
└─────────────────────────────────┘
```

**Features:**
- Auto-detect system issues
- One-click fixes for common problems
- Install OWL if not present
- Configure AppArmor
- Test setup
- Uninstall option

### 10.2 Package Manager Support

Distribute via:
- **PyPI**: `pip install opendrop-gui` (basic)
- **APT (Ubuntu/Debian)**: `apt install opendrop-gui`
- **AUR (Arch)**: `yay -S opendrop-gui`
- **Snap**: `snap install opendrop-gui`
- **Flatpak**: `flatpak install opendrop-gui`

Each with auto-fix scripts for package manager-specific issues

---

## 11. Issue Matrix

| Issue | Auto-Detect | Auto-Fix | GUI Option | CLI Tool | Docs |
|-------|------------|----------|-----------|----------|------|
| AppArmor blocks | ✅ | ✅ | ✅ | ✅ | ✅ |
| Missing OWL | ✅ | ✅ | ✅ | ✅ | ✅ |
| Monitor mode not supported | ✅ | ⚠️* | ✅ | ✅ | ✅ |
| WiFi won't reconnect | ✅ | ⚠️* | ✅ | ✅ | ✅ |
| Permission denied | ✅ | ✅ | ✅ | ✅ | ✅ |
| Python version wrong | ✅ | ❌ | ✅ | ✅ | ✅ |
| WiFi driver issue | ✅ | ⚠️* | ✅ | ✅ | ✅ |

`*` = Can suggest solution, may need hardware change

---

## 12. Success Metrics

Track:
- Installation success rate
- Common issues encountered
- Time to resolve each issue
- User satisfaction
- Support tickets
- Community contribution

**Goal**: 95%+ users successfully running within 5 minutes of install

---

## Implementation Timeline

| Phase | Deliverables |
|-------|--------------|
| **v0.15** | Automated checks, AppArmor auto-fix, GUI diagnostics |
| **v0.16** | Installer, documentation improvements, help system |
| **v0.17** | Feedback system, support bot, community resources |
| **v0.18** | Package managers (APT, AUR, Snap) |
| **v1.0** | Full production support, telemetry, updates |

---

## Key Principles

1. **User First**: Make the common case (AppArmor) work automatically
2. **Clear Guidance**: Explain what's wrong in plain language
3. **Fallback Options**: Always offer alternatives
4. **Community**: Build support channels early
5. **Transparency**: Share what we know about limitations
6. **Iterate**: Learn from user issues, improve continuously

---

## Conclusion

By implementing this strategy, OpenDrop-GUI will be:
- ✅ **Beginner-friendly**: Automatic detection and fixes
- ✅ **Technical-friendly**: Advanced troubleshooting tools
- ✅ **Community-supported**: Multiple help channels
- ✅ **Robust**: Handles edge cases gracefully
- ✅ **Production-ready**: For public release

This transforms OpenDrop from a "developer tool" into a **product users can install and use**.
