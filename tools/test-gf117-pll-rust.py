#!/usr/bin/env python3
"""Differential-test the pure Rust PLL candidate against Nouveau's C source."""
import argparse
import subprocess
import tempfile
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("source", type=Path, help="patched kernel source root")
parser.add_argument("rust_object", type=Path, help="host-compiled Rust PLL object")
args = parser.parse_args()

text = (args.source / "drivers/gpu/drm/nouveau/nvkm/subdev/clk/pllgt215.c").read_text()
start = text.index("\ngt215_pll_calc(") + 1

pll_rust_source = args.source / "drivers/gpu/drm/nouveau/nvkm/subdev/clk/gf117_pll.rs"
if pll_rust_source.exists():
    gf100 = (args.source / "drivers/gpu/drm/nouveau/nvkm/subdev/clk/gf100.c").read_text()
    calc_start = gf100.index("\ncalc_pll(") + 1
    calc_brace = gf100.index("{", calc_start)
    calc_end = calc_brace + 1
    depth = 1
    while depth:
        depth += (gf100[calc_end] == "{") - (gf100[calc_end] == "}")
        calc_end += 1
    calc = gf100[calc_start:calc_end]
    kbuild = (args.source / "drivers/gpu/drm/nouveau/Kbuild").read_text()
    kconfig = (args.source / "drivers/gpu/drm/nouveau/Kconfig").read_text()
    rust_text = pll_rust_source.read_text()
    assert "CONFIG_DRM_NOUVEAU_GF117_RUST_GUARD" in kbuild
    assert "nvkm/subdev/clk/gf117_pll.o" in kbuild
    assert "depends on DRM_NOUVEAU && RUST" in kconfig
    assert "subdev->device->chipset == 0xd7" in calc
    assert "gf117_rust_gt215_pll_calc(" in calc
    assert "gt215_pll_calc(subdev, &limits, freq, &N, NULL, &M, &P)" in calc
    assert "GF117 Rust PLL mismatch; retaining C result" in calc
    for forbidden in ("unsafe", "nvkm_rd32", "nvkm_wr32", "nvkm_mask", "nvkm_volt_set"):
        assert forbidden not in rust_text, f"unexpected hardware operation in Rust: {forbidden}"
    assert "#[repr(C)]" in rust_text
    assert 'pub extern "C" fn gf117_rust_gt215_pll_calc' in rust_text

prefix = r"""
#include <assert.h>
#include <errno.h>
#include <limits.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
typedef uint8_t u8; typedef uint32_t u32; typedef uint64_t u64; typedef int64_t s64;
struct nvkm_subdev { int unused; };
struct nvbios_pll {
    u32 refclk; u8 min_p, max_p;
    struct { u32 max_freq, min_inputfreq, max_inputfreq;
             u8 min_m, max_m, min_n, max_n; } vco1;
};
#define max(a,b) ((a)>(b)?(a):(b))
#define min(a,b) ((a)<(b)?(a):(b))
#define div_u64(n,d) ((n)/(d))
#define unlikely(x) (x)
#define nvkm_error(...) ((void)(subdev))
struct gf117_pll_result { int32_t ret, n, f_n, m, p; };
extern struct gf117_pll_result gf117_rust_gt215_pll_calc(
    uint32_t refclk, uint32_t max_freq, uint32_t min_inputfreq,
    uint32_t max_inputfreq, uint32_t min_m, uint32_t max_m,
    uint32_t min_n, uint32_t max_n, uint32_t min_p, uint32_t max_p,
    uint32_t freq, uint32_t fractional);
"""

