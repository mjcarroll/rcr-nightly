#!/usr/bin/env bash
# Lane 2: regenerate master modules for the ros2.repos subset, wire them into the
# generated RCR workspace, and run `bazel test`. Usage: run_nightly_master.sh [extra bazel args]
set -euo pipefail
export PATH="$HOME/.local/bin:$PATH"
HERE="$(cd "$(dirname "$0")/.." && pwd)"; cd "$HERE"
W=ros-central-registry/workspace
rm -rf master-registry
python3 -u tools/make_master_module.py --rcr ros-central-registry --out master-registry \
  --workspace-module $W/MODULE.bazel.orig --map ros2_repos_packages.json $(cat pkgs_ros2_repos.txt) > gen_all.log 2>&1
python3 -u tools/make_extra_module.py --rcr ros-central-registry --out master-registry $(ls tools/extra_modules) >> gen_all.log 2>&1
(cat $W/MODULE.bazel.orig; echo; echo "# --- extra (unreleased) modules ---"; cat master-registry/extra_deps.bazel; echo; echo "# --- master overrides ---"; cat master-registry/overrides.bazel) > $W/MODULE.bazel
# ros2-repos.txt lists the released-package patterns only: add the extra (unreleased) test modules
cp $W/ros2-repos.txt $W/nightly-targets.txt
for m in $(ls tools/extra_modules); do echo "@$m//..." >> $W/nightly-targets.txt; done
cd $W
bazel test --config=ci --target_pattern_file=nightly-targets.txt --keep_going "$@"
