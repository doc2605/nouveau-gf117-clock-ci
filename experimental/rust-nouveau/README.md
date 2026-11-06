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

The new differential harness compiles the actual C `gt215_pll_calc()` from the
kernel source and compares return codes and successful coefficients against
the Rust object for integer and fractional modes. Locally, it passed edge
half-reference boundaries, 10,000 constrained tuples, and 50,000
deterministic randomized parameter/frequency tuples in both modes, with C
UndefinedBehaviorSanitizer enabled, against the available
patched CachyOS 7.3 source subset. The patch is also applied with zero fuzz to
a minimal synthetic post-0001 tree. Exact pinned 7.2.9-2 full-source
application, module compilation, symbol linkage, and the production C call
path remain pending remote CI. The cross-check has not been tested on GPU
hardware and does not authorize reclocking.

The standalone Kbuild object under `experimental/rust-poc/` remains a toolchain
probe and is not the in-tree Nouveau component. Neither prototype is a DKMS
installation method. Verify artifact hashes against an independently trusted
workflow artifact digest; internal `SHA256SUMS` files alone do not establish
provenance or byte-for-byte reproducibility.
