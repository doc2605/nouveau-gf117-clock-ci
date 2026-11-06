# Initial repository audit — 2026-11-06

## Scope and evidence

This report compares the public default branch and published experiment
branches of `doc2605/nouveau-gf117-ci` with the 7.2, 7.3, DKMS, and Rust work
in `doc2605/nouveau-gf117-clock-ci`. The local working trees are branches of
the second repository; they are not a checkout of the first repository.
Repository trees, workflow definitions, branch tips, and GitHub Actions run
records were inspected. No GPU hardware was accessed.

## Repository 1: `nouveau-gf117-ci`

- Default branch `main` is at `a35ce1cd585583bb3e46760b879564d4edecf284`
  (2026-10-17). The README says the build applies patches 0001–0015, while
  the tree contains patches through 0016. This is a documentation drift.
- `ci/gf117-disable-unverified-pwm-20261017` is at
  `b9f528476a4c91a07e3df5e657f9a7d13f8958f2`; it adds patches 0017–0018
  and a read-only PWM probe harness. Its latest listed run succeeded.
- `ci/gf117-selected-pwm-20261017` is at
  `60473c8f41248e590641b7aa9dbf074e23d5a4a8`; it adds patch 0019 and
  compares the selected channel with the GF119 decoder. Its latest listed
  run succeeded.
- The checked-in workflow builds a 7.2.9-2 CachyOS module in an Arch
  container. It applies the branch patch set, runs source/mock checks, then
  builds the module from matching headers and `Module.symvers`. These jobs
  establish build and source-harness results, not operation on GF117 hardware.

## Repository 2: `nouveau-gf117-clock-ci`

The active development branches at audit time include:

- `research/dkms-collision-test` (`6d261a6008b766cc57ef521afee82d8fb68063f8`):
  a DKMS build-only prototype and isolated collision fixture. CI has built the
  external module through `dkms add` and `dkms build`; install/load and host
  rollback are deliberately untested. DKMS may archive an existing module
  with the same name, so this is not presently a safe installation method.
- `research/gf117-cachyos-7.3.0-4` (`0713e7b1103b0cdb887c984bf579c079413f235b`):
  a 7.3 source port with an external build workflow. The successful build is
  separate from the 7.2 DKMS evidence.
- `research/gf117-rust-nouveau` (`67cf378b5672da46bfc1bf5bf6e6c2685060d6e0`):
  Rust code compiled into the in-tree Nouveau module, plus host harnesses and
  a Rust-enabled full-kernel workflow. The earlier non-MODVERSIONS workflow
  passed. The MODVERSIONS/GENDWARFKSYMS run
  [42167808032](https://github.com/doc2605/nouveau-gf117-clock-ci/actions/runs/42167808032)
  later passed with `CONFIG_EXTENDED_MODVERSIONS=y` and the extended version
  sections in `nouveau.ko`; two preceding attempts failed on missing DWARF
  tooling, and the successful workflow added `libdw-dev`. This build used the
  earlier clock-path Rust hook, which is linked but unreachable through the
  known guarded GF117 voltage backends.
- `research/rust-kbuild-poc` (`13d1fa5ec82dc4154f33e22fc847224dca535837`):
  a standalone external Rust Kbuild probe. It proves toolchain/build
  feasibility, not integration with the real Nouveau driver.
- Additional `ci/gf117-*` branches contain PMU, PWM, timer, and voltage
  experiments. They are parallel experiments, not a single verified release
  series.

The Rust hook is compiled and linked in `nouveau.ko`, but the GF117 PWM and
GPIO/VID voltage backends are rejected by fail-closed patches 0048 and 0050
before reaching that call. Mock harness invocation therefore does not prove
that a real GF117 path executes the Rust validator. The guards must remain in
place until safe hardware behavior is established.

## Cross-repository findings

- Repository 1 is the older patch/test baseline; repository 2 has later PWM,
  voltage, 7.3, DKMS, and Rust experiments. Repository 2's current
  `gf117-consolidated.patch` and experimental patch stack do not make the two
  repositories interchangeable; each workflow builds a different selected
  series and kernel baseline.
- Repeated source helpers and CI metadata differ between branches. Treat
  branch-specific test results as evidence only for that exact commit and
  workflow; do not infer that a success on one branch covers another branch's
  patches.
- No run inspected here is a physical-GPU test. Clock writes, PWM writes,
  voltage changes, temperature behavior, hybrid Intel/NVIDIA behavior, and
  suspend/resume remain unverified on the target notebook.
- Current DKMS evidence is build-only. A same-name Nouveau module creates a
  collision/rollback risk; the technically reliable next installation route
  is a custom kernel package or boot entry that preserves the stock kernel,
  unless a separately verified packaging design resolves that collision.
- The newly added artifact verifier work is local and uncommitted at the
  time of this report. It validates module identity and hashes; it does not
  authenticate artifact provenance or establish signature trust.

## Next work

1. Finish and record the extended MODVERSIONS Rust CI result.
2. Finish DKMS artifact verification for both standard and DKMS module hashes.
3. Decide whether to rebase the Rust integration into the 7.3 series; keep
   claims limited to build/link evidence until a GF117 execution path is
   demonstrably reachable without bypassing safety guards.
4. Keep installation and hardware tests disabled until a separate recovery
   plan and explicit hardware authorization exist.
