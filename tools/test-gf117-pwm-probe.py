#!/usr/bin/env python3
from pathlib import Path
import subprocess
import sys
import tempfile

root = Path(sys.argv[1])
debugfs = (root / "drivers/gpu/drm/nouveau/nouveau_debugfs.c").read_text()
base = (root / "drivers/gpu/drm/nouveau/nvkm/engine/device/base.c").read_text()
therm = (root / "drivers/gpu/drm/nouveau/nvkm/subdev/therm/gf119.c").read_text()
marker = "/* GF117 uses gf119_therm_new(). Resolve the VBIOS VID_PWM line,"
assert marker in debugfs
probe = debugfs.split(marker, 1)[1].split("\n\t\t\t}", 1)[0]
for address in ("0x00d610 + gpio_line * 4", "0x00e114", "0x00e118", "0x00e11c",
                "0x00e120", "0x0200d8", "0x0200dc"):
    assert address in probe, address
assert "nvif_rd32" in probe
for forbidden in ("nvif_wr32", "nvkm_wr32", "nvif_mask", "nvkm_mask"):
    assert forbidden not in probe, forbidden
assert "nvkm_gpio_find(gpio, 0, DCB_GPIO_VID_PWM" in probe
assert "vid_pwm.line" in probe
assert probe.index("nvkm_gpio_find(gpio") < probe.index("switch (gpio_value")
assert "u32 div = 0, duty = 0;" in probe
assert "int pwm_route_valid = 0;" in probe
assert "pwm_index == 2 ||" in probe
assert "pwm_route_valid = 1;" in probe
channel_reads = {
    0: ("0x00e114", "0x00e118"),
    1: ("0x00e11c", "0x00e120"),
    2: ("0x0200d8", "0x0200dc"),
}
switch = probe.split("switch (pwm_index)", 1)[1]
for index, addresses in channel_reads.items():
    case = switch.split(f"case {index}:", 1)[1].split("break;", 1)[0]
    assert all(address in case for address in addresses), (index, addresses)
    for other_index, other_addresses in channel_reads.items():
        if index != other_index:
            assert not any(address in case for address in other_addresses), (index, other_index)
assert "default:\n\t\t\t\t\t\tbreak;" in switch
assert "vbios_vid_pwm_line=%d" in probe
assert "selected=%08x/%08x gpio_lookup=%d" in probe
for mapping in ("case 0x00: case 0x1e: pwm_index = 2;",
                "case 0x19: pwm_index = 1;",
                "case 0x1c: pwm_index = 0;"):
    assert mapping in probe, mapping
nvd7 = base.split("nvd7_chipset =", 1)[1].split("};", 1)[0]
assert '.therm    = { 0x00000001, gf119_therm_new }' in nvd7
assert 'gf117_pwm_diag' in probe

# Compile the real GF119 mux decoder too, so the debugfs probe is compared
# against the production PWM routing rather than a second copied table.
pwm_info = therm[therm.index("\npwm_info(") + 1:]
pwm_info = "static int\n" + pwm_info.split("\n}\n", 1)[0] + "\n}"

