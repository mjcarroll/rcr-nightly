#!/usr/bin/env python3
"""List the nightly packages (and extra test modules) with commits on their branch in the last N hours.

usage: changed_since.py --hours 24 [--map ros2_repos_packages.json] [--pkgs pkgs_ros2_repos.txt]
                        [--extra tools/extra_modules]
Prints one name per line to stdout, a summary to stderr. A package counts as changed when a commit on
its repo's tracked branch touched its directory. Needs `gh` authenticated.
"""
import argparse, datetime, json, subprocess, sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument("--hours", type=float, default=24)
ap.add_argument("--map", default="ros2_repos_packages.json")
ap.add_argument("--pkgs", default="pkgs_ros2_repos.txt")
ap.add_argument("--extra", default="tools/extra_modules")
a = ap.parse_args()

since = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=a.hours)).strftime("%Y-%m-%dT%H:%M:%SZ")
nightly = set(Path(a.pkgs).read_text().split())
jobs = []  # (name, repo, ref, path)
for repo, v in json.load(open(a.map)).items():
    for p in v.get("packages") or []:
        if p["name"] in nightly:
            jobs.append((p["name"], repo, v["ref"], p["path"]))
for spec_file in sorted(Path(a.extra).glob("*/spec.json")):
    s = json.load(open(spec_file))
    jobs.append((spec_file.parent.name, s["repo"], s["ref"], s.get("subdir", "")))


def changed(job):
    name, repo, ref, path = job
    q = f"repos/{repo}/commits?sha={ref}&since={since}&per_page=1" + (f"&path={path}" if path and path != "." else "")
    r = subprocess.run(["gh", "api", q, "--jq", "length"], capture_output=True, text=True)
    if r.returncode != 0:
        print(f"WARN {name}: gh api failed ({r.stderr.strip()[:80]}); treating as changed", file=sys.stderr)
        return name, True  # fail safe: if we cannot tell, test it
    return name, r.stdout.strip() not in ("", "0")


with ThreadPoolExecutor(16) as ex:
    res = list(ex.map(changed, jobs))
out = sorted(n for n, c in res if c)
if out:
    print("\n".join(out))
print(f"changed since {since}: {len(out)} of {len(res)} packages/modules", file=sys.stderr)
