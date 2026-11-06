#!/usr/bin/env python3
"""Differential-test the pure Rust PLL candidate against Nouveau's C source."""
import argparse
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("source", type=Path, help="patched kernel source root")
parser.add_argument("rust_object", type=Path, help="host-compiled Rust PLL object")
args = parser.parse_args()
cc = os.environ.get("CC", "cc")

text = (args.source / "drivers/gpu/drm/nouveau/nvkm/subdev/clk/pllgt215.c").read_text()
matches = list(re.finditer(r"(?m)^gt215_pll_calc\(", text))
if len(matches) != 1:
    raise SystemExit(f"expected one gt215_pll_calc definition, found {len(matches)}")
start = matches[0].start()
brace = text.index("{", start)
end = brace + 1
depth = 1
while depth and end < len(text):
    depth += (text[end] == "{") - (text[end] == "}")
    end += 1
if depth != 0:
    raise SystemExit("could not find end of gt215_pll_calc definition")

pll_rust_source = args.source / "drivers/gpu/drm/nouveau/nvkm/subdev/clk/gf117_pll.rs"
calc_function = ""
if pll_rust_source.exists():
    gf100 = (args.source / "drivers/gpu/drm/nouveau/nvkm/subdev/clk/gf100.c").read_text()
    calc_matches = list(re.finditer(r"(?m)^calc_pll\(", gf100))
    if len(calc_matches) != 1:
        raise SystemExit(f"expected one calc_pll definition, found {len(calc_matches)}")
    calc_start = calc_matches[0].start()
    calc_brace = gf100.index("{", calc_start)
    calc_end = calc_brace + 1
    depth = 1
    while depth and calc_end < len(gf100):
        depth += (gf100[calc_end] == "{") - (gf100[calc_end] == "}")
        calc_end += 1
    if depth != 0:
        raise SystemExit("could not find end of calc_pll definition")
    calc = gf100[calc_start:calc_end]
    calc_function = "static u32\n" + calc
    kbuild = (args.source / "drivers/gpu/drm/nouveau/Kbuild").read_text()
    kconfig = (args.source / "drivers/gpu/drm/nouveau/Kconfig").read_text()
    rust_text = pll_rust_source.read_text()
    assert "CONFIG_DRM_NOUVEAU_GF117_RUST_GUARD" in kbuild
    assert "nvkm/subdev/clk/gf117_pll.o" in kbuild
    assert "depends on DRM_NOUVEAU && RUST" in kconfig
    assert "subdev->device->chipset == 0xd7" in calc
    assert "struct gf117_pll_result { int ret, n, f_n, m, p; };" in gf100
    assert "gf117_rust_gt215_pll_calc(" in calc
    assert "ret = rust.ret;" in calc
    assert "else {\n\t\tret = gt215_pll_calc(subdev, &limits, freq, &N, NULL, &M, &P);" in calc
    assert "#else\n\tret = gt215_pll_calc(subdev, &limits, freq, &N, NULL, &M, &P);" in calc
    for forbidden in ("unsafe", "nvkm_rd32", "nvkm_wr32", "nvkm_mask", "nvkm_volt_set"):
        assert forbidden not in rust_text, f"unexpected hardware operation in Rust: {forbidden}"
    assert "#[repr(C)]" in rust_text
    assert 'pub extern "C" fn gf117_rust_gt215_pll_calc' in rust_text