# Compile and execute the actual diagnostic block with mocked MMIO reads.
# This verifies mux routing, the GF119 special-mode read gate, and that
# invalid/inactive routes touch no candidate register. It does not emulate
# hardware behavior or voltage measurement.
block = probe[probe.index("\n\t\t\t{"):]
block += "\n\t\t\t}"
harness = r'''#include <stdarg.h>
#include <errno.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
typedef uint32_t u32;
struct nvif_object { int unused; };
struct nvkm_gpio { int unused; };
struct dcb_gpio_func { unsigned char line; };
struct nouveau_drm {
	struct { struct { struct nvif_object object; } device; } client;
	struct nvkm_gpio *gpio;
};
struct seq_file { char text[256]; };
struct nvkm_device { int unused; };
struct nvkm_subdev { struct nvkm_device *device; };
struct nvkm_therm { struct nvkm_subdev subdev; };
static u32 gpio_value;
static int vid_pwm_line;
static int gpio_lookup_result;
static u32 addresses[4];
static unsigned read_count;
static unsigned nvkm_gpio_reads;
#define DCB_GPIO_VID_PWM 0x81
#define nvxx_gpio(drm) ((drm)->gpio)
#define u8 unsigned char
static int nvkm_gpio_find(struct nvkm_gpio *gpio, int index, u8 tag, u8 line,
			  struct dcb_gpio_func *func)
{
	(void)gpio; (void)index; (void)tag; (void)line;
	if (gpio_lookup_result) return gpio_lookup_result;
	func->line = vid_pwm_line;
	return 0;
}
static u32 nvkm_rd32(struct nvkm_device *device, u32 address)
{
	(void)device;
	if (address != 0x00d610U + (u32)vid_pwm_line * 4) return 0xffffffff;
	nvkm_gpio_reads++;
	return gpio_value;
}
#define nvkm_error(...) do { } while (0)
static u32 nvif_rd32(struct nvif_object *object, u32 address)
{
	(void)object;
	if (read_count < sizeof(addresses) / sizeof(addresses[0]))
		addresses[read_count] = address;
	read_count++;
	if (address == 0x00d610U + (u32)vid_pwm_line * 4) return gpio_value;
	if (address == 0x00e114) return 0x11141114;
	if (address == 0x00e118) return 0x11181118;
	if (address == 0x00e11c) return 0x111c111c;
	if (address == 0x00e120) return 0x11201120;
	if (address == 0x0200d8) return 0x20d820d8;
	if (address == 0x0200dc) return 0x20dc20dc;
	return 0xffffffff;
}
static int seq_printf(struct seq_file *m, const char *format, ...)
{
	va_list args;
	va_start(args, format);
	int ret = vsnprintf(m->text, sizeof(m->text), format, args);
	va_end(args);
	return ret;
}
/* PWM_INFO_FUNCTION */
static void run_probe(struct nouveau_drm *ndrm, struct seq_file *m)
{
/* PROBE_BLOCK */
}
static int check(int line, u32 gpio, int index, int enabled, u32 first, u32 second,
		 u32 div, u32 duty)
{
	struct nvkm_gpio nvkm_gpio = {0};
	struct nouveau_drm drm = { .gpio = &nvkm_gpio };
	struct seq_file output = {0};
	struct nvkm_device device = {0};
	struct nvkm_therm pwm_therm = { .subdev = { .device = &device } };
	gpio_value = gpio;
	vid_pwm_line = line;
	gpio_lookup_result = 0;
	nvkm_gpio_reads = 0;
	int actual_index = pwm_info(&pwm_therm, line);
	if (index < 0) {
		if (actual_index != -ENODEV || nvkm_gpio_reads != 1) return 6;
	} else if (actual_index != index || nvkm_gpio_reads != 1) {
		return 7;
	}
	read_count = 0;
	memset(addresses, 0, sizeof(addresses));
	run_probe(&drm, &output);
	if (addresses[0] != 0x00d610U + (u32)line * 4) return 1;
	if (index < 0) {
		if (read_count != 1) return 2;
		char expected[160];
		snprintf(expected, sizeof(expected),
			 "vbios_vid_pwm_line=%d gpio=%08x pwm_index=-1 pwm_route_valid=0 "
			 "selected=00000000/00000000 gpio_lookup=0", line, gpio);
		if (!strstr(output.text, expected))
			return 3;
		return 0;
	}
	if (enabled) {
		if (read_count != 3 || addresses[1] != first || addresses[2] != second)
			return 4;
	} else if (read_count != 1) {
		return 8;
	}
	char expected[160];
	snprintf(expected, sizeof(expected),
		 "vbios_vid_pwm_line=%d gpio=%08x pwm_index=%d pwm_route_valid=%d "
		 "selected=%08x/%08x gpio_lookup=0",
		 line, gpio, index, enabled, div, duty);
	return strstr(output.text, expected) ? 0 : 5;
}
int main(void)
{
	if (check(11, 0x5c, 0, 1, 0x00e114, 0x00e118, 0x11141114, 0x11181118)) return 10;
	if (check(7, 0x59, 1, 1, 0x00e11c, 0x00e120, 0x111c111c, 0x11201120)) return 11;
	if (check(11, 0x1c, 0, 0, 0, 0, 0, 0)) return 16;
	if (check(11, 0x19, 1, 0, 0, 0, 0, 0)) return 17;
	if (check(11, 0x00, 2, 1, 0x0200d8, 0x0200dc, 0x20d820d8, 0x20dc20dc)) return 12;
	if (check(11, 0x1e, 2, 1, 0x0200d8, 0x0200dc, 0x20d820d8, 0x20dc20dc)) return 13;
	if (check(11, 0x9c, -1, 0, 0, 0, 0, 0)) return 14;
	if (check(11, 0x01, -1, 0, 0, 0, 0, 0)) return 15;
	struct nvkm_gpio gpio = {0};
	struct nouveau_drm drm = { .gpio = &gpio };
	struct seq_file output = {0};
	vid_pwm_line = 11;
	gpio_lookup_result = -ENOENT;
	read_count = 0;
	run_probe(&drm, &output);
	if (read_count != 0 || !strstr(output.text,
	    "vbios_vid_pwm_line=-1 gpio=00000000 pwm_index=-1 pwm_route_valid=0 "
	    "selected=00000000/00000000 gpio_lookup=-2")) return 18;
	vid_pwm_line = 32;
	gpio_lookup_result = 0;
	memset(&output, 0, sizeof(output));
	read_count = 0;
	run_probe(&drm, &output);
	if (read_count != 0 || !strstr(output.text,
	    "vbios_vid_pwm_line=-1 gpio=00000000 pwm_index=-1 pwm_route_valid=0 "
	    "selected=00000000/00000000 gpio_lookup=-34")) return 19;
	return 0;
}
'''.replace("/* PROBE_BLOCK */", block).replace(
    "/* PWM_INFO_FUNCTION */", pwm_info)
with tempfile.TemporaryDirectory(prefix="gf117-pwm-probe-") as directory:
    source = Path(directory) / "probe.c"
    binary = Path(directory) / "probe"
    source.write_text(harness)
    subprocess.run(["cc", "-std=c11", "-Wall", "-Wextra", "-Werror",
                    str(source), "-o", str(binary)], check=True)
    subprocess.run([str(binary)], check=True)
print("GF117/GF119 PWM probe: routed-source tests passed (mock reads only)")
