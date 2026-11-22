#!/usr/bin/env python3
"""Add newer versions of BCR modules than the Bazel Central Registry has, to the local registry.

For each entry in tools/bcr_bumps.json, take the BCR module files of `base` (MODULE.bazel, overlay), point
source.json at the new tarball, write <out>/modules/<module>/<version>/ and append a
single_version_override to <out>/overrides.bazel. Run after make_master_module.py and make_extra_module.py
(both rewrite overrides.bazel).

usage: make_bcr_bump.py --out <master-registry dir>
"""
import argparse, base64, hashlib, json, os, re, shutil, subprocess, tempfile, urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
CACHE = Path(os.environ.get("MM_CACHE", os.path.expanduser("~/.cache/mm_cache"))); CACHE.mkdir(parents=True, exist_ok=True)
BCR = "https://raw.githubusercontent.com/bazelbuild/bazel-central-registry/main/modules"


def sri(data):
    return "sha256-" + base64.b64encode(hashlib.sha256(data).digest()).decode()


def get(url):
    c = CACHE / hashlib.sha256(url.encode()).hexdigest()
    if not c.exists():
        urllib.request.urlretrieve(url, c.with_suffix(".part")); c.with_suffix(".part").rename(c)
    return c.read_bytes()


def bump(e, out):
    m, base, ver = e["module"], e["base"], e["version"]
    src = json.loads(get(f"{BCR}/{m}/{base}/source.json"))
    mod = out / "modules" / m / ver
    shutil.rmtree(mod, ignore_errors=True); (mod / "overlay").mkdir(parents=True)
    text = get(f"{BCR}/{m}/{base}/MODULE.bazel").decode()
    text = re.sub(r'version = "[^"]+"', f'version = "{ver}"', text, count=1)
    (mod / "MODULE.bazel").write_text(text)
    overlay = {}
    for rel in src.get("overlay", {}):
        data = get(f"{BCR}/{m}/{base}/overlay/{rel}")
        if rel == "MODULE.bazel":
            data = text.encode()
        (mod / "overlay" / rel).write_bytes(data); overlay[rel] = sri(data)
    src.update(url=e["url"], integrity=sri(get(e["url"])), strip_prefix=e["strip_prefix"], overlay=overlay)
    json.dump(src, open(mod / "source.json", "w"), indent=4)
    json.dump({"homepage": "", "maintainers": [], "versions": [ver], "yanked_versions": {}},
              open(out / "modules" / m / "metadata.json", "w"), indent=2)
    print(f"{m}: {base} -> {ver} ({e['why']})")


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--out", required=True)
    out = Path(ap.parse_args().out).resolve()
    entries = json.load(open(HERE / "bcr_bumps.json"))
    for e in entries:
        bump(e, out)
    ovr = out / "overrides.bazel"
    lines = ovr.read_text().splitlines() if ovr.exists() else []
    names = {e["module"] for e in entries}
    lines = [l for l in lines if not any(f'module_name = "{n}"' in l for n in names)]
    lines += [f'single_version_override(module_name = "{e["module"]}", version = "{e["version"]}")' for e in entries]
    ovr.write_text("\n".join(lines) + "\n")


main()