prefix = r"""
#include <assert.h>
#include <errno.h>
#include <limits.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
_Static_assert(sizeof(int) == sizeof(int32_t), "kernel ABI int width");
typedef uint8_t u8; typedef uint32_t u32; typedef uint64_t u64; typedef int64_t s64;
struct nvkm_bios;
struct nvkm_device { struct nvkm_bios *bios; int chipset; };
struct nvkm_subdev { struct nvkm_device *device; };
struct nvbios_pll {
    u32 refclk; u8 min_p, max_p;
    struct { u32 max_freq, min_inputfreq, max_inputfreq;
             u8 min_m, max_m, min_n, max_n; } vco1;
};
struct nvkm_bios { struct nvbios_pll limits; };
struct nvkm_clk { struct nvkm_subdev subdev; };
struct gf100_clk { struct nvkm_clk base; };
#define max(a,b) ((a)>(b)?(a):(b))
#define min(a,b) ((a)<(b)?(a):(b))
#define div_u64(n,d) ((n)/(d))
#define unlikely(x) (x)
#define nvkm_error(...) ((void)(subdev))
struct gf117_pll_result { int32_t ret, n, f_n, m, p; };
_Static_assert(sizeof(struct gf117_pll_result) == 5 * sizeof(int32_t), "PLL result size");
_Static_assert(_Alignof(struct gf117_pll_result) == _Alignof(int32_t), "PLL result alignment");
_Static_assert(offsetof(struct gf117_pll_result, n) == 4, "PLL N offset");
_Static_assert(offsetof(struct gf117_pll_result, f_n) == 8, "PLL fN offset");
_Static_assert(offsetof(struct gf117_pll_result, m) == 12, "PLL M offset");
_Static_assert(offsetof(struct gf117_pll_result, p) == 16, "PLL P offset");
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
    if (c_ret <= 0 && (r.n != 0 || r.f_n != 0 || r.m != 0 || r.p != 0)) {
        fprintf(stderr, "Rust error result did not zero coefficient fields\n");
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
    /* Exact-endpoint bounds: 0013 changes the C divider interval to ceil/floor. */
    compare_case(&sd, &i, 510000, 0, &count);
    compare_case(&sd, &i, 510000, 1, &count);
    {
        int n = 0, m = 0, p = 0;
        int ret = gt215_pll_calc(&sd, &i, 510000, &n, NULL, &m, &p);
        assert(ret == 513000 && n == 38 && m == 1 && p == 2);
    }
    /* The patched C solver rejects an empty M interval instead of relaxing it. */
    i.vco1.min_inputfreq = 1000;
    i.vco1.max_inputfreq = 5000;
    i.vco1.max_m = 4;
    compare_case(&sd, &i, 510000, 0, &count);
    compare_case(&sd, &i, 510000, 1, &count);
    {
        int n = 0, m = 0, p = 0;
        assert(gt215_pll_calc(&sd, &i, 510000, &n, NULL, &m, &p) == -ERANGE);
    }
    i.vco1.min_inputfreq = 10000;
    i.vco1.max_inputfreq = 27000;
    i.vco1.max_m = 8;
    i.refclk = 1;
    i.vco1.max_freq = UINT32_MAX;
    i.vco1.min_inputfreq = 1;
    i.vco1.max_inputfreq = 1;
    i.vco1.min_m = i.vco1.max_m = 1;
    i.vco1.min_n = 1;
    i.vco1.max_n = 255;
    i.min_p = 1;
    i.max_p = 8;
    compare_case(&sd, &i, 1, 0, &count);
    compare_case(&sd, &i, 1, 1, &count);
    i.vco1.max_freq = 100;
    i.min_p = 1;
    i.max_p = 4;
    compare_case(&sd, &i, 1, 0, &count);
    i.vco1.max_freq = 1;
    i.min_p = 2;
    i.max_p = 4;
    compare_case(&sd, &i, 2, 0, &count);

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
    compare_case(&sd, &i, 16500, 2, &count);
    compare_case(&sd, &i, 16500, UINT32_MAX, &count);
    i.vco1.max_freq = 16000;
    i.vco1.min_n = i.vco1.max_n = 16;
    compare_case(&sd, &i, 16000, 0, &count);
    i.vco1.max_freq = 17500;
    compare_case(&sd, &i, 17500, 0, &count);
    i.vco1.max_freq = UINT32_MAX;
    i.vco1.min_n = 1;
    i.vco1.max_n = 255;
    i.min_p = 2;
    i.max_p = 4;
    compare_case(&sd, &i, 16000, 0, &count);

    i.refclk = 1001;
    i.vco1.max_freq = 16517;
    i.vco1.min_inputfreq = i.vco1.max_inputfreq = 1001;
    i.min_p = i.max_p = 1;
    compare_case(&sd, &i, 16516, 0, &count);
    compare_case(&sd, &i, 16516, 1, &count);

    i.refclk = 27000;
    i.vco1.min_inputfreq = 100000;
    i.vco1.max_inputfreq = 200000;
    i.vco1.min_m = 1;
    i.vco1.max_m = 8;
    i.vco1.min_n = 16;
    i.vco1.max_n = 255;
    i.min_p = 1;
    i.max_p = 8;
    compare_case(&sd, &i, 775000, 0, &count);
    compare_case(&sd, &i, 775000, 1, &count);

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

adapter_helpers = r"""
static int nvbios_pll_parse(struct nvkm_bios *bios, u32 reg,
                            struct nvbios_pll *limits)
{
    (void)reg;
    *limits = bios->limits;
    return 0;
}
static u32 read_div(struct gf100_clk *clk, int idx, u32 reg1, u32 reg2)
{
    (void)idx; (void)reg1; (void)reg2;
    return clk->base.subdev.device->bios->limits.refclk;
}
"""

production_adapter_test = r"""
static void test_production_adapter(void)
{
    struct nvkm_bios bios = { .limits = {
        .refclk = 27000, .min_p = 1, .max_p = 8,
        .vco1 = { .max_freq = 1200000, .min_inputfreq = 10000,
                  .max_inputfreq = 27000, .min_m = 1, .max_m = 8,
                  .min_n = 16, .max_n = 255 }
    } };
    struct nvkm_device device = { .bios = &bios, .chipset = 0xd7 };
    struct gf100_clk clk = { .base = { .subdev = { .device = &device } } };
    int n, m, p;
    unsigned int c_calls_before;
    u32 expected_coef = 0, coef = 0;
    int expected = gt215_pll_calc(&clk.base.subdev, &bios.limits, 775000,
                                  &n, NULL, &m, &p);
    expected_coef = (p << 16) | (n << 8) | m;
    c_calls_before = c_solver_calls;
    int got = calc_pll(&clk, 0, 775000, &coef);
    if (got != expected)
        fprintf(stderr, "GF117 adapter result mismatch: got=%d expected=%d coef=%u expected_coef=%u\n",
                got, expected, coef, expected_coef);
    if (coef != expected_coef)
        fprintf(stderr, "GF117 adapter coefficient mismatch: coef=%u expected=%u\n",
                coef, expected_coef);
    assert(got == expected);
    assert(coef == expected_coef);
#ifdef CONFIG_DRM_NOUVEAU_GF117_RUST_GUARD
    assert(c_solver_calls == c_calls_before);
    puts("PASS: GF117 PLL adapter uses Rust without calling the C solver");
#else
    assert(c_solver_calls == c_calls_before + 1);
    puts("PASS: Rust-disabled host adapter uses C for GF117");
#endif

    device.chipset = 0x50;
    coef = 0;
    c_calls_before = c_solver_calls;
    assert(calc_pll(&clk, 0, 775000, &coef) == expected);
    assert(coef == expected_coef);
    assert(c_solver_calls == c_calls_before + 1);
}
"""

fallback_adapter_test = r"""
static int rust_calls;
struct gf117_pll_result gf117_rust_gt215_pll_calc(
    uint32_t refclk, uint32_t max_freq, uint32_t min_inputfreq,
    uint32_t max_inputfreq, uint32_t min_m, uint32_t max_m,
    uint32_t min_n, uint32_t max_n, uint32_t min_p, uint32_t max_p,
    uint32_t freq, uint32_t fractional)
{
    (void)refclk; (void)max_freq; (void)min_inputfreq; (void)max_inputfreq;
    (void)min_m; (void)max_m; (void)min_n; (void)max_n; (void)min_p;
    (void)max_p; (void)freq; (void)fractional;
    ++rust_calls;
    return (struct gf117_pll_result){ .ret = -1, .n = 99, .m = 99, .p = 99 };
}

