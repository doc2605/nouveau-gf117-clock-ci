# Experimental Rust diagnostic inside Nouveau

This proof of concept is based on CachyOS Linux commit
`09bc889a111715e4509b3819b628c9b9d9d09a0b` (7.2.9-2) and patches 0001–0022.
It applies safety patches 0047–0050 before the Rust patch. Patches 0048 and
0050 continue to reject voltage preflight when GF117 PWM or GPIO/VID values
are command-derived rather than independent rail measurements.

Patch `0001-gf117-rust-voltage-plan-diagnostic.patch` adds the optional
`CONFIG_DRM_NOUVEAU_GF117_RUST_GUARD` Kconfig setting (default off). When
enabled, it compiles a small Rust validator into `nouveau.ko`. C calls it
while rendering Nouveau's read-only `pstate_plan` debugfs diagnostic for
chipset `0xd7` (GF117). The C helper maps the requested VBIOS VID and passes
the target, minimum, and maximum microvolt values to Rust. The Rust function
checks only those scalars and returns a diagnostic status; it does not read
MMIO, access pointers, allocate memory, or write hardware. It contains no
`unsafe` blocks. The plan is VBIOS-derived and is not a physical voltage
measurement. When the Kconfig option is off, the same C helper validates the
same values and reports the same result; the option selects which
implementation handles the diagnostic.

This moves Rust into an actual kernel Nouveau diagnostic call path while
keeping it outside the guarded voltage-transition path. It is proof of C/Rust
build and call integration, not proof that the target notebook executes the
debugfs path or that any clock, PWM, voltage, or power behavior works on
hardware. Keep guards 0048 and 0050 unchanged.

The host harness compares C and Rust results for 1,728 scalar combinations.
The source harness extracts the actual Nouveau C helper and C fallback, links
them with the Rust object, and checks accepted and rejected VBIOS ranges in
both Kconfig modes. The in-tree CI
pins the kernel commit, runs `rustavailable`, records Rust/bindgen/Clang and
configuration data, checks the C undefined reference and Rust symbol in
`nouveau.ko`, and attempts a full Rust-enabled kernel build with extended
MODVERSIONS. No module is installed or loaded. A green host harness or build
is separate from hardware evidence; full build success also depends on the
currently running workflow result.

## PLL cross-check stage

The candidate next step is `gt215_pll_calc()` in Nouveau's GF100-family clock
path. Patch `0002-gf117-rust-gt215-pll-crosscheck.patch` adds a no-MMIO Rust
implementation using scalar VBIOS limits. With the opt-in Kconfig enabled,
`gf100.c` invokes it only for chipset `0xd7`, compares its return value and
coefficients with the existing C result, and uses the Rust result only on an
exact match. A mismatch keeps the C result and emits an error. With the option
disabled or on other chipsets, behavior stays on the existing C path. This is
a shadow parity stage: C remains the reference and the extra calculation adds
some opt-in work. Rust does not parse VBIOS structs, access MMIO, or program
registers. The `#[repr(C)]` result carries five fixed `i32` fields; the Rust
function uses no pointers or `unsafe` blocks.

The differential harness compiles the actual C `gt215_pll_calc()` from the
kernel source and compares return codes and successful coefficients against
the Rust object for integer and fractional modes. It exercises half-reference
ties, odd reference clocks, P quotient overflow/clamps, M/N bounds, zero and
invalid values, nonzero fractional flags, 10,000 constrained tuples, and
50,000 deterministic randomized tuples. It checks fixed result-struct layout
and Rust zeroed error fields; C runs under UndefinedBehaviorSanitizer. The
actual `calc_pll()` C function body is extracted, compiled, and executed in a
host harness with stubbed VBIOS parsing and reference-clock helpers. This
verifies the GF117 Rust path and non-GF117 C path without claiming a kernel
runtime test. A second host binary injects a Rust mismatch and verifies the
adapter retains the C coefficient. These tests passed against the available
patched CachyOS 7.3 source subset after a test exposed C's signed-int
conversion of an oversized P quotient; Rust now mirrors the Linux
two's-complement result. The differential and adapter harnesses pass with
both Clang and GCC locally. The
patch applies with zero fuzz to a synthetic post-0001 tree. Exact pinned
7.2.9-2 module linkage and full-kernel compilation remain pending remote CI.
The standalone fractional branch is tested, but the real GF117 caller passes
`fractional = 0`. No PLL change has been tested on GPU hardware or authorizes
reclocking.

