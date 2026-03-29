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
    old = """# Allows us to use ccache with Bazel on Mac\nexport BAZEL_USE_CPP_ONLY_TOOLCHAIN=1\n\nexport BAZEL_VC=\"${VCINSTALLDIR:-}\"\nif [[ -d $BAZEL_VC ]]; then\n    # Work around compiler issues on Windows documented mainly in configure.py but also elsewhere\n    export BUILD_FLAGS=\"--copt=//arch:AVX `#--copt=//arch:AVX2` --copt=-DWIN32_LEAN_AND_MEAN --host_copt=-DWIN32_LEAN_AND_MEAN --copt=-DNOGDI --host_copt=-DNOGDI --copt=-D_USE_MATH_DEFINES --host_copt=-D_USE_MATH_DEFINES --define=override_eigen_strong_inline=true\"\n    # https://software.intel.com/en-us/articles/intel-optimization-for-tensorflow-installation-guide#wind_B_S\n    export PATH=$PATH:$(pwd)/bazel-tensorflow-core-api/external/mkl_windows/lib/\n    export PYTHON_BIN_PATH=$(which python.exe)\nelse\n    export BUILD_FLAGS=\"--copt=-msse4.1 --copt=-msse4.2 --copt=-mavx `#--copt=-mavx2 --copt=-mfma` --cxxopt=-std=c++14 --host_cxxopt=-std=c++14 --linkopt=-lstdc++ --host_linkopt=-lstdc++\"\n    export PYTHON_BIN_PATH=$(which python3)\nfi\n"""
    new = """# Allows us to use ccache with Bazel on Mac, but Android needs Bazel's Android crosstool.\nif [[ \"${PLATFORM:-}\" != \"android-arm64\" ]]; then\n    export BAZEL_USE_CPP_ONLY_TOOLCHAIN=1\nfi\n\nexport BAZEL_VC=\"${VCINSTALLDIR:-}\"\nif [[ \"${PLATFORM:-}\" == \"android-arm64\" ]]; then\n    export TF_ANDROID_COMPAT_LIB_DIR=\"$(pwd)/android-compat-libs\"\n    mkdir -p \"${TF_ANDROID_COMPAT_LIB_DIR}\"\n    printf 'INPUT(-lc)\\n' > \"${TF_ANDROID_COMPAT_LIB_DIR}/libpthread.so\"\n    printf 'INPUT(-lc)\\n' > \"${TF_ANDROID_COMPAT_LIB_DIR}/librt.so\"\n    # tfjava builds TensorFlow as an external Bazel repository, so TensorFlow's\n    # own .bazelrc does not inject framework_shared_object=true for us.\n    export BUILD_FLAGS=\"--config=android_arm64 --host_crosstool_top=@bazel_tools//tools/cpp:toolchain --define=framework_shared_object=true --copt=-DANDROID --cxxopt=-std=c++14 --host_cxxopt=-std=c++14 --cxxopt=-include --cxxopt=cstdint --host_cxxopt=-include --host_cxxopt=cstdint --copt=-Wno-error=array-parameter --host_copt=-Wno-error=array-parameter --copt=-Wno-error=array-bounds --host_copt=-Wno-error=array-bounds --linkopt=-L${TF_ANDROID_COMPAT_LIB_DIR} --linkopt=-llog\"\n    export PYTHON_BIN_PATH=$(which python3)\nelif [[ -d $BAZEL_VC ]]; then\n    # Work around compiler issues on Windows documented mainly in configure.py but also elsewhere\n    export BUILD_FLAGS=\"--copt=//arch:AVX `#--copt=//arch:AVX2` --copt=-DWIN32_LEAN_AND_MEAN --host_copt=-DWIN32_LEAN_AND_MEAN --copt=-DNOGDI --host_copt=-DNOGDI --copt=-D_USE_MATH_DEFINES --host_copt=-D_USE_MATH_DEFINES --define=override_eigen_strong_inline=true\"\n    # https://software.intel.com/en-us/articles/intel-optimization-for-tensorflow-installation-guide#wind_B_S\n    export PATH=$PATH:$(pwd)/bazel-tensorflow-core-api/external/mkl_windows/lib/\n    export PYTHON_BIN_PATH=$(which python.exe)\nelse\n    export BUILD_FLAGS=\"--copt=-msse4.1 --copt=-msse4.2 --copt=-mavx `#--copt=-mavx2 --copt=-mfma` --cxxopt=-std=c++14 --host_cxxopt=-std=c++14 --linkopt=-lstdc++ --host_linkopt=-lstdc++\"\n    export PYTHON_BIN_PATH=$(which python3)\nfi\n\nif [[ -n \"${BAZEL_REPOSITORY_CACHE:-}\" ]]; then\n    export BUILD_FLAGS=\"$BUILD_FLAGS --repository_cache=${BAZEL_REPOSITORY_CACHE}\"\nfi\nif [[ -n \"${BAZEL_DISK_CACHE:-}\" ]]; then\n    export BUILD_FLAGS=\"$BUILD_FLAGS --disk_cache=${BAZEL_DISK_CACHE}\"\nfi\n"""
    text = replace_once(text, old, new, path)
    old = """# Build C API of TensorFlow itself including a target to generate ops for Java\nbazel build $BUILD_FLAGS \\\n    @org_tensorflow//tensorflow:tensorflow \\\n    @org_tensorflow//tensorflow/tools/lib_package:jnilicenses_generate \\\n    :java_proto_gen_sources \\\n    :java_op_generator \\\n    :java_api_import \\\n    :custom_ops_test\n"""
    new = """# Build C API of TensorFlow itself. Android cross-builds reuse the checked-in\n# generated Java sources because the generator is a host tool that loads the\n# produced TensorFlow library at build time.\nBAZEL_TARGETS=(\n    @org_tensorflow//tensorflow:tensorflow\n    @org_tensorflow//tensorflow/tools/lib_package:jnilicenses_generate\n    :java_proto_gen_sources\n    :custom_ops_test\n)\nif [[ \"${PLATFORM:-}\" != \"android-arm64\" ]]; then\n    BAZEL_TARGETS+=(\n        :java_op_generator\n        :java_api_import\n    )\nfi\nbazel build $BUILD_FLAGS \"${BAZEL_TARGETS[@]}\"\n"""
    text = replace_once(text, old, new, path)
    old = """GEN_SRCS_DIR=src/gen/java\nmkdir -p $GEN_SRCS_DIR\n\n# Generate Java operator wrappers\n$BAZEL_BIN/java_op_generator \\\n    --output_dir=$GEN_SRCS_DIR \\\n    --api_dirs=$BAZEL_SRCS/external/org_tensorflow/tensorflow/core/api_def/base_api,src/bazel/api_def \\\n    $TENSORFLOW_LIB\n\n# Copy generated Java protos from source jars\n"""
    new = """GEN_SRCS_DIR=src/gen/java\nmkdir -p $GEN_SRCS_DIR\n\nif [[ \"${PLATFORM:-}\" != \"android-arm64\" ]]; then\n    # Generate Java operator wrappers\n    $BAZEL_BIN/java_op_generator \\\n        --output_dir=$GEN_SRCS_DIR \\\n        --api_dirs=$BAZEL_SRCS/external/org_tensorflow/tensorflow/core/api_def/base_api,src/bazel/api_def \\\n        $TENSORFLOW_LIB\nelse\n    echo \"Skipping java_op_generator for android-arm64; reusing checked-in generated sources.\"\nfi\n\n# Copy generated Java protos from source jars\n"""
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