int main(void)
{
    struct nvkm_bios bios = { .limits = {
        .refclk = 27000, .min_p = 1, .max_p = 8,
        .vco1 = { .max_freq = 1200000, .min_inputfreq = 10000,
                  .max_inputfreq = 27000, .min_m = 1, .max_m = 8,
                  .min_n = 16, .max_n = 255 }
    } };
    struct nvkm_device device = { .bios = &bios, .chipset = 0xd7 };
    struct gf100_clk clk = { .base = { .subdev = { .device = &device } } };
    int n, m, p;
    unsigned int c_calls_before;
    u32 expected_coef, coef = 0;
    int expected = gt215_pll_calc(&clk.base.subdev, &bios.limits, 775000,
                                  &n, NULL, &m, &p);
    expected_coef = (p << 16) | (n << 8) | m;
    c_calls_before = c_solver_calls;
    coef = 0xdeadbeef;
    assert(calc_pll(&clk, 0, 775000, &coef) == 0);
    assert(coef == 0xdeadbeef);
    assert(c_solver_calls == c_calls_before);
    assert(rust_calls == 1);
    puts("PASS: GF117 Rust error yields no PLL and does not call the C solver");

    device.chipset = 0x50;
    coef = 0;
    c_calls_before = c_solver_calls;
    assert(calc_pll(&clk, 0, 775000, &coef) == expected);
    assert(coef == expected_coef);
    assert(c_solver_calls == c_calls_before + 1);
    assert(rust_calls == 1);
}
"""

c_solver = "int\n" + text[start:end]
c_solver = c_solver.replace("gt215_pll_calc(", "gt215_pll_calc_impl(", 1)
c_solver_wrapper = r"""
static unsigned int c_solver_calls;
static int gt215_pll_calc(struct nvkm_subdev *subdev, struct nvbios_pll *info,
                          u32 freq, int *pN, int *pfN, int *pM, int *P)
{
    ++c_solver_calls;
    return gt215_pll_calc_impl(subdev, info, freq, pN, pfN, pM, P);
}
"""

with tempfile.TemporaryDirectory(prefix="gf117-pll-rust-") as temp:
    def run_test(binary: Path) -> None:
        result = subprocess.run([str(binary)], check=False, capture_output=True, text=True)
        if result.stdout:
            print(result.stdout, end="")
        if result.stderr:
            print(result.stderr, end="", file=sys.stderr)
        result.check_returncode()

    cfile = Path(temp) / "test.c"
    binary = Path(temp) / "test"
    differential_main = main
    c_source = prefix + c_solver + c_solver_wrapper
    cflags = []
    if calc_function:
        c_source += adapter_helpers + calc_function
        cflags.append("-DCONFIG_DRM_NOUVEAU_GF117_RUST_GUARD")
        differential_main = differential_main.replace(
            '    puts("PASS: Rust GT215 PLL matches Nouveau C',
            '    test_production_adapter();\n    puts("PASS: Rust GT215 PLL matches Nouveau C',
        )
        c_source += production_adapter_test
    cfile.write_text(c_source + differential_main)
    subprocess.run([
        cc, "-std=gnu11", "-Wall", "-Wextra", "-Werror",
        *cflags,
        "-Wno-sign-compare", "-fsanitize=undefined", "-fno-sanitize-recover=all",
        str(cfile), str(args.rust_object), "-o", str(binary),
    ], check=True)
    run_test(binary)

    if calc_function:
        fallback = Path(temp) / "fallback.c"
        fallback_binary = Path(temp) / "fallback"
        fallback.write_text(prefix + c_solver + c_solver_wrapper + adapter_helpers
                            + calc_function + fallback_adapter_test)
        subprocess.run([
            cc, "-std=gnu11", "-Wall", "-Wextra", "-Werror",
            "-DCONFIG_DRM_NOUVEAU_GF117_RUST_GUARD",
            "-Wno-sign-compare", "-fsanitize=undefined", "-fno-sanitize-recover=all",
            str(fallback), "-o", str(fallback_binary),
        ], check=True)
        run_test(fallback_binary)

        c_only = Path(temp) / "c-only.c"
        c_only_binary = Path(temp) / "c-only"
        c_only_main = production_adapter_test + "\nint main(void) { test_production_adapter(); return 0; }\n"
        c_only.write_text(prefix + c_solver + c_solver_wrapper + adapter_helpers
                          + calc_function + c_only_main)
        subprocess.run([
            cc, "-std=gnu11", "-Wall", "-Wextra", "-Werror",
            "-Wno-sign-compare", "-fsanitize=undefined", "-fno-sanitize-recover=all",
            str(c_only), "-o", str(c_only_binary),
        ], check=True)
        run_test(c_only_binary)
