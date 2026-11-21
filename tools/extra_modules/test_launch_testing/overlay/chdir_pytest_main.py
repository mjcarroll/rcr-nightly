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

"""Run pytest from a directory inside this package's runfiles: chdir_pytest_main.py <subdir> <pytest args>.

The upstream tests find their helper executables/scripts relative to the working directory
(CMake's WORKING_DIRECTORY); this reproduces that without touching the tests.
"""

import os
import sys

import pytest

if __name__ == '__main__':
    # this script lives at <runfiles>/<this repo>/chdir_pytest_main.py
    repo_dir = os.path.dirname(os.path.abspath(__file__))
    subdir, *args = sys.argv[1:]
    args = [os.path.abspath(a) for a in args if not a.startswith('-')] + [a for a in args if a.startswith('-')]
    os.chdir(os.path.join(repo_dir, subdir))
    sys.exit(pytest.main(args))
