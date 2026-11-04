#!/usr/bin/env bash
# Experimental DKMS build entrypoint: no installation or system changes.
set -euo pipefail
[[ $# == 2 ]] || { echo 'expected kernel build directory and release' >&2; exit 2; }
kbuild=$1
release=$2
[[ "$release" == 7.2.9-2-cachyos ]] || { echo "unsupported kernel: $release" >&2; exit 2; }
[[ -f "$kbuild/.config" && -f "$kbuild/Module.symvers" && -f nouveau/Kbuild ]] || {
    echo 'missing prepared kernel configuration, Module.symvers, or patched source' >&2; exit 2;
}
actual=$(make -s -C "$kbuild" kernelrelease)
[[ "$actual" == "$release" ]] || { echo "kernelrelease mismatch: $actual" >&2; exit 2; }
exec make -C "$kbuild" LLVM=1 LLVM_IAS=1 M="$PWD/nouveau" modules
