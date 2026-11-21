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

"""Helpers mirroring test_rclcpp's CMake macros (one RMW: the build's static one)."""

load("@launch_testing_ros//:defs.bzl", "launch_ros_test")

RMW = "rmw_fastrtps_cpp"

def configured_launch_test(name, template, substitutions, exes = [], files = [], data = [], **kwargs):
    """configure_file(<template> @ONLY) + add_launch_test().

    Args:
        name: test name.
        template: the .py.in file.
        substitutions: @KEY@ -> value (a trailing .txt inside quotes is stripped: launch_testing's
            expected_output_from_file() takes the path without extension); values may use $(rlocationpath <label>) of `exes`/`files`.
            Paths are made relative to the test working directory (<runfiles>/_main),
            standing in for $<TARGET_FILE:...>.
        exes: executables the template runs (and that must be built).
        files: data files the template reads.
        data: extra runtime data.
        **kwargs: forwarded to launch_ros_test.
    """
    cmd = "sed " + " ".join([
        "-e 's|@{}@|{}|g'".format(k, v)
        for k, v in substitutions.items()
    ]) + " -e \"s|\\.txt'|'|g\" $(location {}) > $@".format(template)
    native.genrule(
        name = name + "_configure",
        srcs = [template] + files,
        outs = [name + "_launch.py"],
        cmd = cmd,
        tools = exes,
    )
    launch_ros_test(
        name = name,
        src = name + "_launch.py",
        data = data + files,
        deps = exes,
        **kwargs
    )

def rl(label):
    """Working-directory-relative path of a target in the runfiles tree."""
    return "../$(rlocationpath {})".format(label)