The first pinned CI attempt, run 42176186321 on commit `6ad1929`, failed in
the host differential link before the full kernel build. Rust 1.85 emitted an
unresolved `core::panicking::panic_const_div_by_zero` reference for guarded
division in the no-std object. Run 42176826186 on commit `07a4637` passed
patch application and exact-source host tests, then failed during kernel
compilation because `-D missing-docs` rejected the public result struct and
its fields. Expanded commit `150abac` added the signed P-quotient parity fix,
layout assertions, and production adapter/fallback host tests; run 42179812950
passed patch application and host/source tests and was canceled after the same
lint failure was identified. Commit `ee7b337` documents the C ABI result and
each field. The next pinned run, 42180904820, compiled and linked
`nouveau.ko` and defined both Rust entry points, but its final no-undefined
check found `panic_const_mul_overflow` and `panic_const_sub_overflow` references
in `gf117_pll.o`. These came from direct arithmetic with the kernel's overflow
checks enabled. The solver now uses checked multiplication, addition, and
subtraction for those paths. With local rustc 1.99.1, overflow checks enabled,
`nm -u` is empty; the exact-source C/Rust and adapter tests pass with Clang and
GCC, and the module passes the local missing-docs lint. Run 42184995810
confirmed the Rust object has no panic-runtime references and `nouveau.ko`
defines both Rust entry points, but the final assertion incorrectly rejected
its normal `__x86_return_thunk` reference. The workflow now checks specifically
for unresolved Rust panic helpers and leaves architecture/kernel references to
Kbuild modpost. Run 42187920923 passed the complete pinned build with Rust
1.85.0, bindgen 0.71.1, LLVM/Clang, `CONFIG_RUST=y`, and
`CONFIG_EXTENDED_MODVERSIONS=y`. Kbuild compiled both `gf117_rust_guard.o` and
`gf117_pll.o`, linked `nouveau.ko`, and the symbol checks found both Rust
definitions plus their expected C undefined references. The PLL object retained
only the normal `__x86_return_thunk` undefined reference; no Rust panic helper
remained. The compressed module and build metadata passed the artifact's
`SHA256SUMS` checks. The 28,219,665-byte ZIP's digest matched GitHub's artifact
digest `sha256:1211f68df13a937c878084167d133aae9dde455ce0ad7b8b4f3dad9c5d82cb81`
(artifact 13488509959). The artifact records project commit `cbba2c8`, kernel
source commit `09bc889a111715e4509b3819b628c9b9d9d09a0b`, and x86_64.

Run 42190675638 rebuilt the same code at commit `ad38e53` in a separate GitHub
Actions job with the same recorded kernel and compiler versions. Its artifact
digest (`sha256:45fc6f5bdb267e87e7c5bc518b76b41a7640adc905ccdbd5d730a2b337404387`,
ID 13491332165) also matched GitHub's API digest, and its internal
`SHA256SUMS` checks passed. The compressed and uncompressed Nouveau modules
matched the first build byte for byte:

