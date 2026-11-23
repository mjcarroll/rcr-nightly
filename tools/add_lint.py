"""Give ament_cmake packages the lint tests ament_lint_auto adds under colcon.

The RCR only has lint tests for packages with Python test files. For every package whose CMakeLists
calls ament_lint_auto_find_test_dependencies(), define test_{copyright,cpplint,lint_cmake,uncrustify,xmllint}
(the set ament_lint_common provides) in the overlay BUILD file via @rcr_lint//:defs.bzl, and add the
bazel_deps that needs.
"""
import json
import re
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
COMMON = ["copyright", "cpplint", "lint_cmake", "uncrustify", "xmllint"]
LOAD = 'load("@rcr_lint//:defs.bzl", "ament_lint_tests")\n'


# upstream passes generated files through CMake variables (AMENT_LINT_AUTO_FILE_EXCLUDE); spelled out here
EXTRA_EXCLUDE = {
    "rosidl_runtime_c": ["include/rosidl_runtime_c/type_description/**", "src/type_description/**"],
    "rosidl_runtime_cpp": ["include/rosidl_runtime_cpp/type_description/**"],
}


def _cmake(work):
    cm = Path(work) / "CMakeLists.txt"
    return re.sub(r"(?m)#.*$", "", cm.read_text()) if cm.exists() else ""


_EXTS = {
    "cpplint": (".c", ".cc", ".cpp", ".cxx", ".h", ".hh", ".hpp", ".hxx"),
    "uncrustify": (".c", ".cc", ".cpp", ".cxx", ".h", ".hh", ".hpp", ".hxx"),
    "copyright": (".c", ".cc", ".cpp", ".cxx", ".h", ".hh", ".hpp", ".hxx", ".py", ".cmake"),
    "lint_cmake": (".cmake",),
    "xmllint": (".xml",),
}


def _has_files(work, linter):
    """The linters fail with 'No files found' when there is nothing to look at."""
    for f in Path(work).rglob("*"):
        if not f.is_file():
            continue
        if f.name.endswith(_EXTS[linter]) or (linter in ("lint_cmake", "copyright") and f.name == "CMakeLists.txt"):
            return True
    return False


def linters_for(work):
    cm = _cmake(work)
    if "ament_lint_auto_find_test_dependencies" not in cm:
        return []
    pkg_xml = (Path(work) / "package.xml").read_text() if (Path(work) / "package.xml").exists() else ""
    ls = list(COMMON) if "ament_lint_common" in pkg_xml else [l for l in COMMON if f"ament_cmake_{l}" in pkg_xml]
    skipped = set()   # list(APPEND|set AMENT_LINT_AUTO_EXCLUDE ament_cmake_x ...)
    for m in re.finditer(r"(?:list\s*\(\s*APPEND|set\s*\()\s*AMENT_LINT_AUTO_EXCLUDE([^)]*)\)", cm):
        skipped |= set(re.findall(r"ament_cmake_(\w+)", m.group(1)))
    skipped |= set(re.findall(r"set\s*\(\s*ament_cmake_(\w+)_FOUND\s+TRUE", cm))
    return [l for l in ls if l not in skipped and _has_files(work, l)]


def add_lint(pkg, overlay, work, text, ws_text):
    ls = linters_for(Path(work))
    build = Path(overlay) / "BUILD.bazel"
    if not ls or not build.exists():
        return text, []
    body = build.read_text()
    if "ament_lint_tests" in body:
        return text, ls
    # files the RCR overlay adds to the package are not upstream's: upstream's lint never sees them
    patched = set()   # files the RCR (or our) patches rewrite: upstream's lint never saw those edits either
    for pf in (Path(overlay).parent / "patches").glob("*"):
        patched |= {m.group(1) for m in re.finditer(r"(?m)^\+\+\+ b/(\S+)", pf.read_text(errors="replace"))}
    ov_only = sorted(set(patched) | set(EXTRA_EXCLUDE.get(pkg, [])) | set(str(p.relative_to(overlay)) for p in Path(overlay).rglob("*")
                     if p.is_file() and not (Path(work) / p.relative_to(overlay)).exists()
                     and p.name not in ("BUILD.bazel", "LICENSE")))
    # globs stop at package boundaries: every subdirectory with its own BUILD file exports its lintable files
    subs = sorted(str(b.parent.relative_to(overlay)) for b in Path(overlay).rglob("BUILD.bazel") if b.parent != Path(overlay))
    for d in subs:
        sb = Path(overlay) / d / "BUILD.bazel"
        sub_ex = [e[len(d) + 1:] for e in ov_only if e.startswith(d + "/")]
        sb.write_text('load("@rcr_lint//:defs.bzl", "ament_lint_files")\n' + sb.read_text().rstrip("\n")
                      + f"\n\nament_lint_files(exclude = {json.dumps(sub_ex)})\n")
    root_ex = [e for e in ov_only if not any(e.startswith(d + "/") for d in subs)]
    call = (f"\n\nament_lint_tests(\n    linters = {json.dumps(ls)},\n    exclude = {json.dumps(root_ex)},\n"
            f"    subpackages = {json.dumps(subs)},\n)\n")
    build.write_text(LOAD + body.rstrip("\n") + call)
    deps = ["rcr_lint"] + [f"ament_{l}" for l in ls]
    for d in deps:
        if re.search(rf'bazel_dep\(name = "{d}"', text):
            continue
        if d == "rcr_lint":
            text = text.rstrip("\n") + '\nbazel_dep(name = "rcr_lint", version = "0.0.0")\n'
            continue
        m = re.search(rf'bazel_dep\(name = "{d}", version = "([^"]+)"\)', ws_text)
        if m:
            text = text.rstrip("\n") + f'\nbazel_dep(name = "{d}", version = "{m.group(1)}")\n'
    return text, ls


def write_module(out, ws_text):
    """master-registry/rcr_lint/: the macro module, referenced by a local_path_override in the workspace."""
    dst = Path(out) / "rcr_lint"
    shutil.rmtree(dst, ignore_errors=True)
    dst.mkdir(parents=True)
    rp = re.search(r'bazel_dep\(name = "rules_python", version = "([^"]+)"', ws_text).group(1)
    (dst / "MODULE.bazel").write_text((HERE / "rcr_lint" / "MODULE.bazel.in").read_text().replace("@RULES_PYTHON@", rp))
    for f in ("BUILD.bazel", "defs.bzl", "run_lint.py"):
        shutil.copy(HERE / "rcr_lint" / f, dst / f)
