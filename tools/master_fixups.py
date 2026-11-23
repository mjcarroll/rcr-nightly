"""Hand-written overlay edits for master mode that cannot be derived automatically.

Each fixup is (overlay-relative file, old text, new text). Every one is a burn-down
candidate: the goal is for this table to shrink to nothing.
"""
from pathlib import Path

FIXUPS = {
    # The RCR carries a patch to the Python generator's output mapping so outputs have flat names.
    # Declaring upstream's own output names in the aspect makes that patch unnecessary (release too),
    # and also covers the new *_impl.hpp output master added.
    "rosidl_typesupport_fastrtps_c": [(
        "aspects.bzl",
        'templates_hdrs = ["detail/{}__rosidl_typesupport_fastrtps_c.hpp"],\n'
        '        templates_srcs = ["detail/{}__rosidl_typesupport_fastrtps_c.cpp"],',
        'templates_hdrs = [\n'
        '            "detail/{}__rosidl_typesupport_fastrtps_c.hpp",\n'
        '            "detail/{}__rosidl_typesupport_fastrtps_c_impl.hpp",\n'
        '        ],\n'
        '        templates_srcs = ["detail/{}__type_support_c.cpp"],',
    )],
    "rosidl_typesupport_fastrtps_cpp": [(
        "aspects.bzl",
        'templates_hdrs = ["detail/{}__rosidl_typesupport_fastrtps_cpp.hpp"],\n'
        '        templates_srcs = ["detail/{}__rosidl_typesupport_fastrtps_cpp.cpp"],',
        'templates_hdrs = [\n'
        '            "detail/{}__rosidl_typesupport_fastrtps_cpp.hpp",\n'
        '            "detail/{}__rosidl_typesupport_fastrtps_cpp_impl.hpp",\n'
        '        ],\n'
        '        templates_srcs = ["detail/dds_fastrtps/{}__type_support.cpp"],',
    )],
    # ros2cli imports colorama (ros2cli.color) but the overlay doesn't depend on it, although it is in the
    # pip lock: `ros2 ...` and everything that drives it (sros2, ros2topic, ros2pkg, ...) fails to import.
    "ros2cli": [(
        "BUILD.bazel",
        '        requirement("argcomplete"),\n',
        '        requirement("argcomplete"),\n        requirement("colorama"),\n',
    )],
    # Master's rosidl_parser looks for a pre-compiled grammar.lark.bin that CMake generates at build time; the overlay
    # never produced it, so test_grammar_cache_* fail and every parse compiles the grammar from scratch.
    "rosidl_parser": [
        ("BUILD.bazel", 'load("@rules_python//python:defs.bzl", "py_library")\n',
         'load("@rules_python//python:defs.bzl", "py_binary", "py_library")\n'),
        ("BUILD.bazel", '        "rosidl_parser/grammar.lark",\n        "rosidl_parser/py.typed",\n    ],\n    deps = [requirement("lark")],\n)\n',
         '        "rosidl_parser/grammar.lark",\n        "rosidl_parser/py.typed",\n        ":grammar_cache",\n    ],\n    deps = [requirement("lark")],\n)\n\n'
         'py_binary(\n    name = "generate_grammar_cache",\n    srcs = ["rosidl_parser/generate_grammar_cache.py"],\n'
         '    data = ["rosidl_parser/grammar.lark"],\n    main = "rosidl_parser/generate_grammar_cache.py",\n'
         '    deps = [requirement("lark")],\n)\n\n'
         'genrule(\n    name = "grammar_cache",\n    outs = ["rosidl_parser/grammar.lark.bin"],\n'
         '    cmd = "$(location :generate_grammar_cache) --output $@",\n    tools = [":generate_grammar_cache"],\n)\n'),
    ],
    # cli.py imports argcomplete, which mypy must be able to resolve; the lint targets only depend on @ament_<linter>.
    "ament_index_python": [
        ("BUILD.bazel", 'load("@rosdistro//python:defs.bzl", "py_pytest")\n',
         'load("@pip_ros//:requirements.bzl", "requirement")\nload("@rosdistro//python:defs.bzl", "py_pytest")\n'),
        ("BUILD.bazel", '    deps = ["@ament_{0}".format(linter)],\n',
         '    deps = ["@ament_{0}".format(linter)] + ([requirement("argcomplete")] if linter == "mypy" else []),\n'),
    ],
    # The test imports ament_mypy (-> mypy); the overlay does not declare it.
    "camera_info_manager_py": [(
        "test/BUILD.bazel",
        '    deps = ["//:camera_info_manager_py"],',
        '    deps = [\n        "//:camera_info_manager_py",\n        "@ament_mypy",\n    ],',
    )],
    # Upstream links every message_filters gtest into one binary with test_main.cpp (which calls rclcpp::init).
    # The overlay builds one binary per file with the plain gtest main, so this test, which creates a Node,
    # fails with "context argument is null". Give it its own target with test_main.cpp.
    "message_filters": [
        ("test/BUILD.bazel", '    "message_filters-test_time_sequencer": "time_sequencer_unittest.cpp",\n', ''),
        ("test/BUILD.bazel", 'cc_test(\n    name = "message_filters-test_fuzz",',
         'cc_test(\n    name = "message_filters-test_time_sequencer",\n'
         '    srcs = [\n        "test_main.cpp",\n        "time_sequencer_unittest.cpp",\n    ],\n'
         '    dynamic_deps = ["//:transitive_dynamic_deps"],\n'
         '    deps = TEST_DEPENDENCIES.values() + [\n        "@rosdistro//cc:googletest",\n    ],\n)\n\n'
         'cc_test(\n    name = "message_filters-test_fuzz",'),
    ],
    # Test files removed upstream on master (the overlays list them explicitly).
    "rcpputils": [("test/BUILD.bazel", '    "test_endian",\n', '')],
    "ament_index_cpp": [("test/BUILD.bazel", '    "utest_deprecated",\n', '')],
    # chdir() needs <unistd.h>; libc++ no longer provides it transitively.
    "libyaml_vendor": [(
        "BUILD.bazel",
        "    content = [\n        '__attribute__((constructor))",
        "    content = [\n        '#include <unistd.h>',\n        '__attribute__((constructor))",
    )],
    # Upstream dropped src/manifest.cpp: PLUGINLIB_EXPORT_CLASS now lives in raw_publisher.cpp /
    # raw_subscriber.cpp, which are part of the main library. Keep the plugins shared library as a shell.
    "point_cloud_transport": [(
        "BUILD.bazel",
        'cc_shared_library(\n    name = "point_cloud_transport_plugins",',
        'cc_library(\n    name = "point_cloud_transport_plugins_library",\n'
        '    deps = PLUGIN_DEPENDENCIES.values(),\n)\n\n'
        'cc_shared_library(\n    name = "point_cloud_transport_plugins",',
    )],
    # The reconciler appended the two new upstream gtest sources to every sibling srcs list (the plugin
    # libraries included). Remove them there and give each its own cc_test (CMake: ament_add_gtest).
    "class_loader": [
        ("test/BUILD.bazel", '        "external_load_test.cpp",\n', ''),
        ("test/BUILD.bazel", '        "unmanaged_test.cpp",\n', ''),
        ("test/BUILD.bazel",
         'cc_test(\n    name = "class_loader_utest",',
         '[cc_test(\n'
         '    name = "class_loader_" + test,\n'
         '    srcs = [\n        "base.hpp",\n        test + ".cpp",\n    ],\n'
         '    data = [\n        ":ament_index_class_loader_utest",\n    ],\n'
         '    dynamic_deps = ["//:transitive_dynamic_deps"],\n'
         '    deps = DEPENDENCIES.values() + [\n        "//:class_loader_library",\n        "@rosdistro//cc:googletest",\n    ],\n'
         ') for test in [\n    "external_load_test",\n    "unmanaged_test",\n]]\n\n'
         'cc_test(\n    name = "class_loader_utest",'),
    ],
    # New upstream service (used by rosbag2_transport's recorder) that the release overlay does not know about.
    "rosbag2_interfaces": [
        ("srv/BUILD.bazel", '    "GetRate.srv",\n', '    "GetRate.srv",\n    "GetSubscribedTopics.srv",\n'),
        ("srv/BUILD.bazel",
         'ros_service(\n    name = "IsPaused",',
         'ros_service(\n    name = "GetSubscribedTopics",\n    src = "GetSubscribedTopics.srv",\n)\n\nros_service(\n    name = "IsPaused",'),
        ("BUILD.bazel", '        "//srv:GetRate",\n', '        "//srv:GetRate",\n        "//srv:GetSubscribedTopics",\n'),
    ],
    # New upstream overlay/tf_trajectory display and tool headers (their .cpp files were picked up by the
    # reconciler, the headers were not). The ones with Q_OBJECT must also go through moc.
    "rviz_default_plugins": [
        ("BUILD.bazel", '\nHEADERS = [\n',
         '\nHEADERS = [\n'
         '    "include/rviz_default_plugins/displays/overlay/overlay_utils.hpp",\n'
         '    "include/rviz_default_plugins/displays/overlay_camera/overlay_camera_display.hpp",\n'
         '    "include/rviz_default_plugins/displays/overlay_image/overlay_image_display.hpp",\n'
         '    "include/rviz_default_plugins/displays/tf_trajectory/tf_trajectory_display.hpp",\n'
         '    "include/rviz_default_plugins/tools/overlay_picker/overlay_picker_tool.hpp",\n'),
        ("BUILD.bazel", '\nMOC_HEADERS = [\n',
         '\nMOC_HEADERS = [\n'
         '    "include/rviz_default_plugins/displays/overlay_camera/overlay_camera_display.hpp",\n'
         '    "include/rviz_default_plugins/displays/overlay_image/overlay_image_display.hpp",\n'
         '    "include/rviz_default_plugins/displays/tf_trajectory/tf_trajectory_display.hpp",\n'
         '    "include/rviz_default_plugins/tools/overlay_picker/overlay_picker_tool.hpp",\n'),
        # Ogre's OgreUTFString.h needs the registry's libc++ char_traits<unsigned short> patch (same as
        # rviz_2d_overlay_plugins / nav2_rviz_plugins).
        ("BUILD.bazel",
         '    hdrs = MOC_HEADERS + [h for h in HEADERS if h not in MOC_HEADERS],\n    includes = ["include"],\n',
         '    hdrs = MOC_HEADERS + [h for h in HEADERS if h not in MOC_HEADERS],\n'
         '    copts = [\n        "-include",\n        "char_traits_patch.h",\n    ],\n    includes = ["include"],\n'),
    ],
    # Upstream merged rmw_fastrtps_shared_cpp into rmw_fastrtps_cpp (tracked in mjcarroll/ros-project-management#82):
    # drop the old module dependency, resolve merged `rmw_fastrtps_shared_cpp/...` includes from src/, and carry
    # over the old shared module's other dependencies.
    "rmw_fastrtps_cpp": [
        ("BUILD.bazel",
         '    "@rmw_fastrtps_shared_cpp//:rmw_fastrtps_shared_cpp": "@rmw_fastrtps_shared_cpp//:rmw_fastrtps_shared_cpp_library",\n',
         '    "@rmw_security_common//:rmw_security_common": "@rmw_security_common//:rmw_security_common_library",\n'
         '    "@rosidl_typesupport_introspection_c//:rosidl_typesupport_introspection_c": "@rosidl_typesupport_introspection_c//:rosidl_typesupport_introspection_c_library",\n'
         '    "@rosidl_typesupport_introspection_cpp//:rosidl_typesupport_introspection_cpp": "@rosidl_typesupport_introspection_cpp//:rosidl_typesupport_introspection_cpp_library",\n'),
        ("BUILD.bazel", '        "@rmw_fastrtps_shared_cpp//:ament_package",\n', ''),
        ("test/BUILD.bazel",
         '    "@rmw_fastrtps_shared_cpp//:rmw_fastrtps_shared_cpp": "@rmw_fastrtps_shared_cpp//:rmw_fastrtps_shared_cpp_library",\n', ''),
        ("BUILD.bazel",
         '    hdrs = HEADERS,\n    includes = ["include"],\n    local_defines = ros_local_defines(),\n    deps = DEPENDENCIES.values(),',
         '    hdrs = HEADERS,\n    includes = ["include", "src"],\n    local_defines = ros_local_defines(),\n    deps = DEPENDENCIES.values(),'),
    ],
}

