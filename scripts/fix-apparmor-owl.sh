#!/bin/bash

###############################################################################
# AppArmor OWL Profile Installation Script
#
# This script fixes AppArmor restrictions that prevent OWL from creating
# the monitor mode interface (mon0) needed for AWDL support.
#
# Usage: sudo bash scripts/fix-apparmor-owl.sh
#
# What it does:
# 1. Creates an AppArmor profile for OWL with proper nl80211 permissions
# 2. Tests if OWL can now create monitor interfaces
# 3. Sets the profile to enforce mode if successful
###############################################################################

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() {
    echo -e "${BLUE}[INFO]${NC} $*"
}

log_success() {
    echo -e "${GREEN}[✓]${NC} $*"
}

log_error() {
    echo -e "${RED}[✗]${NC} $*"
}

log_warn() {
    echo -e "${YELLOW}[!]${NC} $*"
}

# Require root
if [[ $EUID -ne 0 ]]; then
    log_error "This script must be run as root"
    echo "   Run: sudo bash scripts/fix-apparmor-owl.sh"
    exit 1
fi

echo -e "${BLUE}"
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║           AppArmor OWL Profile Installation                     ║"
echo "║     Fixing AppArmor restrictions for Monitor Mode Support       ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo -e "${NC}"
echo ""

# Step 1: Check if AppArmor is running
log_info "Checking AppArmor status..."
if systemctl is-active --quiet apparmor; then
    log_success "AppArmor is active"
else
    log_warn "AppArmor is not active"
    echo "   (That's fine, OWL should work anyway)"
fi

# Step 2: Create the profile
log_info "Creating OWL AppArmor profile..."

cat > /etc/apparmor.d/owl << 'PROFILE'
#include <tunables/global>

/usr/local/bin/owl {
  #include <abstractions/base>
  #include <abstractions/nameservice>

  # Capabilities for wireless operations (netlink, raw sockets)
  capability net_admin,
  capability net_raw,
  capability sys_admin,

  # Network operations
  network inet raw,
  network inet dgram,
  network unix stream,
  network unix dgram,
  network netlink raw,

  # System interface access
  /sys/class/net/ r,
  /sys/class/net/** rw,
  /sys/module/** r,
  /proc/sys/net/** rw,
  /proc/net/** r,

  # Device access (TUN for awdl0 interface)
  /dev/net/tun rw,
  /dev/urandom r,
  /dev/null rw,

  # Runtime and temporary files
  /run/** rw,
  /tmp/** rw,

  # Logging
  /var/log/** w,

  # OWL binary
  /usr/local/bin/owl mr,
  /usr/local/bin/owl.orig mr,
}
PROFILE

log_success "AppArmor profile created"

# Step 3: Load the profile
log_info "Loading AppArmor profile..."
if apparmor_parser -r /etc/apparmor.d/owl 2>/dev/null; then
    log_success "Profile loaded into AppArmor"
else
    log_warn "Could not reload AppArmor (might not be fully active), continuing..."
fi

echo ""
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║                   Testing OWL Functionality                     ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

# Step 4: Clean up any existing mon0
log_info "Checking for existing mon0 interface..."
if ip link show mon0 &>/dev/null; then
    log_warn "mon0 already exists, removing..."
    iw dev mon0 del
    sleep 1
fi

# Step 5: Test creating mon0
log_info "Attempting to create mon0 monitor interface..."
if iw dev wlo1 interface add mon0 type monitor 2>&1; then
    log_success "mon0 created successfully!"

    log_info "Bringing mon0 up..."
    ip link set mon0 up
    log_success "mon0 is up"

    echo ""
    log_info "Testing OWL binary..."
    sleep 1
    timeout 3 /usr/local/bin/owl -i mon0 2>&1 || true
    sleep 1

    echo ""
    log_info "Checking if awdl0 interface was created..."
    if ip link show awdl0 &>/dev/null; then
        log_success "✓✓✓ SUCCESS! awdl0 interface created by OWL!"
        echo ""
        echo "Interface status:"
        ip link show awdl0
        echo ""
        echo "IPv6 address:"
        ip -6 addr show awdl0
        echo ""
        SUCCESS=1
    else
        log_warn "awdl0 was not created (OWL might need more debug)"
        SUCCESS=0
    fi

    # Cleanup
    echo ""
    log_info "Cleaning up test interfaces..."
    iw dev mon0 del 2>/dev/null || true
    sleep 1
    log_success "Cleanup complete"
else
    log_error "Failed to create mon0!"
    echo ""
    echo "Possible causes:"
    echo "  1. WiFi driver doesn't support monitor mode"
    echo "  2. WiFi interface is locked by another process"
    echo "  3. Kernel modules need reloading"
    echo ""
    echo "Try:"
    echo "  sudo modprobe -r iwlwifi"
    echo "  sudo modprobe iwlwifi"
    echo "  sudo bash scripts/fix-apparmor-owl.sh"
    SUCCESS=0
fi

echo ""
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║                      Final Status                               ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

if [ $SUCCESS -eq 1 ]; then
    log_success "AppArmor profile fixed and OWL is working!"
    echo ""
    echo "Next steps:"
    echo "  1. Reload systemd daemon:"
    echo "     sudo systemctl daemon-reload"
    echo ""
    echo "  2. Start OWL via systemd:"
    echo "     sudo systemctl start owl-awdl.service"
    echo ""
    echo "  3. Launch OpenDrop GUI:"
    echo "     opendrop-gui"
    echo ""
else
    log_error "Setup incomplete - further debugging needed"
    echo ""
    echo "Check:"
    echo "  • WiFi driver supports monitor mode: iw phy phy0 info | grep monitor"
    echo "  • Try reloading WiFi driver: sudo modprobe -r iwlwifi && sudo modprobe iwlwifi"
    echo "  • Run debug tool: sudo bash scripts/debug-owl.sh"
fi

log_success "AppArmor configuration complete!"
exit 0
