#!/usr/bin/env python3
"""Offline tests for standard and build-only DKMS artifact identity gates."""
import hashlib
import importlib.util
import io
import json
import sys
import tempfile
from pathlib import Path
from contextlib import redirect_stdout
from unittest.mock import patch


spec = importlib.util.spec_from_file_location(
    "verify_gf117_artifact", Path(__file__).with_name("verify-gf117-artifact.py")
)
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)


def modinfo_values(vermagic, srcversion, name="nouveau", signer=""):
    return {"name": name, "vermagic": vermagic, "srcversion": srcversion, "signer": signer}


def run_verify(info, *args, **kwargs):
    with patch.object(module.subprocess, "check_output",
                      side_effect=lambda cmd, text: info[cmd[2]]):
        return module.verify(*args, **kwargs)


with tempfile.TemporaryDirectory(prefix="gf117-artifact-test-") as temp:
    root = Path(temp)
    ko = root / "nouveau.ko"
    dkms_ko = root / "dkms-nouveau.ko"
    manifest = root / "manifest.json"
    sidecar = root / "dkms-nouveau.ko.sha256"
    ko.write_bytes(b"standard module bytes")
    dkms_ko.write_bytes(b"separately built DKMS module bytes")
    standard_hash = hashlib.sha256(ko.read_bytes()).hexdigest()
    dkms_hash = hashlib.sha256(dkms_ko.read_bytes()).hexdigest()
    release = "7.2.9-2-cachyos"
    vermagic = release + " SMP preempt mod_unload"
    srcversion = "0123456789ABCDEF"
    base = {
        "schema": "gf117-nouveau-module/v1",
        "kernel_release": release,
        "module_sha256": standard_hash,
        "vermagic": vermagic,
        "srcversion": srcversion,
        "dkms_module_sha256": dkms_hash,
        "dkms_vermagic": vermagic,
        "dkms_srcversion": srcversion,
    }

    def write_manifest(data):
        manifest.write_text(json.dumps(data))

    info = modinfo_values(vermagic, srcversion)
    write_manifest(base)
    run_verify(info, manifest, ko, release)

    # Preserve compatibility with the alias form emitted by an older Actions artifact.
    actions = dict(base)
    actions.pop("kernel_release")
    actions.pop("srcversion")
    actions["kernel"] = release
    actions["module_srcversion"] = srcversion
    write_manifest(actions)
    run_verify(info, manifest, ko, release)

    bad_cases = [
        ("kernel_release", "6.1.0"),
        ("module_sha256", "0" * 64),
        ("vermagic", "6.1.0 SMP"),
        ("srcversion", "FFFFFFFFFFFFFFFF"),
        ("schema", "gf117-nouveau-module/v999"),
    ]
    for key, value in bad_cases:
        bad = dict(base, **{key: value})
        write_manifest(bad)
        try:
            run_verify(info, manifest, ko, release)
        except ValueError:
            pass
        else:
            raise AssertionError(f"accepted mismatched {key}")

    conflicting_aliases = dict(base, kernel="6.1.0")
    write_manifest(conflicting_aliases)
    try:
        run_verify(info, manifest, ko, release)
    except ValueError as exc:
        assert "conflicting manifest fields" in str(exc)
    else:
        raise AssertionError("accepted conflicting kernel aliases")

    # The DKMS payload has its own hash and is explicitly selected; its hash is
    # expected to differ from the standard module hash.
    write_manifest(base)
    sidecar.write_text(f"{dkms_hash}  {dkms_ko}\n")
    signed_info = modinfo_values(vermagic, srcversion, signer="Test signer")
    result = run_verify(signed_info, manifest, dkms_ko, release, "dkms", sidecar)
    assert result["sha256"] == dkms_hash and result["signer"] == "Test signer"
    unsigned_result = run_verify(info, manifest, dkms_ko, release, "dkms", sidecar)
    assert unsigned_result["signer"] == ""

    for signature_info, expected_status in [
        (info, "unsigned (no signer metadata)"),
        (signed_info, "signature metadata present (signer=Test signer)"),
    ]:
        output = io.StringIO()
        args = ["verify-gf117-artifact.py", str(manifest), str(dkms_ko), release,
                "--artifact-kind", "dkms", "--sha256-file", str(sidecar)]
        with patch.object(sys, "argv", args), \
                patch.object(module.subprocess, "check_output",
                             side_effect=lambda cmd, text: signature_info[cmd[2]]), \
                redirect_stdout(output):
            module.main()
        assert expected_status in output.getvalue()
        assert "signer trust is not evaluated" in output.getvalue()

    for contents, expected in [
        (f"{'0' * 64}  {dkms_ko}\n", "manifest DKMS hash"),
        (f"{dkms_hash}\n", "sidecar"),
        (f"{dkms_hash}  {dkms_ko}\n{dkms_hash}  duplicate\n", "exactly one"),
    ]:
        sidecar.write_text(contents)
        try:
            run_verify(info, manifest, dkms_ko, release, "dkms", sidecar)
        except ValueError as exc:
            assert expected.lower() in str(exc).lower()
        else:
            raise AssertionError(f"accepted invalid sidecar: {contents!r}")

    sidecar.write_text(f"{dkms_hash}  {dkms_ko}\n")
    wrong_dkms = dict(base, dkms_module_sha256="0" * 64)
    write_manifest(wrong_dkms)
    try:
        run_verify(info, manifest, dkms_ko, release, "dkms", sidecar)
    except ValueError as exc:
        assert "manifest DKMS hash" in str(exc)
    else:
        raise AssertionError("accepted mismatch between DKMS sidecar and manifest")

    write_manifest(base)
    sidecar.write_text(f"{dkms_hash}  unrelated.ko\n")
    try:
        run_verify(info, manifest, dkms_ko, release, "dkms", sidecar)
    except ValueError as exc:
        assert "different module file" in str(exc)
    else:
        raise AssertionError("accepted sidecar naming a different module")

    sidecar.write_text(f"{dkms_hash}  {dkms_ko}\n")
    try:
        run_verify(modinfo_values(vermagic, srcversion, name="other"),
                   manifest, dkms_ko, release, "dkms", sidecar)
    except ValueError as exc:
        assert "module name" in str(exc)
    else:
        raise AssertionError("accepted module with a different name")

    try:
        module.verify(manifest, dkms_ko, release, "dkms")
    except ValueError as exc:
        assert "requires an explicit" in str(exc)
    else:
        raise AssertionError("accepted DKMS verification without a sidecar")

    ko.write_bytes(b"tampered standard module bytes")
    try:
        run_verify(info, manifest, ko, release)
    except ValueError as exc:
        assert "SHA-256" in str(exc)
    else:
        raise AssertionError("accepted modified standard module")

print("PASS: standard and DKMS identities accept exact hashes and reject tampering, wrong module names, release, vermagic, srcversion, and sidecar mismatches")
