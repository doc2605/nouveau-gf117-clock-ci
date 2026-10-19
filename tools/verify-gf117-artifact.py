#!/usr/bin/env python3
"""Verify the pinned GF117 module before adding it to an experimental boot."""
import hashlib
import json
import subprocess
import sys
from pathlib import Path


def verify(manifest_path: Path, module_path: Path, release: str) -> None:
    manifest = json.loads(manifest_path.read_text())
    if not isinstance(manifest, dict):
        raise ValueError("artifact manifest must be a JSON object")

    schema = manifest.get("schema")
    if schema not in (None, "gf117-nouveau-module/v1"):
        raise ValueError(f"unsupported artifact manifest schema: {schema}")

    manifest_release = _one_of(manifest, "kernel_release", "kernel")
    manifest_srcversion = _one_of(manifest, "srcversion", "module_srcversion")
    module_hash = hashlib.sha256(module_path.read_bytes()).hexdigest()
    vermagic = subprocess.check_output(
        ["modinfo", "-F", "vermagic", str(module_path)], text=True
    ).strip()
    srcversion = subprocess.check_output(
        ["modinfo", "-F", "srcversion", str(module_path)], text=True
    ).strip()

    if manifest_release != release:
        raise ValueError("pinned artifact manifest kernel release mismatch")
    if manifest.get("module_sha256") != module_hash:
        raise ValueError("pinned artifact SHA-256 does not match its manifest")
    if manifest.get("vermagic") != vermagic or vermagic.split()[0] != release:
        raise ValueError("pinned artifact vermagic does not match its manifest/kernel")
    if manifest_srcversion != srcversion:
        raise ValueError("pinned artifact srcversion does not match its manifest")


def _one_of(manifest: dict, primary: str, alias: str) -> str:
    """Read a schema field while rejecting ambiguous/conflicting aliases."""
    first = manifest.get(primary)
    second = manifest.get(alias)
    if first is not None and second is not None and first != second:
        raise ValueError(f"conflicting manifest fields: {primary} and {alias}")
    value = first if first is not None else second
    if not isinstance(value, str) or not value:
        raise ValueError(f"artifact manifest is missing {primary}")
    return value


def main() -> None:
    if len(sys.argv) != 4:
        raise SystemExit(
            "usage: verify-gf117-artifact.py <manifest.json> <nouveau.ko> <kernel-release>"
        )
    try:
        verify(Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3])
    except (OSError, json.JSONDecodeError, subprocess.CalledProcessError, ValueError) as exc:
        raise SystemExit(str(exc)) from exc
    print("PASS: pinned GF117 module matches manifest, vermagic, and srcversion")


if __name__ == "__main__":
    main()
