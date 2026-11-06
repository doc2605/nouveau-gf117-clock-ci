#!/usr/bin/env python3
"""Verify module identity against an explicit standard or DKMS artifact hash."""
import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path


def verify(manifest_path: Path, module_path: Path, release: str,
           artifact_kind: str = "standard", sha256_file: Path | None = None) -> dict[str, str]:
    manifest = json.loads(manifest_path.read_text())
    if not isinstance(manifest, dict):
        raise ValueError("artifact manifest must be a JSON object")

    schema = manifest.get("schema")
    if schema not in (None, "gf117-nouveau-module/v1"):
        raise ValueError(f"unsupported artifact manifest schema: {schema}")

    manifest_release = _one_of(manifest, "kernel_release", "kernel")
    manifest_srcversion = _one_of(manifest, "srcversion", "module_srcversion")
    module_hash = hashlib.sha256(module_path.read_bytes()).hexdigest()
    if artifact_kind == "standard":
        expected_hash = manifest.get("module_sha256")
        if sha256_file is not None:
            raise ValueError("--sha256-file is only valid with --artifact-kind dkms")
    elif artifact_kind == "dkms":
        if sha256_file is None:
            raise ValueError("DKMS verification requires an explicit --sha256-file")
        expected_hash, sidecar_name = _read_sha256_sidecar(sha256_file)
        if Path(sidecar_name).name != module_path.name:
            raise ValueError("DKMS sidecar names a different module file")
        manifest_dkms_hash = manifest.get("dkms_module_sha256")
        if manifest_dkms_hash is not None and manifest_dkms_hash != expected_hash:
            raise ValueError("DKMS sidecar hash does not match manifest DKMS hash")
        if manifest_dkms_hash is None:
            raise ValueError("artifact manifest is missing dkms_module_sha256")
    else:
        raise ValueError(f"unsupported artifact kind: {artifact_kind}")

    name = _modinfo(module_path, "name")
    vermagic = _modinfo(module_path, "vermagic")
    srcversion = _modinfo(module_path, "srcversion")
    signer = _modinfo(module_path, "signer")

    if manifest_release != release:
        raise ValueError("pinned artifact manifest kernel release mismatch")
    if not isinstance(expected_hash, str) or not re.fullmatch(r"[0-9a-f]{64}", expected_hash):
        raise ValueError(f"manifest is missing a valid {artifact_kind} module SHA-256")
    if expected_hash != module_hash:
        raise ValueError(f"pinned {artifact_kind} module SHA-256 does not match its expected hash")
    if name != "nouveau":
        raise ValueError(f"unexpected module name: {name!r}")
    expected_vermagic = (manifest.get("dkms_vermagic") if artifact_kind == "dkms"
                         else manifest.get("vermagic"))
    if not isinstance(expected_vermagic, str) or not expected_vermagic:
        raise ValueError(f"manifest is missing {artifact_kind} vermagic")
    if vermagic != expected_vermagic or vermagic.split()[0] != release:
        raise ValueError(f"pinned {artifact_kind} vermagic does not match its manifest/kernel")
    if srcversion != manifest_srcversion:
        raise ValueError("pinned artifact srcversion does not match its manifest")
    if artifact_kind == "dkms" and manifest.get("dkms_srcversion") != srcversion:
        raise ValueError("DKMS srcversion does not match its manifest")
    return {"name": name, "sha256": module_hash, "vermagic": vermagic,
            "srcversion": srcversion, "signer": signer}


def _read_sha256_sidecar(path: Path) -> tuple[str, str]:
    lines = path.read_text().splitlines()
    if len(lines) != 1:
        raise ValueError("SHA-256 sidecar must contain exactly one entry")
    match = re.fullmatch(r"([0-9a-f]{64})\s+\*?(.+)", lines[0])
    if not match:
        raise ValueError("invalid SHA-256 sidecar entry")
    return match.group(1), match.group(2)


def _modinfo(module_path: Path, field: str) -> str:
    return subprocess.check_output(["modinfo", "-F", field, str(module_path)], text=True).strip()


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
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("module", type=Path)
    parser.add_argument("release", help="explicit target kernel release")
    parser.add_argument("--artifact-kind", choices=("standard", "dkms"), default="standard")
    parser.add_argument("--sha256-file", type=Path,
                        help="one-entry sha256sum sidecar required for DKMS artifacts")
    args = parser.parse_args()
    try:
        result = verify(args.manifest, args.module, args.release,
                        args.artifact_kind, args.sha256_file)
    except (OSError, json.JSONDecodeError, subprocess.CalledProcessError, ValueError) as exc:
        raise SystemExit(str(exc)) from exc
    signer_status = f"signature metadata present (signer={result['signer']})" if result["signer"] else "unsigned (no signer metadata)"
    print(f"PASS: {args.artifact_kind} module identity matches; {signer_status}; signer trust is not evaluated")


if __name__ == "__main__":
    main()
