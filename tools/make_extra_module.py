#!/usr/bin/env python3
"""Create local-registry modules for ros2.repos packages that have no RCR module.

The RCR only packages what is released to rosdistro, so unreleased test packages (system_tests,
test_tf2, ...) live here: tools/extra_modules/<pkg>/{spec.json, overlay/}. For each package this
writes, next to the master modules from make_master_module.py,
  <out>/modules/<pkg>/<ver>/{MODULE.bazel,source.json,overlay/}
appends a single_version_override to <out>/overrides.bazel and writes <out>/extra_deps.bazel
(bazel_dep lines for the workspace MODULE.bazel). Run after make_master_module.py (it rewrites overrides.bazel).

spec.json: {"repo": "ros2/examples", "ref": "rolling", "subdir": "rclcpp/services/deferred_response",
            "template": "examples_rclcpp_minimal_service"}   # RCR module whose MODULE.bazel (deps) to reuse; pick one
            # with the same ROS dependencies

usage: make_extra_module.py --rcr <rcr checkout> --out <master-registry dir> pkg [pkg ...]
"""
import argparse, base64, hashlib, json, os, re, shutil, subprocess, sys, tempfile, urllib.request
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from add_lint import add_lint

CACHE = Path(os.environ.get("MM_CACHE", os.path.expanduser("~/.cache/mm_cache"))); CACHE.mkdir(parents=True, exist_ok=True)
HERE = Path(__file__).resolve().parent


def sri(p):
    return "sha256-" + base64.b64encode(hashlib.sha256(Path(p).read_bytes()).digest()).decode()


def fetch(url, dst):
    c = CACHE / hashlib.sha256(url.encode()).hexdigest()
    if not c.exists():
        urllib.request.urlretrieve(url, c.with_suffix(".part")); c.with_suffix(".part").rename(c)
    shutil.copy(c, dst)


def latest_version(modules_dir, name):
    vs = [d.name for d in (modules_dir / name).iterdir() if d.is_dir()]
    return sorted(vs, key=lambda s: [int(x) if x.isdigit() else 0 for x in re.split(r"[.\-]", s)])[-1]


def one(pkg, rcr, out, ws_text=""):
    spec_dir = HERE / "extra_modules" / pkg
    spec = json.load(open(spec_dir / "spec.json"))
    sha = json.loads(subprocess.run(["gh", "api", f"repos/{spec['repo']}/commits/{spec['ref']}"],
                                    capture_output=True, text=True, check=True).stdout)["sha"]
    tmp = Path(tempfile.mkdtemp(prefix=f"xm_{pkg}_"))
    tgz = tmp / "src.tar.gz"
    url = f"https://github.com/{spec['repo']}/archive/{sha}.tar.gz"
    fetch(url, tgz)
    subprocess.run(["tar", "xzf", tgz, "-C", tmp], check=True)
    root = next(p for p in tmp.iterdir() if p.is_dir())
    shutil.rmtree(tmp / "unused", ignore_errors=True)

    modules = rcr / "modules"
    tver = latest_version(modules, spec["template"])
    text = (modules / spec["template"] / tver / "MODULE.bazel").read_text()
    mod = out / "modules" / pkg / "_tmp"
    shutil.rmtree(mod, ignore_errors=True)
    (mod / "overlay").mkdir(parents=True)
    shutil.copytree(spec_dir / "overlay", mod / "overlay", dirs_exist_ok=True)
    # every module carries the Apache license text the overlays refer to
    lic = modules / spec["template"] / tver / "overlay" / "LICENSE"
    if lic.exists() and not (mod / "overlay" / "LICENSE").exists():
        shutil.copy(lic, mod / "overlay" / "LICENSE")
    extra = spec_dir / "deps.bazel"            # extra bazel_dep lines on top of the template's
    text = re.sub(r'module\(\s*name = "[^"]+",\s*version = "[^"]+"', f'module(\n    name = "{pkg}",\n    version = "0.0.0"', text, count=1)
    if extra.exists():    # bazel_dep lines for deps the template module does not have
        have = set(re.findall(r'bazel_dep\(name = "([^"]+)"', text))
        text += "\n" + "".join(l + "\n" for l in extra.read_text().splitlines()
                               if not (m := re.match(r'bazel_dep\(name = "([^"]+)"', l)) or m.group(1) not in have)
    if not os.environ.get("NO_LINT"):    # same lint tests as the released packages get (upstream's ament_lint_auto set)
        text, _ = add_lint(pkg, mod / "overlay", root / spec["subdir"], text, ws_text)
    ov = {str(p.relative_to(mod / "overlay")): sri(p) for p in sorted((mod / "overlay").rglob("*")) if p.is_file()}
    digest = hashlib.sha256(json.dumps([ov, sri(tgz), text], sort_keys=True).encode()).hexdigest()[:6]
    ver = f"0.0.0.master.{sha[:7]}.{digest}"
    text = re.sub(r'version = "0\.0\.0"', f'version = "{ver}"', text, count=1)
    (mod / "MODULE.bazel").write_text(text)
    strip = f"{root.name}/{spec['subdir']}".rstrip("/")
    json.dump({"integrity": sri(tgz), "url": url, "strip_prefix": strip, "overlay": ov},
              open(mod / "source.json", "w"), indent=4)
    final = out / "modules" / pkg / ver
    shutil.rmtree(final, ignore_errors=True); mod.rename(final)
    json.dump({"homepage": f"https://github.com/{spec['repo']}", "maintainers": [], "versions": [ver], "yanked_versions": {}},
              open(out / "modules" / pkg / "metadata.json", "w"), indent=2)
    shutil.rmtree(tmp)
    print(f"{pkg}: {ver}")
    return ver


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rcr", required=True); ap.add_argument("--out", required=True)
    ap.add_argument("--workspace-module"); ap.add_argument("pkgs", nargs="+")
    a = ap.parse_args()
    rcr, out = Path(a.rcr).resolve(), Path(a.out).resolve()
    ws_text = Path(a.workspace_module).read_text() if a.workspace_module else ""
    vers = {p: one(p, rcr, out, ws_text) for p in a.pkgs}
    ovr = out / "overrides.bazel"
    lines = ovr.read_text().splitlines() if ovr.exists() else []
    lines = [l for l in lines if not any(f'module_name = "{p}"' in l for p in vers)]
    lines += [f'single_version_override(module_name = "{p}", version = "{v}")' for p, v in vers.items()]
    ovr.write_text("\n".join(lines) + "\n")
    # the workspace root must also depend on each extra module
    (out / "extra_deps.bazel").write_text(
        "".join(f'bazel_dep(name = "{p}", version = "0.0.0")\n' for p in sorted(vers)))


main()
