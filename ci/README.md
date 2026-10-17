# GF117 module CI

This workflow builds the Nouveau patch series against CachyOS kernel 7.2.9-2
with mock hardware checks. It does not validate reclocking on a physical GPU.
The bundled headers contain the matching kernel configuration and
Module.symvers; the official matching source tarball is downloaded and checked
by SHA-256.

Clang, LLVM and LLD 23.1.1 come from the official LLVM Linux x86_64 release
archive. Its release SHA-256 is pinned in `ci/toolchain.sha256`. Downloads use
HTTP/1.1 with bounded retries. The artifact contains the compressed module,
patch/source/config hashes, vermagic and full build log. Workflow permissions
are limited to `contents:read`.

The real-source harnesses cover core/voltage, RAM, VGA, CRTC, worker completion,
PLL, and GF117 PWM readback. Helper parsing uses fixtures and does not load a
module or write GPU registers.

The public repository contains only Nouveau patches, source tests, CI scripts
and the kernel header bundle. It contains no proprietary driver files, VBIOS
dump, notebook logs or local build outputs.

Repository: https://github.com/doc2605/nouveau-gf117-clock-ci
