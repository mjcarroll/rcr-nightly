#!/usr/bin/env bash
# Lane 2: regenerate master modules for the ros2.repos subset, wire them into the
# generated RCR workspace, and run `bazel test`. Usage: run_nightly_master.sh [extra bazel args]
# Env: NIGHTLY_SHARD=i/N  run only shard i (0-based) of N, split by target pattern (CI matrix)
#      NIGHTLY_TARGETS=f  run the targets listed in file f instead of the whole nightly
#      GENERATE_ONLY=1    stop after generating the workspace
#      SKIP_GENERATE=1    reuse an existing master-registry/ (e.g. downloaded from the prepare job)
#      SINCE_HOURS=N      only test what changed on the tracked branches in the last N hours (+ everything
#                         downstream of it): writes the affected test targets to nightly-targets.txt
#      NO_LINT=1          do not add the ament_lint_auto lint tests (copyright/cpplint/lint_cmake/uncrustify/xmllint)
#      SLIM_ROSDISTRO=1   patch @rosdistro//:ament_package to not bundle every third-party lib / pip wheel
#                         (cuts the target graph ~40%, actions ~57%; for flake hunts, not the faithful nightly)
set -euo pipefail
export PATH="$HOME/.local/bin:$PATH"
HERE="$(cd "$(dirname "$0")/.." && pwd)"; cd "$HERE"
W=ros-central-registry/workspace
trap 'rc=$?; [ $rc -eq 0 ] || { echo "== failed (exit $rc); tail of gen_all.log:"; tail -40 gen_all.log; }' EXIT
if [ -z "${SKIP_GENERATE:-}" ]; then
  rm -rf master-registry
  python3 -u tools/make_master_module.py --rcr ros-central-registry --out master-registry \
    --workspace-module $W/MODULE.bazel.orig --map ros2_repos_packages.json $(cat pkgs_ros2_repos.txt) > gen_all.log 2>&1
  python3 -u tools/make_extra_module.py --rcr ros-central-registry --out master-registry $(ls tools/extra_modules) >> gen_all.log 2>&1
  python3 -u tools/make_bcr_bump.py --out master-registry >> gen_all.log 2>&1
fi
(cat $W/MODULE.bazel.orig; echo; echo "# --- extra (unreleased) modules ---"; cat master-registry/extra_deps.bazel; echo; echo "# --- master overrides ---"; cat master-registry/overrides.bazel) > $W/MODULE.bazel
if [ -z "${NO_LINT:-}" ]; then
  echo "local_path_override(module_name = \"rcr_lint\", path = \"$HERE/master-registry/rcr_lint\")" >> $W/MODULE.bazel
fi
if [ -n "${SLIM_ROSDISTRO:-}" ]; then
  RD=$(grep -o 'bazel_dep(name = "rosdistro", version = "[^"]*"' $W/MODULE.bazel | sed 's/.*version = "//; s/"$//')
  cp tools/rosdistro_slim/slim_ament_package.patch $W/rosdistro_slim.patch
  echo "single_version_override(module_name = \"rosdistro\", version = \"$RD\", patches = [\"//:rosdistro_slim.patch\"], patch_strip = 1)" >> $W/MODULE.bazel
fi
# the released-package patterns, plus the extra (unreleased) test modules
tr ' ' '\n' < pkgs_ros2_repos.txt | sed '/^$/d; s|^|@|; s|$|//...|' | LC_ALL=C sort > $W/nightly-targets.txt
for m in $(ls tools/extra_modules); do echo "@$m//..." >> $W/nightly-targets.txt; done
if [ -n "${NIGHTLY_TARGETS:-}" ]; then cp "$NIGHTLY_TARGETS" $W/nightly-targets.txt; fi
if [ -n "${SINCE_HOURS:-}" ]; then
  python3 tools/changed_since.py --hours "$SINCE_HOURS" > $W/changed.txt
  if [ -s $W/changed.txt ]; then
    U=$(paste -sd+ $W/nightly-targets.txt | sed 's/+/ + /g'); C=$(sed 's|^|@|; s|$|//...|' $W/changed.txt | paste -sd+ | sed 's/+/ + /g')
    (cd $W && bazel query "let t = tests(rdeps($U, $C)) in \$t except attr(tags, \"\\bmanual\\b\", \$t)" --config=ci --keep_going --noimplicit_deps 2>/dev/null | LC_ALL=C sort > nightly-targets.affected) || true
    mv $W/nightly-targets.affected $W/nightly-targets.txt
  else
    : > $W/nightly-targets.txt
  fi
  echo "SINCE_HOURS=$SINCE_HOURS: $(wc -l < $W/changed.txt) changed -> $(wc -l < $W/nightly-targets.txt) affected targets" | tee -a gen_all.log
fi
if [ -n "${NIGHTLY_SHARD:-}" ]; then
  i=${NIGHTLY_SHARD%/*}; n=${NIGHTLY_SHARD#*/}
  awk -v i="$i" -v n="$n" '(NR-1) % n == i' $W/nightly-targets.txt > $W/nightly-targets.shard && mv $W/nightly-targets.shard $W/nightly-targets.txt
fi
[ -z "${GENERATE_ONLY:-}" ] || exit 0
if [ ! -s $W/nightly-targets.txt ]; then echo "nothing to test"; exit 0; fi
cd $W
bazel test --config=ci --target_pattern_file=nightly-targets.txt --keep_going "$@"
