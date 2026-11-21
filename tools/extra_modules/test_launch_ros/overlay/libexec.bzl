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

"""Lay executables out as lib/<package>/<name>, where launch_ros looks for them."""

def _impl(ctx):
    symlinks = {}
    runfiles = []
    for target, pkg in ctx.attr.executables.items():
        exe = target[DefaultInfo].files_to_run.executable
        symlinks["lib/%s/%s" % (pkg, exe.basename)] = exe
        runfiles.append(target[DefaultInfo].default_runfiles)
    return [DefaultInfo(runfiles = ctx.runfiles(symlinks = symlinks).merge_all(runfiles))]

libexec_layout = rule(
    implementation = _impl,
    attrs = {
        "executables": attr.label_keyed_string_dict(
            doc = "executable target -> ROS package name it is installed under",
        ),
    },
)
