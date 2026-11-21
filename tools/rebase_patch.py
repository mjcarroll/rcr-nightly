"""3-way rebase of an RCR patch onto a newer upstream tree.

  base   = release tree the patch was written against   (rroot)
  theirs = base + patch
  ours   = current upstream tree                         (work)
git merge-file merges (base -> theirs) into ours; a clean merge yields a rebased patch.
"""
import difflib, re, shutil, subprocess, tempfile
from pathlib import Path


def patch_files(patch_text, strip=1):
    return [m.group(1).split("/", strip)[1] for m in re.finditer(r"(?m)^\+\+\+ (\S+)", patch_text)]


def rebase_patch(patch_file, rroot, work):
    """Return (new_patch_text, merged_files{rel: text}) or (None, reason)."""
    text = Path(patch_file).read_text()
    files = patch_files(text)
    if not files:
        return None, "no files"
    tmp = Path(tempfile.mkdtemp(prefix="rebase_"))
    try:
        for rel in files:
            src = Path(rroot) / rel
            if not src.exists():
                return None, f"{rel} not in release tree"
            if not (Path(work) / rel).exists():
                return None, f"{rel} not in upstream tree"
            (tmp / "theirs" / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(src, tmp / "theirs" / rel)
        r = subprocess.run(["patch", "-p1", "-s", "-d", str(tmp / "theirs"), "-i", str(Path(patch_file).resolve())],
                           capture_output=True, text=True)
        if r.returncode != 0:
            return None, "patch does not apply to release tree"
        out, merged = [], {}
        for rel in files:
            base, theirs, ours = Path(rroot) / rel, tmp / "theirs" / rel, Path(work) / rel
            m = subprocess.run(["git", "merge-file", "-p", str(ours), str(base), str(theirs)], capture_output=True, text=True)
            if m.returncode != 0:
                return None, f"conflict in {rel} ({m.returncode} hunks)"
            merged[rel] = m.stdout
            a = ours.read_text().splitlines(keepends=True)
            b = m.stdout.splitlines(keepends=True)
            out.extend(difflib.unified_diff(a, b, f"a/{rel}", f"b/{rel}"))
        return "".join(out), merged
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
