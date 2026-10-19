#!/usr/bin/env bash
set -euo pipefail
repo=$(cd "$(dirname "$0")/.." && pwd)
cd "$repo"
mkdir -p ci-output work
exec > >(tee ci-output/build.log) 2>&1
[[ "$(clang -dumpversion)" == 23.1.1 ]] || {
    echo "Expected Clang 23.1.1; found $(clang -dumpversion)" >&2; exit 1;
}
clang --version
(cd ci && sha256sum -c kernel-7.2.9-2-headers.sha256)
tar --zstd -xf ci/kernel-7.2.9-2-headers.tar.zst -C work
curl --fail --location --retry 3 --output work/source.tar.gz \
    https://github.com/CachyOS/linux/releases/download/cachyos-7.2.9-2/cachyos-7.2.9-2.tar.gz
printf '%s  %s\n' 2da9e6ffe31436657f46909db059059946dac22c2ac6cde05e49a66d61acfcba work/source.tar.gz | sha256sum -c -
tar -xzf work/source.tar.gz -C work cachyos-7.2.9-2/drivers/gpu/drm/nouveau
src="$repo/work/cachyos-7.2.9-2"
patch --batch --fuzz=0 -d "$src" -p1 \
    -i "$repo/patches/nouveau/gf117-consolidated.patch"
patch --batch --fuzz=0 -d "$src" -p1 \
    -i "$repo/experimental/patches/0044-nouveau-gf117-pmu-fuc3-explicit-optin.patch"
patch --batch --fuzz=0 -d "$src" -p1 \
    -i "$repo/experimental/patches/0045-nouveau-gf117-ddr3-hard-block.patch"
patch --batch --fuzz=0 -d "$src" -p1 \
    -i "$repo/experimental/patches/0046-nouveau-gf117-falcon-timer-probe-dispatch.patch"
probe_dir="$src/drivers/gpu/drm/nouveau/nvkm/subdev/pmu"
mkdir -p "$probe_dir/fuc"
cp experimental/fermi/gf117-falcon-timer-probe/host.c \
    "$probe_dir/gf117_timer_probe.c"
cp experimental/fermi/gf117-falcon-timer-probe/host.h \
    "$probe_dir/host.h"
cp experimental/fermi/gf117-falcon-timer-probe/pmu_provider.c \
    "$probe_dir/gf117_timer_probe_pmu.c"
cp experimental/fermi/gf117-falcon-timer-probe/gf117_timer_probe.fuc3.h \
    "$probe_dir/fuc/gf117_timer_probe.fuc3.h"
python3 tools/test-gf117-pmu-optin.py
GF117_NOUVEAU_SRC="$src/drivers/gpu/drm/nouveau" \
    python3 tools/test-gf117-falcon-timer-provider.py
GF117_NOUVEAU_SRC="$src/drivers/gpu/drm/nouveau" \
    python3 tools/test-gf117-falcon-timer-patches.py
for test in core ram vga crtc worker pll; do
    python3 "tools/test-gf117-$test-source.py" "$src"
done
python3 tools/test-gf117-pwm-probe.py "$src"
python3 tools/test-gf117-pwm-voltage.py "$src"
python3 tools/test-gf117-core-helper.py
bash -n tools/test-gf117-core-once.sh
make -C "$repo/work/build" LLVM=1 LLVM_IAS=1 -j"$(nproc)" \
    M="$src/drivers/gpu/drm/nouveau" modules
module="$src/drivers/gpu/drm/nouveau/nouveau.ko"
[[ "$(modinfo -F vermagic "$module" | xargs)" == '7.2.9-2-cachyos SMP preempt mod_unload' ]]
llvm-nm --defined-only "$module" > ci-output/nouveau.symbols
grep -q 'gf117_pmu_new' ci-output/nouveau.symbols
grep -q 'gf117_timer_probe_pmu_new' ci-output/nouveau.symbols
grep -a -q 'NvGf117Pmu' "$module"
grep -a -q 'NvGf117TimerProbe' "$module"
python3 - "$module" <<'MANIFEST'
import hashlib,json,os,subprocess,sys
from pathlib import Path
module=Path(sys.argv[1]);root=Path.cwd()
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
manifest=dict(kernel='7.2.9-2-cachyos',commit=os.environ.get('GITHUB_SHA'),
    schema='gf117-nouveau-module/v1',kernel_release='7.2.9-2-cachyos',
    module_sha256=sha(module),
    srcversion=subprocess.check_output(['modinfo','-F','srcversion',str(module)],text=True).strip(),
    source_sha256=sha(root/'work/source.tar.gz'),
    headers_sha256=sha(root/'ci/kernel-7.2.9-2-headers.tar.zst'),
    config_sha256=sha(root/'work/build/.config'),
    symvers_sha256=sha(root/'work/build/Module.symvers'),
    compiler=subprocess.check_output(['clang','--version'],text=True).splitlines()[0],
    vermagic=subprocess.check_output(['modinfo','-F','vermagic',str(module)],text=True).strip(),
    source_files={name:sha(root/'work/cachyos-7.2.9-2/drivers/gpu/drm/nouveau'/name)
        for name in ('nvkm/engine/device/base.c','nvkm/subdev/pmu/Kbuild',
                     'include/nvkm/subdev/pmu.h','nvkm/subdev/pmu/gf117.c',
                     'nvkm/subdev/fb/ramgf100.c')},
    patches={'consolidated':sha(root/'patches/nouveau/gf117-consolidated.patch'),
        'experimental_pmu':sha(root/'experimental/patches/0044-nouveau-gf117-pmu-fuc3-explicit-optin.patch'),
        'ddr3_hard_block':sha(root/'experimental/patches/0045-nouveau-gf117-ddr3-hard-block.patch'),
        'falcon_timer_dispatch':sha(root/'experimental/patches/0046-nouveau-gf117-falcon-timer-probe-dispatch.patch')},
    timer_probe_files={name:sha(root/'experimental/fermi/gf117-falcon-timer-probe'/name)
        for name in ('gf117_timer_probe.fuc3','gf117_timer_probe.fuc3.h',
                     'test.fuc','host.h','host.c','gf117_kernel.fuc',
                     'gf117_idle.fuc','pmu_provider.c')})
(root/'ci-output/manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(json.dumps(manifest,indent=2))
MANIFEST
python3 tools/test-verify-gf117-artifact.py
python3 tools/verify-gf117-artifact.py ci-output/manifest.json "$module" 7.2.9-2-cachyos
zstd -T0 -6 -o ci-output/nouveau.ko.zst "$module"
sha256sum ci-output/nouveau.ko.zst > ci-output/nouveau.ko.zst.sha256
