#!/usr/bin/env python3
"""Create a local-registry module that builds an RCR package from upstream master.

For package P (repo ros2/R, subdir D) this writes
  <out>/modules/P/<ver>.master.<sha7>/{MODULE.bazel,source.json,overlay/,patches/}
reusing the RCR module's overlay (BUILD files) and every RCR patch that still
applies to master. Patches that fail are recorded in <out>/patch_report.json.

usage: make_master_module.py --rcr <rcr checkout> --out <dir> --workspace-module <MODULE.bazel>
                             --map <ros2_repos_packages.json> pkg [pkg ...]
"""
import argparse, base64, hashlib, json, os, re, shutil, subprocess, sys, tempfile, urllib.request
from pathlib import Path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from reconcile_overlay import reconcile_overlay, reconcile_deps
from master_fixups import apply_fixups, apply_module_fixups
from add_lint import add_lint, write_module as write_lint_module
from rebase_patch import rebase_patch

CACHE = Path(os.environ.get("MM_CACHE", "/tmp/mm_cache")); CACHE.mkdir(parents=True, exist_ok=True)
_SHA = {}

def fetch(url, dst):
    c = CACHE / hashlib.sha256(url.encode()).hexdigest()
    if not c.exists():
        urllib.request.urlretrieve(url, c.with_suffix(".part")); c.with_suffix(".part").rename(c)
    shutil.copy(c, dst)

