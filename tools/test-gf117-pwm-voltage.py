#!/usr/bin/env python3
"""Compile the production GF117 PWM readback and therm dispatch with mocks."""
from pathlib import Path
import subprocess
import tempfile
import sys

root = Path(sys.argv[1])
nouveau = root / "drivers/gpu/drm/nouveau"

def function(path, name, result_type="int"):
    text = path.read_text()
    start = text.index("\n" + name + "(") + 1
    brace = text.index("{", start)
    end = brace + 1
    depth = 1
    while depth:
        depth += (text[end] == "{") - (text[end] == "}")
        end += 1
    return result_type + "\n" + text[start:end] + "\n"

base = (nouveau / "nvkm/subdev/therm/base.c")
volt = (nouveau / "nvkm/subdev/volt/gf117.c")
source = r'''
#include <assert.h>
#include <errno.h>
#include <limits.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
typedef uint8_t u8; typedef uint32_t u32; typedef uint64_t u64;
struct nvkm_therm;
struct nvkm_therm_func {
    int (*pwm_get)(struct nvkm_therm *, int, u32 *, u32 *);
    int (*pwm_clock)(struct nvkm_therm *, int);
};
struct nvkm_therm { struct nvkm_therm_func *func; };
struct nvkm_device { struct nvkm_therm *therm; };
struct nvkm_subdev { struct nvkm_device *device; };
struct nvkm_volt { struct nvkm_subdev subdev; u32 min_uv, max_uv; };
struct nvbios_volt { u32 base, pwm_freq, pwm_range; };
struct gf117_volt { struct nvkm_volt base; struct nvbios_volt bios; u8 pwm_line; };
#define container_of(p,t,m) ((t *)((char *)(p) - offsetof(t,m)))
static u64 div_u64(u64 n, u32 d) { return n / d; }
static u32 test_div, test_duty;
static int test_clock, test_get_ret, test_get_calls;
static int mock_get(struct nvkm_therm *t, int line, u32 *divs, u32 *duty) {
    (void)t; assert(line == 11); test_get_calls++;
    if (test_get_ret) return test_get_ret;
    *divs=test_div; *duty=test_duty; return 0;
}
static int mock_clock(struct nvkm_therm *t, int line) {
    (void)t; assert(line == 11); return test_clock;
}
'''
source += function(base, "nvkm_therm_pwm_get")
source += function(base, "nvkm_therm_pwm_clock")
source += function(volt, "gf117_volt_pwm_get")
source += r'''
int main(void) {
    struct nvkm_therm_func ops={mock_get,mock_clock};
    struct nvkm_therm therm={NULL};
    struct nvkm_device device={&therm};
    struct gf117_volt volt={.base={.subdev={.device=&device},
        .min_uv=650000,.max_uv=1150000},
        .bios={.base=650000,.pwm_freq=172800,.pwm_range=500000},.pwm_line=11};
    int ret;
    assert(gf117_volt_pwm_get(&volt.base) == -ENODEV);
    therm.func=&ops;
    device.therm=NULL;
    assert(gf117_volt_pwm_get(&volt.base) == -ENODEV);
    device.therm=&therm;
    test_get_ret=-EIO;
    assert(gf117_volt_pwm_get(&volt.base) == -EIO);
    test_get_ret=0; test_clock=1350000; test_div=8; test_duty=3;
    ret=gf117_volt_pwm_get(&volt.base);
    assert(ret == 837500);
    test_duty=4; assert(gf117_volt_pwm_get(&volt.base) == 900000);
    volt.base.max_uv=850000;
    assert(gf117_volt_pwm_get(&volt.base) == -ERANGE);
    volt.base.max_uv=1150000; volt.base.min_uv=950000;
    assert(gf117_volt_pwm_get(&volt.base) == -ERANGE);
    volt.base.min_uv=1150001;
    assert(gf117_volt_pwm_get(&volt.base) == -ERANGE);
    volt.base.min_uv=650000;
    test_duty=8; assert(gf117_volt_pwm_get(&volt.base) == 1150000);
    test_duty=9; assert(gf117_volt_pwm_get(&volt.base) == -ERANGE);
    test_duty=3; test_div=7; assert(gf117_volt_pwm_get(&volt.base) == 864285);
    test_div=9; assert(gf117_volt_pwm_get(&volt.base) == -ERANGE);
    test_div=8; test_clock=-ENODEV;
    assert(gf117_volt_pwm_get(&volt.base) == -ENODEV);
    assert(test_get_calls == 11);
    puts("ok: GF117 PWM readback requires active GF119 route and VBIOS divider; voltage math and errors checked");
    return 0;
}
'''

with tempfile.TemporaryDirectory() as d:
    cfile = Path(d) / "test.c"
    binary = Path(d) / "test"
    cfile.write_text(source)
    subprocess.run(["cc", "-std=gnu11", "-O2", str(cfile), "-o", str(binary)],
                   check=True)
    subprocess.run([str(binary)], check=True)
