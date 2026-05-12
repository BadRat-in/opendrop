#!/bin/bash

###############################################################################
# OpenDrop OWL Setup Script
#
# This script must be run as root or with sudo.
# It performs one-time setup for OWL AWDL integration:
# 1. Validates required tools are installed
# 2. Checks WiFi hardware capability (concurrent monitor+managed mode)
# 3. Installs systemd service
# 4. Configures sudoers for privilege escalation
# 5. Installs desktop launcher
#
# Usage: sudo bash scripts/setup-owl.sh
###############################################################################

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SYSTEMD_SRC="${PROJECT_ROOT}/systemd/owl-awdl.service"
VENV_PATH="${PROJECT_ROOT}/.venv"

# ============================================================================
# Helper Functions
# ============================================================================

log_info() {
    echo -e "${BLUE}[INFO]${NC} $*"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $*"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $*"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $*"
}

require_root() {
    if [[ $EUID -ne 0 ]]; then
        log_error "This script must be run as root. Use: sudo bash scripts/setup-owl.sh"
        exit 1
    fi
}

check_command() {
    if ! command -v "$1" &> /dev/null; then
        log_error "Required command not found: $1"
        return 1
    fi
}

# ============================================================================
# Main Setup
# ============================================================================

echo -e "${BLUE}"
echo "╔═══════════════════════════════════════════════════════════════╗"
echo "║         OpenDrop OWL AWDL Setup Wizard                         ║"
echo "║  This will install and configure OWL for AirDrop support       ║"
echo "╚═══════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# Step 1: Verify we're running as root
log_info "Checking root privileges..."
require_root
log_success "Running as root ✓"

# Step 2: Check for required commands
log_info "Checking for required tools..."
for cmd in iw ip owl nmcli systemctl; do
    if check_command "$cmd"; then
        log_success "Found: $cmd"
    else
        log_error "Missing required tool: $cmd"
        exit 1
    fi
done

# Step 3: Check WiFi hardware capability
log_info "Checking WiFi hardware capability for concurrent monitor+managed mode..."
log_warn ""
log_warn "NOTE: On this hardware, OWL will require putting the WiFi adapter"
log_warn "into monitor mode, which will briefly interrupt your WiFi connection."
log_warn "The connection will be automatically restored when OWL stops."
log_warn ""

# Try to detect hardware capability using iw
if iw phy phy0 info &> /dev/null; then
    if iw phy phy0 info | grep -q "managed.*monitor.*simultaneous"; then
        log_success "Hardware supports concurrent monitor+managed mode - WiFi won't be interrupted ✓"
    else
        log_warn "Hardware does NOT support concurrent monitor+managed mode"
        log_warn "WiFi WILL be interrupted while OWL is running"
        log_warn "This is a hardware limitation, not a bug"
    fi
else
    log_warn "Could not determine hardware capability - proceeding anyway"
fi

# Step 4: Check if owl binary exists and has execute permissions
log_info "Checking OWL installation..."
if [[ ! -x /usr/local/bin/owl ]]; then
    log_error "OWL binary not found at /usr/local/bin/owl or not executable"
    log_error "Please install OWL first: https://github.com/seemoo-lab/owl"
    exit 1
fi
log_success "OWL binary found and executable ✓"

# Step 5: Install systemd service
log_info "Installing systemd service..."
if [[ ! -f "$SYSTEMD_SRC" ]]; then
    log_error "systemd service file not found at $SYSTEMD_SRC"
    exit 1
fi

cp "$SYSTEMD_SRC" /etc/systemd/system/owl-awdl.service
chmod 644 /etc/systemd/system/owl-awdl.service
log_success "Installed systemd service to /etc/systemd/system/owl-awdl.service ✓"

# Step 6: Reload systemd daemon
log_info "Reloading systemd daemon..."
systemctl daemon-reload
log_success "Systemd daemon reloaded ✓"

# Step 7: Set up sudoers rule for privilege escalation
log_info "Configuring sudoers for privilege-less OWL control..."
SUDOERS_FILE="/etc/sudoers.d/opendrop"

cat > "$SUDOERS_FILE" << 'EOF'
# OpenDrop AWDL Management
# Allows members of the sudo group to start/stop/status the OWL AWDL service
# without requiring a password. This enables the GUI to work smoothly.

%sudo ALL=(ALL) NOPASSWD: /usr/bin/systemctl start owl-awdl.service
%sudo ALL=(ALL) NOPASSWD: /usr/bin/systemctl stop owl-awdl.service
%sudo ALL=(ALL) NOPASSWD: /usr/bin/systemctl status owl-awdl.service
EOF

chmod 440 "$SUDOERS_FILE"
log_success "Installed sudoers rule to $SUDOERS_FILE ✓"

