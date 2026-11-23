"""Run an ament linter over a whole package (like ament_lint_auto) and report per-file xunit results."""
import os
import shutil
import subprocess
import sys
import tempfile

from python.runfiles import Runfiles


def main():
    r = Runfiles.Create()
    exe = r.Rlocation(sys.argv[1])
    pkg_dir = os.path.dirname(r.Rlocation(sys.argv[2]))
    xunit = os.path.join(os.environ.get("TEST_TMPDIR", tempfile.gettempdir()), "lint.xml")
    # the generated copy of this script sits in the package directory: don't lint it
    cmd = [exe, "--xunit-file", xunit, pkg_dir]
    if "lint_cmake" not in sys.argv[1]:   # ament_lint_cmake has no --exclude (and does not look at .py anyway)
        cmd[1:1] = ["--exclude", os.path.basename(sys.argv[0])]
    rc = subprocess.run(cmd).returncode
    out = os.environ.get("XML_OUTPUT_FILE")
    if out and os.path.exists(xunit):
        shutil.copy(xunit, out)
    sys.exit(rc)


if __name__ == "__main__":
    main()
