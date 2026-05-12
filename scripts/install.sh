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
            # polkit packaging changed in Debian 13+ / Ubuntu 24.04+:
            # the transitional `policykit-1` package was removed and
            # split into `polkitd` (the daemon) and `pkexec` (the CLI).
            # Older releases still expose policykit-1.
            #
            # Use `apt-cache policy` and inspect the Candidate line —
            # `apt-cache show` returns metadata even for packages with no
            # installable candidate, so it gives false positives here.
            local polkit_pkgs="polkitd pkexec"
            if apt-cache policy policykit-1 2>/dev/null \
                | grep -q "Candidate: [0-9]"; then
                polkit_pkgs="policykit-1"
            fi
            # shellcheck disable=SC2086  # word-splitting is intentional
            DEBIAN_FRONTEND=noninteractive apt-get install -y \
                python3 python3-pip python3-venv \
                libpcap-dev libev-dev libnl-3-dev libnl-genl-3-dev \
                bluetooth bluez \
                build-essential cmake git \
                $polkit_pkgs
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

    # Default to the maintained fork, which already carries patches we need
    # (notably: gating the bundled googletest behind -DBUILD_TESTS so GCC 14
    # builds don't fail). Set OWL_REPO=... to override (e.g. for upstream).
    local owl_repo="${OWL_REPO:-https://github.com/BadRat-in/owl.git}"
    local owl_branch="${OWL_BRANCH:-master}"
    info "Cloning ${owl_repo} (branch ${owl_branch})..."
    if ! git clone --recursive --branch "${owl_branch}" \
            "${owl_repo}" "${tmp}/owl"; then
        warn "Failed to clone ${owl_repo}; falling back to upstream."
        rm -rf "${tmp}/owl"
        git clone --recursive https://github.com/seemoo-lab/owl.git "${tmp}/owl"
        # Apply our patches manually if we fell back to upstream.
        if [ -d "${REPO_ROOT}/patches/owl" ]; then
            info "Applying local OWL patches..."
            for patch in "${REPO_ROOT}/patches/owl"/*.patch; do
                [ -f "${patch}" ] || continue
                (cd "${tmp}/owl" && git apply "${patch}") || \
                    warn "Patch did not apply cleanly: $(basename "${patch}")"
            done
        fi
    fi

    cd "${tmp}/owl"
    mkdir -p build
    cd build
    cmake -DCMAKE_BUILD_TYPE=Release ..
    if ! make -j"$(nproc)"; then
        err "OWL build failed."
        cd /
        rm -rf "${tmp}"
        return 1
    fi

    # CMake places the binary in build/<source-subdir>/, here:
    # build/daemon/owl. Find it instead of assuming a fixed path so
    # the script survives any upstream re-layout.
    local owl_bin
    owl_bin="$(find . -type f -executable -name owl | head -n 1)"
    if [ -z "${owl_bin}" ] || [ ! -x "${owl_bin}" ]; then
        err "OWL build succeeded but binary not found under $(pwd)"
        cd /
        rm -rf "${tmp}"
        return 1
    fi
    install -m 755 "${owl_bin}" /usr/local/bin/owl
    cd /
    rm -rf "${tmp}"
    # `command -v owl` would be empty here under pkexec because the
    # sanitized PATH doesn't include /usr/local/bin. Report the absolute
    # path we actually wrote to instead.
    info "OWL installed: /usr/local/bin/owl"
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

    # Install the full hicolor icon set (16-512). The icons live in
    # opendrop/gui/resources/hicolor/<size>/apps/opendrop.png in the repo.
    local src_hicolor="${REPO_ROOT}/opendrop/gui/resources/hicolor"
    local dest_hicolor=/usr/share/icons/hicolor
    if [ -d "${src_hicolor}" ]; then
        for size_dir in "${src_hicolor}"/*; do
            local size="$(basename "${size_dir}")"
            local src_png="${size_dir}/apps/opendrop.png"
            [ -f "${src_png}" ] || continue
            install -D -m 644 "${src_png}" "${dest_hicolor}/${size}/apps/opendrop.png"
        done
        info "Installed hicolor icons into ${dest_hicolor}/<size>/apps/"
        command -v gtk-update-icon-cache >/dev/null 2>&1 && \
            gtk-update-icon-cache -f "${dest_hicolor}" 2>/dev/null || true
    fi
}

_invoking_user_home() {
    # Under sudo / pkexec we run as root but the real user is the one who
    # called us. They typically have uv installed in their home.
    if [ -n "${SUDO_USER:-}" ]; then
        getent passwd "${SUDO_USER}" | cut -d: -f6
    elif [ -n "${PKEXEC_UID:-}" ]; then
        getent passwd "${PKEXEC_UID}" | cut -d: -f6
    else
        echo "${HOME:-/root}"
    fi
}

find_uv() {
    # System-wide first (predictable for pkexec/sudo PATH).
    for p in /usr/local/bin/uv /usr/bin/uv; do
        [ -x "$p" ] && { echo "$p"; return 0; }
    done
    # Then the invoking user's typical uv locations.
    local user_home
    user_home="$(_invoking_user_home)"
    for p in "${user_home}/.local/bin/uv" "${user_home}/.cargo/bin/uv"; do
        [ -x "$p" ] && { echo "$p"; return 0; }
    done
    return 1
}

install_uv_systemwide() {
    info "  installing uv to /usr/local/bin/uv (one-time)..."
    if command -v curl >/dev/null 2>&1; then
        curl -LsSf https://astral.sh/uv/install.sh | \
            env UV_INSTALL_DIR=/usr/local/bin UV_NO_MODIFY_PATH=1 sh >/dev/null
    elif command -v wget >/dev/null 2>&1; then
        wget -qO- https://astral.sh/uv/install.sh | \
            env UV_INSTALL_DIR=/usr/local/bin UV_NO_MODIFY_PATH=1 sh >/dev/null
    else
        err "Neither curl nor wget available; install uv manually."
        return 1
    fi
    [ -x /usr/local/bin/uv ]
}

install_opendrop_python() {
    # Install into a dedicated venv at /opt/opendrop using uv. This:
    #   - uses the pinned versions in uv.lock for reproducible installs,
    #   - is 10-100x faster than pip,
    #   - avoids PEP 668 EXTERNALLY-MANAGED on Debian/Parrot,
    #   - leaves system Python untouched,
    #   - removes cleanly with `rm -rf /opt/opendrop`,
    #   - works identically on Fedora, Arch, openSUSE, Alpine, Void.
    local venv=/opt/opendrop
    info "Installing OpenDrop into ${venv} (via uv)..."

    local uv
    if ! uv="$(find_uv)"; then
        info "  uv not on PATH or in invoking user's home; bootstrapping..."
        if ! install_uv_systemwide; then
            err "Failed to install uv."
            return 1
        fi
        uv=/usr/local/bin/uv
    fi
    info "  using uv: ${uv} ($("${uv}" --version 2>/dev/null | head -1))"

    if [ -d "${venv}" ]; then
        info "  removing previous venv at ${venv}"
        rm -rf "${venv}"
    fi

    # Create the venv with uv (faster than python -m venv, picks the right
    # Python interpreter automatically).
    "${uv}" venv "${venv}" || {
        err "uv venv failed."
        return 1
    }

    # Install from the lockfile if available — reproducible. Otherwise fall
    # back to uv's pip-compat interface.
    if [ -f "${REPO_ROOT}/uv.lock" ]; then
        info "  syncing from uv.lock (--extra gui)"
        (cd "${REPO_ROOT}" && VIRTUAL_ENV="${venv}" "${uv}" sync --extra gui) || {
            err "uv sync failed."
            return 1
        }
    else
        info "  uv.lock not present, falling back to uv pip install"
        "${uv}" pip install --python "${venv}/bin/python" \
            -e "${REPO_ROOT}[gui]" || {
            err "uv pip install failed."
            return 1
        }
    fi

    # Symlink CLI entry points into /usr/local/bin so they're on every
    # user's PATH without any per-user activation.
    for cmd in opendrop opendrop-gui opendrop-doctor; do
        if [ -x "${venv}/bin/${cmd}" ]; then
            ln -sf "${venv}/bin/${cmd}" "/usr/local/bin/${cmd}"
            info "  linked /usr/local/bin/${cmd} -> ${venv}/bin/${cmd}"
        fi
    done
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
