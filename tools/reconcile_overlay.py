"""Reconcile RCR overlay BUILD files against an upstream (master) source tree.

Assumes buildifier-formatted files (one string per line in lists, top-level
statements closed in column 0), which is true of the RCR overlays.

  * drop list entries (in any list: srcs/hdrs/..., or top-level VARIABLE lists such
    as HEADERS) that name a code file that no longer exists in the tree, unless
    the literal is also used outside a list (i.e. it is generated)
  * drop cc_* rules whose srcs/hdrs end up empty
  * add NEW files (absent from `baseline`, the release tree the overlay was written
    against) to every list holding a same-directory, same-extension sibling; a new
    file that only has cc_test-srcs siblings is reported as `new_tests`
"""
import os, re
from pathlib import Path

CODE_EXT = (".hpp", ".h", ".hh", ".cpp", ".cc", ".c", ".inc", ".ipp", ".hxx", ".py", ".em")
ITEM = re.compile(r'^(\s*)"([^"\s()\'=]+)",?\s*$')  # file refs only: not quoted code lines (e.g. write_file content)
LIST_OPEN = re.compile(r'^(\s*)(\w+)\s*=\s*(?:\[[^\]]*\]\s*\+\s*)*\[\s*$')
DICT_STR = re.compile(r'^(\s+)"([^"]+)":\s*"(?!\.\./)([^"/][^"]*\.[A-Za-z0-9]+|[^"]+/[^"]*\.[A-Za-z0-9]+)",?\s*$')
LIST_CONT = re.compile(r'^(\s*)\]\s*\+\s*\[\s*$')
DICT_ITEM = re.compile(r'^(\s*)"([^"]+)":\s*\[((?:"[^"]+"(?:,\s*)?)+)\],?\s*$')
HDR_EXT = {".h", ".hpp", ".hh", ".hxx", ".inc", ".ipp"}
SRC_EXT = {".c", ".cc", ".cpp"}


def _family(ext):
    return "hdr" if ext in HDR_EXT else "src" if ext in SRC_EXT else ext


SKIP_ATTRS = {"deps", "copts", "defines", "linkopts", "tags", "visibility", "includes",
              "local_defines", "features", "env", "args", "outs", "exports_files"}


def _plain(s):
    return not any(c in s for c in ':@{}*') and not s.startswith('//')


def _parse(lines):
    """Return list spans (attr, open, close, indent, rule_kind) and rule spans."""
    rules = []
    i = 0
    while i < len(lines):
        m = re.match(r'^(\w+)\($', lines[i])
        if m:
            j = i
            while not lines[j].startswith(")"):
                j += 1
            rules.append((i, j, m.group(1)))
            i = j
        i += 1
    lists = []
    last_attr = None
    for k, l in enumerate(lines):
        m = LIST_OPEN.match(l)
        if m:
            last_attr = m.group(2)
        else:
            mc = LIST_CONT.match(l)
            if mc and last_attr:
                m = re.match(r'^(\s*)(\w+)$', mc.group(1) + last_attr)
        if not m or m.group(2) in SKIP_ATTRS:
            continue
        close = k + 1
        while not re.match(r'^' + m.group(1) + r'\]', lines[close]):
            close += 1
        kind = next((r[2] for r in rules if r[0] < k < r[1]), None)
        lists.append((m.group(2), k, close, m.group(1), kind))
    return lists, rules


