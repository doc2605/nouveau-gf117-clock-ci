#!/usr/bin/env bash
# Run only in an ephemeral CI environment; never invoke dkms install.
set -euo pipefail
[[ $# == 2 ]] || { echo 'expected patched source root and kernel build directory' >&2; exit 2; }
source_root=$(realpath "$1")
kbuild=$(realpath "$2")
repo=$(cd "$(dirname "$0")/../.." && pwd)
base="$repo/work/dkms-sandbox"
pkg=nouveau-gf117-exp
ver=0.1.0
release=7.2.9-2-cachyos
[[ ! -e "$base" ]] || { echo "refusing existing DKMS sandbox: $base" >&2; exit 2; }
mkdir -p "$base/src/$pkg-$ver" "$base/state" "$base/install" "$base/tmp"
cp -a "$source_root/drivers/gpu/drm/nouveau" "$base/src/$pkg-$ver/nouveau"
cp "$repo/experimental/dkms/dkms.conf" "$repo/experimental/dkms/build-module.sh" "$base/src/$pkg-$ver/"
args=(--sourcetree "$base/src" --dkmstree "$base/state" --installtree "$base/install" --kernelsourcedir "$kbuild")
TMPDIR="$base/tmp" try_sign_modules=false dkms "${args[@]}" add -m "$pkg" -v "$ver" -k "$release"
TMPDIR="$base/tmp" try_sign_modules=false dkms "${args[@]}" build -m "$pkg" -v "$ver" -k "$release"
[[ -z "$(find "$base/install" -mindepth 1 -print -quit)" ]] || { echo 'unexpected install-tree write' >&2; exit 1; }
module="$base/state/$pkg/$ver/$release/$(uname -m)/module/nouveau.ko"
[[ -f "$module" ]] || { echo "DKMS module missing: $module" >&2; exit 1; }
modinfo -F vermagic "$module"
sha256sum "$module" > "$repo/ci-output/dkms-nouveau.ko.sha256"
zstd -T0 -6 -o "$repo/ci-output/dkms-nouveau.ko.zst" "$module"
cp "$base/state/$pkg/$ver/$release/$(uname -m)/log/make.log" "$repo/ci-output/dkms-make.log"
