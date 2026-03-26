from __future__ import annotations

import difflib
import sys
from pathlib import Path


def replace_once(text: str, old: str, new: str, path: Path) -> str:
    if old not in text:
        raise SystemExit(f"pattern not found in {path}: {old[:80]!r}")
    return text.replace(old, new, 1)


def patch_module_pom(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    if "<PLATFORM>${javacpp.platform}</PLATFORM>" in text:
        return
    old = "<EXTENSION>${javacpp.platform.extension}</EXTENSION>"
    new = """<EXTENSION>${javacpp.platform.extension}</EXTENSION>\n                <PLATFORM>${javacpp.platform}</PLATFORM>"""
    text = replace_once(text, old, new, path)
    path.write_text(text, encoding="utf-8")


def patch_build_sh(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    old = """# Allows us to use ccache with Bazel on Mac\nexport BAZEL_USE_CPP_ONLY_TOOLCHAIN=1\n\nexport BAZEL_VC=\"${VCINSTALLDIR:-}\"\nif [[ -d $BAZEL_VC ]]; then\n    # Work around compiler issues on Windows documented mainly in configure.py but also elsewhere\n    export BUILD_FLAGS=\"--copt=//arch:AVX `#--copt=//arch:AVX2` --copt=-DWIN32_LEAN_AND_MEAN --host_copt=-DWIN32_LEAN_AND_MEAN --copt=-DNOGDI --host_copt=-DNOGDI --copt=-D_USE_MATH_DEFINES --host_copt=-D_USE_MATH_DEFINES --define=override_eigen_strong_inline=true\"\n    # https://software.intel.com/en-us/articles/intel-optimization-for-tensorflow-installation-guide#wind_B_S\n    export PATH=$PATH:$(pwd)/bazel-tensorflow-core-api/external/mkl_windows/lib/\n    export PYTHON_BIN_PATH=$(which python.exe)\nelse\n    export BUILD_FLAGS=\"--copt=-msse4.1 --copt=-msse4.2 --copt=-mavx `#--copt=-mavx2 --copt=-mfma` --cxxopt=-std=c++14 --host_cxxopt=-std=c++14 --linkopt=-lstdc++ --host_linkopt=-lstdc++\"\n    export PYTHON_BIN_PATH=$(which python3)\nfi\n"""
    new = """# Allows us to use ccache with Bazel on Mac, but Android needs Bazel's Android crosstool.\nif [[ \"${PLATFORM:-}\" != \"android-arm64\" ]]; then\n    export BAZEL_USE_CPP_ONLY_TOOLCHAIN=1\nfi\n\nexport BAZEL_VC=\"${VCINSTALLDIR:-}\"\nif [[ \"${PLATFORM:-}\" == \"android-arm64\" ]]; then\n    export BUILD_FLAGS=\"--crosstool_top=@androidndk//:default_crosstool --cpu=arm64-v8a --fat_apk_cpu=arm64-v8a --host_crosstool_top=@bazel_tools//tools/cpp:toolchain --copt=-DANDROID --cxxopt=-std=c++14 --host_cxxopt=-std=c++14 --copt=-Wno-error=array-parameter --host_copt=-Wno-error=array-parameter\"\n    export PYTHON_BIN_PATH=$(which python3)\nelif [[ -d $BAZEL_VC ]]; then\n    # Work around compiler issues on Windows documented mainly in configure.py but also elsewhere\n    export BUILD_FLAGS=\"--copt=//arch:AVX `#--copt=//arch:AVX2` --copt=-DWIN32_LEAN_AND_MEAN --host_copt=-DWIN32_LEAN_AND_MEAN --copt=-DNOGDI --host_copt=-DNOGDI --copt=-D_USE_MATH_DEFINES --host_copt=-D_USE_MATH_DEFINES --define=override_eigen_strong_inline=true\"\n    # https://software.intel.com/en-us/articles/intel-optimization-for-tensorflow-installation-guide#wind_B_S\n    export PATH=$PATH:$(pwd)/bazel-tensorflow-core-api/external/mkl_windows/lib/\n    export PYTHON_BIN_PATH=$(which python.exe)\nelse\n    export BUILD_FLAGS=\"--copt=-msse4.1 --copt=-msse4.2 --copt=-mavx `#--copt=-mavx2 --copt=-mfma` --cxxopt=-std=c++14 --host_cxxopt=-std=c++14 --linkopt=-lstdc++ --host_linkopt=-lstdc++\"\n    export PYTHON_BIN_PATH=$(which python3)\nfi\n"""
    text = replace_once(text, old, new, path)
    path.write_text(text, encoding="utf-8")


def patch_preset(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    if 'value = "android-arm64"' in text:
        return
    old = """            preloadresource = "/org/bytedeco/mkldnn/",\n            resource = {"LICENSE", "THIRD_PARTY_TF_JNI_LICENSES"}\n        ),\n"""
    new = """            preloadresource = "/org/bytedeco/mkldnn/",\n            resource = {"LICENSE", "THIRD_PARTY_TF_JNI_LICENSES"}\n        ),\n        @Platform(\n            value = "android-arm64",\n            compiler = "cpp11",\n            include = {\n                "tensorflow/c/tf_attrtype.h",\n                "tensorflow/c/tf_datatype.h",\n                "tensorflow/c/tf_status.h",\n                "tensorflow/c/tf_tensor.h",\n                "tensorflow/c/c_api.h",\n//                "tensorflow/c/env.h",\n                "tensorflow/c/kernels.h",\n                "tensorflow/c/ops.h",\n                "tensorflow/c/eager/c_api.h"\n            },\n            link = "tensorflow@.2",\n            preload = {"tensorflow_framework@.2"},\n            resource = {"LICENSE", "THIRD_PARTY_TF_JNI_LICENSES"}\n        ),\n"""
    text = replace_once(text, old, new, path)
    path.write_text(text, encoding="utf-8")


def patch_workspace(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    if ':tensorflow-android-absl.patch",' not in text:
        old = '        ":tensorflow-proto.patch",\n'
        new = """        ":tensorflow-proto.patch",\n        ":tensorflow-android-absl.patch",\n"""
        text = replace_once(text, old, new, path)
    if "android_ndk_repository(" not in text and "android_sdk_repository(" not in text:
        old = 'bazel_version_repository(name = "bazel_version")\n'
        new = """bazel_version_repository(name = "bazel_version")\n\nandroid_sdk_repository(\n    name = "androidsdk",\n    api_level = 29,\n    build_tools_version = "29.0.3",\n)\n\nandroid_ndk_repository(\n    name = "androidndk",\n    api_level = 21,\n)\n"""
        text = replace_once(text, old, new, path)
    path.write_text(text, encoding="utf-8")


ORIGINAL_TENSORFLOW_ABSL_PATCH = """--- ./absl/time/internal/cctz/BUILD.bazel\t2019-09-23 13:20:52.000000000 -0700
+++ ./absl/time/internal/cctz/BUILD.bazel.fixed\t2019-09-23 13:20:48.000000000 -0700
@@ -76,15 +76,6 @@
         "include/cctz/time_zone.h",
         "include/cctz/zone_info_source.h",
     ],
-    linkopts = select({
-        ":osx": [
-            "-framework Foundation",
-        ],
-        ":ios": [
-            "-framework Foundation",
-        ],
-        "//conditions:default": [],
-    }),
     visibility = ["//visibility:public"],
     deps = [":civil_time"],
 )
--- ./absl/strings/string_view.h\t2019-09-23 13:20:52.000000000 -0700
+++ ./absl/strings/string_view.h.fixed\t2019-09-23 13:20:48.000000000 -0700
@@ -492,7 +492,14 @@
       (std::numeric_limits<difference_type>::max)();
 
   static constexpr size_type CheckLengthInternal(size_type len) {
+#if defined(__NVCC__) && (__CUDACC_VER_MAJOR__<10 || (__CUDACC_VER_MAJOR__==10 && __CUDACC_VER_MINOR__<2)) && !defined(NDEBUG)
+    // An nvcc bug treats the original return expression as a non-constant,
+    // which is not allowed in a constexpr function. This only happens when
+    // NDEBUG is not defined. This will be fixed in the CUDA 10.2 release.
+    return len;
+#else
     return ABSL_ASSERT(len <= kMaxSize), len;
+#endif
   }
 
   const char* ptr_;
"""


ANDROID_GRAPHCYCLES_PATCH_HUNK = """--- ./absl/synchronization/internal/graphcycles.cc\t2019-09-23 13:20:52.000000000 -0700
+++ ./absl/synchronization/internal/graphcycles.cc.fixed\t2019-09-23 13:20:48.000000000 -0700
@@ -35,6 +35,7 @@
 #include "absl/synchronization/internal/graphcycles.h"
 
 #include <algorithm>
 #include <array>
+#include <limits>
 #include "absl/base/internal/hide_ptr.h"
 #include "absl/base/internal/raw_logging.h"
 #include "absl/base/internal/spinlock.h"
"""


ABSL_EXTENSION_CSTDINT_PATCH_HUNK = """--- ./absl/strings/internal/str_format/extension.h\t2019-09-23 13:20:52.000000000 -0700
+++ ./absl/strings/internal/str_format/extension.h.fixed\t2019-09-23 13:20:48.000000000 -0700
@@ -17,6 +17,7 @@
 
 #include <limits.h>
+#include <cstdint>
 #include <cstddef>
 #include <cstring>
 #include <ostream>
"""


BFLOAT16_CSTDINT_PATCH = """--- a/tensorflow/core/lib/bfloat16/bfloat16.h
+++ b/tensorflow/core/lib/bfloat16/bfloat16.h
@@ -17,6 +17,7 @@
 
 #include <cmath>
 #include <complex>
+#include <cstdint>
 #include <iostream>
 
 #include "tensorflow/core/platform/byte_order.h"
"""


def write_tensorflow_android_absl_patch(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    absl_patch_text = (
        ORIGINAL_TENSORFLOW_ABSL_PATCH
        + ANDROID_GRAPHCYCLES_PATCH_HUNK
        + ABSL_EXTENSION_CSTDINT_PATCH_HUNK
    )
    text = "".join(
        difflib.unified_diff(
            ORIGINAL_TENSORFLOW_ABSL_PATCH.splitlines(keepends=True),
            absl_patch_text.splitlines(keepends=True),
            fromfile="a/third_party/com_google_absl_fix_mac_and_nvcc_build.patch",
            tofile="b/third_party/com_google_absl_fix_mac_and_nvcc_build.patch",
        )
    )
    text += BFLOAT16_CSTDINT_PATCH
    if not text.endswith("\n"):
        text += "\n"
    path.write_text(text, encoding="utf-8")


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: patch_tfjava.py <tfjava-root>")
    root = Path(sys.argv[1]).resolve()
    patch_module_pom(root / "tensorflow-core" / "tensorflow-core-api" / "pom.xml")
    patch_build_sh(root / "tensorflow-core" / "tensorflow-core-api" / "build.sh")
    patch_workspace(root / "tensorflow-core" / "tensorflow-core-api" / "WORKSPACE")
    write_tensorflow_android_absl_patch(
        root
        / "tensorflow-core"
        / "tensorflow-core-api"
        / "external"
        / "tensorflow-android-absl.patch"
    )
    patch_preset(
        root
        / "tensorflow-core"
        / "tensorflow-core-api"
        / "src"
        / "main"
        / "java"
        / "org"
        / "tensorflow"
        / "internal"
        / "c_api"
        / "presets"
        / "tensorflow.java"
    )


if __name__ == "__main__":
    main()
