#!/bin/bash

###############################################################################
# OpenDrop GUI Pre-Flight Checklist
#
# Verifies that the system is ready to run OpenDrop GUI (Option A - No OWL)
# Usage: bash scripts/check-gui-ready.sh
###############################################################################

set +e  # Don't exit on errors, we want to show all checks

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

CHECKS_PASSED=0
CHECKS_FAILED=0

check() {
    local name=$1
    local command=$2

    echo -n "Checking: $name ... "

    if eval "$command" &>/dev/null; then
        echo -e "${GREEN}✓${NC}"
        ((CHECKS_PASSED++))
        return 0
    else
        echo -e "${RED}✗${NC}"
        ((CHECKS_FAILED++))
        return 1
    fi
}

echo -e "${BLUE}════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}  OpenDrop GUI (Option A) - Pre-Flight Checklist${NC}"
echo -e "${BLUE}════════════════════════════════════════════════════════${NC}"
echo ""

echo "PYTHON & DEPENDENCIES:"
check "Python 3.10+" "python3 --version | grep -E 'Python 3\.(1[0-9]|[0-9]{2})'"
check "uv package manager" "command -v uv"
check "PyQt6 installed" "python3 -c 'import PyQt6'"
check "zeroconf installed" "python3 -c 'import zeroconf'"
check "requests installed" "python3 -c 'import requests'"

echo ""
echo "OPENDROP MODULES:"
check "opendrop.gui.settings" "python3 -c 'from opendrop.gui.settings import OpenDropSettings'"
check "opendrop.gui.privilege" "python3 -c 'from opendrop.gui.privilege import SudoExecutor'"
check "opendrop.gui.owl_manager" "python3 -c 'from opendrop.gui.owl_manager import OWLManager'"
check "opendrop.gui.worker" "python3 -c 'from opendrop.gui.worker import BrowseWorker'"
check "opendrop.client" "python3 -c 'from opendrop.client import AirDropBrowser'"
check "opendrop.server" "python3 -c 'from opendrop.server import AirDropServer'"

echo ""
echo "NETWORK & SYSTEM:"
check "WiFi interface available" "ip link | grep -E 'wlan|wlo|eth'"
check "IPv6 enabled" "ip -6 addr | grep -E '(fe80|2[0-9a-f]{3})'"
check "Bonjour/mDNS support" "python3 -c 'from zeroconf import Zeroconf'"
check "HTTPS support" "python3 -c 'import ssl; ssl.create_default_context()'"
check "libarchive available" "python3 -c 'import libarchive'"

echo ""
echo "FILESYSTEM:"
check "Config directory" "test -d ~/.config || mkdir -p ~/.config"
check "Config writable" "test -w ~/.config"
check "OpenDrop dir" "test -d ~/.config/opendrop || mkdir -p ~/.config/opendrop"

echo ""
echo "GUI ENTRY POINT:"
check "main.py exists" "test -f opendrop/gui/main.py"
check "opendrop-gui script" "command -v opendrop-gui || python3 -m opendrop.gui.main --help"

echo ""
echo -e "${BLUE}════════════════════════════════════════════════════════${NC}"
echo "SUMMARY:"
echo -e "${GREEN}Passed: $CHECKS_PASSED${NC}"
echo -e "${RED}Failed: $CHECKS_FAILED${NC}"

if [ $CHECKS_FAILED -eq 0 ]; then
    echo -e "${GREEN}✓ All checks passed!${NC}"
    echo ""
    echo "OpenDrop GUI is ready to launch:"
    echo "  opendrop-gui"
    echo ""
    echo "Or with debugging:"
    echo "  python3 -m opendrop.gui.main --debug"
    exit 0
else
    echo -e "${RED}✗ Some checks failed!${NC}"
    echo ""
    echo "Run this to install missing dependencies:"
    echo "  source .venv/bin/activate"
    echo "  uv sync --all-extras"
    exit 1
fi