| Output | SHA-256 shared by all four runs |
| --- | --- |
| `nouveau-rust.ko.zst` | `f3decbd35e4ae5e8a861f78afa30002965bb6c6696cce463446d34d3a2c9253c` |
| uncompressed `nouveau.ko` | `d3cc32a0aaede4373f20933f201933bf3f0d24d8a9a950d1d9100c06277532bf` |
| `kernel.config` | `590d951a3b7ad0b29dd00521d37ba24e81d6bc83d8e189623b4ae6e7644e4a84` |
| `Module.symvers` | `8bff4c168e57002131fa0447a19a910e7f91048106a03dc5279407782e0e3500` |
| `nouveau.symbols` | `ee0450498cbff9057a7c529ddba295ac5c99924d43701bd9cc441c1dac2abbe0` |

Run 42208371477 independently rebuilt the same source at commit `c2e3ea2`.
Its 28,219,777-byte artifact (ID 13499370863) matched GitHub's API digest
`sha256:0b08b5dd40949368b4df300d9da7f74bab461c317221df46ce2bdd47143197a3`;
the downloaded ZIP passed `unzip -t`, its internal `SHA256SUMS` passed, and the
uncompressed module hash matched the previous two artifacts. The compressed
module, config, `Module.symvers`, symbol listings and debugfs undefined-symbol
listing are byte-identical across all three successful builds.

Run 42209101812 rebuilt that same source at commit `62a1696` (the commit added
only the repository audit document). Its 28,219,681-byte artifact (ID
13500165502) matched GitHub's API digest
`sha256:76abf6316a45229b1a4c4eda3d1ccddf3341272915f7a96fbee2aabb27033985`.
The downloaded ZIP passed `unzip -t` and its internal checks. Its compressed and
uncompressed module hashes, kernel configuration, `Module.symvers`, and symbol
listings match all three earlier builds.

The complete ZIPs are not byte-identical: `build-info.txt` records different
project commits, `kernel-build.log` differs between runner executions, and
`SHA256SUMS` consequently differs. Thus four runs establish repeatable module
bytes for this pinned kernel, configuration, architecture and recorded
toolchain, not identical workflow archives or a cross-toolchain guarantee.
None tests module loading, runtime behavior, or hardware operation.

Workflow commit `7957cb4` adds `gf100-undefined.symbols` and
`gf117-pll-undefined.symbols` to the internal `SHA256SUMS` manifest. Earlier
artifacts contain these diagnostic files, and their ZIP digests are verified
externally, but their per-file checksums were omitted from the manifest. CI run
`42212595424` is validating the revised manifest.

The standalone Kbuild object under `experimental/rust-poc/` remains a toolchain
probe and is not the in-tree Nouveau component. Neither prototype is a DKMS
installation method. Keep checking the external GitHub artifact digest as well
as the artifact's internal `SHA256SUMS`; neither check alone proves the broader
runtime or hardware behavior of the module.

## Kernel Rust APIs and DKMS boundary

The selected CachyOS source commit contains Rust PCI abstractions in
`rust/kernel/pci.rs` (`pci::Driver`, `pci::Device`, and BAR resource helpers),
MMIO abstractions in `rust/kernel/io/mem.rs` (`IoRequest`, `IoMem`, and mapped
read/write accessors), and coherent DMA wrappers in `rust/kernel/dma.rs`
(`Coherent`, `CoherentBox`, and `CoherentHandle`). Their presence does not mean
that Nouveau's NVKM ownership, BAR lifetime, DMA mapping, teardown, or ordering
rules are already represented by safe Rust abstractions. The current Rust code
deliberately avoids those APIs and keeps PCI, MMIO, DMA, and device lifecycle in
the existing C/NVKM implementation.

The separate external-module Kbuild probe passed on run 41810297951, proving
that a small scalar-only C/Rust module can be built against a fully configured
Rust-enabled kernel tree. It does not exercise the DKMS lifecycle or the
Nouveau internals. The GF117 integration is patched into the in-tree Nouveau
build; the available evidence does not show that CachyOS's distributed kernel
headers enable Rust or include the full artifacts/toolchain required for DKMS.
For now, use the kernel's own Kbuild against the pinned, configured source tree
for this component. Revisit DKMS only after testing against the actual packaged
headers and a complete install/rebuild/remove cycle.
