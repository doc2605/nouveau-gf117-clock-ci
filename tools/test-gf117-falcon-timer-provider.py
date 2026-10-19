#!/usr/bin/env python3
"""Audit the isolated timer PMU provider and its hard recovery gate."""
from pathlib import Path
import os

root = Path(__file__).resolve().parents[1]
provider_path = root / "experimental/fermi/gf117-falcon-timer-probe/pmu_provider.c"
provider = provider_path.read_text()
nouveau = Path(os.environ.get("GF117_NOUVEAU_SRC", str(
    root / "work/cachyos-7.2.9-2/drivers/gpu/drm/nouveau")))
kbuild_path = nouveau / "nvkm/subdev/pmu/Kbuild"
dispatch_path = nouveau / "nvkm/engine/device/base.c"
gf117_path = nouveau / "nvkm/subdev/pmu/gf117.c"
if not kbuild_path.is_file() or not dispatch_path.is_file() or not gf117_path.is_file():
    print("SKIP: prepared Nouveau source unavailable for provider-dispatch audit")
    raise SystemExit(0)
prod_kbuild = kbuild_path.read_text()
dispatch = dispatch_path.read_text()
gf117 = gf117_path.read_text()

assert "#define GF117_TIMER_PROBE_RECOVERY_VERIFIED 0" in provider
assert '"NvGf117TimerProbe", false' in provider
gate = provider.split("gf117_timer_probe_pmu_new(", 1)[1].split("\n}", 1)[0]
assert gate.index("return -EOPNOTSUPP;") < gate.index("nvkm_pmu_new_(")
assert "device->chipset != 0xd7" in gate
assert "*ppmu = NULL;" in gate

init = provider.split("gf117_timer_probe_pmu_init(", 1)[1].split("\n}", 1)[0]
assert init.index("gt215_pmu_init(pmu)") < init.index("gf117_timer_probe_collect_pmu")
assert "ARRAY_SIZE(samples)" in init
assert "nvkm_memx" not in provider and "ramfuc" not in provider.lower()
assert ".code.data = gf117_timer_probe_pmu_code" in provider
assert ".data.data = gf117_timer_probe_pmu_data" in provider

# The experimental dispatch is wired, but default-off. Even an explicit option
# cannot construct the PMU while the compile-time recovery gate remains closed.
assert "nvkm/subdev/pmu/gf117_timer_probe.o" in prod_kbuild
assert "nvkm/subdev/pmu/gf117_timer_probe_pmu.o" in prod_kbuild
dispatch_body = gf117.split("gf117_pmu_new(", 1)[1].split("\n}", 1)[0]
assert dispatch_body.index('"NvGf117TimerProbe", false') < dispatch_body.index("gf117_timer_probe_pmu_new(")
assert dispatch_body.index("gf117_timer_probe_pmu_new(") < dispatch_body.index('"NvGf117Pmu", false')
chip = dispatch.split("nvd7_chipset = {", 1)[1].split("\n};", 1)[0]
assert ".pmu      = { 0x00000001, gf117_pmu_new }" in chip
print("PASS: timer provider is wired only through default-off opt-in and hard-blocked before PMU construction without verified recovery")
