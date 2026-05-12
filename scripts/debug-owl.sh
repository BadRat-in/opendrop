#!/bin/bash

###############################################################################
# OWL Debugging Script
#
# This script helps diagnose why OWL might be failing to start.
# Run this to see detailed error messages from OWL.
#
# Usage: sudo bash scripts/debug-owl.sh
###############################################################################

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║                    OWL Debugging Script                         ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

# Check if running as root
if [[ $EUID -ne 0 ]]; then
    echo "❌ This script must be run as root"
    echo "   Run: sudo bash scripts/debug-owl.sh"
    exit 1
fi

echo "Step 1: Checking OWL binary..."
if ! command -v owl &> /dev/null; then
    echo "❌ OWL binary not found!"
    echo "   Install OWL: git clone https://github.com/seemoo-lab/owl && cd owl && make && sudo make install"
    exit 1
fi
echo "✓ OWL binary found: $(which owl)"
echo ""

echo "Step 2: Checking WiFi interface..."
if ! ip link show wlo1 &> /dev/null; then
    echo "⚠ Interface 'wlo1' not found"
    echo "   Available interfaces:"
    ip link show | grep ":" | awk '{print "   - " $2}'
    echo ""
    read -p "Enter your WiFi interface name (e.g., wlan0): " WIFI_IF
    if [[ -z "$WIFI_IF" ]]; then
        echo "❌ No interface specified"
        exit 1
    fi
else
    WIFI_IF="wlo1"
fi
echo "✓ Using interface: $WIFI_IF"
echo ""

echo "Step 3: Checking for existing mon0 interface..."
if ip link show mon0 &> /dev/null; then
    echo "⚠ mon0 already exists (from previous failed attempt)"
    echo "   Cleaning up..."
    iw dev mon0 del 2>/dev/null || true
    sleep 1
fi
echo "✓ mon0 cleaned up"
echo ""

echo "Step 4: Creating monitor interface..."
echo "   Running: iw dev $WIFI_IF interface add mon0 type monitor"
if ! iw dev "$WIFI_IF" interface add mon0 type monitor; then
    echo "❌ Failed to create mon0 interface"
    echo ""
    echo "Possible causes:"
    echo "  1. WiFi interface is locked by another process"
    echo "  2. Driver doesn't support monitor mode"
    echo "  3. Missing kernel modules"
    echo ""
    echo "Try:"
    echo "  sudo modprobe -a mac80211 cfg80211"
    exit 1
fi
echo "✓ mon0 interface created"
echo ""

echo "Step 5: Bringing mon0 up..."
if ! ip link set mon0 up; then
    echo "❌ Failed to bring mon0 up"
    iw dev mon0 del 2>/dev/null || true
    exit 1
fi
echo "✓ mon0 interface is up"
echo ""

echo "Step 6: Testing OWL binary..."
echo "   Running: owl -i mon0"
echo "   (Press Ctrl+C to stop after seeing the startup message)"
echo ""
echo "================================================================"

# Run OWL and capture output
timeout 10 owl -i mon0 2>&1 &
OWL_PID=$!
sleep 3

# Check if OWL is still running
if kill -0 $OWL_PID 2>/dev/null; then
    echo ""
    echo "================================================================"
    echo "✓ OWL appears to be running!"
    echo ""
    echo "Check if awdl0 was created:"
    ip link show awdl0 && echo "✓ awdl0 is up" || echo "⚠ awdl0 not found"
    echo ""
    echo "Stopping OWL..."
    kill $OWL_PID 2>/dev/null || true
    wait $OWL_PID 2>/dev/null || true
else
    echo ""
    echo "================================================================"
    echo "❌ OWL exited with an error"
    echo ""
    echo "Check the output above for error messages"
fi

echo ""
echo "Step 7: Cleaning up..."
iw dev mon0 del 2>/dev/null || true
sleep 1
echo "✓ mon0 interface removed"
echo ""

echo "════════════════════════════════════════════════════════════════"
echo "Debug complete!"
echo ""
echo "If OWL failed:"
echo "  1. Check the error messages above"
echo "  2. See: https://github.com/seemoo-lab/owl/issues"
echo "  3. Ensure your WiFi adapter supports monitor mode"
echo ""
echo "Next steps:"
echo "  • If successful: sudo systemctl start owl-awdl.service"
echo "  • If failed: Check driver/kernel module support"
echo ""