def reconcile_build(build, base, others, baseline, referenced_elsewhere_pkg, provided=frozenset()):
    rep = {"removed": [], "added": [], "removed_rules": [], "new_tests": [], "unplaced": []}
    text0 = build.read_text()
    # expand single-line file lists so the line-based logic below can see/modify them
    def _expand(m):
        items = re.findall(r'"[^"]*"', m.group(3))
        return f"{m.group(1)}{m.group(2)} = [\n" + "".join(f"{m.group(1)}    {i},\n" for i in items) + f"{m.group(1)}],"
    text0 = re.sub(r'(?m)^(\s*)(srcs|hdrs|textual_hdrs|private_hdrs|data) = \[((?:"[^"]*"(?:,\s*)?)+)\],?[ \t]*$', _expand, text0)
    # rules with a single missing interface file: src = "X.msg" -> drop the rule and every reference to it
    while True:
        hit = None
        for m in re.finditer(r'(?m)^\w+\(\n(?:.*\n)*?^\)\n\n?', text0):
            body = m.group(0)
            sm = re.search(r'\n    src = "([^"/][^"]*\.[A-Za-z0-9]+)",', body)
            nm = re.search(r'\n    name = "([^"]+)"', body)
            if (sm and nm and _plain(sm.group(1)) and not (base / sm.group(1)).exists() and sm.group(1) not in provided
                    and not re.search(r'outs?\s*=\s*\[?[^\]]*"' + re.escape(sm.group(1)) + '"', text0.replace(body, ""))):
                hit = (m, sm.group(1), nm.group(1))
                break
        if not hit:
            break
        m, src, name = hit
        text0 = text0[:m.start()] + text0[m.end():]
        for ref in (f'":{name}"', f'"{src}"'):
            text0 = re.sub(r'(?m)^\s+' + re.escape(ref) + r',?\n', "", text0)
        rep["removed_rules"].append(name); rep["removed"].append(src)
    lines = text0.split("\n")
    lists, _ = _parse(lines)
    item_lines = {n for _, o, c, _, _ in lists for n in range(o + 1, c)}
    dict_str = {n: DICT_STR.match(l) for n, l in enumerate(lines) if DICT_STR.match(l)}
    item_lines |= set(dict_str)
    non_list = set()
    for n, l in enumerate(lines):
        if n not in item_lines:
            non_list.update(re.findall(r'"([^"]+)"', l))
    drop = set()
    for attr, o, c, ind, kind in lists:
        for n in range(o + 1, c):
            m = ITEM.match(lines[n])
            if not m:
                continue
            p = m.group(2)
            if _plain(p) and os.path.splitext(p)[1] and "/" in p + "/" and not p.startswith(("http", ".")) and not (base / p).exists() and p not in provided and p not in non_list:
                drop.add(n)
                rep["removed"].append(p)
    # dict-style entries: "test_x": ["path.cpp"],
    dicts = [(n, DICT_ITEM.match(l)) for n, l in enumerate(lines) if DICT_ITEM.match(l)]
    dict_paths = set()
    for n, m in dicts:
        paths = re.findall(r'"([^"]+)"', m.group(3))
        dict_paths.update(paths)
        if any(_plain(x) and os.path.splitext(x)[1] and not (base / x).exists() and x not in provided for x in paths):
            drop.add(n)
            rep["removed"].extend(paths)
    dict_inserts = {}
    for n, m in dict_str.items():
        v = m.group(3)
        if _plain(v) and not (base / v).exists() and v not in provided and v not in non_list:
            drop.add(n)
            rep["removed"].append(v)
    # additions
    listed = set(dict_paths)
    for attr, o, c, ind, kind in lists:
        for n in range(o + 1, c):
            m = ITEM.match(lines[n])
            if m:
                listed.add(m.group(2))
    inserts = {}
    for root, dirs, files in os.walk(base):
        dirs[:] = [d for d in dirs if (Path(root) / d) not in others]
        for f in sorted(files):
            rel = str((Path(root) / f).relative_to(base))
            if not f.endswith(CODE_EXT) or rel in listed or rel in baseline or rel in referenced_elsewhere_pkg:
                continue
            d, ext = os.path.dirname(rel), os.path.splitext(rel)[1]
            placed = False
            dsib = [(n, m) for n, m in dicts if n not in drop and any(os.path.dirname(x) == d for x in re.findall(r'"([^"]+)"', m.group(3)))]
            if dsib and ext == ".cpp" and os.path.basename(rel).startswith("test_"):
                nm = os.path.splitext(os.path.basename(rel))[0]
                pos = next((n for n, m in dicts if n not in drop and m.group(2) > nm and abs(n - dsib[0][0]) < 400), dsib[-1][0] + 1)
                ind = dsib[0][1].group(1)
                dict_inserts.setdefault(pos, []).append(f'{ind}"{nm}": ["{rel}"],')
                rep["new_tests"].append(rel); continue
            for attr, o, c, ind, kind in lists:
                items = [ITEM.match(lines[n]).group(2) for n in range(o + 1, c)
                         if ITEM.match(lines[n]) and n not in drop]
                if not any(os.path.dirname(x) == d and _family(os.path.splitext(x)[1]) == _family(ext) for x in items):
                    continue
                if kind in ("cc_test", "cc_binary") and attr == "srcs":
                    rep["new_tests"].append(rel); placed = True
                    continue
                pos = c
                for n in range(o + 1, c):
                    m = ITEM.match(lines[n])
                    if m and n not in drop and m.group(2) > rel:
                        pos = n
                        break
                inserts.setdefault(pos, []).append(f'{ind}    "{rel}",')
                placed = True
            if not placed and _family(ext) in ("hdr", "src") and "test" not in d.split("/") and "tests" not in d.split("/"):
                # fallback: library list (not a cc_test) of the same family sharing the longest directory prefix
                best, best_score = None, 0
                for attr, o, c, ind, kind in lists:
                    if kind in ("cc_test", None) or attr not in ("srcs", "hdrs", "textual_hdrs"):
                        continue
                    for n in range(o + 1, c):
                        m = ITEM.match(lines[n])
                        if m and n not in drop and _family(os.path.splitext(m.group(2))[1]) == _family(ext):
                            a, b = os.path.dirname(m.group(2)).split("/"), d.split("/")
                            score = 0
                            while score < min(len(a), len(b)) and a[score] == b[score]:
                                score += 1
                            if score > best_score:
                                best, best_score = (attr, o, c, ind), score
                if best:
                    attr, o, c, ind = best
                    pos = c
                    for n in range(o + 1, c):
                        m = ITEM.match(lines[n])
                        if m and n not in drop and m.group(2) > rel:
                            pos = n
                            break
                    inserts.setdefault(pos, []).append(f'{ind}    "{rel}",')
                    placed = True
            if placed:
                if rel not in rep["added"] and rel not in rep["new_tests"]:
                    rep["added"].append(rel)
            else:
                rep["unplaced"].append(rel)
    out = []
    for n, l in enumerate(lines):
        if n in inserts:
            out.extend(inserts[n])
        if n in dict_inserts:
            out.extend(dict_inserts[n])
        if n not in drop:
            out.append(l)
    text = "\n".join(out)
    # prune cc_* rules left with no sources
    for _ in range(3):
        changed = False
        for m in list(re.finditer(r'(?m)^(cc_test|cc_binary|cc_library)\(\n(?:.*\n)*?^\)\n\n?', text)):
            body = m.group(0)
            if re.search(r'srcs = \[\n\s+\],?', body) or re.search(r'srcs = \[\s*\]', body):
                if not re.search(r'hdrs = \[\n\s+"', body) and not re.search(r'hdrs = \["', body):
                    nm = re.search(r'name = "([^"]+)"', body)
                    rep["removed_rules"].append(nm.group(1) if nm else "?")
                    text = text.replace(body, "")
                    changed = True
        if not changed:
            break
    build.write_text(text)
    return rep


