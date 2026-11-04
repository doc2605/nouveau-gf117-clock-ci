#!/usr/bin/env python3
"""Check the DKMS entrypoint's argument and kernel-release gates without a kernel build."""
import os
from pathlib import Path
import subprocess
import tempfile

script = Path(__file__).with_name('build-module.sh').resolve()
with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    for name in ('kernel', 'nouveau', 'bin'):
        (root / name).mkdir()
    for name in ('.config', 'Module.symvers'):
        (root / 'kernel' / name).touch()
    (root / 'nouveau' / 'Kbuild').touch()
    fake_make = root / 'bin' / 'make'
    fake_make.write_text('#!/bin/sh\ncase " $* " in *" kernelrelease "*) echo 7.2.9-2-cachyos;; esac\n')
    fake_make.chmod(0o755)
    env = dict(os.environ, PATH=str(root / 'bin') + ':' + os.environ['PATH'])
    for tail in ([], ['LLVM=1']):
        result = subprocess.run(['bash', str(script), str(root / 'kernel'), '7.2.9-2-cachyos', *tail], cwd=root, env=env)
        assert result.returncode == 0, tail
    for release, tail in (('7.3.0-4-cachyos', []), ('7.2.9-2-cachyos', ['BAD=1'])):
        result = subprocess.run(['bash', str(script), str(root / 'kernel'), release, *tail], cwd=root, env=env, capture_output=True)
        assert result.returncode != 0, (release, tail)
print('PASS: DKMS entrypoint gates release and accepts DKMS LLVM=1 argument')
