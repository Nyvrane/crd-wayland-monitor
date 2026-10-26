#!/usr/bin/python3
import os
from pathlib import Path
import shlex
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent
flags = shlex.split(subprocess.check_output(['pkg-config', '--cflags', '--libs', 'gio-unix-2.0'], text=True))
with tempfile.TemporaryDirectory(prefix='crd-checks-') as temp:
    output = Path(temp) / 'portal-monitor-test'
    subprocess.run(['cc', '-Wall', '-Wextra', '-Werror', '-O2', '-DSELF_TEST',
        str(ROOT / 'portal-monitor.c'), '-o', str(output), *flags, '-ldl'], check=True)
    env = os.environ.copy(); env['CRD_MONITOR_TOKEN_FILE'] = str(Path(temp) / 'token')
    subprocess.run([str(output)], env=env, check=True)
    assert (Path(temp) / 'token').stat().st_mode & 0o777 == 0o600
suite = unittest.defaultTestLoader.discover(str(ROOT), pattern='test_*.py')
if not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful():
    raise SystemExit(1)