def reconcile_overlay(overlay_dir, tree_dir, baseline=frozenset()):
    overlay_dir, tree_dir = Path(overlay_dir), Path(tree_dir)
    builds = sorted(overlay_dir.rglob("BUILD.bazel"))
    owned = {tree_dir / b.parent.relative_to(overlay_dir) for b in builds}
    owned |= {p.parent for p in tree_dir.rglob("BUILD.bazel")}
    report = {}
    for b in builds:
        reld = b.parent.relative_to(overlay_dir)
        base = tree_dir / reld
        others = {d for d in owned if d != base}
        prefix = "" if str(reld) == "." else str(reld) + "/"
        bl = {p[len(prefix):] for p in baseline if p.startswith(prefix)}
        provided = {str(p.relative_to(b.parent)) for p in b.parent.rglob("*") if p.is_file()}
        report[str(reld / "BUILD.bazel")] = reconcile_build(b, base, others, bl, set(), provided)
    # template renames (X__Y.h.em -> X__Y.hpp.em) => rename the declared outputs in overlay .bzl files
    removed = {Path(x) for rep in report.values() for x in rep["removed"]}
    added = {Path(x) for rep in report.values() for x in rep["added"]}
    renames = []
    for old in removed:
        if old.suffix != ".em":
            continue
        old_out = old.name[:-3]                      # msg__rosidl_typesupport_fastrtps_c.h
        stem, _, ext = old_out.partition(".")
        for new in added:
            if new.parent == old.parent and new.suffix == ".em" and new.name[:-3].partition(".")[0] == stem:
                new_ext = new.name[:-3].partition(".")[2]
                if new_ext != ext and "__" in stem:
                    renames.append((stem.split("__", 1)[1], ext, new_ext))
    for bzl in overlay_dir.rglob("*.bzl"):
        t = bzl.read_text(); t0 = t
        for suffix, old_ext, new_ext in set(renames):
            t = t.replace(f'__{suffix}.{old_ext}"', f'__{suffix}.{new_ext}"')
        if t != t0:
            bzl.write_text(t)
            report.setdefault("_bzl_renames", []).append(str(bzl.relative_to(overlay_dir)))
    return report


