# Copyright 2026 Open Source Robotics Foundation, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""A private lttng-sessiond per test run.

The daemon's unix socket lives under $LTTNG_HOME/.lttng (default $HOME, which is far too long inside
the Bazel sandbox: sun_path is limited to 108 bytes), and $LTTNG_HOME must exist. A shared daemon is
raced for by parallel tests and dies with whichever test started it, so each run gets its own short
home, and its daemon is stopped at the end.
"""

import os
import shutil
import signal
import tempfile

_home = tempfile.mkdtemp(prefix='lt', dir='/tmp')
os.environ['LTTNG_HOME'] = _home


def pytest_sessionfinish(session, exitstatus):
    try:
        with open(os.path.join(_home, '.lttng', 'lttng-sessiond.pid')) as f:
            os.kill(int(f.read().strip()), signal.SIGTERM)
    except (OSError, ValueError):
        pass
    shutil.rmtree(_home, ignore_errors=True)
