#!/usr/bin/env python3
"""Check that the isolated GF117 PMU and timer-dispatch patches round-trip."""
from pathlib import Path
import os
import shutil
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
source = Path(os.environ.get("GF117_NOUVEAU_SRC", str(
    root / "work/cachyos-7.2.9-2/drivers/gpu/drm/nouveau")))
patches = [
    root / "experimental/patches/0044-nouveau-gf117-pmu-fuc3-explicit-optin.patch",
    root / "experimental/patches/0046-nouveau-gf117-falcon-timer-probe-dispatch.patch",
]
files = [
    "nvkm/engine/device/base.c",
    "nvkm/subdev/pmu/Kbuild",
    "include/nvkm/subdev/pmu.h",
    "nvkm/subdev/pmu/gf117.c",
]
if not all((source / name).is_file() for name in files):
    print("SKIP: prepared Nouveau source unavailable for experimental patch round-trip")
    raise SystemExit(0)

with tempfile.TemporaryDirectory(prefix="gf117-timer-patch-roundtrip-") as tmp:
    tree = Path(tmp)
    prefix = Path("drivers/gpu/drm/nouveau")
    for name in files:
        dest = tree / prefix / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source / name, dest)

    def apply(path, reverse=False):
        command = ["patch", "--batch", "--fuzz=0", "-p1", "-d", str(tree)]
        command.insert(1, "--reverse" if reverse else "--forward")
        with path.open("rb") as patch_file:
            result = subprocess.run(command, stdin=patch_file, check=False,
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.STDOUT)
        if result.returncode:
            raise RuntimeError(result.stdout.decode(errors="replace"))

    # Return to the unpatched baseline, then replay the exact experimental
    # series. This catches malformed hunks and ordering/context drift.
    for path in reversed(patches):
        apply(path, reverse=True)
    for path in patches:
        apply(path)

    for name in files:
        assert (tree / prefix / name).read_bytes() == (source / name).read_bytes(), name

print("PASS: experimental GF117 PMU and timer-dispatch patches apply in order and reproduce the prepared source exactly")
