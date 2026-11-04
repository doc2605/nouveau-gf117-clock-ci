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
