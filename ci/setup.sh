#!/usr/bin/env bash
# Clone ros-central-registry at the pinned commit and generate its workspace/ for the pinned release.
# Idempotent. Run from the repo root.
set -euo pipefail
cd "$(dirname "$0")/.."
source ci/pins.env
# Dozens of CI jobs clone this at the same moment and GitHub answers some of them with a 403: retry with backoff.
retry() { local n; for n in 1 2 3 4 5 6; do "$@" && return 0; echo "retry $n/6: $*" >&2; rm -rf ros-central-registry; sleep $((n * 10 + RANDOM % 10)); done; return 1; }
if [ ! -d ros-central-registry/.git ]; then
  retry git clone --filter=blob:none "$RCR_REPO" ros-central-registry
fi
git -C ros-central-registry fetch --quiet origin "$RCR_SHA" 2>/dev/null || git -C ros-central-registry fetch --quiet origin
git -C ros-central-registry checkout --quiet "$RCR_SHA"
if [ ! -f ros-central-registry/workspace/MODULE.bazel.orig ]; then
  (cd ros-central-registry && bazel run //tools/ci:setup_workspace -- --release="$RCR_RELEASE")
  mv ros-central-registry/workspace/MODULE.bazel ros-central-registry/workspace/MODULE.bazel.orig
fi

# Make Bazel look in our generated master-registry first (setup_workspace doesn't know about it).
python3 - <<'PY'
p = "ros-central-registry/workspace/.bazelrc"
s = open(p).read()
line = "common --registry=file:///%workspace%/../../master-registry \\\n       "
if "master-registry" not in s:
    old = "common --registry=file:///%workspace%/..  "
    assert old in s, "unexpected .bazelrc layout"
    s = s.replace(old, line + old.replace("common ", "", 1), 1)
    open(p, "w").write(s)
PY
