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
"""Helpers mirroring test_communication's CMake macros (one RMW: the build's static one).

`ros2 daemon stop` in the templates is replaced by `true`: there is no daemon in a hermetic run.
"""

load("@launch_testing_ros//:defs.bzl", "launch_ros_test")

RMW = "rmw_fastrtps_cpp"

def configured_launch_test(name, template, substitutions, exes = [], files = [], data = [], pydeps = [], **kwargs):
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
        pydeps: python libraries for helper scripts started with the test interpreter.
        **kwargs: forwarded to launch_ros_test.
    """
    cmd = "sed " + " ".join([
        "-e 's|@{}@|{}|g'".format(k, v)
        for k, v in substitutions.items()
    ]) + " -e \"s|\\['ros2', 'daemon', 'stop'\\]|['true']|\" -e \"s|\\.txt'|'|g\" $(location {}) > $@".format(template)
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
        deps = exes + pydeps,
        **kwargs
    )

def rl(label):
    """Working-directory-relative path of a target in the runfiles tree."""
    return "../$(rlocationpath {})".format(label)

def comm_launch_tests(cpp, py, data, py_deps, message_types, service_types, action_types):
    """add_launch_test for publisher/subscriber, requester/replier, action client/server over client library pairs.

    Args:
        cpp: role -> label of the rclcpp executable.
        py: role -> path of the rclpy script.
        data: runtime data.
        py_deps: python libraries for the rclpy scripts.
        message_types: interface names to exercise.
        service_types: interface names to exercise.
        action_types: interface names to exercise.
    """
    for kind, role1, role2, types_var, types, rmw_vars in [
        ("publisher_subscriber", "publisher", "subscriber", "MESSAGE_TYPES", message_types, ["PUBLISHER_RMW", "SUBSCRIBER_RMW"]),
        ("requester_replier", "requester", "replier", "SERVICE_TYPES", service_types, ["REQUESTER_RMW", "REPLIER_RMW"]),
        ("action_client_server", "action_client", "action_server", "ACTION_TYPES", action_types, ["ACTION_CLIENT_RMW", "ACTION_SERVER_RMW"]),
    ]:
        for lib1 in ["rclpy", "rclcpp"]:
            for lib2 in ["rclpy", "rclcpp"]:
                subs = {
                    "TEST_" + role1.upper() + "_EXECUTABLE": rl(cpp[role1] if lib1 == "rclcpp" else py[role1]),
                    "TEST_" + role2.upper() + "_EXECUTABLE": rl(cpp[role2] if lib2 == "rclcpp" else py[role2]),
                    "TEST_" + role1.upper() + "_RCL": lib1,
                    "TEST_" + role2.upper() + "_RCL": lib2,
                    "TEST_" + types_var: ";".join(types),
                }
                for v in rmw_vars:
                    subs[v] = RMW
                configured_launch_test(
                    name = "test_{}__{}__{}".format(kind, lib1, lib2),
                    template = "test/test_{}.py.in".format(kind),
                    data = data,
                    exes = [cpp[role1], cpp[role2]],
                    files = [py[role1], py[role2]],
                    pydeps = py_deps,
                    substitutions = subs,
                    timeout = "moderate",
                    env = {"RMW_IMPLEMENTATION": RMW},
                )
