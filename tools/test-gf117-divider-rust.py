#!/usr/bin/env python3
"""Differential-test GF117 Rust divider math against Nouveau's C helper."""
import argparse
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("source", type=Path, help="patched kernel source root")
parser.add_argument("rust_object", type=Path, help="host-compiled Rust object")
args = parser.parse_args()
cc = os.environ.get("CC", "cc")

gf100_path = args.source / "drivers/gpu/drm/nouveau/nvkm/subdev/clk/gf100.c"
gf100 = gf100_path.read_text()
matches = list(re.finditer(r"(?m)^calc_div\(", gf100))
if len(matches) != 1:
    raise SystemExit(f"expected one calc_div definition, found {len(matches)}")
start = matches[0].start()
brace = gf100.index("{", start)
end = brace + 1
depth = 1
while depth and end < len(gf100):
    depth += (gf100[end] == "{") - (gf100[end] == "}")
    end += 1
if depth != 0:
    raise SystemExit("could not find end of calc_div definition")
calc_div = "static u32\n" + gf100[start:end]

rust_path = args.source / "drivers/gpu/drm/nouveau/nvkm/subdev/clk/gf117_pll.rs"
rust_text = rust_path.read_text()
kbuild = (args.source / "drivers/gpu/drm/nouveau/Kbuild").read_text()
kconfig = (args.source / "drivers/gpu/drm/nouveau/Kconfig").read_text()
assert "CONFIG_DRM_NOUVEAU_GF117_RUST_GUARD" in kbuild
assert "nvkm/subdev/clk/gf117_pll.o" in kbuild
assert "depends on DRM_NOUVEAU && RUST" in kconfig
assert "chipset == 0xd7" in calc_div
assert "gf117_rust_calc_div(ref, freq)" in calc_div
assert "pub extern \"C\" fn gf117_rust_calc_div" in rust_text
assert "#[repr(C)]\npub struct Gf117DivResult" in rust_text
for forbidden in ("unsafe", "nvkm_rd32", "nvkm_wr32", "nvkm_mask", "nvkm_volt_set"):
    assert forbidden not in rust_text, f"unexpected unsafe/hardware operation: {forbidden}"

prefix = r"""
#include <assert.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
typedef uint32_t u32;
#define min(a, b) ((a) < (b) ? (a) : (b))
struct gf117_div_result { u32 freq, ddiv; };
_Static_assert(sizeof(struct gf117_div_result) == 8, "divider ABI size");
_Static_assert(_Alignof(struct gf117_div_result) == _Alignof(u32), "divider ABI alignment");
_Static_assert(offsetof(struct gf117_div_result, freq) == 0, "freq ABI offset");
_Static_assert(offsetof(struct gf117_div_result, ddiv) == 4, "ddiv ABI offset");
struct nvkm_device { int chipset; };
struct nvkm_subdev { struct nvkm_device *device; };
struct nvkm_clk { struct nvkm_subdev subdev; };
struct gf100_clk { struct nvkm_clk base; };
extern struct gf117_div_result gf117_rust_calc_div(u32 refclk, u32 freq);
"""