# Validate sudoers syntax
if ! visudo -c -f "$SUDOERS_FILE" &> /dev/null; then
    log_error "Invalid sudoers syntax!"
    rm "$SUDOERS_FILE"
    exit 1
fi

# Step 8: Install GUI wrapper script
log_info "Installing GUI wrapper script..."
WRAPPER_SRC="${PROJECT_ROOT}/scripts/opendrop-gui-wrapper.sh"
WRAPPER_DST="/usr/local/bin/opendrop-gui"

if [[ ! -f "$WRAPPER_SRC" ]]; then
    log_error "Wrapper script not found at $WRAPPER_SRC"
    exit 1
fi

cp "$WRAPPER_SRC" "$WRAPPER_DST"
chmod 755 "$WRAPPER_DST"
log_success "Installed GUI wrapper to $WRAPPER_DST ✓"

# Step 9: Install helper scripts
log_info "Installing helper scripts..."

# Install WiFi reconnection helper
WIFI_HELPER_SRC="${PROJECT_ROOT}/scripts/wifi-reconnect.sh"
WIFI_HELPER_DST="/usr/local/bin/wifi-reconnect"
if [[ -f "$WIFI_HELPER_SRC" ]]; then
    cp "$WIFI_HELPER_SRC" "$WIFI_HELPER_DST"
    chmod 755 "$WIFI_HELPER_DST"
    log_success "Installed WiFi reconnection helper to $WIFI_HELPER_DST ✓"
fi

# Install OWL debug script
DEBUG_HELPER_SRC="${PROJECT_ROOT}/scripts/debug-owl.sh"
DEBUG_HELPER_DST="/usr/local/bin/owl-debug"
if [[ -f "$DEBUG_HELPER_SRC" ]]; then
    cp "$DEBUG_HELPER_SRC" "$DEBUG_HELPER_DST"
    chmod 755 "$DEBUG_HELPER_DST"
    log_success "Installed OWL debug tool to $DEBUG_HELPER_DST ✓"
fi

# Step 10: Create desktop launcher (if GUI is used)
log_info "Setting up desktop launcher..."
DESKTOP_FILE="/usr/share/applications/opendrop-gui.desktop"

cat > "$DESKTOP_FILE" << 'EOF'
[Desktop Entry]
Version=1.0
Type=Application
Terminal=false
Name=OpenDrop
Comment=AirDrop-compatible file sharing for Linux
Comment[de]=AirDrop-kompatibles Dateifreigabesystem für Linux
Icon=opendrop
Exec=/usr/local/bin/opendrop-gui
Categories=Network;FileTransfer;
Keywords=airdrop;filesharing;wifi;awdl;
StartupNotify=false
NoDisplay=false
EOF

chmod 644 "$DESKTOP_FILE"
log_success "Created desktop launcher to $DESKTOP_FILE ✓"

# Step 11: Summary and next steps
echo ""
echo -e "${GREEN}╔═══════════════════════════════════════════════════════════════╗"
echo "║                   Setup Complete!                                ║"
echo "╚═══════════════════════════════════════════════════════════════╝${NC}"
echo ""
log_success "OWL AWDL integration is now ready!"
echo ""
echo "Available commands:"
echo ""
echo "• opendrop-gui                    # Launch GUI"
echo "• opendrop find                   # Discover devices"
echo "• opendrop send -r <device> ...   # Send files"
echo "• opendrop receive                # Receive files"
echo ""
echo "Helper tools:"
echo ""
echo "• wifi-reconnect                  # Manually reconnect WiFi after OWL stops"
echo "• owl-debug                       # Debug OWL startup issues"
echo ""
echo "Now you can use OpenDrop in three ways:"
echo ""
echo "1. Command line (from anywhere):"
echo "   opendrop-gui                    # Launch GUI"
echo "   opendrop find                   # Discover devices"
echo "   opendrop send -r <device> ...   # Send files"
echo "   opendrop receive                # Receive files"
echo ""
echo "2. Application menu:"
echo "   Look for 'OpenDrop' in your application menu"
echo ""
echo "3. Manual OWL control:"
echo ""
echo "2. Verify awdl0 interface was created:"
echo "   ip link show awdl0"
echo ""
echo "3. Start receiving files:"
echo "   opendrop receive"
echo ""
echo "4. Discover nearby devices:"
echo "   opendrop find"
echo ""
echo -e "${YELLOW}⚠  IMPORTANT:${NC}"
echo "   • OWL requires your WiFi interface (wlo1) to be in monitor mode"
echo "   • This may briefly interrupt your WiFi connection"
echo "   • The connection will be restored when OWL stops"
echo "   • The GUI will warn you about this before starting OWL"
echo ""
echo "For more information, visit: https://owlink.org"
echo ""

log_success "Setup complete!"
exit 0
