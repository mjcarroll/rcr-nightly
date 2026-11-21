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
"""Helpers mirroring test_security's CMake macros (one RMW: the build's static one).

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
    ]) + " -e \"s|\\['ros2', 'daemon', 'stop'\\]|['true']|\" -e \"s|\\.txt'|'|g\" -e \"s|'ABS::\\([^']*\\)'|os.path.abspath('\\1')|g\" $(location {}) > $@".format(template)
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

def _sros_keystore_impl(ctx):
    out = ctx.actions.declare_directory(ctx.label.name)
    ctx.actions.run(
        executable = ctx.executable.tool,
        arguments = [out.path, ctx.file.invalid_cert.path],
        inputs = [ctx.file.invalid_cert],
        outputs = [out],
        mnemonic = "SrosKeystore",
        progress_message = "Generating SROS2 keystore %{label}",
    )
    return [DefaultInfo(files = depset([out]), runfiles = ctx.runfiles([out]))]

sros_keystore = rule(
    doc = "The keystore test_security's sros_artifacts fixture creates (ros2 security generate_artifacts).",
    implementation = _sros_keystore_impl,
    attrs = {
        "invalid_cert": attr.label(allow_single_file = True, mandatory = True),
        "tool": attr.label(executable = True, cfg = "exec", mandatory = True),
    },
)
