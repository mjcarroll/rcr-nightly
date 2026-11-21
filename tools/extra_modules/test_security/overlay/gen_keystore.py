"""sros_artifacts.cmake: generate the enclaves, then break two of them on purpose."""

import os
import pathlib
import shutil
import sys


# ament_index_python only falls back to the runfiles tree inside a test; this runs as a build
# action, so point it there explicitly (the ament_index data lands in the main repo's root).
if not os.environ.get('AMENT_PREFIX_PATH'):
    os.environ['AMENT_PREFIX_PATH'] = os.path.join(os.environ['RUNFILES_DIR'], '_main')

from sros2.api import _artifact_generation  # noqa: E402
import sros2.errors  # noqa: E402

keystore, invalid_cert = sys.argv[1:3]
enclaves = ['/publisher', '/subscriber', '/publisher_missing_key', '/publisher_invalid_cert']

# What `ros2 security generate_artifacts -k <keystore> -e <enclaves>` does (the ros2 CLI
# itself is not needed, and ros2cli.color wants colorama).
try:
    _artifact_generation.generate_artifacts(pathlib.Path(keystore), enclaves, [])
except sros2.errors.SROS2Error as e:
    print(f'Unable to generate artifacts: {e}', file=sys.stderr)
    sys.exit(1)

os.remove(os.path.join(keystore, 'enclaves', 'publisher_missing_key', 'key.pem'))
shutil.copy(invalid_cert, os.path.join(keystore, 'enclaves', 'publisher_invalid_cert', 'cert.pem'))
