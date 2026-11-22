RCR's `@rosdistro//:ament_package` bundles every third-party shared library and every pip wheel of the
distribution (`THIRD_PARTY_SHARED_LIBRARIES` + `all_requirements`), and every package's `:ament_package`
depends on it. Any test that uses the ament index therefore drags in opencv, Ogre, SDL, the pip hub, etc.
This patch (applied with `single_version_override(patches = ...)`) empties both lists. On `test_ros_timer`:
configured targets 59k -> 34k, packages loaded 2179 -> 956, actions 59k -> 25k. Enable with SLIM_ROSDISTRO=1.
