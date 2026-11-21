#!/usr/bin/env python3
"""Map ros2.repos (rolling) -> ROS package names, and diff against RCR modules.

Usage: ros2_repos_packages.py <ros2.repos> <rcr modules dir> > out.json
Needs `gh` authenticated (uses the git trees API, one call per repo, plus raw fetches).
"""
import json, re, subprocess, sys, os
from concurrent.futures import ThreadPoolExecutor

def gh(path):
    return json.loads(subprocess.run(["gh", "api", path], capture_output=True, text=True, check=True).stdout)

def raw(owner_repo, ref, path):
    r = subprocess.run(["gh", "api", f"repos/{owner_repo}/contents/{path}?ref={ref}", "-H", "Accept: application/vnd.github.raw"],
                       capture_output=True, text=True)
    return r.stdout if r.returncode == 0 else ""

def packages_of(entry):
    name, url, ref = entry
    m = re.match(r"https://github.com/([^/]+/[^/.]+)", url)
    if not m:
        return name, ref, None, "non-github"
    orepo = m.group(1)
    try:
        tree = gh(f"repos/{orepo}/git/trees/{ref}?recursive=1")["tree"]
    except Exception as e:
        return name, ref, None, f"tree-error"
    pkgs = []
    for t in tree:
        if t["path"].endswith("package.xml") and "/test/" not in t["path"]:
            x = raw(orepo, ref, t["path"])
            mm = re.search(r"<name>\s*([^<\s]+)\s*</name>", x)
            if mm and not re.search(r"<name>.*</name>", "") :
                pkgs.append((mm.group(1), os.path.dirname(t["path"])))
    return name, ref, pkgs, "ok"

def main():
    text = open(sys.argv[1]).read()
    entries = re.findall(r"^  (\S+):\n    type: git\n    url: (\S+)\n    version: (\S+)", text, re.M)
    mods = {d for d in os.listdir(sys.argv[2]) if os.path.isdir(os.path.join(sys.argv[2], d))}
    out = {}
    with ThreadPoolExecutor(8) as ex:
        for name, ref, pkgs, status in ex.map(packages_of, entries):
            out[name] = {"ref": ref, "status": status,
                         "packages": [{"name": p, "path": d, "in_rcr": p in mods} for p, d in (pkgs or [])]}
    json.dump(out, sys.stdout, indent=1)

main()
