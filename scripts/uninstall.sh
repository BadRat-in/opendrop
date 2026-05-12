#!/usr/bin/env bash
# OpenDrop uninstaller.
#
# Reverses what scripts/install.sh did:
#   - removes the polkit policy
#   - removes the .desktop entries and icon
#   - removes the optional systemd user tray service
#   - pip-uninstalls the opendrop Python package
#
# Does NOT touch:
#   - OWL (we built it from source; user can remove /usr/local/bin/owl manually)
#   - System packages installed by install.sh (libpcap, bluez, etc.) — those
#     belong to the user's package manager and may be used by other apps
#   - User config under ~/.config/opendrop / ~/.opendrop (those contain keys
#     and history; ask explicitly)
#
# Usage:
#   sudo ./scripts/uninstall.sh
#   sudo ./scripts/uninstall.sh --purge   # also delete user data

set -euo pipefail

PURGE=0
for arg in "$@"; do
    case "$arg" in
        --purge|-p) PURGE=1 ;;
        -h|--help)
            sed -n '2,17p' "$0" | sed 's/^# \{0,1\}//'
            exit 0
            ;;
        *)
            echo "Unknown arg: $arg" >&2
            exit 2
            ;;
    esac
done

LOG_PREFIX="[opendrop-uninstall]"
info() { echo -e "\e[36m${LOG_PREFIX}\e[0m $*"; }
warn() { echo -e "\e[33m${LOG_PREFIX}\e[0m WARN: $*"; }

need_root() {
    if [ "$(id -u)" -ne 0 ]; then
        echo "Re-run with sudo: sudo $0 $*" >&2
        exit 1
    fi
}

remove_path() {
    local path="$1"
    if [ -e "$path" ]; then
        rm -f "$path"
        info "removed: $path"
    fi
}

remove_polkit() {
    remove_path /usr/share/polkit-1/actions/org.opendrop.policy
}

remove_desktop_entries() {
    remove_path /usr/share/applications/opendrop.desktop
    remove_path /usr/share/applications/opendrop-doctor.desktop
    # Legacy filename from earlier installer.
    remove_path /usr/share/applications/opendrop-gui.desktop
    remove_path /usr/share/icons/hicolor/256x256/apps/opendrop.png
    command -v gtk-update-icon-cache >/dev/null 2>&1 && \
        gtk-update-icon-cache -f /usr/share/icons/hicolor 2>/dev/null || true
    command -v update-desktop-database >/dev/null 2>&1 && \
        update-desktop-database 2>/dev/null || true
}

remove_legacy_systemd() {
    # Older installs put an owl-awdl.service in /etc/systemd. install.sh
    # doesn't do that, but if the old one is around, clean it up.
    if [ -f /etc/systemd/system/owl-awdl.service ]; then
        systemctl stop owl-awdl.service 2>/dev/null || true
        systemctl disable owl-awdl.service 2>/dev/null || true
        rm -f /etc/systemd/system/owl-awdl.service
        systemctl daemon-reload 2>/dev/null || true
        info "removed legacy owl-awdl.service"
    fi
    # Legacy sudoers file from setup-owl.sh.
    remove_path /etc/sudoers.d/opendrop
}

uninstall_python() {
    # install.sh places OpenDrop in a dedicated venv at /opt/opendrop and
    # symlinks the CLI entry points into /usr/local/bin. Reverse both.
    info "Removing Python install..."
    local venv=/opt/opendrop
    if [ -d "${venv}" ]; then
        rm -rf "${venv}"
        info "  removed venv: ${venv}"
    fi
    for cmd in opendrop opendrop-gui opendrop-doctor; do
        local link="/usr/local/bin/${cmd}"
        if [ -L "${link}" ] || [ -f "${link}" ]; then
            rm -f "${link}"
            info "  removed ${link}"
        fi
    done

    # Belt-and-suspenders: clean up any stray pip-installed copy from older
    # install.sh versions that wrote into system Python.
    if command -v pip3 >/dev/null 2>&1; then
        pip3 uninstall -y opendrop >/dev/null 2>&1 || true
    fi
}

purge_user_data() {
    # Ask the original user, not root, where their data lives.
    local user_home
    user_home="$(eval echo ~"${SUDO_USER:-$USER}")"
    for d in "${user_home}/.config/opendrop" "${user_home}/.opendrop"; do
        if [ -d "$d" ]; then
            rm -rf "$d"
            info "purged: $d"
        fi
    done
}

need_root "$@"
remove_polkit
remove_desktop_entries
remove_legacy_systemd
uninstall_python

if [ "${PURGE}" -eq 1 ]; then
    purge_user_data
else
    info "user data left intact under ~/.config/opendrop and ~/.opendrop"
    info "  (pass --purge to delete them)"
fi

info "Done. OWL itself was not removed; delete it with:"
info "  sudo rm -f /usr/local/bin/owl"