# ---------------------------------------------------------------------------
# dependency drift: package.xml deps added upstream since the release the
# overlay was written against.
# ---------------------------------------------------------------------------
PKG_DEP_TAGS = ("depend", "build_depend", "build_export_depend", "exec_depend", "test_depend")


def _pkg_deps(xml):
    out = {"run": set(), "test": set()}
    for tag, name in re.findall(r"<(" + "|".join(PKG_DEP_TAGS) + r")(?:\s[^>]*)?>\s*([^<\s]+)\s*<", xml):
        out["test" if tag == "test_depend" else "run"].add(name)
    return out


def _target_style(modules_dir, ws_text, dep):
    """How a dependency's targets are named: 'iface' (cc_shared/cc), 'lib' (<n>/<n>_library) or None."""
    m = re.search(rf'bazel_dep\(name = "{re.escape(dep)}", version = "([^"]+)"\)', ws_text)
    if not m:
        return None, None
    b = Path(modules_dir) / dep / m.group(1) / "overlay" / "BUILD.bazel"
    if not b.exists():
        return None, m.group(1)
    t = b.read_text()
    if "default_generators(" in t or (re.search(r'name = "cc_shared"', t) and re.search(r'name = "cc"', t)):
        return "iface", m.group(1)
    if re.search(rf'name = "{re.escape(dep)}_library"', t):
        return "lib", m.group(1)
    return None, m.group(1)


def reconcile_deps(overlay_dir, tree_pkg_xml, baseline_pkg_xml, module_text, ws_text, modules_dir):
    """Add upstream-new package.xml deps to MODULE.bazel and the DEPENDENCIES dicts. Returns (module_text, report)."""
    rep = {"added": [], "missing_module": [], "unplaced": []}
    new, old = _pkg_deps(tree_pkg_xml), _pkg_deps(baseline_pkg_xml)
    for kind in ("run", "test"):
        for dep in sorted(new[kind] - old[kind] - old["run" if kind == "test" else "test"]):
            if dep.startswith("ament_") or dep in ("rosidl_default_generators",):
                continue
            if re.search(rf'bazel_dep\(name = "{re.escape(dep)}"', module_text):
                already = True
            else:
                already = False
            style, ver = _target_style(modules_dir, ws_text, dep)
            if ver is None:
                rep["missing_module"].append(dep)
                continue
            if style is None:
                rep["unplaced"].append(dep)
                continue
            if style == "iface":
                key, val = f'"@{dep}//:cc_shared"', f'"@{dep}//:cc"'
            else:
                key, val = f'"@{dep}//:{dep}"', f'"@{dep}//:{dep}_library"'
            target = Path(overlay_dir) / ("test/BUILD.bazel" if kind == "test" else "BUILD.bazel")
            if not target.exists():
                rep["unplaced"].append(dep)
                continue
            text = target.read_text()
            m = re.search(r'(?m)^(\w*DEPENDENCIES) = \{\n((?:    .*\n)*?)\}\n', text)
            if not m or key in text:
                if not m:
                    rep["unplaced"].append(dep)
                continue
            lines = m.group(2).rstrip("\n").split("\n")
            entry = f"    {key}: {val},"
            pos = next((i for i, l in enumerate(lines) if l.strip() > entry.strip()), len(lines))
            lines.insert(pos, entry)
            text = text[:m.start(2)] + "\n".join(lines) + "\n" + text[m.end(2):]
            target.write_text(text)
            if not already:
                module_text = module_text.rstrip("\n") + f'\nbazel_dep(name = "{dep}", version = "{ver}")\n'
            rep["added"].append(f"{kind}:{dep}")
    return module_text, rep
