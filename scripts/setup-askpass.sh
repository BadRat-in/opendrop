#!/usr/bin/env bash
# Configure sudo to use a graphical askpass helper when invoked without
# a controlling terminal (e.g. from Claude Code's shell, from a desktop
# launcher, or from a non-interactive script).
#
# After this runs once:
#   - `sudo -A command` always pops up a graphical password prompt
#   - `sudo command` still uses the terminal when one is present
#   - $SUDO_ASKPASS is set in /etc/environment so all login sessions
#     inherit the right helper path
#
# Idempotent. Re-running is safe.

set -euo pipefail

info() { echo -e "\e[36m[setup-askpass]\e[0m $*"; }
warn() { echo -e "\e[33m[setup-askpass]\e[0m WARN: $*"; }
err()  { echo -e "\e[31m[setup-askpass]\e[0m ERROR: $*" >&2; }

if [ "$(id -u)" -ne 0 ]; then
    err "Re-run with sudo: sudo $0"
    err "  (or use pkexec: pkexec bash $0)"
    exit 1
fi

# Pick the best askpass helper available, preferring desktop-native dialogs
# over the plain X11 ssh-askpass.
ASKPASS=""
for cand in \
    /usr/bin/ksshaskpass \
    /usr/bin/lxqt-openssh-askpass \
    /usr/libexec/openssh/gnome-ssh-askpass \
    /usr/lib/openssh/gnome-ssh-askpass \
    /usr/bin/ssh-askpass-gnome \
    /usr/bin/ssh-askpass; do
    if [ -x "${cand}" ]; then
        ASKPASS="${cand}"
        break
    fi
done

if [ -z "${ASKPASS}" ]; then
    err "No askpass helper found. Install one first:"
    err "  sudo apt install ksshaskpass        # KDE"
    err "  sudo apt install lxqt-openssh-askpass  # LXQt"
    err "  sudo apt install ssh-askpass        # generic X11 fallback"
    exit 2
fi
info "Using askpass helper: ${ASKPASS}"

# 1. sudoers: make `sudo -A` use this helper.
SUDOERS_FILE=/etc/sudoers.d/askpass
TMP="$(mktemp)"
cat >"${TMP}" <<EOF
# Installed by scripts/setup-askpass.sh
Defaults askpass=${ASKPASS}
EOF
if visudo -cf "${TMP}" >/dev/null; then
    install -m 440 "${TMP}" "${SUDOERS_FILE}"
    info "Installed ${SUDOERS_FILE}"
else
    err "visudo refused our generated file; aborting before damage"
    rm -f "${TMP}"
    exit 3
fi
rm -f "${TMP}"

# 2. /etc/environment: export SUDO_ASKPASS for every login session so the
# `-A` flag is the only thing the caller has to remember. Replace any
# existing line, don't accumulate duplicates.
ENV_FILE=/etc/environment
if grep -q '^SUDO_ASKPASS=' "${ENV_FILE}" 2>/dev/null; then
    sed -i "s|^SUDO_ASKPASS=.*|SUDO_ASKPASS=${ASKPASS}|" "${ENV_FILE}"
else
    echo "SUDO_ASKPASS=${ASKPASS}" >> "${ENV_FILE}"
fi
info "SUDO_ASKPASS=${ASKPASS} set in ${ENV_FILE}"

# 3. /etc/profile.d: belt-and-suspenders for shells that don't read
# /etc/environment (some non-PAM contexts skip it).
cat >/etc/profile.d/sudo-askpass.sh <<EOF
# Installed by scripts/setup-askpass.sh
export SUDO_ASKPASS=${ASKPASS}
EOF
chmod 644 /etc/profile.d/sudo-askpass.sh
info "Wrote /etc/profile.d/sudo-askpass.sh"

cat <<EOF

Done. Usage:

  sudo -A <command>      # always pop up a graphical password prompt
  pkexec   <command>     # alternative: polkit-based (no -A needed)

The dialog appears on your desktop, even if the calling shell has no TTY.

If you want every \`sudo\` to use the popup automatically (no -A flag
needed), add this to your shell rc:

    alias sudo='sudo -A'

— but note that aliases don't apply to non-interactive shells, so for
Claude Code you'll still need the -A flag explicitly, or use pkexec.
EOF
