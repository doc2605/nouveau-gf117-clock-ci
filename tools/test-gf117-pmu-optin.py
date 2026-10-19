#!/usr/bin/env python3
"""Exercise the experimental GF117 PMU constructor gate without hardware."""
from pathlib import Path
import hashlib
import os
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'work/cachyos-7.2.9-2/drivers/gpu/drm/nouveau'
PATCH = ROOT / 'experimental/patches/0044-nouveau-gf117-pmu-fuc3-explicit-optin.patch'

patch_text = PATCH.read_text()
assert 'gf117_pmu_new' in patch_text and 'NvGf117Pmu' in patch_text
assert not any(line.startswith('-') and 'gf119_pmu_new' in line
               for line in patch_text.splitlines())
assert 'nvkm/subdev/pmu/gf117.o' in patch_text
assert 'ramgf100.c' not in patch_text, 'experiment must not modify DDR3 execution path'

# Pin the four production files after applying the full patch stack. These
# hashes were compared with the clean-source application and the tree whose
# gf117.o was compiled locally; CI must build the same constructor/dispatch.
expected_sources = {
    'nvkm/engine/device/base.c':
        '97c7158a25fb10b603b43dd8b6e02f26e17da75442b7b388dec420142c2c52bc',
    'nvkm/subdev/pmu/Kbuild':
        '4c6fd9b1c9b13e99432d2abbef1147f3a64d6264c24690e8c66b377d091f5dee',
    'include/nvkm/subdev/pmu.h':
        '77be5e7541e627255b5d74612c9eb465f8758d56c0bc64ad49d62f1c9df64c33',
    'nvkm/subdev/pmu/gf117.c':
        '6cf6bf26eccff2b0bd9e224ea5e96a7097a0ae3f68f58c29e99e9fb812153d64',
}
if all((SRC / path).is_file() for path in expected_sources):
    for path, expected in expected_sources.items():
        actual = hashlib.sha256((SRC / path).read_bytes()).hexdigest()
        assert actual == expected, f'{path} differs from the locally compiled prototype: {actual}'
    print('PASS: clean patched source hashes match the locally compiled GF117 PMU prototype')
else:
    raise AssertionError('patched Nouveau source tree is incomplete; cannot verify exact source hashes')

# Compile the exact new C file carried by the applyable experimental patch.
marker = '+++ b/drivers/gpu/drm/nouveau/nvkm/subdev/pmu/gf117.c\n'
section = patch_text.split(marker, 1)[1]
section = section.split('\n--- ', 1)[0]
gate_source = '\n'.join(line[1:] for line in section.splitlines() if line.startswith('+')) + '\n'
assert '"NvGf117Pmu", false' in gate_source
start = gate_source.index('int\ngf117_pmu_new(')
brace = gate_source.index('{', start)
depth = 0
end = None
for i in range(brace, len(gate_source)):
    if gate_source[i] == '{':
        depth += 1
    elif gate_source[i] == '}':
        depth -= 1
        if depth == 0:
            end = i + 1
            break
assert end is not None, 'could not extract complete production gate function'
gate = gate_source[start:end]
assert '"NvGf117Pmu", false' in gate
assert gate.index('return -ENODEV;') < gate.index('return gf100_pmu_new(')

harness = r'''#include <assert.h>
#include <errno.h>
#include <stdbool.h>
#include <string.h>

struct nvkm_device { unsigned int chipset; const char *cfgopt; };
enum nvkm_subdev_type { NVKM_SUBDEV_PMU };
struct nvkm_pmu { int marker; };
static int delegate_calls, delegate_result;
static struct nvkm_pmu sentinel = { .marker = 0x117 };

static bool nvkm_boolopt(const char *opts, const char *name, bool fallback)
{
    if (!opts || strcmp(name, "NvGf117Pmu")) return fallback;
    if (!strcmp(opts, "NvGf117Pmu=1")) return true;
    if (!strcmp(opts, "NvGf117Pmu=0")) return false;
    return fallback;
}

int gf100_pmu_new(struct nvkm_device *device, enum nvkm_subdev_type type,
                  int inst, struct nvkm_pmu **out)
{
    (void)device; (void)type; (void)inst;
    delegate_calls++;
    *out = &sentinel;
    return delegate_result;
}

''' + gate + r'''

int main(void)
{
    struct nvkm_device dev = { .chipset = 0xd7, .cfgopt = NULL };
    struct nvkm_pmu *out = &sentinel;
    assert(gf117_pmu_new(&dev, NVKM_SUBDEV_PMU, -1, NULL) == -EINVAL);
    assert(delegate_calls == 0);
    assert(gf117_pmu_new(NULL, NVKM_SUBDEV_PMU, -1, &out) == -ENODEV);
    assert(out == NULL && delegate_calls == 0);
    out = &sentinel;
    assert(gf117_pmu_new(&dev, NVKM_SUBDEV_PMU, -1, &out) == -ENODEV);
    assert(out == NULL && delegate_calls == 0);
    dev.cfgopt = "NvGf117Pmu=0";
    out = &sentinel;
    assert(gf117_pmu_new(&dev, NVKM_SUBDEV_PMU, -1, &out) == -ENODEV);
    assert(out == NULL && delegate_calls == 0);
    dev.cfgopt = "NvGf117Pmu=1";
    dev.chipset = 0xd8;
    out = &sentinel;
    assert(gf117_pmu_new(&dev, NVKM_SUBDEV_PMU, -1, &out) == -ENODEV);
    assert(out == NULL && delegate_calls == 0);
    dev.chipset = 0xd7;
    assert(gf117_pmu_new(&dev, NVKM_SUBDEV_PMU, -1, &out) == 0);
    assert(delegate_calls == 1 && out == &sentinel);
    delegate_result = -ETIMEDOUT;
    assert(gf117_pmu_new(&dev, NVKM_SUBDEV_PMU, -1, &out) == -ETIMEDOUT);
    assert(delegate_calls == 2);
    return 0;
}
'''

if (SRC.is_dir() and (SRC / 'nvkm/subdev/fb/ramgf100.c').is_file()):
    ram = (SRC / 'nvkm/subdev/fb/ramgf100.c').read_text()
    calc = ram.split('gf100_ram_calc(', 1)[1].split('\n}\n', 1)[0]
    d7_hard_block = 'if (device->chipset == 0xd7)\n\t\treturn -EOPNOTSUPP;'
    experimental_hard_block = 'if (vbios_timing)\n\t\treturn -EOPNOTSUPP;'
    assert d7_hard_block in calc or experimental_hard_block in calc
    assert calc.index('return -EOPNOTSUPP;') < calc.index('ret = ram_init(')

with tempfile.TemporaryDirectory(prefix='gf117-pmu-gate-') as tmp:
    c = Path(tmp) / 'gate.c'
    exe = Path(tmp) / 'gate-test'
    c.write_text(harness)
    cc = os.environ.get('CC', 'cc')
    subprocess.run([cc, '-std=c11', '-Wall', '-Wextra', '-Werror', str(c), '-o', str(exe)], check=True)
    subprocess.run([str(exe)], check=True)

print('PASS: production constructor gate defaults off, rejects other chipsets, delegates only on explicit opt-in, and propagates errors')
print('PASS: GF119 dispatch is unchanged; GF117 DDR3 RAMFUC still returns -EOPNOTSUPP')
print('LIMIT: this host harness does not initialize or execute the Falcon firmware')
