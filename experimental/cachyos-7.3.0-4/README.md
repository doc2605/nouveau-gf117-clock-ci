# Experimental CachyOS 7.3.0-4 source port

This is a **source-only experiment**, not a built, installable or hardware
validated driver. Three replacement patches adapt 0005, 0006 and 0011 to the
pstate lookup changes at CachyOS Linux commit
`6f1d90319ee9a72139f60d4547c2b44064ee2987`. The other patches remain those
of the numbered 0001–0022 series. The original pstate `found` check is
preserved; the experimental preflight and core-only path are inserted after
it. Patch order is mandatory.
The additional 0047 patch propagates generic hwmon voltage read errors;
it does not validate the accuracy of PWM-derived command estimates.
Patch 0048 keeps the GF117 PWM-derived estimate out of measured-voltage
hwmon reporting and rejects it as a core-clock preflight input. The raw
read-only PWM diagnostics remain available. This is a conservative guard,
not a validation of voltage behavior or a permanent feature decision.

`apply-and-test.sh <clean-kernel-git-checkout>` checks the exact commit and
rejects a dirty Nouveau tree, copies Nouveau to a temporary directory, applies
the series with zero fuzz, and runs the existing mocked source harnesses. It
never compiles a kernel module, loads a module, or touches hardware. It accepts
no version other than the pinned commit. A successful result demonstrates
patch applicability and mock behavior only; review, exact-ABI build, safety
analysis and physical tests with authorization remain necessary. The old
numbered branch's experimental clock and voltage restrictions remain in force;
this port does not incorporate the separate PMU branch or its safety patch.

An optional second argument selects a new output directory outside the kernel
checkout, used by the build-only CI. The CI downloads the archived x86_64-v3
`linux-cachyos-headers-7.3.0-4` package, pinned by SHA-256. Its signature was
independently checked against the local CachyOS keyring before pinning (key
fingerprint `882DCFE48E2051D48E2562ABF3B607488DB35A47`). The LLVM release
archive is also pinned by SHA-256. CI results, warnings and artifact manifest
must be inspected; the presence of this workflow does not prove a successful
build or allow installing the output.
