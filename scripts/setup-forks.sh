#!/usr/bin/env bash
# Bootstrap the BadRat-in/owl fork from upstream + this repo's patches/.
#
# Run this ONCE after creating https://github.com/BadRat-in/owl on the
# GitHub web UI by forking seemoo-lab/owl. It will:
#
#   1. Clone seemoo-lab/owl into a scratch directory.
#   2. Add BadRat-in/owl as a new remote.
#   3. Apply every patch from patches/owl/*.patch.
#   4. Commit and push to the fork's master branch.
#
# Safe to re-run — already-applied patches are skipped via `git am --skip`.
#
# Usage:
#   bash scripts/setup-forks.sh                          # SSH via github.com
#   FORK_SSH_HOST=badrat.github.com bash scripts/...     # SSH host alias
#   FORK_URL=https://github.com/BadRat-in/owl.git bash scripts/...  # HTTPS
#   FORK_OWNER=otheruser FORK_REPO=owl-fork bash scripts/...        # custom

set -euo pipefail

FORK_OWNER="${FORK_OWNER:-BadRat-in}"
FORK_REPO="${FORK_REPO:-owl}"
# SSH host alias — change this if you have a per-account host in ~/.ssh/config
# (e.g. `Host badrat.github.com` with a specific IdentityFile).
FORK_SSH_HOST="${FORK_SSH_HOST:-github.com}"
UPSTREAM_URL="https://github.com/seemoo-lab/owl.git"
FORK_URL="${FORK_URL:-git@${FORK_SSH_HOST}:${FORK_OWNER}/${FORK_REPO}.git}"

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PATCH_DIR="${REPO_ROOT}/patches/owl"
WORK_DIR="$(mktemp -d -t owl-fork-XXXX)"

trap 'rm -rf "${WORK_DIR}"' EXIT

info() { echo -e "\e[36m[setup-forks]\e[0m $*"; }
warn() { echo -e "\e[33m[setup-forks]\e[0m WARN: $*"; }
err()  { echo -e "\e[31m[setup-forks]\e[0m ERROR: $*" >&2; }

if [ ! -d "${PATCH_DIR}" ]; then
    err "patch directory not found: ${PATCH_DIR}"
    exit 1
fi

info "Cloning ${UPSTREAM_URL} into ${WORK_DIR}..."
git clone --recursive "${UPSTREAM_URL}" "${WORK_DIR}/owl"

cd "${WORK_DIR}/owl"

# Configure committer identity from the user's global git config, falling
# back to the fork owner if nothing's set.
git_name="$(git config --global user.name || echo "${FORK_OWNER}")"
git_email="$(git config --global user.email || echo "${FORK_OWNER}@users.noreply.github.com")"
git config user.name "${git_name}"
git config user.email "${git_email}"

info "Adding fork remote: ${FORK_URL}"
git remote remove fork 2>/dev/null || true
git remote add fork "${FORK_URL}"

# Apply patches in sorted order.
patches=("${PATCH_DIR}"/*.patch)
if [ ! -e "${patches[0]}" ]; then
    warn "No patches found in ${PATCH_DIR}; nothing to apply."
else
    info "Applying $(ls "${PATCH_DIR}"/*.patch | wc -l) patch(es)..."
    for p in "${patches[@]}"; do
        info "  - $(basename "${p}")"
        if ! git am --keep-cr "${p}"; then
            err "Patch did not apply cleanly: ${p}"
            err "Investigate with: cd ${WORK_DIR}/owl && git am --show-current-patch"
            exit 2
        fi
    done
fi

# Fetch the fork first so --force-with-lease has a remote-tracking baseline
# to compare against. Without this, git refuses with "stale info" because it
# doesn't know the current remote state.
info "Fetching ${FORK_URL}..."
if ! git fetch fork 2>&1 | grep -v "^From"; then
    warn "fetch from fork failed; will attempt push without lease check"
    push_cmd=(git push --force fork master)
else
    push_cmd=(git push --force-with-lease=master fork master)
fi

info "Pushing to ${FORK_URL} (master)..."
if ! "${push_cmd[@]}"; then
    err "Push failed."
    err ""
    err "Common fixes:"
    err "  - Use a custom SSH host alias from ~/.ssh/config:"
    err "      FORK_SSH_HOST=badrat.github.com bash scripts/setup-forks.sh"
    err "  - Use HTTPS instead of SSH:"
    err "      FORK_URL=https://github.com/${FORK_OWNER}/${FORK_REPO}.git \\"
    err "        bash scripts/setup-forks.sh"
    err "  - Make sure ${FORK_OWNER}/${FORK_REPO} exists on GitHub:"
    err "      https://github.com/${FORK_OWNER}/${FORK_REPO}"
    exit 3
fi

info "Done. ${FORK_OWNER}/${FORK_REPO} now contains upstream + $(ls "${PATCH_DIR}"/*.patch 2>/dev/null | wc -l) patch(es)."
info "scripts/install.sh will use this fork by default."
