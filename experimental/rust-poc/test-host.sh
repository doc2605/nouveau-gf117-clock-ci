#!/bin/sh
set -eu
root=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT HUP INT TERM
rustc --edition=2021 --crate-type=lib --emit=obj -C panic=abort -C opt-level=2 "$root/limits.rs" -o "$tmp/limits.o"
cc -std=c11 -Wall -Wextra -Werror "$root/test.c" "$tmp/limits.o" -o "$tmp/test"
"$tmp/test"
