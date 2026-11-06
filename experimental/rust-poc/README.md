# C + Rust kernel integration probes

`limits.rs`, `glue.c`, and the external-module `Makefile` are a standalone
Kbuild/toolchain probe. The module is not Nouveau and its glue does not touch
hardware. `test-host.sh` compiles the Rust validator to an object, links it to
C, and compares C and Rust behavior across 1,728 boundary combinations. It
uses temporary files and does not require Cargo.

The in-tree Nouveau proof of concept is separate and lives under
`experimental/rust-nouveau/`. That patch compiles Rust into `nouveau.ko` and
calls it from the read-only GF117 `pstate_plan` diagnostic. The standalone
probe must not be used as evidence that the Nouveau C caller is reachable or
that any module works on hardware.

Kernel build integration is performed in CI against a pinned full CachyOS
source tree. The CI checks `rustavailable`, the Rust and bindgen versions,
Kconfig, C/Rust linkage, extended MODVERSIONS, and a full kernel/module build.
No module is installed or loaded. The local probe remains optional and should
not add a Rust toolchain requirement to normal development or DKMS builds.
