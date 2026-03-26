from __future__ import annotations

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
    new = """# Allows us to use ccache with Bazel on Mac, but Android needs Bazel's Android crosstool.\nif [[ \"${PLATFORM:-}\" != \"android-arm64\" ]]; then\n    export BAZEL_USE_CPP_ONLY_TOOLCHAIN=1\nfi\n\nexport BAZEL_VC=\"${VCINSTALLDIR:-}\"\nif [[ \"${PLATFORM:-}\" == \"android-arm64\" ]]; then\n    export BUILD_FLAGS=\"--crosstool_top=@androidndk//:default_crosstool --cpu=arm64-v8a --fat_apk_cpu=arm64-v8a --host_crosstool_top=@bazel_tools//tools/cpp:toolchain --cxxopt=-std=c++14 --host_cxxopt=-std=c++14\"\n    export PYTHON_BIN_PATH=$(which python3)\nelif [[ -d $BAZEL_VC ]]; then\n    # Work around compiler issues on Windows documented mainly in configure.py but also elsewhere\n    export BUILD_FLAGS=\"--copt=//arch:AVX `#--copt=//arch:AVX2` --copt=-DWIN32_LEAN_AND_MEAN --host_copt=-DWIN32_LEAN_AND_MEAN --copt=-DNOGDI --host_copt=-DNOGDI --copt=-D_USE_MATH_DEFINES --host_copt=-D_USE_MATH_DEFINES --define=override_eigen_strong_inline=true\"\n    # https://software.intel.com/en-us/articles/intel-optimization-for-tensorflow-installation-guide#wind_B_S\n    export PATH=$PATH:$(pwd)/bazel-tensorflow-core-api/external/mkl_windows/lib/\n    export PYTHON_BIN_PATH=$(which python.exe)\nelse\n    export BUILD_FLAGS=\"--copt=-msse4.1 --copt=-msse4.2 --copt=-mavx `#--copt=-mavx2 --copt=-mfma` --cxxopt=-std=c++14 --host_cxxopt=-std=c++14 --linkopt=-lstdc++ --host_linkopt=-lstdc++\"\n    export PYTHON_BIN_PATH=$(which python3)\nfi\n"""
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


def write_tensorflow_android_absl_patch(path: Path) -> None:
    text = """diff --git a/tensorflow/workspace.bzl b/tensorflow/workspace.bzl
--- a/tensorflow/workspace.bzl
+++ b/tensorflow/workspace.bzl
@@ -186,7 +186,8 @@ def tf_workspace(path_prefix = \"\", tf_repo_name = \"\"):\n     tf_http_archive(\n         name = \"com_google_absl\",\n         build_file = clean_dep(\"//third_party:com_google_absl.BUILD\"),\n         # TODO: Remove the patch when https://github.com/abseil/abseil-cpp/issues/326 is resolved\n         # and when TensorFlow is build against CUDA 10.2\n -        patch_file = clean_dep(\"//third_party:com_google_absl_fix_mac_and_nvcc_build.patch\"),\n +        patch_file = clean_dep(\"//third_party:com_google_absl_fix_mac_and_nvcc_build.patch\"),\n +        patch_cmds = [\"grep -q '^#include <limits>$' absl/synchronization/internal/graphcycles.cc || sed -i '/#include <algorithm>/a #include <limits>' absl/synchronization/internal/graphcycles.cc\"],\n         sha256 = \"acd93f6baaedc4414ebd08b33bebca7c7a46888916101d8c0b8083573526d070\",  # SHARED_ABSL_SHA\n         strip_prefix = \"abseil-cpp-43ef2148c0936ebf7cb4be6b19927a9d9d145b8f\",\n         urls = [\n"""
    path.write_text(text, encoding="utf-8")


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: patch_tfjava.py <tfjava-root>")
    root = Path(sys.argv[1]).resolve()
    patch_module_pom(root / "tensorflow-core" / "tensorflow-core-api" / "pom.xml")
    patch_build_sh(root / "tensorflow-core" / "tensorflow-core-api" / "build.sh")
    patch_workspace(root / "tensorflow-core" / "tensorflow-core-api" / "WORKSPACE")
    write_tensorflow_android_absl_patch(
        root / "tensorflow-core" / "tensorflow-core-api" / "tensorflow-android-absl.patch"
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
