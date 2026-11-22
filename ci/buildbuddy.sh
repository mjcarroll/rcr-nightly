#!/usr/bin/env bash
# Point Bazel at BuildBuddy (remote cache + build/test results UI) when BUILDBUDDY_API_KEY is set.
# Writes ~/.bazelrc, which is read after the workspace .bazelrc, so it overrides the RCR default
# read-only cache (storage.googleapis.com/intrinsic-opensource-buildcache). Without the key this
# is a no-op and Bazel keeps the defaults.
# BB_UPLOAD=0 makes the cache read-only.
set -euo pipefail
if [ -z "${BUILDBUDDY_API_KEY:-}" ]; then
  echo "BUILDBUDDY_API_KEY not set: using default caches"; exit 0
fi
echo "::add-mask::$BUILDBUDDY_API_KEY"
upload=true; [ "${BB_UPLOAD:-1}" = "1" ] || upload=false
cat > "$HOME/.bazelrc" <<RC
common --remote_cache=grpcs://remote.buildbuddy.io
common --remote_header=x-buildbuddy-api-key=$BUILDBUDDY_API_KEY
common --remote_upload_local_results=$upload
common --remote_timeout=600
common --bes_backend=grpcs://remote.buildbuddy.io
common --bes_results_url=https://app.buildbuddy.io/invocation/
common --build_metadata=ROLE=CI
common --build_metadata=REPO_URL=${GITHUB_SERVER_URL:-https://github.com}/${GITHUB_REPOSITORY:-}
common --build_metadata=COMMIT_SHA=${GITHUB_SHA:-}
RC
chmod 600 "$HOME/.bazelrc"
echo "BuildBuddy configured (upload=$upload)"
