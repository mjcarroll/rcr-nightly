"""Summarize a `bazel test` log from run_nightly_master.sh: per-module pass/fail counts.

usage: summarize_nightly.py logs/nightly_full.log [--json out.json]
"""
import collections
import json
import re
import sys

STATUS = r"(FAILED TO BUILD|NO STATUS|PASSED|FAILED|FLAKY|TIMEOUT|SKIPPED|INCOMPLETE)"
LINE = re.compile(r"^(@[\w.+-]+//[^\s]*)\s+" + STATUS)
BUILD_ERR = re.compile(r"^ERROR: .*external/([\w.+-]+?)\+/.*(?:failed|Compiling|Linking)")


def main():
    log = sys.argv[1]
    tests = {}
    build_errors = collections.Counter()
    for raw in open(log, errors="replace"):
        line = raw.rstrip("\n")
        m = LINE.match(line)
        if m:
            tests[m.group(1)] = m.group(2)
        m = BUILD_ERR.match(line)
        if m:
            build_errors[m.group(1)] += 1
    per = collections.defaultdict(collections.Counter)
    for label, st in tests.items():
        per[label.split("//")[0].lstrip("@")][st] += 1
    total = collections.Counter(tests.values())
    for raw in open(log, errors="replace"):
        if raw.startswith("Executed ") and "tests" in raw:
            print(raw.strip())
    print("listed:", dict(total), "tests:", len(tests))
    bad = sorted(((sum(c[s] for s in c if s != "PASSED"), mod, c) for mod, c in per.items()), reverse=True)
    print("\nmodules with non-passing tests:")
    for n, mod, c in bad:
        if n:
            print(f"  {mod:45s} {dict(c)}")
    if build_errors:
        print("\nbuild errors by module:")
        for mod, n in build_errors.most_common(25):
            print(f"  {mod:45s} {n}")
    if "--json" in sys.argv:
        json.dump({"tests": tests, "build_errors": build_errors}, open(sys.argv[sys.argv.index("--json") + 1], "w"), indent=1)


main()
