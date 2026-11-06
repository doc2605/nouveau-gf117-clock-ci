#!/usr/bin/env python3
"""Exercise upstream DKMS collision handling with inert files in a user namespace.

Requires a downloaded, SHA-256-verified DKMS v3.1.7 dkms.in, unshare and bash.
Only disposable trees under a private TemporaryDirectory are used.
No module is built, loaded, signed, or installed into the host module tree.
"""
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import tempfile

EXPECTED = 'd5c23ea16b3709e38b37a53fabed414f9d2e5933a8059429b045338bb04b240d'
if len(sys.argv) != 2:
    raise SystemExit('usage: test-collision-dkms-3.1.7.py <dkms-v3.1.7-dkms.in>')
dkms = Path(sys.argv[1]).resolve(strict=True)
if hashlib.sha256(dkms.read_bytes()).hexdigest() != EXPECTED:
    raise SystemExit('unexpected DKMS source; refusing to execute')

with tempfile.TemporaryDirectory(prefix='gf117-dkms-fixture-') as temp:
    root = Path(temp)
    source, state, install, scratch = (root / p for p in ('src', 'state', 'install', 'tmp'))
    for directory in (source, state, install, scratch):
        directory.mkdir()
    release, arch, package, version = '0.0-gf117-fixture', 'x86_64', 'gf117_collision_fixture', '0.1'
    config = source / (package + '-' + version)
    config.mkdir()
    (config / 'dkms.conf').write_text(
        'PACKAGE_NAME="gf117_collision_fixture"\nPACKAGE_VERSION="0.1"\n'
        'BUILT_MODULE_NAME[0]="nouveau"\nDEST_MODULE_LOCATION[0]="/updates/dkms"\n'
        'AUTOINSTALL="no"\n')
    original = install / release / 'kernel/drivers/gpu/drm/nouveau/nouveau.ko'
    original.parent.mkdir(parents=True)
    original.write_bytes(b'inert original fixture\n')
    # Keep depmod from ever inspecting or updating host module trees.
    stub_bin = root / 'bin'
    stub_bin.mkdir()
    depmod = stub_bin / 'depmod'
    depmod.write_text('#!/bin/sh\necho "fixture depmod stub: $*"\nexit 0\n')
    depmod.chmod(0o755)
    built = state / package / version / release / arch / 'module'
    built.mkdir(parents=True)
    (built / 'nouveau.ko').write_bytes(b'inert experimental fixture\n')
    (state / package / version / 'source').symlink_to(config)
    args = ['unshare', '-Ur', 'bash', str(dkms), '--sourcetree', str(source),
            '--dkmstree', str(state), '--installtree', str(install), '--no-depmod',
            '--force-version-override', '-m', package, '-v', version, '-k', release, '-a', arch]
    environment = {**os.environ, 'PATH': str(stub_bin) + os.pathsep + os.environ['PATH'],
                   'TMPDIR': str(scratch)}
    def run(action):
        result = subprocess.run(args + [action], env=environment, text=True,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=True)
        print(result.stdout, end='')
    run('install')
    backup = state / package / 'original_module' / release / arch / 'nouveau.ko'
    replacement = install / release / 'updates/dkms/nouveau.ko'
    assert not original.exists(), 'original unexpectedly remained at its path'
    assert backup.read_bytes() == b'inert original fixture\n'
    assert replacement.read_bytes() == b'inert experimental fixture\n'
    run('uninstall')
    assert original.read_bytes() == b'inert original fixture\n'
    assert not replacement.exists()
    print('PASS: DKMS moves original on install and restores it on simple uninstall')
