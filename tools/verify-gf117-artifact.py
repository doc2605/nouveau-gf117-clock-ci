#!/usr/bin/env python3
"""Verify a physical-test module against its CI manifest and local safety patches."""
import hashlib
import json
from pathlib import Path
import sys


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify(manifest_path: Path, module_path: Path, repo_root: Path, expected_hash: str) -> None:
    try:
        manifest = json.loads(manifest_path.read_text())
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"manifest missing or invalid: {error}") from error

    module_hash = sha256(module_path)
    if manifest.get("kernel") != "7.2.9-2-cachyos":
        raise ValueError("manifest identifies an incompatible kernel")
    if manifest.get("module_sha256") != module_hash or module_hash != expected_hash:
        raise ValueError("module hash does not match both manifest and external SHA-256")

    patch_dir = repo_root / "experimental/rust-nouveau"
    patch_names = (
        "0047-nouveau-hwmon-voltage-errors.patch",
        "0048-nouveau-gf117-pwm-estimate-guard.patch",
        "0049-nouveau-initialize-estimate-flag.patch",
        "0050-nouveau-gf117-vid-preflight-guard.patch",
    )
    expected_patches = {name: sha256(patch_dir / name) for name in patch_names}
    if manifest.get("safety_patches") != expected_patches:
        raise ValueError("manifest does not confirm local safety patches 0047–0050")


if __name__ == "__main__":
    if len(sys.argv) != 5:
        raise SystemExit("usage: verify-gf117-artifact.py MANIFEST MODULE REPO_ROOT EXPECTED_SHA256")
    try:
        verify(Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]), sys.argv[4])
    except (OSError, ValueError) as error:
        raise SystemExit(str(error))
    print("ok: module hash, kernel, and safety patch hashes verified")
