#!/usr/bin/env bash
# OpenDrop universal installer.
#
# Works on Debian/Ubuntu/Parrot, Fedora/RHEL, Arch/Manjaro, openSUSE, and
# Alpine. Detects the distro, installs OS-level dependencies, builds OWL
# from source if a package isn't available, and installs a polkit policy
# so the GUI can start/stop OWL without a tty password prompt.
#
# Usage:
#   curl -fsSL https://example.com/install.sh | bash
#   # or
#   ./scripts/install.sh
#
# Re-runnable: skips steps that are already done.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LOG_PREFIX="[opendrop-install]"

info() { echo -e "\e[36m${LOG_PREFIX}\e[0m $*"; }
warn() { echo -e "\e[33m${LOG_PREFIX}\e[0m WARN: $*"; }
err()  { echo -e "\e[31m${LOG_PREFIX}\e[0m ERROR: $*" >&2; }

need_root() {
    if [ "$(id -u)" -ne 0 ]; then
        err "Re-run with sudo: sudo $0"
        exit 1
    fi
}

detect_distro() {
    if [ -r /etc/os-release ]; then
        # shellcheck disable=SC1091
        . /etc/os-release
        DISTRO_ID="${ID:-unknown}"
        DISTRO_ID_LIKE="${ID_LIKE:-}"
    else
        DISTRO_ID="unknown"
        DISTRO_ID_LIKE=""
    fi
    info "Detected distro: ${DISTRO_ID} (${PRETTY_NAME:-unknown})"
}

install_packages() {
    info "Installing system dependencies..."
    case "${DISTRO_ID}" in
        debian|ubuntu|parrot|kali|linuxmint|pop|elementary)
            DEBIAN_FRONTEND=noninteractive apt-get update -qq
            DEBIAN_FRONTEND=noninteractive apt-get install -y \
                python3 python3-pip python3-venv \
                libpcap-dev libev-dev libnl-3-dev libnl-genl-3-dev \
                bluetooth bluez \
                build-essential cmake git \
                policykit-1
            ;;
        fedora|rhel|centos|rocky|alma)
            dnf install -y \
                python3 python3-pip \
                libpcap-devel libev-devel libnl3-devel \
                bluez \
                gcc make cmake git \
                polkit
            ;;
        arch|manjaro|endeavouros|cachyos)
            pacman -Syu --needed --noconfirm \
                python python-pip \
                libpcap libev libnl \
                bluez bluez-utils \
                base-devel cmake git \
                polkit
            ;;
        opensuse*|sles)
            zypper install -y \
                python3 python3-pip \
                libpcap-devel libev-devel libnl3-devel \
                bluez \
                gcc make cmake git \
                polkit
            ;;
        alpine)
            apk add --no-cache \
                python3 py3-pip \
                libpcap-dev libev-dev libnl3-dev \
                bluez \
                gcc make cmake git musl-dev \
                polkit
            ;;
        void)
            xbps-install -Sy \
                python3 python3-pip \
                libpcap-devel libev-devel libnl-devel \
                bluez \
                gcc make cmake git \
                polkit
            ;;
        *)
            warn "Distro '${DISTRO_ID}' is not in our installer table."
            warn "You will need to install these packages manually:"
            warn "  python3, pip, libpcap, libev, libnl, bluez, gcc, cmake, git, polkit"
            ;;
    esac
}

build_owl() {
    if command -v owl >/dev/null 2>&1; then
        info "OWL already installed at: $(command -v owl)"
        return
    fi
    info "Building OWL from source (this may take a couple of minutes)..."
    local tmp
    tmp="$(mktemp -d)"
    git clone --recursive https://github.com/seemoo-lab/owl.git "${tmp}/owl"
    cd "${tmp}/owl"
    mkdir -p build
    cd build
    cmake ..
    make -j"$(nproc)"
    make install
    cd /
    rm -rf "${tmp}"
    info "OWL installed: $(command -v owl)"
}

install_polkit_policy() {
    local policy_dir=/usr/share/polkit-1/actions
    local src="${REPO_ROOT}/packaging/org.opendrop.policy"
    if [ ! -d "${policy_dir}" ]; then
        warn "polkit actions dir not found, skipping policy install"
        return
    fi
    if [ ! -f "${src}" ]; then
        warn "polkit policy source not found at ${src}, skipping"
        return
    fi
    info "Installing polkit policy → ${policy_dir}/"
    install -m 644 "${src}" "${policy_dir}/org.opendrop.policy"
}

install_desktop_files() {
    local app_dir=/usr/share/applications
    local src_dir="${REPO_ROOT}/packaging"
    if [ ! -d "${app_dir}" ]; then
        warn "applications dir not found, skipping .desktop install"
        return
    fi
    for f in opendrop.desktop opendrop-doctor.desktop; do
        if [ -f "${src_dir}/${f}" ]; then
            install -m 644 "${src_dir}/${f}" "${app_dir}/${f}"
            info "Installed ${app_dir}/${f}"
        fi
    done

    # Icon: we don't ship an SVG yet, but copy a reasonable PNG if present.
    local icon_dir=/usr/share/icons/hicolor/256x256/apps
    if [ -f "${REPO_ROOT}/opendrop/gui/resources/icon_active.png" ]; then
        install -D -m 644 \
            "${REPO_ROOT}/opendrop/gui/resources/icon_active.png" \
            "${icon_dir}/opendrop.png"
        # Refresh the icon cache if available.
        command -v gtk-update-icon-cache >/dev/null 2>&1 && \
            gtk-update-icon-cache -f /usr/share/icons/hicolor || true
    fi
}

install_opendrop_python() {
    info "Installing OpenDrop Python package..."
    # Prefer uv if present, fall back to pip3.
    if command -v uv >/dev/null 2>&1; then
        (cd "${REPO_ROOT}" && uv pip install --system -e ".[gui]")
    else
        pip3 install --break-system-packages -e "${REPO_ROOT}[gui]" 2>/dev/null || \
            pip3 install -e "${REPO_ROOT}[gui]"
    fi
}

main() {
    need_root
    detect_distro
    install_packages
    build_owl
    install_polkit_policy
    install_desktop_files
    install_opendrop_python
    info "Done. Run as your user (NOT root):  opendrop-doctor"
    info "If 'opendrop-doctor' reports green, launch the GUI: opendrop-gui"
}

main "$@"
