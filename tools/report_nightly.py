"""Merge the per-shard summaries of a nightly run and fail on failures that are not in tools/known_failures.txt.

usage: report_nightly.py <dir with summary-<rmw>-<n>.json files> [--known tools/known_failures.txt]
Prints markdown (for $GITHUB_STEP_SUMMARY); exit status 1 if there are unexpected failures or build errors.
"""
import argparse
import collections
import glob
import json
import os
import re
import sys

BAD = ("FAILED", "TIMEOUT", "NO STATUS", "FAILED TO BUILD", "INCOMPLETE")


def load_known(path):
    known = {}   # target -> set of rmws or None (= all)
    for line in open(path):
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        target, _, rmws = line.partition(" ")
        rmws = rmws.strip() or "*"
        known[target] = None if rmws == "*" else set(rmws.split(","))
    return known


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dir")
    ap.add_argument("--known", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "known_failures.txt"))
    a = ap.parse_args()
    known = load_known(a.known)
    res = collections.defaultdict(dict)
    build = collections.defaultdict(list)
    for f in sorted(glob.glob(os.path.join(a.dir, "summary-*.json"))):
        rmw = re.search(r"summary-(.+)-\d+\.json", os.path.basename(f)).group(1)
        d = json.load(open(f))
        for k, v in d["tests"].items():
            # a SKIPPED (incompatible here) result must not hide a real result from another job
            if v != "SKIPPED" or k not in res[rmw]:
                res[rmw][k] = v
        build[rmw] += d.get("build_errors", [])
    if not res:
        print("## Nightly\n\nnothing to test (no changes in the window) or no summaries")
        return 0
    print("## Nightly\n")
    unexpected, flaky, fixed = [], [], []
    for rmw, ts in sorted(res.items()):
        c = collections.Counter(ts.values())
        print(f"- **{rmw}**: " + ", ".join(f"{k}: {v}" for k, v in sorted(c.items())) + f", build errors: {len(build[rmw])}")
        for t, s in ts.items():
            expected = t in known and (known[t] is None or rmw in known[t])
            if s in BAD and not expected:
                unexpected.append((t, rmw, s))
            elif s == "FLAKY":
                flaky.append((t, rmw))
            elif s in ("PASSED", "SKIPPED") and expected and s == "PASSED":
                fixed.append((t, rmw))
    print(f"\n### Unexpected failures ({len(unexpected)})\n")
    by = collections.defaultdict(list)
    for t, rmw, s in unexpected:
        by[t].append(f"{rmw} {s}")
    for t in sorted(by):
        print(f"- `{t}`: " + ", ".join(sorted(by[t])))
    for rmw, errs in sorted(build.items()):
        for e in errs:
            print(f"- BUILD ({rmw}) {e}")
    print(f"\n### Flaky ({len(flaky)})\n")
    for t, rmw in sorted(flaky):
        print(f"- `{t}` ({rmw})")
    print(f"\n### Known failures now passing ({len(fixed)}) - remove from tools/known_failures.txt\n")
    for t, rmw in sorted(fixed):
        print(f"- `{t}` ({rmw})")
    return 1 if unexpected or any(build.values()) else 0


if __name__ == "__main__":
    sys.exit(main())
