#!/usr/bin/env python3
"""Compile the actual hwmon voltage callback with isolated mock devices."""
import argparse
from pathlib import Path
import subprocess
import tempfile

parser = argparse.ArgumentParser()
parser.add_argument('source', type=Path)
root = parser.parse_args().source
text = (root / 'drivers/gpu/drm/nouveau/nouveau_hwmon.c').read_text()
start = text.index('\nnouveau_in_read(') + 1
brace = text.index('{', start)
end, depth = brace + 1, 1
while depth:
    depth += (text[end] == '{') - (text[end] == '}')
    end += 1
function = 'static int\n' + text[start:end]
prelude = r'''
#include <assert.h>
#include <errno.h>
#include <stdint.h>
#include <stdio.h>
typedef uint32_t u32;
enum { hwmon_in_input, hwmon_in_min, hwmon_in_max, other_attr };
enum { DRM_SWITCH_POWER_ON = 1 };
struct nvkm_volt { unsigned int min_uv, max_uv; int current_uv; };
struct nouveau_drm { struct nvkm_volt *volt; };
struct drm_device { int switch_power_state; struct nouveau_drm driver; };
struct device { struct drm_device *drm; };
static struct drm_device *dev_get_drvdata(struct device *d) { return d->drm; }
static struct nouveau_drm *nouveau_drm(struct drm_device *d) { return &d->driver; }
static struct nvkm_volt *nvxx_volt(struct nouveau_drm *d) { return d->volt; }
static int nvkm_volt_get(struct nvkm_volt *v) { return v->current_uv; }
'''
tests = r'''
int main(void) {
    struct nvkm_volt volt = {650000, 1150000, 900000};
    struct drm_device drm = {DRM_SWITCH_POWER_ON, {&volt}};
    struct device dev = {&drm}; long value = 12345;
    assert(nouveau_in_read(&dev, hwmon_in_input, 0, &value) == 0 && value == 900);
    volt.current_uv = -EIO; value = 12345;
    assert(nouveau_in_read(&dev, hwmon_in_input, 0, &value) == -EIO && value == 12345);
    volt.current_uv = -ENODEV;
    assert(nouveau_in_read(&dev, hwmon_in_input, 0, &value) == -ENODEV && value == 12345);
    drm.switch_power_state = 0;
    assert(nouveau_in_read(&dev, hwmon_in_input, 0, &value) == -EINVAL);
    assert(nouveau_in_read(&dev, hwmon_in_min, 0, &value) == 0 && value == 650);
    assert(nouveau_in_read(&dev, hwmon_in_max, 0, &value) == 0 && value == 1150);
    value = 12345; volt.min_uv = volt.max_uv = 0;
    assert(nouveau_in_read(&dev, hwmon_in_min, 0, &value) == -ENODEV && value == 12345);
    assert(nouveau_in_read(&dev, hwmon_in_max, 0, &value) == -ENODEV && value == 12345);
    assert(nouveau_in_read(&dev, other_attr, 0, &value) == -EOPNOTSUPP);
    drm.driver.volt = NULL;
    assert(nouveau_in_read(&dev, hwmon_in_input, 0, &value) == -EOPNOTSUPP);
    puts("PASS: hwmon voltage errors propagate; valid values retain mV units");
}
'''
with tempfile.TemporaryDirectory(prefix='gf117-hwmon-') as tmp:
    source = Path(tmp) / 'test.c'
    binary = Path(tmp) / 'test'
    source.write_text(prelude + function + tests)
    subprocess.run(['cc', '-std=c11', '-Wall', '-Wextra', '-Werror', '-Wno-unused-parameter',
                    '-fsanitize=undefined', '-fno-sanitize-recover=all', str(source), '-o', str(binary)], check=True)
    subprocess.run([str(binary)], check=True)
