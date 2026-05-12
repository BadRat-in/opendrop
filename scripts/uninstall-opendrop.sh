#!/bin/bash

###############################################################################
# OpenDrop Complete Uninstaller
#
# Removes all OpenDrop-related files, configs, and system integration
# to allow for a fresh clean installation.
#
# Usage: bash scripts/uninstall-opendrop.sh
###############################################################################

set +e  # Don't exit on errors

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

removed_items=0

log_info() {
    echo -e "${BLUE}[INFO]${NC} $*"
}

log_success() {
    echo -e "${GREEN}[✓]${NC} $*"
    ((removed_items++))
}

log_warn() {
    echo -e "${YELLOW}[!]${NC} $*"
}

log_error() {
    echo -e "${RED}[✗]${NC} $*"
}

echo -e "${BLUE}"
echo "╔═══════════════════════════════════════════════════════════════╗"
echo "║          OpenDrop Complete Uninstaller                         ║"
echo "║  This will remove ALL OpenDrop files and configurations        ║"
echo "╚═══════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# Confirmation
read -p "Are you sure you want to REMOVE all OpenDrop files? (yes/no): " confirm
if [[ "$confirm" != "yes" ]]; then
    echo "Uninstall cancelled."
    exit 0
fi

echo ""
echo "Starting uninstall..."
echo ""

# ============================================================================
# 1. Stop running processes
# ============================================================================
log_info "Stopping OpenDrop processes..."

pkill -f "opendrop-gui" 2>/dev/null && log_success "Stopped opendrop-gui process" || true
pkill -f "python.*opendrop" 2>/dev/null && log_success "Stopped OpenDrop Python processes" || true
sleep 1

# ============================================================================
# 2. Remove system-wide installations
# ============================================================================
log_info "Removing system-wide installations..."

# Remove wrapper script
if [[ -f /usr/local/bin/opendrop-gui ]]; then
    sudo rm -f /usr/local/bin/opendrop-gui 2>/dev/null && log_success "Removed /usr/local/bin/opendrop-gui" || log_warn "Could not remove /usr/local/bin/opendrop-gui"
fi

# Remove helper scripts
if [[ -f /usr/local/bin/wifi-reconnect ]]; then
    sudo rm -f /usr/local/bin/wifi-reconnect 2>/dev/null && log_success "Removed /usr/local/bin/wifi-reconnect" || true
fi

if [[ -f /usr/local/bin/owl-debug ]]; then
    sudo rm -f /usr/local/bin/owl-debug 2>/dev/null && log_success "Removed /usr/local/bin/owl-debug" || true
fi

# Remove desktop launcher
if [[ -f /usr/share/applications/opendrop-gui.desktop ]]; then
    sudo rm -f /usr/share/applications/opendrop-gui.desktop 2>/dev/null && log_success "Removed desktop launcher" || log_warn "Could not remove desktop launcher"
fi

# Clear desktop cache
if command -v update-desktop-database &> /dev/null; then
    sudo update-desktop-database 2>/dev/null && log_success "Cleared desktop database" || true
fi

# ============================================================================
# 3. Remove systemd service
# ============================================================================
log_info "Removing systemd service..."

if [[ -f /etc/systemd/system/owl-awdl.service ]]; then
    sudo systemctl stop owl-awdl.service 2>/dev/null || true
    sudo systemctl disable owl-awdl.service 2>/dev/null || true
    sudo rm -f /etc/systemd/system/owl-awdl.service 2>/dev/null && log_success "Removed systemd service" || log_warn "Could not remove systemd service"
    sudo systemctl daemon-reload 2>/dev/null || true
fi

# ============================================================================
# 4. Remove sudoers configuration
# ============================================================================
log_info "Removing sudoers configuration..."

if [[ -f /etc/sudoers.d/opendrop ]]; then
    sudo rm -f /etc/sudoers.d/opendrop 2>/dev/null && log_success "Removed sudoers configuration" || log_warn "Could not remove sudoers"
