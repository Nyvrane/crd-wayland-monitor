import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import types
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location('crd_installer', Path(__file__).resolve().parent / 'install.py')
installer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(installer)

class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='crd-installer-test-')
        self.addCleanup(self.temp.cleanup)
        home = Path(self.temp.name) / 'home with spaces'
        home.mkdir()
        for name, value in {'HOME': home, 'DEST': home / '.local/lib/crd-wayland-monitor',
                'STATE': home / '.local/state/crd-wayland-monitor',
                'CONFIG': home / '.config', 'DATA': home / '.local/share'}.items():
            replacement = patch.object(installer, name, value)
            replacement.start(); self.addCleanup(replacement.stop)
        self.host = home / '.config/chrome-remote-desktop/host#test.json'
        self.host.parent.mkdir(parents=True)
        self.args = types.SimpleNamespace(host_config=None, restore_previous=False)

    def registration(self, suffix=''):
        path = self.host.with_name('host#test' + suffix + '.json')
        path.write_text(json.dumps({'host_id': 'fake-host', 'host_name': 'Test computer',
            'private_key': 'TEST-PRIVATE-KEY-DO-NOT-COPY', 'oauth_refresh_token': 'TEST-TOKEN-DO-NOT-COPY'}))
        return path

    def test_missing_or_ambiguous_registration_does_not_touch_services(self):
        with patch.object(installer, 'verify_requirements'), patch.object(installer, 'userctl') as ctl:
            with self.assertRaises(SystemExit): installer.install(self.args)
            ctl.assert_not_called()
            self.registration(); self.registration('second')
            with self.assertRaises(SystemExit): installer.install(self.args)
            ctl.assert_not_called()

    def test_explicit_registration_and_no_credentials_copied(self):
        path = self.registration(); self.registration('second')
        self.args.host_config = str(path)
        def fake_build(output): output.write_bytes(b'test-library')
        with patch.object(installer, 'verify_requirements'), patch.object(installer, 'build', side_effect=fake_build), \
             patch.object(installer, 'userctl') as ctl, patch.object(installer, 'stop_previous_system_host'), \
             patch.object(installer, 'run'), patch.object(installer.time, 'sleep'):
            installer.install(self.args)
            installer.install(self.args)
        settings = (installer.DEST / 'settings.json').read_text()
        self.assertNotIn('PRIVATE', settings)
        self.assertNotIn('TOKEN', settings)
        self.assertEqual(json.loads(settings)['host_id'], 'fake-host')
        self.assertEqual((installer.DEST / 'settings.json').stat().st_mode & 0o777, 0o600)
        self.assertTrue((installer.DATA / 'applications' / installer.APP).is_file())
        self.assertTrue((installer.CONFIG / 'systemd/user' / installer.UNIT).is_file())
        self.assertIn(unittest.mock.call('restart', installer.UNIT), ctl.call_args_list)

    def test_build_failure_leaves_old_services_untouched(self):
        self.registration()
        with patch.object(installer, 'verify_requirements'), \
             patch.object(installer, 'build', side_effect=subprocess.CalledProcessError(1, 'test-compiler')), \
             patch.object(installer, 'stop_previous_system_host') as stop, patch.object(installer, 'userctl') as ctl:
            with self.assertRaises(subprocess.CalledProcessError): installer.install(self.args)
            stop.assert_not_called(); ctl.assert_not_called()

    def test_uninstall_preserves_registration_and_private_state(self):
        self.registration()
        installer.STATE.mkdir(parents=True)
        token = installer.STATE / 'portal-token'; token.write_text('test-private-token')
        with patch.object(installer, 'userctl'):
            installer.uninstall(self.args)
        self.assertTrue(self.host.exists())
        self.assertEqual(token.read_text(), 'test-private-token')

if __name__ == '__main__':
    unittest.main()
