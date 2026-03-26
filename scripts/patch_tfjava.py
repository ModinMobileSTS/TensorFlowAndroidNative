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
    new = """# Allows us to use ccache with Bazel on Mac, but Android needs Bazel's Android crosstool.\nif [[ \"${PLATFORM:-}\" != \"android-arm64\" ]]; then\n    export BAZEL_USE_CPP_ONLY_TOOLCHAIN=1\nfi\n\nexport BAZEL_VC=\"${VCINSTALLDIR:-}\"\nif [[ \"${PLATFORM:-}\" == \"android-arm64\" ]]; then\n    export BUILD_FLAGS=\"--config=android_arm64 --cxxopt=-std=c++14 --host_cxxopt=-std=c++14\"\n    export PYTHON_BIN_PATH=$(which python3)\nelif [[ -d $BAZEL_VC ]]; then\n    # Work around compiler issues on Windows documented mainly in configure.py but also elsewhere\n    export BUILD_FLAGS=\"--copt=//arch:AVX `#--copt=//arch:AVX2` --copt=-DWIN32_LEAN_AND_MEAN --host_copt=-DWIN32_LEAN_AND_MEAN --copt=-DNOGDI --host_copt=-DNOGDI --copt=-D_USE_MATH_DEFINES --host_copt=-D_USE_MATH_DEFINES --define=override_eigen_strong_inline=true\"\n    # https://software.intel.com/en-us/articles/intel-optimization-for-tensorflow-installation-guide#wind_B_S\n    export PATH=$PATH:$(pwd)/bazel-tensorflow-core-api/external/mkl_windows/lib/\n    export PYTHON_BIN_PATH=$(which python.exe)\nelse\n    export BUILD_FLAGS=\"--copt=-msse4.1 --copt=-msse4.2 --copt=-mavx `#--copt=-mavx2 --copt=-mfma` --cxxopt=-std=c++14 --host_cxxopt=-std=c++14 --linkopt=-lstdc++ --host_linkopt=-lstdc++\"\n    export PYTHON_BIN_PATH=$(which python3)\nfi\n"""
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


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: patch_tfjava.py <tfjava-root>")
    root = Path(sys.argv[1]).resolve()
    patch_module_pom(root / "tensorflow-core" / "tensorflow-core-api" / "pom.xml")
    patch_build_sh(root / "tensorflow-core" / "tensorflow-core-api" / "build.sh")
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