# MODULE.bazel edits: (old module dep to drop, new module deps to add), versions come from the workspace pins.
MODULE_FIXUPS = {
    "camera_info_manager_py": ([], ["ament_mypy"]),
    "rmw_fastrtps_cpp": (["rmw_fastrtps_shared_cpp"],
                         ["rmw_security_common", "rosidl_typesupport_introspection_c", "rosidl_typesupport_introspection_cpp"]),
}


def apply_module_fixups(pkg, text, ws_text):
    import re
    drop, add = MODULE_FIXUPS.get(pkg, ([], []))
    for d in drop:
        text = re.sub(rf'(?m)^bazel_dep\(name = "{d}", version = "[^"]+"\)\n', "", text)
    for a in add:
        if re.search(rf'bazel_dep\(name = "{a}"', text):
            continue
        m = re.search(rf'bazel_dep\(name = "{a}", version = "([^"]+)"\)', ws_text)
        if m:
            text = text.rstrip("\n") + f'\nbazel_dep(name = "{a}", version = "{m.group(1)}")\n'
    return text


def apply_fixups(pkg, overlay_dir):
    applied, missed = [], []
    for rel, old, new in FIXUPS.get(pkg, []):
        f = Path(overlay_dir) / rel
        t = f.read_text() if f.exists() else ""
        if old in t:
            f.write_text(t.replace(old, new)); applied.append(rel)
        else:
            missed.append(rel)
    return applied, missed
