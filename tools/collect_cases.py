"""Collect per-testcase results from bazel-testlogs test.xml files.

usage: collect_cases.py <testlogs-dir> out.json

Output: {"<repo>//<pkg>:<target>": [[classname, name, status], ...]}
status is PASSED / FAILED / SKIPPED. Targets whose xml has no <testcase>
(e.g. a crash before any case ran) map to an empty list.
"""
import json
import os
import sys
import xml.etree.ElementTree as ET


def status(tc):
    if tc.find("failure") is not None or tc.find("error") is not None:
        return "FAILED"
    if tc.find("skipped") is not None or tc.get("status") in ("notrun", "skipped"):
        return "SKIPPED"
    return "PASSED"


def main():
    root, out = sys.argv[1], sys.argv[2]
    res = {}
    for dirpath, _, files in os.walk(root, followlinks=False):
        if "test.xml" not in files:
            continue
        rel = os.path.relpath(dirpath, root)
        parts = rel.split(os.sep)
        if parts[0] == "external" and len(parts) > 1:
            repo = parts[1].split("+")[0]
            label = f"{repo}//" + "/".join(parts[2:])
        else:
            label = rel
        try:
            tree = ET.parse(os.path.join(dirpath, "test.xml"))
        except ET.ParseError:
            res[label] = None
            continue
        res[label] = [[tc.get("classname", ""), tc.get("name", ""), status(tc)]
                      for tc in tree.iter("testcase")]
    json.dump(res, open(out, "w"), separators=(",", ":"))
    n = sum(len(v) for v in res.values() if v)
    print(f"collected {n} cases from {len(res)} targets "
          f"({sum(1 for v in res.values() if not v)} without cases)")


if __name__ == "__main__":
    main()
