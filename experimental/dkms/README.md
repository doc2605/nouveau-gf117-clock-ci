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
module dependency files.

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