parity_main = r"""
static uint32_t rng_state = 0x6717f117u;
static uint32_t next_u32(void)
{
    rng_state ^= rng_state << 13;
    rng_state ^= rng_state >> 17;
    rng_state ^= rng_state << 5;
    return rng_state;
}

static void compare_case(u32 ref, u32 freq, unsigned int *count)
{
    u32 c_ddiv = 0xfeedu;
    u32 c_freq;
    struct gf117_div_result rust;

    assert(freq != 0);
    c_freq = calc_div(NULL, 0, ref, freq, &c_ddiv);
    rust = gf117_rust_calc_div(ref, freq);
    if (c_freq != rust.freq || c_ddiv != rust.ddiv) {
        fprintf(stderr,
                "divider mismatch: ref=%u freq=%u C=(%u,%u) Rust=(%u,%u)\n",
                ref, freq, c_freq, c_ddiv, rust.freq, rust.ddiv);
        abort();
    }
    ++*count;
}

int main(void)
{
    static const u32 values[] = {
        0, 1, 2, 3, 31, 32, 63, 64, 65, 66, 127, 128, 129,
        UINT32_MAX / 2 - 1, UINT32_MAX / 2, UINT32_MAX / 2 + 1,
        UINT32_MAX - 1, UINT32_MAX
    };
    unsigned int count = 0;
    struct gf117_div_result zero = gf117_rust_calc_div(1234, 0);

    assert(zero.freq == 0 && zero.ddiv == 0);
    for (unsigned int r = 0; r < sizeof(values) / sizeof(values[0]); ++r) {
        for (unsigned int f = 0; f < sizeof(values) / sizeof(values[0]); ++f) {
            if (values[f] != 0)
                compare_case(values[r], values[f], &count);
        }
    }
    /* Quotient boundaries below/at/above the 2 and 65 clamps. */
    compare_case(0, 1, &count);
    compare_case(1, 1, &count);
    compare_case(1, 2, &count);
    compare_case(65, 2, &count);   /* quotient 65 */
    compare_case(99, 3, &count);   /* quotient 66, capped at 65 */
    compare_case(UINT32_MAX / 2, 1, &count);
    compare_case(UINT32_MAX / 2 + 1, 1, &count); /* u32 multiply wraps */
    compare_case(UINT32_MAX, 1, &count);

    for (unsigned int i = 0; i < 100000; ++i) {
        u32 freq = next_u32();
        if (!freq)
            freq = 1;
        compare_case(next_u32(), freq, &count);
    }

    printf("PASS: Rust divider matches extracted Nouveau C calc_div on %u cases\n",
           count);
    return 0;
}
"""

route_stub = r"""
static unsigned int rust_calls;
struct gf117_div_result gf117_rust_calc_div(u32 ref, u32 freq)
{
    ++rust_calls;
    return (struct gf117_div_result){ .freq = ref ^ freq, .ddiv = 37 };
}

int main(void)
{
    struct nvkm_device device = { .chipset = 0xd7 };
    struct gf100_clk clk = { .base = { .subdev = { .device = &device } } };
    u32 ddiv = 0;
    assert(calc_div(&clk, 0, 123, 17, &ddiv) == (123u ^ 17u));
    assert(ddiv == 37 && rust_calls == 1);

    device.chipset = 0x50;
    ddiv = 0;
    assert(calc_div(&clk, 0, 65, 2, &ddiv) == 2);
    assert(ddiv == 63 && rust_calls == 1);
    puts("PASS: GF117 dispatches to Rust; other chipsets remain on C");
    return 0;
}
"""

with tempfile.TemporaryDirectory(prefix="gf117-divider-rust-") as temp:
    temp_path = Path(temp)

    def build_and_run(name: str, source: str, flags: list[str], objects: list[str]) -> None:
        cfile = temp_path / f"{name}.c"
        binary = temp_path / name
        cfile.write_text(source)
        subprocess.run([
            cc, "-std=gnu11", "-Wall", "-Wextra", "-Werror",
            "-Wno-unused-parameter", "-Wno-unused-function",
            "-fsanitize=undefined", "-fno-sanitize-recover=all",
            *flags, str(cfile), *objects, "-o", str(binary),
        ], check=True)
        result = subprocess.run([str(binary)], check=False, capture_output=True, text=True)
        if result.stdout:
            print(result.stdout, end="")
        if result.stderr:
            print(result.stderr, end="", file=sys.stderr)
        result.check_returncode()

    # With the option off, the exact source body is the C reference solver.
    off_probe = temp_path / "config_off.c"
    off_probe.write_text(prefix + calc_div + "int main(void) { return 0; }\n")
    parity_object = temp_path / "config_off.o"
    subprocess.run([
        cc, "-std=gnu11", "-Wall", "-Wextra", "-Werror",
        "-Wno-unused-parameter", "-Wno-unused-function", "-c",
        str(off_probe), "-o", str(parity_object),
    ], check=True)
    undefined = subprocess.run(["nm", "-u", str(parity_object)],
                               check=True, capture_output=True, text=True).stdout
    assert "gf117_rust_calc_div" not in undefined, undefined
    build_and_run("parity", prefix + calc_div + parity_main, [],
                  [str(args.rust_object)])

    # The real patched wrapper calls Rust only for GF117; exercise that branch
    # with a test stub so the symbol call count is observable.
    build_and_run("dispatch", prefix + "#define CONFIG_DRM_NOUVEAU_GF117_RUST_GUARD 1\n"
                  + calc_div + route_stub, [], [])
