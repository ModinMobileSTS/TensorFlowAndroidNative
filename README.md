# TensorFlow Android Native

GitHub Actions build harness for producing Android `arm64-v8a` TensorFlow Java JNI binaries for the `org.tensorflow` stack.

Current workflow:

- checks out the historical `tensorflow/java` baseline closest to the Slay-I mod
- patches it for Android `arm64`
- builds with Java 11, Bazel, Android SDK, and NDK
- uploads build logs and produced `.so` files as workflow artifacts

The first runs are expected to be iterative because this source tree predates current Android and Bazel toolchains.
