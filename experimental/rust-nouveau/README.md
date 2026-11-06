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
division in the no-std object. The solver now uses checked division and
remainder operations; the local optimized no-std object has no undefined
symbols and the differential harness still passes. A fresh pinned CI run is
required to verify this fix before the PLL cross-check is considered
compilable.

The standalone Kbuild object under `experimental/rust-poc/` remains a toolchain
probe and is not the in-tree Nouveau component. Neither prototype is a DKMS
installation method. Verify artifact hashes against an independently trusted
workflow artifact digest; internal `SHA256SUMS` files alone do not establish
provenance or byte-for-byte reproducibility.