fi

# ============================================================================
# 5. Remove AppArmor profile
# ============================================================================
log_info "Removing AppArmor profile..."

if [[ -f /etc/apparmor.d/owl ]]; then
    sudo apparmor_parser -R /etc/apparmor.d/owl 2>/dev/null || true
    sudo rm -f /etc/apparmor.d/owl 2>/dev/null && log_success "Removed AppArmor profile" || log_warn "Could not remove AppArmor profile"
fi

# ============================================================================
# 6. Remove user configuration and cache
# ============================================================================
log_info "Removing user configuration..."

if [[ -d ~/.config/opendrop ]]; then
    rm -rf ~/.config/opendrop 2>/dev/null && log_success "Removed ~/.config/opendrop" || log_warn "Could not remove config directory"
fi

if [[ -d ~/.cache/opendrop ]]; then
    rm -rf ~/.cache/opendrop 2>/dev/null && log_success "Removed ~/.cache/opendrop" || true
fi

# ============================================================================
# 7. Remove Python virtual environment (if in project)
# ============================================================================
log_info "Removing Python virtual environment..."

if [[ -d .venv ]]; then
    read -p "Remove .venv directory? (yes/no): " remove_venv
    if [[ "$remove_venv" == "yes" ]]; then
        rm -rf .venv 2>/dev/null && log_success "Removed .venv directory" || log_warn "Could not remove .venv"
    fi
fi

# ============================================================================
# 8. Remove uv cache (optional)
# ============================================================================
log_info "Checking uv cache..."

if [[ -d ~/.cache/uv ]]; then
    cache_size=$(du -sh ~/.cache/uv 2>/dev/null | cut -f1)
    read -p "Remove uv cache (~${cache_size})? (yes/no): " remove_cache
    if [[ "$remove_cache" == "yes" ]]; then
        rm -rf ~/.cache/uv 2>/dev/null && log_success "Removed uv cache" || log_warn "Could not remove uv cache"
    fi
fi

# ============================================================================
# 9. Remove uv package cache for opendrop (optional)
# ============================================================================
log_info "Checking uv package cache..."

if [[ -d ~/.cache/uv/projects ]]; then
    read -p "Remove uv project cache? (yes/no): " remove_proj_cache
    if [[ "$remove_proj_cache" == "yes" ]]; then
        rm -rf ~/.cache/uv/projects/*opendrop* 2>/dev/null && log_success "Removed uv project cache" || log_warn "Could not remove project cache"
    fi
fi

# ============================================================================
# Summary
# ============================================================================
echo ""
echo -e "${BLUE}╔═══════════════════════════════════════════════════════════════╗"
echo "║                    Uninstall Complete                             ║"
echo "╚═══════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${GREEN}Items removed: $removed_items${NC}"
echo ""
echo "Remaining files:"
echo "- Project source code: opendrop/ directory"
echo "- Documentation: *.md files"
echo "- Scripts: scripts/ directory"
echo ""
echo "These can be kept for reference or deleted manually."
echo ""
echo -e "${YELLOW}Next steps for fresh installation:${NC}"
echo ""
echo "1. Create new virtual environment:"
echo "   ${BLUE}python3 -m venv .venv${NC}"
echo ""
echo "2. Activate it:"
echo "   ${BLUE}source .venv/bin/activate${NC}"
echo ""
echo "3. Install uv (if not already installed):"
echo "   ${BLUE}pip install uv${NC}"
echo ""
echo "4. Install OpenDrop with all dependencies:"
echo "   ${BLUE}uv sync --all-extras${NC}"
echo ""
echo "5. Verify installation:"
echo "   ${BLUE}bash scripts/check-gui-ready.sh${NC}"
echo ""
echo "6. Launch GUI:"
echo "   ${BLUE}opendrop-gui${NC}"
echo ""
echo -e "${GREEN}✓ Uninstall complete!${NC}"
echo ""

