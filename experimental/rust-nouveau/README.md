# Experimental Rust guard inside Nouveau

After patches 0001–0022 on CachyOS Linux commit
`09bc889a111715e4509b3819b628c9b9d9d09a0b`, the safety patches 0047–0049 suppress voltage estimates as hwmon measurements
and block the GF117 voltage preflight when PWM readback is only an estimate.
Patch 0050 also rejects the experimental GF117 GPIO/VID voltage preflight:
the VID bits and VBIOS table represent a command, not independent rail
measurement. The Rust CI applies 0050 before the Rust guard.
The Rust patch introduces
`CONFIG_DRM_NOUVEAU_GF117_RUST_GUARD` (default off; requires Rust and Nouveau).
When enabled it compiles a Rust scalar validator into `nouveau.ko` and calls it
from the GF117 core-only path after voltage-command readback. When disabled the
existing C comparison remains. The function uses no pointers, MMIO, allocation
or unsafe blocks. This is not a claim that the PWM command measures the real
rail voltage, nor that a reclock transition is safe.

With the current fail-closed patches applied, the experimental C call site is
not known to be reachable from the real GF117 voltage backends: 0048 blocks the
PWM estimate and 0050 blocks GPIO/VID before the call. The C/Rust source harness
uses a mocked non-GF117 backend to exercise the call and compare scalar
behavior. It proves the opt-in code is part of the Nouveau build and links to
Rust, but does not prove execution through an enabled GF117 hardware path. Do
not relax either safety guard merely to make the Rust function reachable.

Host CI exercises the actual PWM, hwmon and cstate source with mock hardware.
It runs the cstate harness twice, using either
the C fallback or the Rust object, plus 1,728 boundary cases in the standalone
FFI proof. A separate Kbuild job verifies the kernel configuration, the Rust
symbol in Nouveau, and a reference to it from the C clock object. No module is
loaded. The kernel used has a custom Rust-enabled configuration and is not the
distributed CachyOS kernel. Do not install these experimental artifacts.

The artifact's `SHA256SUMS` uses paths relative to its extracted directory and
includes the compressed module, configuration, build metadata, symbol listings,
and build log. Verify it there with `sha256sum -c SHA256SUMS`. These hashes
identify the uploaded files; they do not prove independent build reproducibility.
