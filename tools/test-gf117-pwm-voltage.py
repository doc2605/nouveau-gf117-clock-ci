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
gf119 = (nouveau / "nvkm/subdev/therm/gf119.c")
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
struct nvkm_device { struct nvkm_therm *therm; u32 crystal; };
struct nvkm_subdev { struct nvkm_device *device; };
struct nvkm_therm { struct nvkm_subdev subdev; struct nvkm_therm_func *func; };
struct nvkm_volt { struct nvkm_subdev subdev; u32 min_uv, max_uv; };
struct nvbios_volt { u32 base, pwm_freq, pwm_range; };
struct gf117_volt { struct nvkm_volt base; struct nvbios_volt bios; u8 pwm_line; };
#define container_of(p,t,m) ((t *)((char *)(p) - offsetof(t,m)))
static u64 div_u64(u64 n, u32 d) { return n / d; }
static u32 test_div, test_duty, test_gpio;
static int test_line=11;
static unsigned read_count;
static int bad_read;
#define nvkm_error(...) do { } while (0)
static u32 nvkm_rd32(struct nvkm_device *device, u32 addr) {
    (void)device; read_count++;
    if (addr == 0x00d610 + (u32)test_line * 4) return test_gpio;
    if (addr == 0x00e114 || addr == 0x00e11c) return test_div;
    if (addr == 0x00e118 || addr == 0x00e120) return test_duty;
    if (addr == 0x0200d8) return test_div | 0xffffe000;
    if (addr == 0x0200dc) return test_duty | 0xffffe000;
    bad_read++;
    return 0xffffffff;
}
'''
source += function(base, "nvkm_therm_pwm_get")
source += function(base, "nvkm_therm_pwm_clock")
source += function(gf119, "pwm_info")
source += function(gf119, "gf119_fan_pwm_get")
source += function(gf119, "gf119_fan_pwm_clock")
source += function(volt, "gf117_volt_pwm_get")
source += r'''
int main(void) {
    struct nvkm_therm_func ops={gf119_fan_pwm_get,gf119_fan_pwm_clock};
    struct nvkm_device device={.crystal=27000};
    struct nvkm_therm therm={.subdev={.device=&device},.func=NULL};
    device.therm=&therm;
    struct gf117_volt volt={.base={.subdev={.device=&device},
        .min_uv=650000,.max_uv=1150000},
        .bios={.base=650000,.pwm_freq=172800,.pwm_range=500000},.pwm_line=11};
    int ret;
    assert(gf117_volt_pwm_get(&volt.base) == -ENODEV);
    therm.func=&ops;
    device.therm=NULL;
    assert(gf117_volt_pwm_get(&volt.base) == -ENODEV);
    device.therm=&therm;
    test_gpio=0x0000005c; /* special mode, route 0x1c -> PWM channel 0 */
    test_div=8; test_duty=3;
    ret=gf117_volt_pwm_get(&volt.base);
    assert(ret == 837500 && read_count > 0 && bad_read == 0);
    test_gpio=0x00000059; /* special mode, route 0x19 -> PWM channel 1 */
    read_count=0;
    assert(gf117_volt_pwm_get(&volt.base) == 837500 && read_count > 0);
    test_gpio=0x0000001e; /* route 0x1e -> PTHERM PWM channel 2 */
    test_div=16; read_count=0;
    assert(gf117_volt_pwm_get(&volt.base) == 743750 && read_count > 0);
    test_gpio=0x0000005c;
    test_div=8;
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
    test_div=8; device.crystal=0;
    assert(gf117_volt_pwm_get(&volt.base) == -ENODEV);
    device.crystal=27000; test_gpio=0x00000080;
    assert(gf117_volt_pwm_get(&volt.base) == -ENODEV);
    assert(bad_read == 0);
    puts("ok: GF117 voltage getter exercised production GF119 PWM route/register callbacks and VBIOS bounds");
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
