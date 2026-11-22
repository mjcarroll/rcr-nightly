# rcr-nightly

A nightly of ROS 2 repo tips (`ros2.repos` master) built and tested with Bazel against the
[ros-central-registry](https://github.com/openrobotics/ros-central-registry) (RCR), mainly as a
**test-deflaking tool**: it runs the ROS 2 test-suites in a different environment (Bazel, libc++,
sandboxed, random `ROS_DOMAIN_ID` per test) and can repeat any test hundreds of times.

This repo holds only the tooling and the patches; the registry and the generated workspace are
recreated on every run.

## How it works

1. `ci/setup.sh` clones RCR at the commit in `ci/pins.env` and generates its `workspace/` for the pinned release.
2. `tools/make_master_module.py` turns each released RCR module into a *master* module: source from
   the repo tip in `ros2.repos`, with the RCR overlay (Bazel BUILD files) **reconciled** onto it
   (`tools/reconcile_overlay.py`) so new/removed files and tests on master are picked up.
3. `tools/master_fixups.py` and `tools/source_patches/` carry what the reconciler can't infer.
4. `tools/extra_modules/` adds unreleased packages that only exist on master (extra test modules).
5. `tools/make_bcr_bump.py` / `bcr_bumps.json` bump BCR deps that master needs newer.
6. `tools/run_nightly_master.sh` wires it all into the workspace and runs `bazel test --config=ci`.

## Where the patches live

| What | Where | Used for |
|---|---|---|
| Build-file edits to an overlay | `tools/master_fixups.py` | master drift in BUILD/overlay files |
| Patches to upstream source | `tools/source_patches/<pkg>/*.patch` | real upstream bugs / libc++ gaps, one file per patch |
| Unreleased packages | `tools/extra_modules/<pkg>/` | packages with no RCR module yet |
| BCR version bumps | `tools/bcr_bumps.json` | deps master needs newer than BCR |

Source patches that are also proposed upstream should say so in the patch header and be dropped
here once merged. Currently: ros/class_loader#253, ros2/rclpy#1778.

## Workflows

- **nightly** (cron + manual): shards `nightly-targets.txt` across a matrix (`NIGHTLY_SHARD=i/N`),
  summarizes each shard and merges the results into the run summary.
- **flake-hunt** (manual): give it targets and `runs_per_test`; it reports pass/flake/timeout counts.

Hosted runners (4 cores, ~14 GB disk, 6 h cap) are a lot smaller than the machine this was developed
on, so treat the first runs as experimental: shard count, disk cleanup and the cache may need tuning.
Tests needing a display (rviz) or tracing (`--@rosdistro//:enable_tracing`) are not expected to pass yet.

## Running locally

```bash
ci/setup.sh
tools/run_nightly_master.sh                    # everything
NIGHTLY_SHARD=0/12 tools/run_nightly_master.sh # one shard
NIGHTLY_TARGETS=my_targets.txt tools/run_nightly_master.sh
GENERATE_ONLY=1 tools/run_nightly_master.sh    # then `bazel test ...` inside ros-central-registry/workspace
```

Requires Bazel (via bazelisk), Python 3 and `patch`.

## Refreshing the package list

`ros2.repos`, `ros2_repos_packages.json` and `pkgs_ros2_repos.txt` are checked in; regenerate them
with `tools/ros2_repos_packages.py` when `ros2.repos` or the RCR modules change.
