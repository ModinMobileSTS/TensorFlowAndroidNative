from __future__ import annotations

import difflib
import re
import sys
from pathlib import Path


def replace_once(text: str, old: str, new: str, path: Path) -> str:
    if old not in text:
        raise SystemExit(f"pattern not found in {path}: {old[:80]!r}")
    return text.replace(old, new, 1)


def patch_module_pom(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    if "<PLATFORM>${javacpp.platform}</PLATFORM>" in text:
        pass
    else:
        old = "<EXTENSION>${javacpp.platform.extension}</EXTENSION>"
        new = """<EXTENSION>${javacpp.platform.extension}</EXTENSION>\n                <PLATFORM>${javacpp.platform}</PLATFORM>"""
        text = replace_once(text, old, new, path)
    if "${project.basedir}/android-gnu-stl/include" not in text:
        old = """          <includePaths>\n            <includePath>${project.basedir}/</includePath>\n            <includePath>${project.basedir}/bazel-${project.artifactId}/external/org_tensorflow/</includePath>\n          </includePaths>\n"""
        new = """          <includePaths>\n            <includePath>${project.basedir}/</includePath>\n            <includePath>${project.basedir}/bazel-${project.artifactId}/external/org_tensorflow/</includePath>\n            <includePath>${project.basedir}/android-gnu-stl/include</includePath>\n            <includePath>${project.basedir}/android-gnu-stl/arm64-v8a/include</includePath>\n          </includePaths>\n"""
        text = replace_once(text, old, new, path)
    if "<linkPath>${project.basedir}/android-gnu-stl/arm64-v8a</linkPath>" not in text:
        old = """          <linkPaths>\n            <linkPath>${project.basedir}/bazel-bin/external/org_tensorflow/tensorflow/</linkPath>\n          </linkPaths>\n"""
        new = """          <linkPaths>\n            <linkPath>${project.basedir}/bazel-bin/external/org_tensorflow/tensorflow/</linkPath>\n            <linkPath>${project.basedir}/android-gnu-stl/arm64-v8a</linkPath>\n          </linkPaths>\n"""
        text = replace_once(text, old, new, path)
    path.write_text(text, encoding="utf-8")


def patch_build_sh(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    old = """# Allows us to use ccache with Bazel on Mac
export BAZEL_USE_CPP_ONLY_TOOLCHAIN=1

export BAZEL_VC="${VCINSTALLDIR:-}"
if [[ -d $BAZEL_VC ]]; then
    # Work around compiler issues on Windows documented mainly in configure.py but also elsewhere
    export BUILD_FLAGS="--copt=//arch:AVX `#--copt=//arch:AVX2` --copt=-DWIN32_LEAN_AND_MEAN --host_copt=-DWIN32_LEAN_AND_MEAN --copt=-DNOGDI --host_copt=-DNOGDI --copt=-D_USE_MATH_DEFINES --host_copt=-D_USE_MATH_DEFINES --define=override_eigen_strong_inline=true"
    # https://software.intel.com/en-us/articles/intel-optimization-for-tensorflow-installation-guide#wind_B_S
    export PATH=$PATH:$(pwd)/bazel-tensorflow-core-api/external/mkl_windows/lib/
    export PYTHON_BIN_PATH=$(which python.exe)
else
    export BUILD_FLAGS="--copt=-msse4.1 --copt=-msse4.2 --copt=-mavx `#--copt=-mavx2 --copt=-mfma` --cxxopt=-std=c++14 --host_cxxopt=-std=c++14 --linkopt=-lstdc++ --host_linkopt=-lstdc++"
    export PYTHON_BIN_PATH=$(which python3)
fi
"""
    new = """# Allows us to use ccache with Bazel on Mac, but Android needs Bazel's Android crosstool.
if [[ "${PLATFORM:-}" != "android-arm64" ]]; then
    export BAZEL_USE_CPP_ONLY_TOOLCHAIN=1
fi

export BAZEL_VC="${VCINSTALLDIR:-}"
if [[ "${PLATFORM:-}" == "android-arm64" ]]; then
    export TF_ANDROID_COMPAT_LIB_DIR="$(pwd)/android-compat-libs"
    mkdir -p "${TF_ANDROID_COMPAT_LIB_DIR}"
    printf 'INPUT(-lc)\\n' > "${TF_ANDROID_COMPAT_LIB_DIR}/libpthread.so"
    printf 'INPUT(-lc)\\n' > "${TF_ANDROID_COMPAT_LIB_DIR}/librt.so"
    # tfjava builds TensorFlow as an external Bazel repository, so TensorFlow's
    # own .bazelrc does not inject framework_shared_object=true for us.
    export BUILD_FLAGS="--config=android_arm64 --host_crosstool_top=@bazel_tools//tools/cpp:toolchain --define=framework_shared_object=true --copt=-DANDROID --copt=-DSUPPORT_SELECTIVE_REGISTRATION --cxxopt=-std=c++14 --host_cxxopt=-std=c++14 --cxxopt=-include --cxxopt=cstdint --host_cxxopt=-include --host_cxxopt=cstdint --copt=-Wno-error=array-parameter --host_copt=-Wno-error=array-parameter --copt=-Wno-error=array-bounds --host_copt=-Wno-error=array-bounds --linkopt=-L${TF_ANDROID_COMPAT_LIB_DIR} --linkopt=-llog"
    export PYTHON_BIN_PATH=$(which python3)
elif [[ -d $BAZEL_VC ]]; then
    # Work around compiler issues on Windows documented mainly in configure.py but also elsewhere
    export BUILD_FLAGS="--copt=//arch:AVX `#--copt=//arch:AVX2` --copt=-DWIN32_LEAN_AND_MEAN --host_copt=-DWIN32_LEAN_AND_MEAN --copt=-DNOGDI --host_copt=-DNOGDI --copt=-D_USE_MATH_DEFINES --host_copt=-D_USE_MATH_DEFINES --define=override_eigen_strong_inline=true"
    # https://software.intel.com/en-us/articles/intel-optimization-for-tensorflow-installation-guide#wind_B_S
    export PATH=$PATH:$(pwd)/bazel-tensorflow-core-api/external/mkl_windows/lib/
    export PYTHON_BIN_PATH=$(which python.exe)
else
    export BUILD_FLAGS="--copt=-msse4.1 --copt=-msse4.2 --copt=-mavx `#--copt=-mavx2 --copt=-mfma` --cxxopt=-std=c++14 --host_cxxopt=-std=c++14 --linkopt=-lstdc++ --host_linkopt=-lstdc++"
    export PYTHON_BIN_PATH=$(which python3)
fi

if [[ -n "${BAZEL_REPOSITORY_CACHE:-}" ]]; then
    export BUILD_FLAGS="$BUILD_FLAGS --repository_cache=${BAZEL_REPOSITORY_CACHE}"
fi
if [[ -n "${BAZEL_DISK_CACHE:-}" ]]; then
    export BUILD_FLAGS="$BUILD_FLAGS --disk_cache=${BAZEL_DISK_CACHE}"
fi
"""
    text = replace_once(text, old, new, path)

    old = """# Build C API of TensorFlow itself including a target to generate ops for Java
bazel build $BUILD_FLAGS \\
    @org_tensorflow//tensorflow:tensorflow \\
    @org_tensorflow//tensorflow/tools/lib_package:jnilicenses_generate \\
    :java_proto_gen_sources \\
    :java_op_generator \\
    :java_api_import \\
    :custom_ops_test
"""
    new = """# Build C API of TensorFlow itself. Android cross-builds reuse the checked-in
# generated Java sources because the generator is a host tool that loads the
# produced TensorFlow library at build time.
BAZEL_TARGETS=(
    @org_tensorflow//tensorflow:tensorflow
    @org_tensorflow//tensorflow/tools/lib_package:jnilicenses_generate
    :custom_ops_test
)
if [[ "${PLATFORM:-}" != "android-arm64" ]]; then
    BAZEL_TARGETS+=(
        :java_proto_gen_sources
        :java_op_generator
        :java_api_import
    )
else
    bazel build $BUILD_FLAGS --nobuild "${BAZEL_TARGETS[@]}"
    BAZEL_OUTPUT_BASE="$(bazel info $BUILD_FLAGS output_base)"
    TF_C_BUILD_FILE="$BAZEL_OUTPUT_BASE/external/org_tensorflow/tensorflow/c/BUILD"
    TF_C_BUILD_FILE="$TF_C_BUILD_FILE" python3 - <<'PY'
import os
from pathlib import Path

path = Path(os.environ["TF_C_BUILD_FILE"])
text = path.read_text(encoding="utf-8")

replacements = [
    (
        '''tf_cuda_library(
    name = "tf_status_internal",
    hdrs = [
        "tf_status.h",
        "tf_status_internal.h",
    ],
    visibility = [
        "//tensorflow/c:__subpackages__",
    ],
    deps = select({
        "//tensorflow:android": [
            "//tensorflow/core:android_tensorflow_lib_lite",
        ],
        "//conditions:default": [
            "//tensorflow/core:lib",
        ],
    }),
)''',
        '''tf_cuda_library(
    name = "tf_status_internal",
    hdrs = [
        "tf_status.h",
        "tf_status_internal.h",
    ],
    visibility = [
        "//tensorflow/c:__subpackages__",
    ],
    deps = select({
        "//tensorflow:android": [
            "//tensorflow/core:lib",
        ],
        "//conditions:default": [
            "//tensorflow/core:lib",
        ],
    }),
)''',
        "tf_status_internal",
    ),
    (
        '''cc_library(
    name = "tf_status",
    srcs = ["tf_status.cc"],
    hdrs = ["tf_status.h"],
    visibility = ["//visibility:public"],
    deps = select({
        "//tensorflow:android": [
            "//tensorflow/core:android_tensorflow_lib_lite",
        ],
        "//conditions:default": [
            ":tf_status_internal",
            "//tensorflow/core:lib",
        ],
    }),
)''',
        '''cc_library(
    name = "tf_status",
    srcs = ["tf_status.cc"],
    hdrs = ["tf_status.h"],
    visibility = ["//visibility:public"],
    deps = select({
        "//tensorflow:android": [
            ":tf_status_internal",
            "//tensorflow/core:lib",
        ],
        "//conditions:default": [
            ":tf_status_internal",
            "//tensorflow/core:lib",
        ],
    }),
)''',
        "tf_status",
    ),
    (
        '''cc_library(
    name = "tf_datatype",
    srcs = ["tf_datatype.cc"],
    hdrs = ["tf_datatype.h"],
    visibility = ["//visibility:public"],
    deps = select({
        "//tensorflow:android": [
            "//tensorflow/core:android_tensorflow_lib_lite",  # TODO(annarev): exclude runtime srcs
        ],
        "//conditions:default": [
            "//tensorflow/core:framework",
        ],
    }),
    alwayslink = 1,
)''',
        '''cc_library(
    name = "tf_datatype",
    srcs = ["tf_datatype.cc"],
    hdrs = ["tf_datatype.h"],
    visibility = ["//visibility:public"],
    deps = select({
        "//tensorflow:android": [
            "//tensorflow/core:framework",
        ],
        "//conditions:default": [
            "//tensorflow/core:framework",
        ],
    }),
    alwayslink = 1,
)''',
        "tf_datatype",
    ),
    (
        '''cc_library(
    name = "tf_tensor",
    srcs = ["tf_tensor.cc"],
    hdrs = ["tf_tensor.h"],
    visibility = ["//visibility:public"],
    deps = select({
        "//tensorflow:android": [
            "//tensorflow/core:android_tensorflow_lib_lite",
        ],
        "//conditions:default": [
            ":tf_datatype",
            ":tf_status",
            ":tf_status_helper",
            ":tf_tensor_internal",
            "//tensorflow/core:framework",
            "//tensorflow/core:lib",
            "//tensorflow/core:protos_all_cc",
        ],
    }),
)''',
        '''cc_library(
    name = "tf_tensor",
    srcs = [
        "tf_tensor.cc",
        "tf_datatype.h",
        "tf_status.h",
        "tf_status_helper.h",
        "tf_tensor_internal.h",
    ],
    hdrs = ["tf_tensor.h"],
    visibility = ["//visibility:public"],
    deps = select({
        "//tensorflow:android": [
            ":tf_datatype",
            ":tf_status",
            ":tf_status_helper",
            ":tf_tensor_internal",
            "//tensorflow/core:framework",
            "//tensorflow/core:lib",
            "//tensorflow/core:protos_all_cc",
        ],
        "//conditions:default": [
            ":tf_datatype",
            ":tf_status",
            ":tf_status_helper",
            ":tf_tensor_internal",
            "//tensorflow/core:framework",
            "//tensorflow/core:lib",
            "//tensorflow/core:protos_all_cc",
        ],
    }),
)''',
        "tf_tensor",
    ),
    (
        '''tf_cuda_library(
    name = "tf_tensor_internal",
    hdrs = [
        "tf_tensor.h",
        "tf_tensor_internal.h",
    ],
    visibility = ["//tensorflow/c:__subpackages__"],
    deps = select({
        "//tensorflow:android": [
            "//tensorflow/core:android_tensorflow_lib_lite",
        ],
        "//conditions:default": [
            ":tf_datatype",
            ":tf_status",
            "//tensorflow/core:framework",
            "//tensorflow/core:protos_all_cc",
        ],
    }),
)''',
        '''tf_cuda_library(
    name = "tf_tensor_internal",
    hdrs = [
        "tf_tensor.h",
        "tf_tensor_internal.h",
    ],
    visibility = ["//tensorflow/c:__subpackages__"],
    deps = select({
        "//tensorflow:android": [
            ":tf_datatype",
            ":tf_status",
            "//tensorflow/core:framework",
            "//tensorflow/core:protos_all_cc",
        ],
        "//conditions:default": [
            ":tf_datatype",
            ":tf_status",
            "//tensorflow/core:framework",
            "//tensorflow/core:protos_all_cc",
        ],
    }),
)''',
        "tf_tensor_internal",
    ),
]

for old, new, name in replacements:
    if old in text:
        text = text.replace(old, new, 1)
    elif new not in text:
        raise SystemExit(f"{name} android deps not found in {path}")


def replace_rule(rule_name: str, rule_kind: str, new_rule: str) -> None:
    global text
    marker = f'name = "{rule_name}"'
    marker_pos = text.find(marker)
    if marker_pos == -1:
        raise SystemExit(f"{rule_name} rule not found in {path}")
    rule_start = text.rfind(f"{rule_kind}(", 0, marker_pos)
    if rule_start == -1:
        raise SystemExit(f"{rule_name} {rule_kind} start not found in {path}")
    rule_end = text.find('\\n)\\n', marker_pos)
    if rule_end == -1:
        raise SystemExit(f"{rule_name} rule end not found in {path}")
    rule_end += 3
    rule = text[rule_start:rule_end]
    if rule != new_rule:
        text = text[:rule_start] + new_rule + text[rule_end:]


replace_rule(
    "c_api_no_xla",
    "tf_cuda_library",
    '''tf_cuda_library(
    name = "c_api_no_xla",
    srcs = [
        "c_api.cc",
        "c_api_function.cc",
        "//tensorflow/cc/saved_model:loader.h",
    ],
    hdrs = [
        "c_api.h",
    ],
    copts = tf_copts(),
    visibility = ["//tensorflow/c:__subpackages__"],
    deps = [
        ":c_api_internal",
        ":tf_attrtype",
        ":tf_datatype",
        ":tf_status_internal",
        ":tf_status",
        ":tf_tensor",
        "@com_google_absl//absl/strings",
        "//tensorflow/cc/saved_model:loader_lite",
        "//tensorflow/cc:gradients",
        "//tensorflow/cc:ops",
        "//tensorflow/cc:grad_ops",
        "//tensorflow/cc:scope_internal",
        "//tensorflow/cc:while_loop",
        "//tensorflow/core:core_cpu",
        "//tensorflow/core:core_cpu_internal",
        "//tensorflow/core:framework",
        "//tensorflow/core:op_gen_lib",
        "//tensorflow/core:protos_all_cc",
        "//tensorflow/core:lib",
        "//tensorflow/core:lib_internal",
        "//tensorflow/core/kernels:logging_ops",
    ],
    alwayslink = 1,
)''',
)

path.write_text(text, encoding="utf-8")
PY

    sed -n '/name = "tf_status_internal"/,/^)/p' "$TF_C_BUILD_FILE"
    echo '---'
    sed -n '/name = "tf_tensor"/,/^)/p' "$TF_C_BUILD_FILE"
    echo '---'
    sed -n '/name = "c_api_no_xla"/,/^)/p' "$TF_C_BUILD_FILE"
    echo '---'

    EAGER_BUILD_FILE="$BAZEL_OUTPUT_BASE/external/org_tensorflow/tensorflow/core/common_runtime/eager/BUILD"
    EAGER_BUILD_FILE="$EAGER_BUILD_FILE" python3 - <<'PY'
import os
from pathlib import Path

path = Path(os.environ["EAGER_BUILD_FILE"])
text = path.read_text(encoding="utf-8")


def patch_rule(rule_name: str, old: str, new: str) -> None:
    global text
    marker = f'name = "{rule_name}"'
    rule_start = text.find(marker)
    if rule_start == -1:
        raise SystemExit(f"{rule_name} rule not found in {path}")
    rule_end = text.find('\\n)\\n', rule_start)
    if rule_end == -1:
        raise SystemExit(f"{rule_name} rule end not found in {path}")
    rule_end += 3
    rule = text[rule_start:rule_end]
    if old in rule:
        rule = rule.replace(old, new, 1)
    elif new not in rule:
        raise SystemExit(f"{rule_name} android deps not found in {path}")
    text = text[:rule_start] + rule + text[rule_end:]


patch_rule(
    "tensor_handle_data",
    '''        "//tensorflow:android": [
            "//tensorflow/core:android_tensorflow_lib_lite",
        ],''',
    '''        "//tensorflow:android": [
            "@com_google_absl//absl/types:variant",
            "//tensorflow/core:framework",
            "//tensorflow/core:lib",
            "//tensorflow/core/profiler/lib:traceme",
        ],''',
)

patch_rule(
    "kernel_and_device",
    '''        "//tensorflow:android": [
            "//tensorflow/core:android_tensorflow_lib_lite",
        ],''',
    '''        "//tensorflow:android": [
            "//tensorflow/core:core_cpu_lib",
            "//tensorflow/core:framework",
            "//tensorflow/core:framework_internal",
            "//tensorflow/core:lib",
            "//tensorflow/core:lib_internal",
            "//tensorflow/core:protos_all_cc",
            "//tensorflow/core/profiler/lib:annotated_traceme",
            "//tensorflow/core/profiler/lib:traceme",
        ],''',
)

path.write_text(text, encoding="utf-8")
PY

    sed -n '/name = "tensor_handle_data"/,/^)/p' "$EAGER_BUILD_FILE"
    echo '---'
    sed -n '/name = "kernel_and_device"/,/^)/p' "$EAGER_BUILD_FILE"
    echo '---'

    TENSOR_HANDLE_DATA_CC="$BAZEL_OUTPUT_BASE/external/org_tensorflow/tensorflow/core/common_runtime/eager/tensor_handle_data.cc"
    TENSOR_HANDLE_DATA_CC="$TENSOR_HANDLE_DATA_CC" python3 - <<'PY'
import os
from pathlib import Path

path = Path(os.environ["TENSOR_HANDLE_DATA_CC"])
text = path.read_text(encoding="utf-8")
text = text.replace('#include "tensorflow/core/profiler/lib/traceme.h"\\n', '', 1)
old = '''    profiler::TraceMe activity(
        [caller] { return absl::StrCat(caller, " WaitReady"); },

        profiler::TraceMeLevel::kInfo);
    DVLOG(3) << "WaitReady: " << caller << " " << this;
'''
new = '''    DVLOG(3) << "WaitReady: " << caller << " " << this;
'''
if old in text:
    text = text.replace(old, new, 1)
elif '#include "tensorflow/core/profiler/lib/traceme.h"' in text:
    raise SystemExit(f"tensor_handle_data TraceMe block not found in {path}")
path.write_text(text, encoding="utf-8")
PY
fi
bazel build $BUILD_FLAGS --nofetch "${BAZEL_TARGETS[@]}"
"""
    text = replace_once(text, old, new, path)

    old = """GEN_SRCS_DIR=src/gen/java
mkdir -p $GEN_SRCS_DIR

# Generate Java operator wrappers
$BAZEL_BIN/java_op_generator \\
    --output_dir=$GEN_SRCS_DIR \\
    --api_dirs=$BAZEL_SRCS/external/org_tensorflow/tensorflow/core/api_def/base_api,src/bazel/api_def \\
    $TENSORFLOW_LIB

# Copy generated Java protos from source jars
"""
    new = """GEN_SRCS_DIR=src/gen/java
mkdir -p $GEN_SRCS_DIR

if [[ "${PLATFORM:-}" != "android-arm64" ]]; then
    # Generate Java operator wrappers
    $BAZEL_BIN/java_op_generator \\
        --output_dir=$GEN_SRCS_DIR \\
        --api_dirs=$BAZEL_SRCS/external/org_tensorflow/tensorflow/core/api_def/base_api,src/bazel/api_def \\
        $TENSORFLOW_LIB
else
    echo "Skipping Java source generation for android-arm64; reusing checked-in generated sources."
fi

# Copy generated Java protos from source jars
"""
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


LLVM_ANDROID_CONFIG_PATCH = """--- a/third_party/llvm/llvm.bzl
+++ b/third_party/llvm/llvm.bzl
@@ -248,6 +248,13 @@ linux_cmake_vars = {
     "HAVE_FUTIMENS": 1,
 }
 
+android_cmake_vars = {
+    "HAVE_BACKTRACE": 0,
+    "HAVE_EXECINFO_H": 0,
+    "HAVE_LIBPTHREAD": 0,
+    "HAVE__UNWIND_BACKTRACE": 0,
+}
+
 # CMake variables specific to the FreeBSD platform
 freebsd_cmake_vars = {
     "HAVE_MALLOC_H": 1,
@@ -311,6 +319,14 @@ llvm_all_cmake_vars = select({
             darwin_cmake_vars,
         ),
     ),
+    "@org_tensorflow//tensorflow:android": cmake_var_string(
+        _dict_add(
+            cmake_vars,
+            llvm_target_cmake_vars("AArch64", "aarch64-unknown-linux-android"),
+            posix_cmake_vars,
+            android_cmake_vars,
+        ),
+    ),
     "@org_tensorflow//tensorflow:linux_ppc64le": cmake_var_string(
         _dict_add(
             cmake_vars,
@@ -344,6 +360,7 @@ llvm_all_cmake_vars = select({
 
 llvm_linkopts = select({
     "@org_tensorflow//tensorflow:windows": [],
+    "@org_tensorflow//tensorflow:android": ["-ldl", "-lm"],
     "@org_tensorflow//tensorflow:freebsd": ["-ldl", "-lm", "-lpthread", "-lexecinfo"],
     "//conditions:default": ["-ldl", "-lm", "-lpthread"],
 })
"""


TFE_C_API_ANDROID_DEPS_PATCH = """--- a/tensorflow/c/eager/BUILD
+++ b/tensorflow/c/eager/BUILD
@@ -37,7 +37,28 @@ tf_cuda_library(
     visibility = ["//visibility:public"],
     deps = select({
-        "//tensorflow:android": [
-            "//tensorflow/core:android_tensorflow_lib_lite",
-        ],
+        "//tensorflow:android": [
+            "@com_google_absl//absl/algorithm:container",
+            "@com_google_absl//absl/container:fixed_array",
+            "//tensorflow/c:c_api",
+            "//tensorflow/c:c_api_internal",
+            "//tensorflow/c:tf_tensor_internal",
+            "//tensorflow/core:core_cpu",
+            "//tensorflow/core/common_runtime/eager:attr_builder",
+            "//tensorflow/core/common_runtime/eager:context",
+            "//tensorflow/core/common_runtime/eager:eager_executor",
+            "//tensorflow/core/common_runtime/eager:execute",
+            "//tensorflow/core/common_runtime/eager:kernel_and_device",
+            "//tensorflow/core/common_runtime/eager:tensor_handle",
+            "//tensorflow/core/common_runtime/eager:copy_to_device_node",
+            "//tensorflow/core:core_cpu_internal",
+            "//tensorflow/core:framework",
+            "//tensorflow/core:framework_internal",
+            "//tensorflow/core:lib",
+            "//tensorflow/core:lib_internal",
+            "//tensorflow/core/platform:casts",
+            "//tensorflow/core/platform:errors",
+            "//tensorflow/core:protos_all_cc",
+            "//tensorflow/core/profiler/lib:traceme",
+        ],
         "//conditions:default": [
             "@com_google_absl//absl/algorithm:container",
             "@com_google_absl//absl/container:fixed_array",
@@ -73,20 +94,24 @@ tf_cuda_library(
     }) + [
         "@com_google_absl//absl/memory",
         "//tensorflow/core/common_runtime/eager:eager_operation",
-        "//tensorflow/core/distributed_runtime/eager:remote_mgr",
-        "//tensorflow/core/distributed_runtime/eager:cluster_function_library_runtime",
-        "//tensorflow/core/distributed_runtime/eager:eager_client",
-        "//tensorflow/core/distributed_runtime/rpc/eager:grpc_eager_client",
-        "//tensorflow/core/distributed_runtime/rpc:grpc_channel",
-        "//tensorflow/core/distributed_runtime/rpc:grpc_server_lib",
-        "//tensorflow/core/distributed_runtime/rpc:grpc_worker_cache",
-        "//tensorflow/core/distributed_runtime/rpc:grpc_worker_service",
-        "//tensorflow/core/distributed_runtime/rpc:rpc_rendezvous_mgr",
-        "//tensorflow/core/distributed_runtime:remote_device",
-        "//tensorflow/core/distributed_runtime:server_lib",
-        "//tensorflow/core/distributed_runtime:worker_env",
         "//tensorflow/core:gpu_runtime",
-    ],
+    ] + select({
+        "//tensorflow:android": [],
+        "//conditions:default": [
+            "//tensorflow/core/distributed_runtime/eager:remote_mgr",
+            "//tensorflow/core/distributed_runtime/eager:cluster_function_library_runtime",
+            "//tensorflow/core/distributed_runtime/eager:eager_client",
+            "//tensorflow/core/distributed_runtime/rpc/eager:grpc_eager_client",
+            "//tensorflow/core/distributed_runtime/rpc:grpc_channel",
+            "//tensorflow/core/distributed_runtime/rpc:grpc_server_lib",
+            "//tensorflow/core/distributed_runtime/rpc:grpc_worker_cache",
+            "//tensorflow/core/distributed_runtime/rpc:grpc_worker_service",
+            "//tensorflow/core/distributed_runtime/rpc:rpc_rendezvous_mgr",
+            "//tensorflow/core/distributed_runtime:remote_device",
+            "//tensorflow/core/distributed_runtime:server_lib",
+            "//tensorflow/core/distributed_runtime:worker_env",
+        ],
+    }),
     alwayslink = 1,
 )
 
@@ -221,7 +246,24 @@ tf_cuda_library(
     visibility = ["//visibility:public"],
     deps = select({
-        "//tensorflow:android": [
-            "//tensorflow/core:android_tensorflow_lib_lite",
-        ],
+        "//tensorflow:android": [
+            ":c_api",
+            ":c_api_internal",
+            "//tensorflow/c:c_api",
+            "//tensorflow/c:c_api_internal",
+            "//tensorflow/core:core_cpu",
+            "//tensorflow/core/common_runtime/eager:attr_builder",
+            "//tensorflow/core/common_runtime/eager:context",
+            "//tensorflow/core/common_runtime/eager:eager_executor",
+            "//tensorflow/core/common_runtime/eager:execute",
+            "//tensorflow/core/common_runtime/eager:kernel_and_device",
+            "//tensorflow/core/common_runtime/eager:tensor_handle",
+            "//tensorflow/core/common_runtime/eager:copy_to_device_node",
+            "//tensorflow/core:core_cpu_internal",
+            "//tensorflow/core:framework",
+            "//tensorflow/core:framework_internal",
+            "//tensorflow/core:lib",
+            "//tensorflow/core:lib_internal",
+            "//tensorflow/core:protos_all_cc",
+        ],
         "//conditions:default": [
             ":c_api",
             ":c_api_internal",
@@ -254,18 +296,22 @@ tf_cuda_library(
         "@com_google_absl//absl/memory",
         "//tensorflow/c:tf_status_helper",
         "//tensorflow/core/common_runtime/eager:eager_operation",
-        "//tensorflow/core/distributed_runtime/eager:eager_client",
-        "//tensorflow/core/distributed_runtime/rpc/eager:grpc_eager_client",
-        "//tensorflow/core/distributed_runtime/rpc:grpc_channel",
-        "//tensorflow/core/distributed_runtime/rpc:grpc_server_lib",
-        "//tensorflow/core/distributed_runtime/rpc:grpc_worker_cache",
-        "//tensorflow/core/distributed_runtime/rpc:grpc_worker_service",
-        "//tensorflow/core/distributed_runtime/rpc:rpc_rendezvous_mgr",
-        "//tensorflow/core/distributed_runtime:remote_device",
-        "//tensorflow/core/distributed_runtime:server_lib",
-        "//tensorflow/core/distributed_runtime:worker_env",
         "//tensorflow/core:gpu_runtime",
-    ],
+    ] + select({
+        "//tensorflow:android": [],
+        "//conditions:default": [
+            "//tensorflow/core/distributed_runtime/eager:eager_client",
+            "//tensorflow/core/distributed_runtime/rpc/eager:grpc_eager_client",
+            "//tensorflow/core/distributed_runtime/rpc:grpc_channel",
+            "//tensorflow/core/distributed_runtime/rpc:grpc_server_lib",
+            "//tensorflow/core/distributed_runtime/rpc:grpc_worker_cache",
+            "//tensorflow/core/distributed_runtime/rpc:grpc_worker_service",
+            "//tensorflow/core/distributed_runtime/rpc:rpc_rendezvous_mgr",
+            "//tensorflow/core/distributed_runtime:remote_device",
+            "//tensorflow/core/distributed_runtime:server_lib",
+            "//tensorflow/core/distributed_runtime:worker_env",
+        ],
+    }),
     alwayslink = 1,
 )
 
"""


EAGER_CONTEXT_ANDROID_DEPS_PATCH = """--- a/tensorflow/core/common_runtime/eager/BUILD
+++ b/tensorflow/core/common_runtime/eager/BUILD
@@ -29,7 +29,12 @@ tf_cuda_library(
     visibility = ["//tensorflow:internal"],
     deps = select({
-        "//tensorflow:android": [
-            "//tensorflow/core:android_tensorflow_lib_lite",
-        ],
+        "//tensorflow:android": [
+            "//tensorflow/core:core_cpu_lib",
+            "//tensorflow/core:framework",
+            "//tensorflow/core:framework_internal",
+            "//tensorflow/core:lib",
+            "//tensorflow/core:lib_internal",
+            "//tensorflow/core:protos_all_cc",
+        ],
         "//conditions:default": [
             "//tensorflow/core:core_cpu_lib",
             "//tensorflow/core:framework",
@@ -55,14 +60,20 @@ tf_cuda_library(
         ":eager_executor",
         ":kernel_and_device",
         ":process_function_library_runtime",
-        "//tensorflow/core/distributed_runtime/eager:remote_tensor_handle",
-        "//tensorflow/core/distributed_runtime:rendezvous_mgr_interface",
-        "//tensorflow/core/distributed_runtime:worker_env",
     ] + select({
         "//tensorflow:android": [
-            "//tensorflow/core:android_tensorflow_lib_lite",
+            "//tensorflow/core:core_cpu_lib",
+            "//tensorflow/core:framework",
+            "//tensorflow/core:framework_internal",
+            "//tensorflow/core:lib",
+            "//tensorflow/core:lib_internal",
+            "//tensorflow/core:protos_all_cc",
+            "//tensorflow/core:session_options",
         ],
         "//conditions:default": [
+            "//tensorflow/core/distributed_runtime/eager:remote_tensor_handle",
+            "//tensorflow/core/distributed_runtime:rendezvous_mgr_interface",
+            "//tensorflow/core/distributed_runtime:worker_env",
             "//tensorflow/core:core_cpu_lib",
             "//tensorflow/core:framework",
             "//tensorflow/core:framework_internal",
@@ -115,7 +126,7 @@ tf_cuda_library(
         "//tensorflow/core/platform:platform_port",
     ] + select({
-        "//tensorflow:android": [
-            "//tensorflow/core:android_tensorflow_lib_lite",
-        ],
+        "//tensorflow:android": [
+            "//tensorflow/core:core_cpu_lib",
+        ],
         "//conditions:default": [
             "//tensorflow/core:core_cpu_lib",
         ],
@@ -137,7 +148,10 @@ tf_cuda_library(
         ":eager_executor",
     ] + select({
-        "//tensorflow:android": [
-            "//tensorflow/core:android_tensorflow_lib_lite",
-        ],
+        "//tensorflow:android": [
+            "@com_google_absl//absl/types:variant",
+            "//tensorflow/core:framework",
+            "//tensorflow/core:lib",
+            "//tensorflow/core/profiler/lib:traceme",
+        ],
         "//conditions:default": [
             "@com_google_absl//absl/types:variant",
             "//tensorflow/core:framework",
@@ -164,7 +178,16 @@ tf_cuda_library(
         ":tensor_handle_data",
     ] + select({
-        "//tensorflow:android": [
-            "//tensorflow/core:android_tensorflow_lib_lite",
-        ],
+        "//tensorflow:android": [
+            "@com_google_absl//absl/strings",
+            "@com_google_absl//absl/types:variant",
+            "//tensorflow/core:core_cpu_lib",
+            "//tensorflow/core:framework",
+            "//tensorflow/core:framework_internal",
+            "//tensorflow/core:lib",
+            "//tensorflow/core:lib_internal",
+            "//tensorflow/core:protos_all_cc",
+            "//tensorflow/core:session_options",
+            "//tensorflow/core/profiler/lib:traceme",
+        ],
         "//conditions:default": [
             "@com_google_absl//absl/strings",
             "@com_google_absl//absl/types:variant",
@@ -265,7 +288,7 @@ tf_cuda_library(
         "@farmhash_archive//:farmhash",
     ] + select({
-        "//tensorflow:android": [
-            "//tensorflow/core:android_tensorflow_lib_lite",
-        ],
+        "//tensorflow:android": [
+            KERNEL_AND_DEVICE_DEPS,
+        ],
         "//tensorflow:windows": KERNEL_AND_DEVICE_DEPS,
         "//conditions:default": KERNEL_AND_DEVICE_DEPS + [
             "//tensorflow/compiler/jit:xla_kernel_creator_util",
@@ -285,7 +308,12 @@ tf_cuda_library(
     visibility = ["//tensorflow:internal"],
     deps = select({
-        "//tensorflow:android": [
-            "//tensorflow/core:android_tensorflow_lib_lite",
-        ],
+        "//tensorflow:android": [
+            "@com_google_absl//absl/types:optional",
+            "//tensorflow/core:core_cpu_lib",
+            "//tensorflow/core:framework",
+            "//tensorflow/core:lib",
+            "//tensorflow/core:lib_internal",
+            "//tensorflow/core:protos_all_cc",
+        ],
         "//conditions:default": [
             "@com_google_absl//absl/types:optional",
             "//tensorflow/core:core_cpu_lib",
@@ -357,7 +385,12 @@ cc_library(
         "//tensorflow/core/profiler/lib:traceme",
     ] + select({
-        "//tensorflow:android": [
-            "//tensorflow/core:android_tensorflow_lib_lite",
-        ],
+        "//tensorflow:android": [
+            "//tensorflow/core:core_cpu_lib",
+            "//tensorflow/core:framework",
+            "//tensorflow/core:framework_internal",
+            "//tensorflow/core:lib",
+            "//tensorflow/core:lib_internal",
+            "//tensorflow/core:protos_all_cc",
+        ],
         "//conditions:default": [
             "//tensorflow/core/distributed_runtime/eager:remote_mgr",
             "//tensorflow/core:core_cpu_lib",
@@ -434,7 +467,13 @@ tf_cuda_library(
         "@farmhash_archive//:farmhash",
     ] + select({
-        "//tensorflow:android": [
-            "//tensorflow/core:android_tensorflow_lib_lite",
-        ],
+        "//tensorflow:android": [
+            "//tensorflow/core:core_cpu",
+            "//tensorflow/core:core_cpu_internal",
+            "//tensorflow/core:framework",
+            "//tensorflow/core:framework_internal",
+            "//tensorflow/core:lib",
+            "//tensorflow/core:lib_internal",
+            "//tensorflow/core:protos_all_cc",
+        ],
         "//conditions:default": [
             "//tensorflow/core:core_cpu",
             "//tensorflow/core:core_cpu_internal",
"""


TF_C_BUILD_ANDROID_FULL_DEPS_PATCH = """--- a/tensorflow/c/BUILD
+++ b/tensorflow/c/BUILD
@@ -82,7 +82,12 @@ tf_cuda_library(
     ],
     deps = select({
-        "//tensorflow:android": [
-            "//tensorflow/core:android_tensorflow_lib_lite",
-        ],
+        "//tensorflow:android": [
+            ":tf_attrtype",
+            "//tensorflow/core:core_cpu",
+            "//tensorflow/core:framework",
+            "//tensorflow/core:lib",
+            "//tensorflow/core/platform:platform",
+            "//tensorflow/core:op_gen_lib",
+        ],
         "//conditions:default": [
             ":tf_attrtype",
             "//tensorflow/core:core_cpu",
@@ -149,10 +154,15 @@ tf_cuda_library(
     srcs = [
         "c_api.cc",
         "c_api_function.cc",
-    ],
+    ] + select({
+        "//tensorflow:android": ["//tensorflow/cc/saved_model:loader.h"],
+        "//conditions:default": [],
+    }),
     hdrs = [
         "c_api.h",
     ],
     copts = tf_copts(),
     visibility = ["//tensorflow/c:__subpackages__"],
@@ -162,7 +167,23 @@ tf_cuda_library(
         ":tf_status_internal",
     ] + select({
-        "//tensorflow:android": [
-            "//tensorflow/core:android_tensorflow_lib_lite",
-        ],
+        "//tensorflow:android": [
+            ":tf_status",
+            ":tf_tensor",
+            "@com_google_absl//absl/strings",
+            "//tensorflow/cc/saved_model:loader_lite",
+            "//tensorflow/cc:gradients",
+            "//tensorflow/cc:ops",
+            "//tensorflow/cc:grad_ops",
+            "//tensorflow/cc:scope_internal",
+            "//tensorflow/cc:while_loop",
+            "//tensorflow/core:core_cpu",
+            "//tensorflow/core:core_cpu_internal",
+            "//tensorflow/core:framework",
+            "//tensorflow/core:op_gen_lib",
+            "//tensorflow/core:protos_all_cc",
+            "//tensorflow/core:lib",
+            "//tensorflow/core:lib_internal",
+            "//tensorflow/core/kernels:logging_ops",
+        ],
         "//conditions:default": [
             ":tf_status",
             ":tf_tensor",
@@ -199,7 +220,7 @@ tf_cuda_library(
     ],
     deps = select({
-        "//tensorflow:android": [
-            "//tensorflow/core:android_tensorflow_lib_lite",
-        ],
+        "//tensorflow:android": [
+            "//tensorflow/core:lib",
+        ],
         "//conditions:default": [
             "//tensorflow/core:lib",
         ],
@@ -214,7 +235,8 @@ cc_library(
     visibility = ["//visibility:public"],
     deps = select({
-        "//tensorflow:android": [
-            "//tensorflow/core:android_tensorflow_lib_lite",
-        ],
+        "//tensorflow:android": [
+            ":tf_status_internal",
+            "//tensorflow/core:lib",
+        ],
         "//conditions:default": [
             ":tf_status_internal",
             "//tensorflow/core:lib",
@@ -242,7 +264,7 @@ cc_library(
     visibility = ["//visibility:public"],
     deps = select({
-        "//tensorflow:android": [
-            "//tensorflow/core:android_tensorflow_lib_lite",  # TODO(annarev): exclude runtime srcs
-        ],
+        "//tensorflow:android": [
+            "//tensorflow/core:framework",
+        ],
         "//conditions:default": [
             "//tensorflow/core:framework",
         ],
@@ -253,7 +253,13 @@
 
 cc_library(
     name = "tf_tensor",
-    srcs = ["tf_tensor.cc"],
+    srcs = [
+        "tf_tensor.cc",
+        "tf_datatype.h",
+        "tf_status.h",
+        "tf_status_helper.h",
+        "tf_tensor_internal.h",
+    ],
     hdrs = ["tf_tensor.h"],
     visibility = ["//visibility:public"],
     deps = select({
@@ -258,7 +280,13 @@ cc_library(
     visibility = ["//visibility:public"],
     deps = select({
-        "//tensorflow:android": [
-            "//tensorflow/core:android_tensorflow_lib_lite",
-        ],
+        "//tensorflow:android": [
+            ":tf_datatype",
+            ":tf_status",
+            ":tf_status_helper",
+            ":tf_tensor_internal",
+            "//tensorflow/core:framework",
+            "//tensorflow/core:lib",
+            "//tensorflow/core:protos_all_cc",
+        ],
         "//conditions:default": [
             ":tf_datatype",
             ":tf_status",
@@ -281,7 +309,10 @@ tf_cuda_library(
     visibility = ["//tensorflow/c:__subpackages__"],
     deps = select({
-        "//tensorflow:android": [
-            "//tensorflow/core:android_tensorflow_lib_lite",
-        ],
+        "//tensorflow:android": [
+            ":tf_datatype",
+            ":tf_status",
+            "//tensorflow/core:framework",
+            "//tensorflow/core:protos_all_cc",
+        ],
         "//conditions:default": [
             ":tf_datatype",
             ":tf_status",
@@ -387,7 +422,7 @@ tf_cuda_library(
     visibility = ["//visibility:public"],
     deps = select({
-        "//tensorflow:android": [
-            "//tensorflow/core:android_tensorflow_lib_lite",
-        ],
+        "//tensorflow:android": [
+            "//tensorflow/core:framework",
+        ],
         "//conditions:default": [
             "//tensorflow/core:framework",
         ],
@@ -418,7 +453,9 @@ tf_cuda_library(
     ] + select({
         "//tensorflow:android": [
             ":c_api_internal",
-            "//tensorflow/core:android_tensorflow_lib_lite",
+            ":tf_tensor",
+            "//tensorflow/core:framework",
+            "//tensorflow/core:framework_lite",
         ],
         "//conditions:default": [
             ":c_api_internal",
@@ -445,7 +482,7 @@ tf_cuda_library(
         ":tf_status_helper",
     ] + select({
-        "//tensorflow:android": [
-            "//tensorflow/core:android_tensorflow_lib_lite",
-        ],
+        "//tensorflow:android": [
+            "//tensorflow/core:framework",
+        ],
         "//conditions:default": [
             "//tensorflow/core:framework",
         ],
"""


DISTRIBUTED_EAGER_ANDROID_PATCH = """--- a/tensorflow/core/distributed_runtime/eager/BUILD
+++ b/tensorflow/core/distributed_runtime/eager/BUILD
@@ -23,9 +23,12 @@ cc_library(

 cc_library(
     name = "cluster_function_library_runtime",
-    srcs = [
-        "cluster_function_library_runtime.cc",
-    ],
+    srcs = select({
+        "//tensorflow:android": [],
+        "//conditions:default": [
+            "cluster_function_library_runtime.cc",
+        ],
+    }),
     hdrs = [
         "cluster_function_library_runtime.h",
     ],
@@ -71,7 +74,10 @@ cc_library(

 cc_library(
     name = "remote_execute_node",
-    srcs = ["remote_execute_node.cc"],
+    srcs = select({
+        "//tensorflow:android": [],
+        "//conditions:default": ["remote_execute_node.cc"],
+    }),
     hdrs = ["remote_execute_node.h"],
     deps = [
         ":eager_client",
@@ -90,7 +96,10 @@ cc_library(

 cc_library(
     name = "eager_service_impl",
-    srcs = ["eager_service_impl.cc"],
+    srcs = select({
+        "//tensorflow:android": [],
+        "//conditions:default": ["eager_service_impl.cc"],
+    }),
     hdrs = [
         "eager_service_impl.h",
     ],
@@ -154,9 +163,12 @@ tf_cc_test(

 cc_library(
     name = "remote_mgr",
-    srcs = [
-        "remote_mgr.cc",
-    ],
+    srcs = select({
+        "//tensorflow:android": [],
+        "//conditions:default": [
+            "remote_mgr.cc",
+        ],
+    }),
     hdrs = [
         "remote_mgr.h",
     ],
@@ -185,7 +197,10 @@ tf_cc_test(

 cc_library(
     name = "remote_tensor_handle_data",
-    srcs = ["remote_tensor_handle_data.cc"],
+    srcs = select({
+        "//tensorflow:android": [],
+        "//conditions:default": ["remote_tensor_handle_data.cc"],
+    }),
     hdrs = ["remote_tensor_handle_data.h"],
     deps = [
         ":destroy_tensor_handle_node",
@@ -199,9 +214,12 @@ cc_library(

 cc_library(
     name = "remote_copy_node",
-    srcs = [
-        "remote_copy_node.cc",
-    ],
+    srcs = select({
+        "//tensorflow:android": [],
+        "//conditions:default": [
+            "remote_copy_node.cc",
+        ],
+    }),
     hdrs = [
         "remote_copy_node.h",
     ],
"""


GRPC_SERVER_LIB_ANDROID_BUILD_PATCH = """--- a/tensorflow/core/distributed_runtime/rpc/BUILD
+++ b/tensorflow/core/distributed_runtime/rpc/BUILD
@@ -312,8 +312,12 @@
         "//tensorflow/core/distributed_runtime:session_mgr",
         "//tensorflow/core/distributed_runtime:worker_cache_wrapper",
         "//tensorflow/core/distributed_runtime:worker_env",
-        "//tensorflow/core/distributed_runtime/rpc/eager:grpc_eager_service_impl",
-    ],
+    ] + select({
+        "//tensorflow:android": [],
+        "//conditions:default": [
+            "//tensorflow/core/distributed_runtime/rpc/eager:grpc_eager_service_impl",
+        ],
+    }),
     alwayslink = 1,
 )
 
"""


GRPC_SERVER_LIB_ANDROID_CC_PATCH = """--- a/tensorflow/core/distributed_runtime/rpc/grpc_server_lib.cc
+++ b/tensorflow/core/distributed_runtime/rpc/grpc_server_lib.cc
@@ -34,7 +34,9 @@
 #include "tensorflow/core/distributed_runtime/master_env.h"
 #include "tensorflow/core/distributed_runtime/master_session.h"
 #include "tensorflow/core/distributed_runtime/rpc/async_service_interface.h"
+#if !defined(IS_MOBILE_PLATFORM)
 #include "tensorflow/core/distributed_runtime/rpc/eager/grpc_eager_service_impl.h"
+#endif  // !defined(IS_MOBILE_PLATFORM)
 #include "tensorflow/core/distributed_runtime/rpc/grpc_channel.h"
 #include "tensorflow/core/distributed_runtime/rpc/grpc_master_service.h"
 #include "tensorflow/core/distributed_runtime/rpc/grpc_worker_cache.h"
@@ -231,7 +233,9 @@
   worker_service_ = NewGrpcWorkerService(worker_impl_.get(), &builder,
                                          opts.worker_service_options)
                         .release();
+#if !defined(IS_MOBILE_PLATFORM)
   eager_service_ = new eager::GrpcEagerServiceImpl(&worker_env_, &builder);
+#endif  // !defined(IS_MOBILE_PLATFORM)
 
   // extra service:
   if (opts.service_func != nullptr) {
@@ -383,9 +387,11 @@
       worker_thread_.reset(
           env_->StartThread(ThreadOptions(), "TF_worker_service",
                             [this] { worker_service_->HandleRPCsLoop(); }));
+#if !defined(IS_MOBILE_PLATFORM)
       eager_thread_.reset(
           env_->StartThread(ThreadOptions(), "TF_eager_service",
                             [this] { eager_service_->HandleRPCsLoop(); }));
+#endif  // !defined(IS_MOBILE_PLATFORM)
       state_ = STARTED;
       LOG(INFO) << "Started server with target: " << target();
       return Status::OK();
@@ -402,9 +408,14 @@
 
 Status GrpcServer::AddMasterEagerContextToEagerService(
     const tensorflow::uint64 context_id, tensorflow::EagerContext* context) {
+#if defined(IS_MOBILE_PLATFORM)
+  return errors::Unimplemented(
+      "GRPC eager service is not supported on mobile builds.");
+#else
   auto* eager_service =
       static_cast<eager::GrpcEagerServiceImpl*>(eager_service_);
   return eager_service->CreateMasterContext(context_id, context);
+#endif  // defined(IS_MOBILE_PLATFORM)
 }
 
 Status GrpcServer::UpdateServerDef(const ServerDef& server_def) {
"""


TF_C_API_EXPERIMENTAL_BUILD_PATCH = """--- a/tensorflow/c/BUILD
+++ b/tensorflow/c/BUILD
@@ -315,10 +315,14 @@
         "//tensorflow/core:protos_all_cc",
         "//tensorflow/core/common_runtime/eager:attr_builder",
         "//tensorflow/core/common_runtime/eager:context",
-        "//tensorflow/core/distributed_runtime/rpc:grpc_server_lib",
         "//tensorflow/core/platform",
         "@com_google_absl//absl/strings",
-    ],
+    ] + select({
+        "//tensorflow:android": [],
+        "//conditions:default": [
+            "//tensorflow/core/distributed_runtime/rpc:grpc_server_lib",
+        ],
+    }),
     alwayslink = 1,
 )
 
"""


TF_C_API_EXPERIMENTAL_CC_PATCH = """--- a/tensorflow/c/c_api_experimental.cc
+++ b/tensorflow/c/c_api_experimental.cc
@@ -24,7 +24,10 @@
 #include "tensorflow/compiler/jit/flags.h"
 #include "tensorflow/core/common_runtime/eager/attr_builder.h"
 #include "tensorflow/core/common_runtime/eager/context.h"
+#include "tensorflow/core/platform/platform.h"
+#if !defined(IS_MOBILE_PLATFORM)
 #include "tensorflow/core/distributed_runtime/rpc/grpc_server_lib.h"
+#endif  // !IS_MOBILE_PLATFORM
 #include "tensorflow/core/framework/node_def.pb.h"
 #include "tensorflow/core/framework/shape_inference.h"
 #include "tensorflow/core/framework/tensor.pb.h"
@@ -687,6 +690,7 @@
 }
 
 namespace {
+#if !defined(IS_MOBILE_PLATFORM)
 tensorflow::Status EnableCollectiveOps(const tensorflow::ServerDef& server_def,
                                        TFE_Context* ctx) {
   // We don't use the TF_RETURN_IF_ERROR macro directly since that destroys the
@@ -728,6 +732,14 @@
   return tensorflow::Status::OK();
 #undef LOG_AND_RETURN_IF_ERROR
 }
+#else
+
+tensorflow::Status EnableCollectiveOps(const tensorflow::ServerDef& server_def,
+                                       TFE_Context* ctx) {
+  return tensorflow::errors::Unimplemented(
+      "TFE_EnableCollectiveOps is not supported on mobile builds.");
+}
+#endif  // !IS_MOBILE_PLATFORM
 }  // namespace
 
 // Set server_def on the context, possibly updating it.
"""


TF_C_API_SAVED_MODEL_INCLUDE_PATCH = """--- a/tensorflow/c/c_api.cc
+++ b/tensorflow/c/c_api.cc
@@ -29,11 +29,13 @@ limitations under the License.
 #include "tensorflow/cc/framework/ops.h"
 #include "tensorflow/cc/framework/scope_internal.h"
 #include "tensorflow/cc/ops/while_loop.h"
-#include "tensorflow/cc/saved_model/loader.h"
 #include "tensorflow/core/distributed_runtime/server_lib.h"
 #include "tensorflow/core/framework/logging.h"
 #include "tensorflow/core/framework/op_gen_lib.h"
 #endif  // !defined(IS_MOBILE_PLATFORM) && !defined(IS_SLIM_BUILD)
+#if !defined(IS_SLIM_BUILD)
+#include "tensorflow/cc/saved_model/loader.h"
+#endif  // !defined(IS_SLIM_BUILD)
 #include "tensorflow/c/c_api_internal.h"
 #include "tensorflow/c/tf_status_internal.h"
 #include "tensorflow/c/tf_tensor.h"
"""


TF_C_API_SAVED_MODEL_ANDROID_PATCH = """--- a/tensorflow/c/c_api.cc
+++ b/tensorflow/c/c_api.cc
@@ -2189,11 +2189,11 @@
     TF_Graph* graph, TF_Buffer* meta_graph_def, TF_Status* status) {
 // TODO(sjr): Remove the IS_MOBILE_PLATFORM guard. This will require ensuring
 // that the tensorflow/cc/saved_model:loader build target is mobile friendly.
-#if defined(IS_MOBILE_PLATFORM) || defined(IS_SLIM_BUILD)
+#if defined(IS_SLIM_BUILD)
   status->status = tensorflow::errors::Unimplemented(
       "Loading a SavedModel is not supported on mobile. File a bug at "
       "https://github.com/tensorflow/tensorflow/issues if this feature is "
       "important to you");
   return nullptr;
 #else
   mutex_lock l(graph->mu);
"""


# Keep upstream SavedModel loader wiring on Android so the C API can resolve
# TF_LoadSessionFromSavedModel() once the mobile guard above is removed.
SAVED_MODEL_ANDROID_LOADER_PATCH = """--- a/tensorflow/cc/saved_model/BUILD
+++ b/tensorflow/cc/saved_model/BUILD
@@ -44,13 +44,12 @@ cc_library(
     name = "reader",
     srcs = ["reader.cc"],
     hdrs = ["reader.h"],
-    deps = [":constants"] + if_not_mobile([
-        # TODO(b/111634734): :lib and :protos_all contain dependencies that
-        # cannot be built on mobile platforms. Instead, include the appropriate
-        # tf_lib depending on the build platform.
+    deps = [
+        ":constants",
+        # Android JNI build needs the full loader graph available here.
         "//tensorflow/core:lib",
         "//tensorflow/core:protos_all_cc",
-    ]),
+    ],
 )
 
 tf_cc_test(
@@ -94,11 +93,11 @@ cc_library(
     hdrs = ["loader.h"],
     deps = if_static([
         ":loader_lite_impl",
-    ]) + if_not_mobile([
+    ]) + [
         "//tensorflow/core:core_cpu",
         "//tensorflow/core:lib",
         "//tensorflow/core:protos_all_cc",
-    ]),
+    ],
 )
 
 cc_library(
@@ -108,14 +107,13 @@ cc_library(
     deps = [
         ":constants",
         ":reader",
-    ] + if_not_mobile([
         "//tensorflow/core:core_cpu",
         "//tensorflow/core:framework",
         "//tensorflow/core:lib",
         "//tensorflow/core:lib_internal",
         "//tensorflow/core:protos_all_cc",
         "//tensorflow/core/util/tensor_bundle:naming",
-    ]),
+    ],
     alwayslink = 1,
 )
 
"""


# Keep upstream tensorflow_framework deps on Android so loader_lite_impl stays
# bundled into libtensorflow_framework.so.
TENSORFLOW_FRAMEWORK_ANDROID_PATCH = ""


ANDROID_PORTABLE_LIB_SHIM_PATCH = """--- a/tensorflow/core/BUILD
+++ b/tensorflow/core/BUILD
@@ -1399,18 +1399,34 @@
 )
 
-alias(
+cc_library(
     name = "android_tensorflow_lib_lite",
-    actual = ":portable_tensorflow_lib_lite",
+    deps = if_android([
+        ":core_cpu",
+        ":core_cpu_internal",
+        ":framework",
+        ":framework_internal",
+        ":lib",
+        ":lib_internal",
+        ":protos_all_cc",
+    ]) + select({
+        "//tensorflow:android": [],
+        "//conditions:default": [
+            ":portable_tensorflow_lib_lite",
+        ],
+    }),
     visibility = ["//visibility:public"],
+    alwayslink = 1,
 )
 
 alias(
     name = "android_tensorflow_lib_lite_nortti",
-    actual = ":portable_tensorflow_lib_lite",
+    actual = ":android_tensorflow_lib_lite",
     visibility = ["//visibility:public"],
 )
 
 alias(
     name = "android_tensorflow_lib_lite_nortti_lite_protos",
-    actual = ":portable_tensorflow_lib_lite",
+    actual = ":android_tensorflow_lib_lite",
     visibility = ["//visibility:public"],
 )
@@ -1478,9 +1494,22 @@
 # Full TensorFlow library with operator support. Use this unless reducing
 # binary size (by packaging a reduced operator set) is a concern.
-alias(
+cc_library(
     name = "android_tensorflow_lib",
-    actual = ":portable_tensorflow_lib",
+    deps = if_android([
+        ":core_cpu",
+        ":core_cpu_internal",
+        ":framework",
+        ":framework_internal",
+        ":lib",
+        ":lib_internal",
+        ":protos_all_cc",
+    ]) + select({
+        "//tensorflow:android": [],
+        "//conditions:default": [
+            ":portable_tensorflow_lib",
+        ],
+    }),
     visibility = ["//visibility:public"],
+    alwayslink = 1,
 )
"""

HUNK_HEADER_RE = re.compile(
    r"^@@ -(?P<old_start>\d+)(?:,(?P<old_count>\d+))? "
    r"\+(?P<new_start>\d+)(?:,(?P<new_count>\d+))? @@(?P<section>.*)$"
)


def normalize_unified_diff_hunk_counts(text: str) -> str:
    lines = text.splitlines(keepends=True)
    normalized: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        match = HUNK_HEADER_RE.match(line.rstrip("\r\n"))
        if not match:
            normalized.append(line)
            i += 1
            continue

        old_count = 0
        new_count = 0
        j = i + 1
        while j < len(lines):
            body_line = lines[j]
            if body_line.startswith(("--- ", "+++ ", "@@ ")):
                break
            if body_line.startswith("diff --git "):
                break

            prefix = body_line[:1]
            if prefix == " ":
                old_count += 1
                new_count += 1
            elif prefix == "-":
                old_count += 1
            elif prefix == "+":
                new_count += 1
            elif prefix == "\\":
                pass
            else:
                break
            j += 1

        newline = "\r\n" if line.endswith("\r\n") else "\n"
        normalized.append(
            "@@ -{old_start},{old_count} +{new_start},{new_count} @@{section}{newline}".format(
                old_start=match.group("old_start"),
                old_count=old_count,
                new_start=match.group("new_start"),
                new_count=new_count,
                section=match.group("section"),
                newline=newline,
            )
        )
        normalized.extend(lines[i + 1 : j])
        i = j

    return "".join(normalized)


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
    text += LLVM_ANDROID_CONFIG_PATCH
    text += TFE_C_API_ANDROID_DEPS_PATCH
    text += EAGER_CONTEXT_ANDROID_DEPS_PATCH
    text += TF_C_BUILD_ANDROID_FULL_DEPS_PATCH
    text += DISTRIBUTED_EAGER_ANDROID_PATCH
    text += GRPC_SERVER_LIB_ANDROID_BUILD_PATCH
    text += GRPC_SERVER_LIB_ANDROID_CC_PATCH
    text += TF_C_API_EXPERIMENTAL_CC_PATCH
    text += TF_C_API_SAVED_MODEL_INCLUDE_PATCH
    text += TF_C_API_SAVED_MODEL_ANDROID_PATCH
    text += SAVED_MODEL_ANDROID_LOADER_PATCH
    text += TENSORFLOW_FRAMEWORK_ANDROID_PATCH
    text += normalize_unified_diff_hunk_counts(ANDROID_PORTABLE_LIB_SHIM_PATCH)
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
