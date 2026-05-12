#!/bin/bash

###############################################################################
# OpenDrop Context Menu Integration Setup
#
# Integrates "Send with OpenDrop" into file manager context menus
# Supports: Nautilus (GNOME), Dolphin (KDE), Thunar (Xfce)
#
# Usage: bash scripts/setup-context-menu.sh
###############################################################################

set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BLUE}════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}  OpenDrop Context Menu Integration Setup${NC}"
echo -e "${BLUE}════════════════════════════════════════════════════════${NC}"
echo ""

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SEND_SCRIPT="$PROJECT_ROOT/scripts/opendrop-send.py"
VENV_BIN="$PROJECT_ROOT/.venv/bin"

# Verify send script exists
if [[ ! -f "$SEND_SCRIPT" ]]; then
    echo "❌ Send script not found: $SEND_SCRIPT"
    exit 1
fi

chmod +x "$SEND_SCRIPT"
echo "✓ Send script ready: $SEND_SCRIPT"
echo ""

# ============================================================================
# GNOME Nautilus Integration
# ============================================================================

echo -e "${YELLOW}Setting up Nautilus (GNOME)...${NC}"

if command -v nautilus &> /dev/null; then
    NAUTILUS_SCRIPTS="$HOME/.local/share/nautilus/scripts"
    mkdir -p "$NAUTILUS_SCRIPTS"

    # Create Nautilus script
    cat > "$NAUTILUS_SCRIPTS/Send_with_OpenDrop" << 'EOF'
#!/bin/bash
# Send selected file(s) with OpenDrop
# Nautilus will pass selected files as arguments

VENV_BIN="$(cd "$(dirname "$0")/../../../Projects/opendrop/.venv/bin" 2>/dev/null && pwd)"

if [[ -x "$VENV_BIN/python3" ]]; then
    "$VENV_BIN/python3" "$(dirname "$0")/../../../Projects/opendrop/scripts/opendrop-send.py" "$@"
else
    notify-send "OpenDrop" "Failed to find OpenDrop environment"
fi
EOF

    chmod +x "$NAUTILUS_SCRIPTS/Send_with_OpenDrop"
    echo "✓ Nautilus script installed: $NAUTILUS_SCRIPTS/Send_with_OpenDrop"
    echo "  → Right-click files → Scripts → Send_with_OpenDrop"
else
    echo "⚠ Nautilus not found (GNOME not installed)"
fi

echo ""

# ============================================================================
# KDE Dolphin Integration
# ============================================================================

echo -e "${YELLOW}Setting up Dolphin (KDE)...${NC}"

if command -v dolphin &> /dev/null; then
    DOLPHIN_SCRIPTS="$HOME/.local/share/dolphin/scripts"
    mkdir -p "$DOLPHIN_SCRIPTS"

    # Create Dolphin script
    cat > "$DOLPHIN_SCRIPTS/send-with-opendrop.sh" << 'EOF'
#!/bin/bash
# Send files with OpenDrop (KDE Dolphin)

VENV_BIN="$(cd "$(dirname "$0")/../../../Projects/opendrop/.venv/bin" 2>/dev/null && pwd)"

if [[ -x "$VENV_BIN/python3" ]]; then
    "$VENV_BIN/python3" "$(dirname "$0")/../../../Projects/opendrop/scripts/opendrop-send.py" "$@"
else
    kdialog --error "Failed to find OpenDrop environment"
fi
EOF

    chmod +x "$DOLPHIN_SCRIPTS/send-with-opendrop.sh"
    echo "✓ Dolphin script installed: $DOLPHIN_SCRIPTS/send-with-opendrop.sh"
    echo "  → Right-click files → Scripts → send-with-opendrop.sh"
else
    echo "⚠ Dolphin not found (KDE not installed)"
fi

echo ""

# ============================================================================
# Xfce Thunar Integration
# ============================================================================

echo -e "${YELLOW}Setting up Thunar (Xfce)...${NC}"

if command -v thunar &> /dev/null; then
    THUNAR_ACTIONS="$HOME/.config/Thunar/uca.xml"
    mkdir -p "$(dirname "$THUNAR_ACTIONS")"

    # Create Thunar custom action
    cat > "$THUNAR_ACTIONS" << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<actions>
  <action>
    <name>Send with OpenDrop</name>
    <description>Send file(s) via AirDrop</description>
    <patterns>*</patterns>
    <exec>opendrop-send %f</exec>
    <icon-name>opendrop</icon-name>
  </action>
</actions>
EOF

    echo "✓ Thunar custom action installed: $THUNAR_ACTIONS"
    echo "  → Right-click files → Edit → Send with OpenDrop"
else
    echo "⚠ Thunar not found (Xfce not installed)"
fi

echo ""

# ============================================================================
# Desktop Action File (Universal)
# ============================================================================

echo -e "${YELLOW}Setting up Desktop Actions (Universal)...${NC}"

DESKTOP_ACTIONS="$HOME/.local/share/applications"
mkdir -p "$DESKTOP_ACTIONS"

cat > "$DESKTOP_ACTIONS/opendrop-send.desktop" << 'EOF'
[Desktop Entry]
Type=Application
Version=1.0
Name=Send with OpenDrop
Comment=Send files via AirDrop
Icon=opendrop
Exec=opendrop-send %F
Terminal=false
Categories=Utility;
MimeType=*/*

[Desktop Action send]
Name=Send with OpenDrop
Exec=opendrop-send %F
EOF

chmod 644 "$DESKTOP_ACTIONS/opendrop-send.desktop"
echo "✓ Desktop action installed: $DESKTOP_ACTIONS/opendrop-send.desktop"

# Update desktop database
if command -v update-desktop-database &> /dev/null; then
    update-desktop-database "$DESKTOP_ACTIONS" 2>/dev/null || true
    echo "✓ Desktop database updated"
fi

echo ""

# ============================================================================
# Summary
# ============================================================================

echo -e "${BLUE}════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}✓ Context Menu Integration Complete!${NC}"
echo -e "${BLUE}════════════════════════════════════════════════════════${NC}"
echo ""

echo "You can now:"
echo ""
echo "1. Right-click any file in your file manager"
echo "2. Select 'Send with OpenDrop' (or Scripts → Send_with_OpenDrop)"
echo "3. Choose a device from the list"
echo "4. File will be sent via AirDrop"
echo ""

echo "Supported file managers:"
if command -v nautilus &> /dev/null; then
    echo "  ✓ Nautilus (GNOME)"
fi
if command -v dolphin &> /dev/null; then
    echo "  ✓ Dolphin (KDE)"
fi
if command -v thunar &> /dev/null; then
    echo "  ✓ Thunar (Xfce)"
fi
echo ""

echo "Troubleshooting:"
echo "  • If 'Send with OpenDrop' doesn't appear, restart your file manager"
echo "  • For Nautilus: Clear cache with: rm -rf ~/.cache/nautilus"
echo "  • For Dolphin: Dolphin may need restart"
echo ""

echo "Example usage (from terminal):"
echo "  opendrop-send /path/to/file.pdf"
echo "  opendrop-send file1.txt file2.pdf file3.docx"
echo ""

echo -e "${GREEN}All set! Try right-clicking a file now.${NC}"