SAVED_MODEL_ANDROID_LOADER_PATCH = """--- a/tensorflow/cc/saved_model/BUILD
+++ b/tensorflow/cc/saved_model/BUILD
@@ -92,7 +92,7 @@
 cc_library(
     name = "loader_lite",
     hdrs = ["loader.h"],
-    deps = if_static([
+    deps = if_static_and_not_mobile([
         ":loader_lite_impl",
     ]) + if_not_mobile([
         "//tensorflow/core:core_cpu",
"""


TENSORFLOW_FRAMEWORK_ANDROID_PATCH = """--- a/tensorflow/BUILD
+++ b/tensorflow/BUILD
@@ -635,8 +635,12 @@
     per_os_targets = True,
     soversion = VERSION,
     visibility = ["//visibility:public"],
-    deps = [
-        "//tensorflow/cc/saved_model:loader_lite_impl",
+    deps = select({
+        "//tensorflow:android": [],
+        "//conditions:default": [
+            "//tensorflow/cc/saved_model:loader_lite_impl",
+        ],
+    }) + [
         "//tensorflow/core:core_cpu_impl",
         "//tensorflow/core:framework_internal_impl",
         "//tensorflow/core:gpu_runtime_impl",
         "//tensorflow/core/grappler/optimizers:custom_graph_optimizer_registry_impl",
         "//tensorflow/core:lib_internal_impl",
         "//tensorflow/core/profiler:profiler_impl",
         "//tensorflow/stream_executor:stream_executor_impl",
         "//tensorflow:tf_framework_version_script.lds",
-    ] + tf_additional_binary_deps(),
+    ] + tf_additional_binary_deps(),
 )
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
    text += LLVM_ANDROID_CONFIG_PATCH
    text += TFE_C_API_ANDROID_DEPS_PATCH
    text += EAGER_CONTEXT_ANDROID_DEPS_PATCH
    text += TF_C_BUILD_ANDROID_FULL_DEPS_PATCH
    text += DISTRIBUTED_EAGER_ANDROID_PATCH
    text += GRPC_SERVER_LIB_ANDROID_BUILD_PATCH
    text += GRPC_SERVER_LIB_ANDROID_CC_PATCH
    text += TF_C_API_EXPERIMENTAL_CC_PATCH
    text += SAVED_MODEL_ANDROID_LOADER_PATCH
    text += TENSORFLOW_FRAMEWORK_ANDROID_PATCH
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
