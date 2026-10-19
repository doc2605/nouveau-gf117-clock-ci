#!/usr/bin/env python3
"""Offline tests for the pinned module identity gate."""
import hashlib
import importlib.util
import json
import tempfile
from pathlib import Path
from unittest.mock import patch


spec = importlib.util.spec_from_file_location(
    "verify_gf117_artifact", Path(__file__).with_name("verify-gf117-artifact.py")
)
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)

with tempfile.TemporaryDirectory(prefix="gf117-artifact-test-") as temp:
    root = Path(temp)
    ko = root / "nouveau.ko"
    manifest = root / "manifest.json"
    ko.write_bytes(b"test module bytes")
    base = {
        "schema": "gf117-nouveau-module/v1",
        "kernel_release": "7.2.9-2-cachyos",
        "module_sha256": hashlib.sha256(ko.read_bytes()).hexdigest(),
        "vermagic": "7.2.9-2-cachyos SMP preempt mod_unload",
        "srcversion": "0123456789ABCDEF",
    }

    def write_manifest(data):
        manifest.write_text(json.dumps(data))

    with patch.object(module.subprocess, "check_output", side_effect=[
        base["vermagic"], base["srcversion"]
    ]):
        write_manifest(base)
        module.verify(manifest, ko, "7.2.9-2-cachyos")

    # The GitHub Actions artifact schema used by the public build has the
    # aliases `kernel` and `module_srcversion`; verify that form too.
    actions = {
        "schema": "gf117-nouveau-module/v1",
        "kernel": base["kernel_release"],
        "module_sha256": base["module_sha256"],
        "vermagic": base["vermagic"],
        "module_srcversion": base["srcversion"],
    }
    with patch.object(module.subprocess, "check_output", side_effect=[
        base["vermagic"], base["srcversion"]
    ]):
        write_manifest(actions)
        module.verify(manifest, ko, "7.2.9-2-cachyos")

    bad_cases = [
        ("kernel_release", "6.1.0"),
        ("module_sha256", "0" * 64),
        ("vermagic", "6.1.0 SMP"),
        ("srcversion", "FFFFFFFFFFFFFFFF"),
        ("schema", "gf117-nouveau-module/v999"),
    ]
    for key, value in bad_cases:
        bad = dict(base, **{key: value})
        with patch.object(module.subprocess, "check_output", side_effect=[
            base["vermagic"], base["srcversion"]
        ]):
            write_manifest(bad)
            try:
                module.verify(manifest, ko, "7.2.9-2-cachyos")
            except ValueError:
                pass
            else:
                raise AssertionError(f"accepted mismatched {key}")

    conflicting_aliases = dict(base, kernel="6.1.0")
    with patch.object(module.subprocess, "check_output", side_effect=[
        base["vermagic"], base["srcversion"]
    ]):
        write_manifest(conflicting_aliases)
        try:
            module.verify(manifest, ko, "7.2.9-2-cachyos")
        except ValueError as exc:
            assert "conflicting manifest fields" in str(exc)
        else:
            raise AssertionError("accepted conflicting kernel aliases")

    ko.write_bytes(b"changed module bytes")
    with patch.object(module.subprocess, "check_output", side_effect=[
        base["vermagic"], base["srcversion"]
    ]):
        write_manifest(base)
        try:
            module.verify(manifest, ko, "7.2.9-2-cachyos")
        except ValueError:
            pass
        else:
            raise AssertionError("accepted a module changed after manifest creation")

print("PASS: artifact gate accepts exact identity and rejects kernel, hash, vermagic, and srcversion mismatches")
