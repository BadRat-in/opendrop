#!/bin/bash

###############################################################################
# OpenDrop GUI Wrapper Script
#
# This wrapper script activates the OpenDrop virtual environment and launches
# the GUI. It's installed to /usr/local/bin/opendrop-gui by the setup script.
#
# Usage: opendrop-gui
###############################################################################

# Detect the installation directory
# Try common installation paths in order:
for INSTALL_PATH in \
    "/opt/opendrop" \
    "/usr/local/opt/opendrop" \
    "$(dirname "$(command -v opendrop-gui)" | sed 's|/bin$||')" \
    "$HOME/.local/opendrop" \
    "/home/*/Projects/opendrop"; do

    if [[ -f "$INSTALL_PATH/.venv/bin/opendrop-gui" ]]; then
        export VENV_PATH="$INSTALL_PATH/.venv"
        break
    fi
done

# If still not found, try to find it via pip
if [[ -z "$VENV_PATH" ]]; then
    VENV_PATH=$(python3 -c "
import site
import os
for path in site.getsitepackages() + [site.getusersitepackages()]:
    root = os.path.dirname(os.path.dirname(path))
    if os.path.exists(os.path.join(root, '.venv')):
        print(os.path.join(root, '.venv'))
        break
" 2>/dev/null)
fi

# Fallback: look in current directory (development mode)
if [[ -z "$VENV_PATH" || ! -d "$VENV_PATH" ]]; then
    if [[ -d ".venv" ]]; then
        VENV_PATH=".venv"
    elif [[ -d "../.venv" ]]; then
        VENV_PATH="../.venv"
    fi
fi

# Final check
if [[ ! -d "$VENV_PATH" ]]; then
    echo "Error: Could not find OpenDrop virtual environment."
    echo "Please ensure OpenDrop is properly installed."
    echo ""
    echo "Install with: uv sync --extra gui"
    exit 1
fi

# Activate the virtual environment and run the GUI
source "$VENV_PATH/bin/activate"
exec python3 -m opendrop.gui.main "$@"
