#!/usr/bin/env bash
# Clone ros-central-registry at the pinned commit and generate its workspace/ for the pinned release.
# Idempotent. Run from the repo root.
set -euo pipefail
cd "$(dirname "$0")/.."
source ci/pins.env
if [ ! -d ros-central-registry/.git ]; then
  git clone --filter=blob:none "$RCR_REPO" ros-central-registry
fi
git -C ros-central-registry fetch --quiet origin "$RCR_SHA" 2>/dev/null || git -C ros-central-registry fetch --quiet origin
git -C ros-central-registry checkout --quiet "$RCR_SHA"
if [ ! -f ros-central-registry/workspace/MODULE.bazel.orig ]; then
  (cd ros-central-registry && bazel run //tools/ci:setup_workspace -- --release="$RCR_RELEASE")
  mv ros-central-registry/workspace/MODULE.bazel ros-central-registry/workspace/MODULE.bazel.orig
fi
