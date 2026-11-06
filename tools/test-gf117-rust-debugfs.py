#!/usr/bin/env python3
"""Compare the actual Nouveau debugfs helper's C fallback and Rust paths."""
import sys
from pathlib import Path
import subprocess
import tempfile


if len(sys.argv) != 3:
    raise SystemExit("usage: test-gf117-rust-debugfs.py <kernel-source> <rust-object>")
source = Path(sys.argv[1]) / "drivers/gpu/drm/nouveau/nouveau_debugfs.c"
volt_source = Path(sys.argv[1]) / "drivers/gpu/drm/nouveau/nvkm/subdev/volt/base.c"
rust_object = Path(sys.argv[2])
text = source.read_text()
def extract_function(name):
    start = text.index("\n" + name + "(") + 1
    brace = text.index("{", start)
    end = brace + 1
    depth = 1
    while depth:
        depth += (text[end] == "{") - (text[end] == "}")
        end += 1
    return "static int\n" + text[start:end]


helper = extract_function("nouveau_debugfs_validate_voltage_range_c")
helper += extract_function("nouveau_debugfs_validate_voltage_plan")

callback_start = text.index("\nnouveau_debugfs_pstate_plan_get(") + 1
callback_brace = text.index("{", callback_start)
callback_end = callback_brace + 1
depth = 1
while depth:
    depth += (text[callback_end] == "{") - (text[callback_end] == "}")
    callback_end += 1
callback = text[callback_start:callback_end]
assert "chipset == 0xd7" in callback
assert "nouveau_debugfs_validate_voltage_plan(clk, &cstate)" in callback
assert "voltage_plan_check" in callback
assert "nvkm_wr32" not in callback and "nvkm_mask" not in callback

volt_text = volt_source.read_text()
map_start = volt_text.index("\nnvkm_volt_map(") + 1
map_brace = volt_text.index("{", map_start)
map_end = map_brace + 1
depth = 1
while depth:
    depth += (volt_text[map_end] == "{") - (volt_text[map_end] == "}")
    map_end += 1
voltage_map = volt_text[map_start:map_end]
assert "nvkm_rd32" not in voltage_map and "nvkm_wr32" not in voltage_map
assert "nvkm_mask" not in voltage_map and "nvkm_volt_get" not in voltage_map
assert "nvkm_volt_set_id" not in voltage_map

stub = r'''
#include <assert.h>
#include <errno.h>
#include <stdint.h>
typedef uint8_t u8;
struct nvkm_volt { int target_uv; unsigned int min_uv, max_uv; };
struct nvkm_device { struct nvkm_volt *volt; int chipset; };
struct nvkm_subdev { struct nvkm_device *device; };
struct nvkm_clk { struct nvkm_subdev subdev; int temp; };
struct nvkm_cstate { int voltage; };
static int map_calls;
static int nvkm_volt_map(struct nvkm_volt *volt, u8 id, u8 temperature)
{ assert(id == 17 && temperature == 30); map_calls++; return volt->target_uv; }
extern int gf117_rust_validate_voltage_range(int target_uv, int min_uv, int max_uv);
'''
main = r'''
int main(void)
{
    struct nvkm_volt volt = { .target_uv = 800000, .min_uv = 700000, .max_uv = 1000000 };
    struct nvkm_device device = { .volt = &volt, .chipset = 0xd7 };
    struct nvkm_clk clk = { .subdev = { .device = &device }, .temp = 30 };
    struct nvkm_cstate state = { .voltage = 17 };
    assert(nouveau_debugfs_validate_voltage_range_c(800000, 700000, 1000000) == 0);
    assert(nouveau_debugfs_validate_voltage_range_c(600000, 700000, 1000000) == -3);
    assert(nouveau_debugfs_validate_voltage_range_c(800000, 1000000, 700000) == -2);
    assert(nouveau_debugfs_validate_voltage_plan(&clk, &state) == 0);
    assert(map_calls == 1);
    volt.target_uv = 600000;
    assert(nouveau_debugfs_validate_voltage_plan(&clk, &state) == -3);
    volt.target_uv = 800000; volt.min_uv = 1000000; volt.max_uv = 700000;
    assert(nouveau_debugfs_validate_voltage_plan(&clk, &state) == -2);
    device.volt = 0;
    assert(nouveau_debugfs_validate_voltage_plan(&clk, &state) == -1);
    return 0;
}
'''

with tempfile.TemporaryDirectory(prefix="gf117-rust-debugfs-test-") as temp:
    for mode, flags, libraries in [
        ("rust", ["-DCONFIG_DRM_NOUVEAU_GF117_RUST_GUARD"], [str(rust_object)]),
        ("c-fallback", [], []),
    ]:
        cfile = Path(temp) / f"{mode}.c"
        binary = Path(temp) / mode
        cfile.write_text(stub + helper + main)
        subprocess.run(["cc", "-std=gnu11", "-Wall", "-Wextra", "-Werror",
                        *flags, str(cfile), *libraries, "-o", str(binary)], check=True)
        subprocess.run([str(binary)], check=True)

print("PASS: Nouveau's actual debugfs helper matches C fallback and Rust across accepted and rejected voltage plans")
