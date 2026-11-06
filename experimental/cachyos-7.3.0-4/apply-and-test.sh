#!/usr/bin/env bash
# Source-only compatibility check; this does not build or load a module.
set -euo pipefail
[[ $# == 1 || $# == 2 ]] || { echo 'usage: apply-and-test.sh <clean pinned kernel git checkout> [new output directory]' >&2; exit 2; }
source_root=$(realpath "$1")
repo=$(cd "$(dirname "$0")/../.." && pwd)
expected=6f1d90319ee9a72139f60d4547c2b44064ee2987
[[ "$(git -C "$source_root" rev-parse HEAD)" == "$expected" ]] || { echo 'kernel commit mismatch' >&2; exit 2; }
[[ -z "$(git -C "$source_root" status --porcelain --untracked-files=all -- drivers/gpu/drm/nouveau)" ]] || { echo 'Nouveau source is dirty' >&2; exit 2; }
if [[ $# == 2 ]]; then
    [[ ! -e "$2" ]] || { echo 'output directory already exists' >&2; exit 2; }
    work=$(realpath -m "$2")
    case "$work/" in "$source_root"/*) echo 'output must be outside the kernel checkout' >&2; exit 2;; esac
    mkdir -p "$work"
else
    work=$(mktemp -d)
    trap 'rm -rf "$work"' EXIT
fi
mkdir -p "$work/drivers/gpu/drm"
cp -a "$source_root/drivers/gpu/drm/nouveau" "$work/drivers/gpu/drm/nouveau"
for original in "$repo"/patches/nouveau/[0-9]*.patch; do
    name=${original##*/}
    adapted="$repo/experimental/cachyos-7.3.0-4/patches/$name"
    selected=$original
    [[ ! -f "$adapted" ]] || selected=$adapted
    sha256sum "$selected"
    patch --batch --fuzz=0 -d "$work" -p1 -i "$selected"
done
extra="$repo/experimental/cachyos-7.3.0-4/extra/0047-nouveau-hwmon-voltage-errors.patch"
sha256sum "$extra"
patch --batch --fuzz=0 -d "$work" -p1 -i "$extra"
extra="$repo/experimental/cachyos-7.3.0-4/extra/0048-nouveau-gf117-pwm-estimate-guard.patch"
sha256sum "$extra"
patch --batch --fuzz=0 -d "$work" -p1 -i "$extra"
extra="$repo/experimental/cachyos-7.3.0-4/extra/0049-nouveau-initialize-estimate-flag.patch"
sha256sum "$extra"
patch --batch --fuzz=0 -d "$work" -p1 -i "$extra"
extra="$repo/experimental/cachyos-7.3.0-4/extra/0050-nouveau-gf117-vid-preflight-guard.patch"
sha256sum "$extra"
patch --batch --fuzz=0 -d "$work" -p1 -i "$extra"
for test in core ram vga crtc worker pll; do
    python3 "$repo/tools/test-gf117-$test-source.py" "$work"
done
python3 "$repo/tools/test-gf117-pwm-probe.py" "$work"
python3 "$repo/tools/test-gf117-pwm-voltage.py" "$work"
python3 "$repo/tools/test-gf117-hwmon-voltage.py" "$work"
