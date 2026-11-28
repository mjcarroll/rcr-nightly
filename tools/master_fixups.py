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
    # test_cli_extension.py does not use test_convert_round_trip.py, which imports the generated test messages that
    # this target does not depend on (the overlay bundled the file into it).
    "rosidl_generator_py": [
        ("test/BUILD.bazel", '        "test_cli_extension.py",\n        "test_convert_round_trip.py",\n', '        "test_cli_extension.py",\n'),
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
    # The reconciler appended the new upstream gtest sources to every sibling srcs list (the plugin
    # libraries included). Remove them there and give each its own cc_test (CMake: ament_add_gtest).
    "class_loader": [
        ("test/BUILD.bazel", '        "external_load_test.cpp",\n', ''),
        ("test/BUILD.bazel", '        "unmanaged_test.cpp",\n', ''),
        ("test/BUILD.bazel", '        "multi_library_exit_test.cpp",\n', ''),
        ("test/BUILD.bazel",
         'cc_test(\n    name = "class_loader_utest",',
         '[cc_test(\n'
         '    name = "class_loader_" + test,\n'
         '    srcs = [\n        "base.hpp",\n        test + ".cpp",\n    ],\n'
         '    data = [\n        ":ament_index_class_loader_utest",\n    ],\n'
         '    dynamic_deps = ["//:transitive_dynamic_deps"],\n'
         '    deps = DEPENDENCIES.values() + [\n        "//:class_loader_library",\n        "@rosdistro//cc:googletest",\n    ],\n'
         ') for test in [\n    "external_load_test",\n    "multi_library_exit_test",\n    "unmanaged_test",\n]]\n\n'
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
    # Upstream (rqt#371) added test/msg/Constants.msg; the reconciler does not add new interface files.
    "rqt_py_common": [
        ("test/msg/BUILD.bazel", '    "ArrayVal.msg",\n    "Val.msg",\n',
         '    "ArrayVal.msg",\n    "Constants.msg",\n    "Val.msg",\n'),
        ("test/msg/BUILD.bazel", '\nros_message(\n    name = "Val",',
         '\nros_message(\n    name = "Constants",\n    src = "Constants.msg",\n'
         '    package = "rqt_py_common_test_interfaces",\n)\n\nros_message(\n    name = "Val",'),
        ("BUILD.bazel", '        "//test/msg:ArrayVal",\n', '        "//test/msg:ArrayVal",\n        "//test/msg:Constants",\n'),
        ("BUILD.bazel", '        "//test/msg:ArrayVal.msg",\n', '        "//test/msg:ArrayVal.msg",\n        "//test/msg:Constants.msg",\n'),
    ],
    # qt_cc_test defaults to QT_QPA_PLATFORM=offscreen (and that wins over --test_env); under it Qt's winId() is not an
    # X window, so Ogre cannot create a GLX render window on it. Tests that render need the xcb platform (Xvfb on CI).
    "class_loader": [
        # upstream now builds src/shared_library.cpp only with CLASS_LOADER_USE_RCPPUTILS=OFF; the default (ON) aliases
        # rcpputils::SharedLibrary in the header, so compiling it clashes.
        ("BUILD.bazel", '        "src/multi_library_class_loader.cpp",\n        "src/shared_library.cpp",\n',
         '        "src/multi_library_class_loader.cpp",\n'),
        ("test/BUILD.bazel", '        "external_load_test.cpp",\n', ''),
        ("test/BUILD.bazel", '        "multi_library_exit_test.cpp",\n', ''),
        ("test/BUILD.bazel", '        "shared_library_test.cpp",\n', ''),
        ("test/BUILD.bazel", '        "shared_library_test_library.cpp",\n', ''),
        ("test/BUILD.bazel", '        "unmanaged_test.cpp",\n', ''),
        ("test/BUILD.bazel", 'cc_test(\n    name = "class_loader_fviz_test",', 'class_loader_plugin(\n    name = "class_loader_TestSharedLibrary",\n    srcs = ["shared_library_test_library.cpp"],\n    deps = ["//:class_loader_headers"],\n)\n\nament_index(\n    name = "ament_index_unmanaged_test",\n    libraries = [\n        ":class_loader_TestPlugins1",\n        ":class_loader_TestPlugins2",\n        ":class_loader_TestPlugins3",\n    ],\n)\n\ncc_test(\n    name = "class_loader_unmanaged_test",\n    srcs = ["unmanaged_test.cpp", "base.hpp"],\n    data = [":ament_index_unmanaged_test"],\n    dynamic_deps = ["//:transitive_dynamic_deps"],\n    deps = DEPENDENCIES.values() + [\n        "//:class_loader_library",\n        "@rosdistro//cc:googletest",\n    ],\n)\n\nament_index(\n    name = "ament_index_external_load_test",\n    libraries = [\n        ":class_loader_TestPlugins1",\n        ":class_loader_TestPlugins2",\n    ],\n)\n\ncc_test(\n    name = "class_loader_external_load_test",\n    srcs = ["external_load_test.cpp", "base.hpp"],\n    data = [":ament_index_external_load_test"],\n    dynamic_deps = ["//:transitive_dynamic_deps"],\n    deps = DEPENDENCIES.values() + [\n        "//:class_loader_library",\n        "@rosdistro//cc:googletest",\n    ],\n)\n\nament_index(\n    name = "ament_index_multi_library_exit_test",\n    libraries = [\n        ":class_loader_TestPlugins1",\n    ],\n)\n\ncc_test(\n    name = "class_loader_multi_library_exit_test",\n    srcs = ["multi_library_exit_test.cpp"],\n    data = [":ament_index_multi_library_exit_test"],\n    dynamic_deps = ["//:transitive_dynamic_deps"],\n    deps = DEPENDENCIES.values() + [\n        "//:class_loader_library",\n        "@rosdistro//cc:googletest",\n    ],\n)\n\nament_index(\n    name = "ament_index_shared_library_test",\n    libraries = [":class_loader_TestSharedLibrary"],\n)\n\ncc_test(\n    name = "class_loader_shared_library_test",\n    srcs = ["shared_library_test.cpp"],\n    data = [":ament_index_shared_library_test"],\n    dynamic_deps = ["//:transitive_dynamic_deps"],\n    deps = DEPENDENCIES.values() + [\n        "//:class_loader_library",\n        "@rosdistro//cc:googletest",\n    ],\n)\n\ncc_test(\n    name = "class_loader_fviz_test",'),
    ],
    "lifecycle": [
        ("test/BUILD.bazel", '    tags = [\n        "manual",\n        "xfail",\n    ],\n', ''),
    ],
    "lifecycle_py": [
        ("test/BUILD.bazel", '    tags = [\n        "manual",\n        "xfail",\n    ],\n', ''),
        ("test/BUILD.bazel", '        "@lifecycle//:lifecycle_listener",\n',
         '        "@lifecycle//:lifecycle_listener",\n        "//:lifecycle_talker",\n'),
    ],
    "rosbag2_py": [
        ("test/BUILD.bazel", '    tags = ["manual"] if test == "transport" else [],\n', ''),
        ("test/BUILD.bazel", '        "@rcl_interfaces//:py",\n', '        "@rcl_interfaces//:py",\n        "@rosbag2_interfaces//:py",\n'),
    ],
    "rclcpp_components": [
        # removed upstream (rclcpp#3447); the overlay's ament_package still lists the executables
        ("BUILD.bazel", '        ":component_container_event",\n        ":component_container_mt",\n        ":component_container_isolated",\n', ''),
    ],
    "rqt_bag": [
        # RCR wires no tests for this package; upstream has four pytest files besides the lint ones
        ("BUILD.bazel", 'load("@rosdistro//ament:defs.bzl", "ament_index", "ament_package")\n',
         'load("@rosdistro//ament:defs.bzl", "ament_index", "ament_package")\nload("@rosdistro//python:defs.bzl", "py_pytest")\n'),
        ("BUILD.bazel", 'ament_package(\n    name = "ament_package",', '[py_pytest(\n    name = test,\n    srcs = ["test/{0}.py".format(test)],\n    imports = ["test"],\n    deps = [\n        ":rqt_bag",\n        "@rclpy",\n        "@rosbag2_py",\n        "@rosgraph_msgs//:py",\n        "@std_msgs//:py",\n    ],\n) for test in [\n    "test_player",\n    "test_player_clock",\n    "test_rosbag2_compression",\n    "test_rosbag2_missing_message_package",\n]]\n\n' + 'ament_package(\n    name = "ament_package",'),
    ],
    "camera_info_manager": [
        # RCR tags the unit test manual+xfail; it needs only the installed calibration yaml.
        ("tests/BUILD.bazel", '    tags = [\n        "manual",\n        "xfail",\n    ],\n', ''),
    ],
    "rviz_common": [
        ("BUILD.bazel", '    name = "frame_manager_test",\n    srcs = [],\n    data = TEST_DATA,\n',
         '    name = "frame_manager_test",\n    srcs = [],\n    data = TEST_DATA,\n'
         '    env = {"QT_QPA_PLATFORM": "xcb"},\n'),
    ],
    "rviz_default_plugins": [
        ("test/BUILD.bazel", '    data = TEST_DATA,\n',
         '    data = TEST_DATA,\n    env = {"QT_QPA_PLATFORM": "xcb"},\n'),
        ("test/BUILD.bazel", '    "@rviz_rendering_tests//:ament_index",\n] + [',
         '    "@rviz_rendering_tests//:ament_index",\n    "@rviz_visual_testing_framework//:ament_index",\n    "@urdf//:ament_index",\n    "@urdf_parser_plugin//:ament_index",\n] + ['),
        # RCR tags the display tests manual+xfail because they could not run (no OGRE GL plugin, no display). With the
        # plugin restored and Xvfb on the runner they run again. The *_visual_test targets stay manual: upstream only
        # builds them with -DEnableVisualTests=True (they also need reference images), so the nightly never ran them.
        ("test/BUILD.bazel",
         '    tags = [\n        "manual",\n        "no-sandbox",\n        "xfail",\n    ],\n'
         '    deps = TEST_DEPS,\n) for test, srcs in DISPLAY_TESTS.items()]',
         '    tags = ["no-sandbox"],\n    deps = TEST_DEPS,\n) for test, srcs in DISPLAY_TESTS.items()]'),
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
    # Upstream removed rmw_fastrtps_dynamic_cpp / rmw_fastrtps_shared_cpp (rmw_fastrtps#923); the stale RCR release
    # no longer compiles against master rmw (rmw_send_response takes a const response), so drop it from the set.
    "rmw_implementation": [
        ("BUILD.bazel",
         'config_setting(\n    name = "rmw_fastrtps_dynamic_cpp",\n'
         '    flag_values = {"@rosdistro//:rmw": "rmw_fastrtps_dynamic_cpp"},\n)\n\n', ""),
        ("BUILD.bazel", '            "@rmw_fastrtps_dynamic_cpp",\n', ""),
        ("BUILD.bazel", '            "@rmw_fastrtps_dynamic_cpp//:ament_package",\n', ""),
        ("BUILD.bazel", '        "@rmw_fastrtps_dynamic_cpp//:ament_package",\n', ""),
        ("BUILD.bazel",
         '        ":rmw_fastrtps_dynamic_cpp": "@rmw_fastrtps_dynamic_cpp//:rmw_fastrtps_dynamic_cpp_library",\n', ""),
        ("BUILD.bazel",
         '        ":rmw_fastrtps_dynamic_cpp": "@rmw_fastrtps_dynamic_cpp//:rmw_fastrtps_dynamic_cpp",\n', ""),
    ],
}

# MODULE.bazel edits: (old module dep to drop, new module deps to add), versions come from the workspace pins.
MODULE_FIXUPS = {
    "camera_info_manager_py": ([], ["ament_mypy"]),
    "rmw_implementation": (["rmw_fastrtps_dynamic_cpp"], []),
    "rosbag2_py": ([], ["rosbag2_interfaces"]),
    "rqt_bag": ([], ["std_msgs", "rosgraph_msgs"]),
    "rviz_default_plugins": ([], ["urdf", "urdf_parser_plugin"]),
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