def sri(p):
    return "sha256-" + base64.b64encode(hashlib.sha256(Path(p).read_bytes()).digest()).decode()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rcr", required=True); ap.add_argument("--out", required=True)
    ap.add_argument("--workspace-module", required=True); ap.add_argument("--map", required=True)
    ap.add_argument("pkgs", nargs="+")
    a = ap.parse_args()
    rmap = json.load(open(a.map))
    pkg2repo = {p["name"]: (r, p["path"], v["ref"]) for r, v in rmap.items() for p in v["packages"]}
    ws = open(a.workspace_module).read()
    out = Path(a.out).resolve(); report = {}
    def one(pkg):
        repo, subdir, ref = pkg2repo[pkg]
        ver = re.search(rf'bazel_dep\(name = "{pkg}", version = "([^"]+)"\)', ws).group(1)
        base = Path(a.rcr).resolve() / "modules" / pkg / ver
        if (repo, ref) not in _SHA:
            _SHA[(repo, ref)] = json.loads(subprocess.run(["gh", "api", f"repos/{repo}/commits/{ref}"], capture_output=True, text=True, check=True).stdout)["sha"]
        sha = _SHA[(repo, ref)]
        newver = f"{ver}.master.{sha[:7]}"
        tmp = Path(tempfile.mkdtemp(prefix=f"mm_{pkg}_"))
        tgz = tmp / "src.tar.gz"
        url = f"https://github.com/{repo}/archive/{sha}.tar.gz"
        fetch(url, tgz)
        subprocess.run(["tar", "xzf", tgz, "-C", tmp], check=True)
        root = next(p for p in tmp.iterdir() if p.is_dir())
        work = root / subdir
        src_in = json.load(open(base / "source.json"))
        final_newver = newver
        mod = out / "modules" / pkg / "_tmp"
        shutil.rmtree(mod, ignore_errors=True)
        (mod / "overlay").mkdir(parents=True, exist_ok=True); (mod / "patches").mkdir(exist_ok=True)
        # overlay: copy RCR overlay files verbatim
        ov = {}
        for rel in src_in.get("overlay", {}):
            dst = mod / "overlay" / rel; dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(base / "overlay" / rel, dst); ov[rel] = sri(dst)
        # patches: keep those that apply (cumulatively, in order)
        rtmp = Path(tempfile.mkdtemp(prefix=f"rel_{pkg}_")); rtgz = rtmp / "rel.tar.gz"
        fetch(src_in["url"], rtgz)
        subprocess.run(["tar", "xzf", rtgz, "-C", rtmp], check=True)
        rroot = next(p for p in rtmp.iterdir() if p.is_dir())
        applied, failed, rebased = {}, [], {}
        for name in sorted(src_in.get("patches", {})):
            pf = base / "patches" / name
            dry = subprocess.run(["patch", "-p1", "--forward", "-s", "--dry-run", "-d", str(work), "-i", str(pf)], capture_output=True, text=True)
            if dry.returncode == 0:
                subprocess.run(["patch", "-p1", "--forward", "-s", "-d", str(work), "-i", str(pf)], check=True)
                shutil.copy(pf, mod / "patches" / name); applied[name] = sri(mod / "patches" / name)
                continue
            hand = Path(__file__).resolve().parent / "hand_rebased" / pkg / name
            if hand.exists() and subprocess.run(["patch", "-p1", "--forward", "-s", "--dry-run", "-d", str(work), "-i", str(hand)]).returncode == 0:
                subprocess.run(["patch", "-p1", "--forward", "-s", "-d", str(work), "-i", str(hand)], check=True)
                shutil.copy(hand, mod / "patches" / name); applied[name] = sri(mod / "patches" / name); rebased[name] = "hand"
                continue
            newp, info = rebase_patch(pf, rroot, work)
            if newp is not None:
                (mod / "patches" / name).write_text(newp)
                for rel, txt in info.items():
                    (work / rel).write_text(txt)
                applied[name] = sri(mod / "patches" / name); rebased[name] = "3-way"
            else:
                failed.append(name); rebased[name] = f"FAILED: {info}"
                subprocess.run(["bash", "-c", f"cd {work} && find . -name '*.rej' -o -name '*.orig' | xargs rm -f"])
        # source patches that are ours (not carried by the RCR): tools/source_patches/<pkg>/*.patch.
        # Each is a burn-down candidate for an upstream PR.
        for pf in sorted((Path(__file__).resolve().parent / "source_patches" / pkg).glob("*.patch")):
            r = subprocess.run(["patch", "-p1", "--forward", "-s", "-d", str(work), "-i", str(pf)], capture_output=True, text=True)
            name = "ours_" + pf.name
            if r.returncode == 0:
                shutil.copy(pf, mod / "patches" / name); applied[name] = sri(mod / "patches" / name); rebased[name] = "ours"
            else:
                failed.append(name); rebased[name] = f"FAILED: {r.stdout}{r.stderr}"
                subprocess.run(["bash", "-c", f"cd {work} && find . -name '*.rej' -o -name '*.orig' | xargs rm -f"])
        # baseline = files in the release tarball the overlay was written against
        baseline = {str(p.relative_to(rroot)) for p in rroot.rglob("*") if p.is_file()}
        base_pkg_xml = (rroot / "package.xml").read_text() if (rroot / "package.xml").exists() else ""
        shutil.rmtree(rtmp)
        rec = reconcile_overlay(mod / "overlay", work, baseline)
        for rel in ov:
            ov[rel] = sri(mod / "overlay" / rel)
        fx_ok, fx_missed = apply_fixups(pkg, mod / "overlay")
        rec["_fixups"] = {"applied": fx_ok, "missed": fx_missed}
        text = (base / "MODULE.bazel").read_text()
        pkg_xml = (work / "package.xml").read_text() if (work / "package.xml").exists() else ""
        text, deprep = reconcile_deps(mod / "overlay", pkg_xml, base_pkg_xml, text, ws, Path(a.rcr).resolve() / "modules")
        text = apply_module_fixups(pkg, text, ws)
        if not os.environ.get("NO_LINT"):
            text, lints = add_lint(pkg, mod / "overlay", work, text, ws)
            rec["_lint"] = lints
        rec["_deps"] = deprep
        for rel in ov:
            ov[rel] = sri(mod / "overlay" / rel)
        digest = hashlib.sha256(json.dumps([ov, applied, sri(tgz), text], sort_keys=True).encode()).hexdigest()[:6]
        newver = f"{ver}.master.{sha[:7]}.{digest}"
        text = re.sub(r'version = "[^"]+",', f'version = "{newver}",', text, count=1)
        (mod / "MODULE.bazel").write_text(text)
        sj = {"integrity": sri(tgz), "url": url, "strip_prefix": f"{root.name}/{subdir}".rstrip("/"),
              "patch_strip": 1, "overlay": ov, "patches": applied}
        json.dump(sj, open(mod / "source.json", "w"), indent=4)
        final = out / "modules" / pkg / newver
        shutil.rmtree(final, ignore_errors=True); mod.rename(final); mod = final
        md = out / "modules" / pkg / "metadata.json"
        json.dump({"homepage": f"https://github.com/{repo}", "maintainers": [], "versions": [newver], "yanked_versions": {}}, open(md, "w"), indent=2)
        report[pkg] = {"repo": repo, "ref": ref, "sha": sha, "version": newver, "base_version": ver,
                       "patches_total": len(src_in.get("patches", {})), "patches_applied": len(applied), "patches_failed": failed, "patches_rebase": rebased, "overlay_reconcile": rec}
        print(f"{pkg}: {newver}  patches {len(applied)}/{len(src_in.get('patches', {}))} apply (rebased: {[k for k, v in rebased.items() if v in ('3-way', 'hand')]}); failed: {failed}")
        print("  deps:", rec.get("_deps"))
        for f, r in rec.items():
            if f in ("_deps", "_bzl_renames", "_fixups", "_lint"): continue
            print(f"  overlay {f}: -{len(r['removed'])} +{len(r['added'])} new_tests={len(r['new_tests'])} rules_removed={r['removed_rules']} unplaced={r['unplaced']}")
        shutil.rmtree(tmp)
    for pkg in a.pkgs:
        try:
            one(pkg)
        except Exception as e:
            report[pkg] = {"error": f"{type(e).__name__}: {e}"}
            print(f"{pkg}: ERROR {type(e).__name__}: {e}", flush=True)
    out.mkdir(parents=True, exist_ok=True)
    write_lint_module(out, ws)
    json.dump({"mirrors": []}, open(out / "bazel_registry.json", "w"))
    prev = json.load(open(out / "patch_report.json")) if (out / "patch_report.json").exists() else {}
    prev.update(report); json.dump(prev, open(out / "patch_report.json", "w"), indent=1)
    with open(out / "overrides.bazel", "w") as f:
        for pkg, r in sorted(prev.items()):
            if "error" in r: continue
            f.write(f'single_version_override(module_name = "{pkg}", version = "{r["version"]}")\n')

main()
