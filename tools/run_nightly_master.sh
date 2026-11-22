#!/usr/bin/env bash
# Lane 2: regenerate master modules for the ros2.repos subset, wire them into the
# generated RCR workspace, and run `bazel test`. Usage: run_nightly_master.sh [extra bazel args]
# Env: NIGHTLY_SHARD=i/N  run only shard i (0-based) of N, split by target pattern (CI matrix)
#      NIGHTLY_TARGETS=f  run the targets listed in file f instead of the whole nightly
#      GENERATE_ONLY=1    stop after generating the workspace
set -euo pipefail
export PATH="$HOME/.local/bin:$PATH"
HERE="$(cd "$(dirname "$0")/.." && pwd)"; cd "$HERE"
W=ros-central-registry/workspace
rm -rf master-registry
trap 'rc=$?; [ $rc -eq 0 ] || { echo "== failed (exit $rc); tail of gen_all.log:"; tail -40 gen_all.log; }' EXIT
python3 -u tools/make_master_module.py --rcr ros-central-registry --out master-registry \
  --workspace-module $W/MODULE.bazel.orig --map ros2_repos_packages.json $(cat pkgs_ros2_repos.txt) > gen_all.log 2>&1
python3 -u tools/make_extra_module.py --rcr ros-central-registry --out master-registry $(ls tools/extra_modules) >> gen_all.log 2>&1
python3 -u tools/make_bcr_bump.py --out master-registry >> gen_all.log 2>&1
(cat $W/MODULE.bazel.orig; echo; echo "# --- extra (unreleased) modules ---"; cat master-registry/extra_deps.bazel; echo; echo "# --- master overrides ---"; cat master-registry/overrides.bazel) > $W/MODULE.bazel
# ros2-repos.txt lists the released-package patterns only: add the extra (unreleased) test modules
cp $W/ros2-repos.txt $W/nightly-targets.txt
for m in $(ls tools/extra_modules); do echo "@$m//..." >> $W/nightly-targets.txt; done
if [ -n "${NIGHTLY_TARGETS:-}" ]; then cp "$NIGHTLY_TARGETS" $W/nightly-targets.txt; fi
if [ -n "${NIGHTLY_SHARD:-}" ]; then
  i=${NIGHTLY_SHARD%/*}; n=${NIGHTLY_SHARD#*/}
  awk -v i="$i" -v n="$n" '(NR-1) % n == i' $W/nightly-targets.txt > $W/nightly-targets.shard && mv $W/nightly-targets.shard $W/nightly-targets.txt
fi
[ -z "${GENERATE_ONLY:-}" ] || exit 0
cd $W
bazel test --config=ci --target_pattern_file=nightly-targets.txt --keep_going "$@"
