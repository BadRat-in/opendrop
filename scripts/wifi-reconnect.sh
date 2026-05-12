#!/bin/bash

###############################################################################
# WiFi Reconnection Helper Script
#
# Reconnects to saved WiFi networks after OWL stops.
# Install to /usr/local/bin/wifi-reconnect.sh
#
# The OWL systemd service puts WiFi into monitor mode, which disconnects it.
# This script reconnects to previously connected networks.
#
# Usage: wifi-reconnect.sh
###############################################################################

set -e

echo "Attempting to reconnect WiFi interface (wlo1)..."

# Step 1: Ensure interface is up
echo "  [1/3] Bringing interface up..."
ip link set wlo1 up || true
sleep 1

# Step 2: Try automatic reconnection (uses saved credentials)
echo "  [2/3] Reconnecting to saved network..."
nmcli device connect wlo1 2>&1 | grep -v "Warning" | grep -v "nm-cli" || true
sleep 2

# Step 3: Verify connection
echo "  [3/3] Verifying connection..."
if nmcli device status | grep -q "wlo1.*connected"; then
    echo "✓ WiFi reconnected successfully!"
    nmcli device status | grep wlo1
    exit 0
else
    echo "⚠ WiFi still disconnected. Manual action needed:"
    echo ""
    echo "  Option 1: Click WiFi in system tray and reconnect"
    echo ""
    echo "  Option 2: Reconnect via command:"
    echo "    nmcli device wifi connect 'rb_alderson' password YOUR_PASSWORD"
    echo ""
    echo "  Option 3: List available networks:"
    echo "    nmcli device wifi list"
    exit 1
fi
