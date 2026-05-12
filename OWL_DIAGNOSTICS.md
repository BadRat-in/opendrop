# OWL Monitor Mode Issue - Diagnostics and Resolution

## Problem Summary

OWL fails with: `ERROR: Error while receiving via netlink: Operation not supported`

The monitor interface (mon0) CAN be created successfully, but OWL cannot initialize it for AWDL operations.

## Root Cause Analysis

### What Works ✓
- AppArmor: Fixed and verified
- Kernel modules: All loaded (iwlwifi, mac80211, cfg80211)
- Monitor mode support: Confirmed in driver capabilities
- mon0 creation: Successful via `iw dev wlo1 interface add mon0 type monitor`

### What Fails ✗
- OWL netlink operations on mon0
- Error: "Operation not supported" when OWL tries to configure monitor interface

### Contributing Factors

1. **Regulatory Domain Restrictions (PRIMARY CAUSE)**
   - Current domain: **IN (India)** - self-managed
   - Passive-scan only restrictions on many frequencies
   - Firmware enforces these rules, limiting monitor mode operations
   - iwlwifi firmware may restrict certain nl80211 operations based on country code

2. **WiFi Driver Limitations**
   - iwlwifi driver has firmware-enforced restrictions
   - Not all monitor mode operations are supported on all hardware
   - Monitor mode may require additional configuration

## Solution Options

### Option 1: Change Regulatory Domain (Most Likely to Work)
```bash
# Temporarily set to worldwide (00) which has fewer restrictions
sudo iw reg set 00

# Then try OWL again
sudo systemctl restart owl-awdl.service
```

**Pros:**
- May enable full monitor mode functionality
- Simple to try

**Cons:**
- Requires root
- May violate local regulations (only for testing)
- Not permanent after reboot

### Option 2: Set Permanent Regulatory Domain
```bash
# Check what country code you want (e.g., US, GB, DE, etc.)
# Then configure in /etc/default/crda
echo "REGDOMAIN=US" | sudo tee /etc/default/crda

# Or use regulatory database tool
sudo iw reg set US
```

### Option 3: Update iwlwifi Firmware
```bash
# Check current firmware version
sudo modinfo iwlwifi | grep version

# Check available firmware
ls -la /lib/firmware/iwlwifi-*

# Reload driver with latest firmware
sudo modprobe -r iwlwifi iwlmvm
sudo modprobe iwlwifi iwlmvm
```

### Option 4: Check OWL Compatibility
- Visit: https://github.com/seemoo-lab/owl/issues
- Search for: "Operation not supported" + iwlwifi
- Look for known limitations on Intel WiFi hardware

## Immediate Next Steps

1. **Try setting regulatory domain to worldwide:**
   ```bash
   sudo iw reg set 00
   sudo bash scripts/debug-owl.sh
   ```

2. **If that works, set permanent domain:**
   ```bash
   # For your country (replace XX with your code)
   echo "REGDOMAIN=XX" | sudo tee /etc/default/crda
   ```

3. **Report findings** - if it works, we'll document the permanent fix

## Alternative: Use Secondary WiFi Adapter

If regulatory domain doesn't help, the reliable workaround is:
1. Get a USB WiFi adapter (TP-Link TL-WN722N, Alfa AWUS036, etc.)
2. OWL can use the secondary adapter while main WiFi stays on primary
3. Add logic to detect and use secondary adapter

## Files Updated

- This diagnostic file added to track investigation
- No code changes yet - awaiting regulatory domain testing

## References

- iwlwifi driver source: https://git.kernel.org/pub/scm/linux/kernel/git/iwlwifi/iwlwifi.git
- Linux regulatory framework: https://wireless.wiki.kernel.org/en/developers/regulatory
- OWL project: https://github.com/seemoo-lab/owl