main = r"""
static unsigned int rng_state = 0x6717f117u;
static uint32_t next_u32(void)
{
    rng_state ^= rng_state << 13;
    rng_state ^= rng_state >> 17;
    rng_state ^= rng_state << 5;
    return rng_state;
}

static void compare_case(struct nvkm_subdev *sd, struct nvbios_pll *i, u32 freq,
                         int fractional, unsigned int *count)
{
    int n = 0x1234567, f_n = 0x2345678, m = 0x3456789, p = 0x456789a;
    int c_ret = gt215_pll_calc(sd, i, freq, &n, fractional ? &f_n : NULL, &m, &p);
    struct gf117_pll_result r = gf117_rust_gt215_pll_calc(
        i->refclk, i->vco1.max_freq, i->vco1.min_inputfreq,
        i->vco1.max_inputfreq, i->vco1.min_m, i->vco1.max_m,
        i->vco1.min_n, i->vco1.max_n, i->min_p, i->max_p, freq,
        (uint32_t)fractional);
    if (c_ret != r.ret) {
        fprintf(stderr, "return mismatch: c=%d rust=%d freq=%u ref=%u frac=%d\n",
                c_ret, r.ret, freq, i->refclk, fractional);
        abort();
    }
    if (c_ret > 0 && (n != r.n || m != r.m || p != r.p ||
                      (fractional && f_n != r.f_n))) {
        fprintf(stderr, "coefficient mismatch: c=(%d,%d,%d,%d) rust=(%d,%d,%d,%d)\n",
                n, f_n, m, p, r.n, r.f_n, r.m, r.p);
        abort();
    }
    ++*count;
}

int main(void)
{
    struct nvkm_subdev sd = {0};
    struct nvbios_pll i = {
        .refclk = 27000, .min_p = 1, .max_p = 8,
        .vco1 = { .max_freq = 1200000, .min_inputfreq = 10000,
                  .max_inputfreq = 27000, .min_m = 1, .max_m = 8,
                  .min_n = 16, .max_n = 255 }
    };
    unsigned int count = 0;
    static const u32 edge_values[] = {
        0, 1, 2, 3, 7, 15, 16, 17, 255, 256, 65535, 65536,
        INT_MAX - 1u, INT_MAX, INT_MAX + 1u, UINT32_MAX
    };

    compare_case(&sd, &i, 775000, 0, &count);
    compare_case(&sd, &i, 775000, 1, &count);
    i.refclk = 1000;
    i.vco1.max_freq = 16501;
    i.vco1.min_inputfreq = 1000;
    i.vco1.max_inputfreq = 1000;
    i.vco1.min_m = i.vco1.max_m = 1;
    i.vco1.min_n = 1;
    i.vco1.max_n = 255;
    i.min_p = i.max_p = 1;
    compare_case(&sd, &i, 16499, 0, &count);
    compare_case(&sd, &i, 16500, 0, &count);
    compare_case(&sd, &i, 16501, 0, &count);
    compare_case(&sd, &i, 16499, 1, &count);
    compare_case(&sd, &i, 16500, 1, &count);
    compare_case(&sd, &i, 16501, 1, &count);

    for (unsigned int x = 0; x < 10000; ++x) {
        i.refclk = 10000 + next_u32() % 1000000;
        i.vco1.max_freq = 200000 + next_u32() % 3000000;
        i.vco1.min_inputfreq = i.refclk / 10;
        i.vco1.max_inputfreq = i.refclk;
        i.vco1.min_m = 1;
        i.vco1.max_m = 10;
        i.vco1.min_n = 1 + (u8)(next_u32() % 32);
        i.vco1.max_n = 255;
        i.min_p = 1;
        i.max_p = 8;
        u32 freq = 1 + next_u32() % 2000000;
        compare_case(&sd, &i, freq, 0, &count);
        compare_case(&sd, &i, freq, 1, &count);
    }

    for (unsigned int x = 0; x < sizeof(edge_values)/sizeof(edge_values[0]); ++x) {
        i.refclk = edge_values[x];
        i.vco1.max_freq = edge_values[(x + 3) % (sizeof(edge_values)/sizeof(edge_values[0]))];
        i.vco1.min_inputfreq = edge_values[(x + 5) % (sizeof(edge_values)/sizeof(edge_values[0]))];
        i.vco1.max_inputfreq = edge_values[(x + 7) % (sizeof(edge_values)/sizeof(edge_values[0]))];
        i.vco1.min_m = (u8)edge_values[(x + 9) % (sizeof(edge_values)/sizeof(edge_values[0]))];
        i.vco1.max_m = (u8)edge_values[(x + 11) % (sizeof(edge_values)/sizeof(edge_values[0]))];
        i.vco1.min_n = (u8)edge_values[(x + 13) % (sizeof(edge_values)/sizeof(edge_values[0]))];
        i.vco1.max_n = (u8)edge_values[(x + 15) % (sizeof(edge_values)/sizeof(edge_values[0]))];
        i.min_p = (u8)edge_values[(x + 1) % (sizeof(edge_values)/sizeof(edge_values[0]))];
        i.max_p = (u8)edge_values[(x + 2) % (sizeof(edge_values)/sizeof(edge_values[0]))];
        compare_case(&sd, &i, edge_values[(x + 4) % (sizeof(edge_values)/sizeof(edge_values[0]))], 0, &count);
        compare_case(&sd, &i, edge_values[(x + 6) % (sizeof(edge_values)/sizeof(edge_values[0]))], 1, &count);
    }

    for (unsigned int x = 0; x < 50000; ++x) {
        i.refclk = next_u32();
        i.vco1.max_freq = next_u32();
        i.vco1.min_inputfreq = next_u32();
        i.vco1.max_inputfreq = next_u32();
        i.vco1.min_m = (u8)next_u32();
        i.vco1.max_m = (u8)next_u32();
        i.vco1.min_n = (u8)next_u32();
        i.vco1.max_n = (u8)next_u32();
        i.min_p = (u8)next_u32();
        i.max_p = (u8)next_u32();
        u32 freq = next_u32();
        compare_case(&sd, &i, freq, 0, &count);
        compare_case(&sd, &i, freq, 1, &count);
    }

    puts("PASS: Rust GT215 PLL matches Nouveau C on half-reference boundaries, 10,000 valid and 50,000 randomized tuples (integer and fractional)");
    return 0;
}
"""

with tempfile.TemporaryDirectory(prefix="gf117-pll-rust-") as temp:
    cfile = Path(temp) / "test.c"
    binary = Path(temp) / "test"
    cfile.write_text(prefix + "int\n" + text[start:] + main)
    subprocess.run([
        "cc", "-std=gnu11", "-Wall", "-Wextra", "-Werror",
        "-Wno-sign-compare", "-fsanitize=undefined", "-fno-sanitize-recover=all",
        str(cfile), str(args.rust_object), "-o", str(binary),
    ], check=True)
    subprocess.run([str(binary)], check=True)
