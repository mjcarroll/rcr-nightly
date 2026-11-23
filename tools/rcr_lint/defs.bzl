"""ament_lint_auto equivalents: one test per linter, scanning the whole package like the CMake tests do."""

load("@rules_python//python:defs.bzl", "py_test")

_CPP = ["**/*.c", "**/*.cc", "**/*.cpp", "**/*.cxx", "**/*.h", "**/*.hh", "**/*.hpp", "**/*.hxx"]

_FILES = {
    "copyright": _CPP + ["**/*.py", "**/*.cmake", "CMakeLists.txt", "**/CMakeLists.txt"],
    "cpplint": _CPP,
    "lint_cmake": ["CMakeLists.txt", "**/CMakeLists.txt", "**/*.cmake"],
    "uncrustify": _CPP,
    "xmllint": ["**/*.xml"],
}

def ament_lint_tests(linters, exclude = []):
    """Defines test_<linter> for each linter that has files to look at and no test of that name yet."""
    for linter in linters:
        name = "test_" + linter
        if native.existing_rule(name):
            continue
        files = native.glob(_FILES[linter], exclude = exclude, allow_empty = True)
        if not files:
            continue
        tool = "@ament_%s//:cli" % linter
        native.genrule(
            name = name + "_main",
            srcs = ["@rcr_lint//:run_lint.py"],
            outs = [name + "_main.py"],
            cmd = "cp $< $@",
        )
        py_test(
            name = name,
            srcs = [name + "_main.py"],
            main = name + "_main.py",
            args = ["$(rlocationpath %s)" % tool, "$(rlocationpath package.xml)"],
            data = files + [f for f in ["package.xml"] if f not in files] + [tool],
            deps = ["@rules_python//python/runfiles"],
            size = "small",
        )
