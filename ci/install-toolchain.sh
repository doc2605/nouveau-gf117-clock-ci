#!/usr/bin/env bash
set -euo pipefail
repo=$(cd "$(dirname "$0")/.." && pwd)
pkg_dir=$(mktemp -d)
trap 'rm -rf "$pkg_dir"' EXIT
cd "$pkg_dir"
file=LLVM-23.1.1-Linux-X64.tar.zst
url=https://github.com/llvm/llvm-project/releases/download/llvmorg-23.1.1/$file
curl --fail --location --http1.1 --connect-timeout 20 --max-time 900 \
    --retry 3 --retry-all-errors --retry-delay 2 --output "$file" "$url"
sha256sum -c "$repo/ci/toolchain.sha256"
prefix="$repo/work/llvm-23.1.1"
mkdir -p "$prefix"
tar --zstd -xf "$file" --strip-components=1 -C "$prefix"
"$prefix/bin/clang" --version
[[ "$("$prefix/bin/clang" -dumpversion)" == 23.1.1 ]]
"$prefix/bin/ld.lld" --version
echo "$prefix/bin" >> "$GITHUB_PATH"
