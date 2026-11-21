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
