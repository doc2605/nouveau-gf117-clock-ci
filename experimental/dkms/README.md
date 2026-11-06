# Build-only DKMS prototype

This prototype is restricted to `7.2.9-2-cachyos`; it requires the matching
prepared kernel tree and already-patched Nouveau source. The CI script stages
both DKMS metadata and source in a new sandbox under `work/`, then invokes
only `dkms add` and `dkms build` with isolated source, DKMS and install trees.
`AUTOINSTALL` is disabled and the script checks that the install tree is empty.
No driver is installed or loaded. CI captures the make log, a module hash, and
the compressed DKMS build output.

This is an experimental build demonstration, not an installation package.
In particular, standard `dkms install` may move an existing same-named module;
do not use it until a safe installation and rollback procedure has been
verified separately. Successful compilation does not establish ABI, hardware
or Secure Boot compatibility. The voltage readback remains an estimate of a
PWM command, not a physical rail measurement.

## Current build evidence (2026-11-06)

The [7.2.9-2 build-only run](https://github.com/doc2605/nouveau-gf117-clock-ci/actions/runs/42164791436)
completed successfully using DKMS `3.2.2-1ubuntu1` in an isolated CI
container. The workflow ran `dkms add` and `dkms build`, verified the
install tree stayed empty, and produced `nouveau.ko.zst`. Artifact
`13478728568` expires 2026-11-13; ZIP SHA-256:
`d144308b5f06fcc8e0834e945be557a45c04af3624d7b1407f762360f34d61ca`.
The uncompressed module SHA-256 is
`ca105cb01496acbb1a3530ab1269e0bfe8a8624775103426dca382713ba3b28`;
its vermagic is `7.2.9-2-cachyos SMP preempt mod_unload`. The log reports
that no isolated `sign-file` was available, so the module is unsigned, and
notes compiler and pahole version differences. This is exact-ABI build
evidence only.

The artifact verifier distinguishes `standard` and `dkms` module payloads.
The standard module is checked against `module_sha256`; DKMS verification must
select `--artifact-kind dkms` and supply the one-entry DKMS SHA-256 sidecar.
Both paths require the target kernel release explicitly and check the module
name, vermagic, and srcversion. The manifest records a separate DKMS hash,
vermagic, and srcversion, so the different DKMS `.ko` cannot accidentally be
compared with the standard module's digest. The verifier reports whether
signature metadata is present; it does not determine whether a signer is
trusted by a target kernel or by Secure Boot.
The raw DKMS module hash is recorded in the manifest and sidecar; the separate
compressed DKMS artifact also has its own `.zst.sha256` sidecar.

For a downloaded artifact, first verify the ZIP digest against a value
obtained through a trusted channel. The internal manifest and sidecar bind the
module to the build output but are not signatures and do not prove who
produced them. A passing verification establishes artifact identity only;
it does not mean the module is installed, loadable, trusted, or runtime-tested.

A separate external-module workflow built for
[`7.3.0-4-cachyos`](https://github.com/doc2605/nouveau-gf117-clock-ci/actions/runs/42164770902)
without DKMS installation. Artifact `13478029616` expires 2026-11-20; ZIP
SHA-256:
`3125a3c0189292aab9adf804bf056f2ee3a1d19f9b23bd76db4783d78e0a086e`.
This is a distinct source-port/build path, not evidence that the DKMS package
supports 7.3.

## Isolated collision experiment

`tests/test-collision-dkms-3.1.7.py` runs the pinned upstream DKMS script
against inert fixture files in a user namespace. It creates private source,
DKMS-state, install, and temporary trees, and removes them on exit. The test
checks that an existing same-named `nouveau.ko` is moved into DKMS's
`original_module` archive, that the fixture replacement is placed under the
isolated `updates/dkms` tree, and that a simple uninstall restores the original.
This exercises DKMS install/uninstall logic on fixture files only; it is not an
installation or rollback test on the host, a kernel build, or a hardware test.
The harness places a `depmod` stub first in `PATH`, so DKMS cannot update host
module dependency files. The collision fixture uses DKMS v3.1.7; the remote
build-only CI above uses v3.2.2, and no real-module installation is attempted.

Reproduce on a Linux host with `unshare` user namespaces enabled:

```sh
cd experimental/dkms
curl -fL https://raw.githubusercontent.com/dkms-project/dkms/v3.1.7/dkms.in \
  -o /tmp/dkms-v3.1.7-dkms.in
sha256sum /tmp/dkms-v3.1.7-dkms.in
python3 tests/test-collision-dkms-3.1.7.py /tmp/dkms-v3.1.7-dkms.in
```

The harness refuses to execute unless the source hash is
`d5c23ea16b3709e38b37a53fabed414f9d2e5933a8059429b045338bb04b240d`.
Recorded local run: 2026-11-06; hash matched and the harness printed
`PASS: DKMS moves original on install and restores it on simple uninstall`.
The upstream output reported archiving the pre-existing fixture, installing
the replacement, invoking the fixture `depmod` stub, deleting the replacement
on uninstall, and restoring the archived fixture.
No host module tree, loaded module, initramfs, or system DKMS state was touched.
