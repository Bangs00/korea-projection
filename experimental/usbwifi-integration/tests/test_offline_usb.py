# SPDX-License-Identifier: AGPL-3.0-only
from pathlib import Path
import configparser
import hashlib
import tempfile
import unittest
import zipfile
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import build

class OfflineUsbTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.usb = Path(self.temp.name)
        (self.usb/'packages').mkdir()
        for package in ['korea.projection', 'korea.projection.usblogs']:
            with zipfile.ZipFile(self.usb/'packages'/f'{package}.zip', 'w') as z:
                z.writestr('NEMESIS.data', '[nemesis]\nid='+package+'\npackage-version=1.7.4.2\n')
        (self.usb/'KP_USB_EXPORT.txt').write_bytes((build.BASE/'usb/KP_USB_EXPORT.txt').read_bytes())

    def resolve_install(self, root):
        config = configparser.ConfigParser(interpolation=None)
        config.read(root/'NEMESIS.data')
        self.assertEqual(set(config.sections()), {'nemesis'})
        self.assertEqual(config['nemesis']['type'], 'install')
        relative = Path(config['nemesis']['path'])
        self.assertFalse(relative.is_absolute())
        self.assertNotIn('..', relative.parts)
        self.assertNotIn('://', str(relative))
        target = root/relative
        self.assertTrue(target.is_file())
        with zipfile.ZipFile(target) as z:
            package = configparser.ConfigParser(interpolation=None)
            package.read_string(z.read('NEMESIS.data').decode())
            return package['nemesis']['id']

    def test_main_uses_the_original_native_kp_install_contract(self):
        before = (self.usb/'packages/korea.projection.zip').read_bytes()
        build.write_offline_entrypoints(self.usb)
        self.assertEqual(self.resolve_install(self.usb), 'korea.projection')
        self.assertEqual((self.usb/'packages/korea.projection.zip').read_bytes(), before)

    def test_logs_folder_is_self_contained_when_copied_to_a_separate_usb(self):
        build.write_offline_entrypoints(self.usb)
        logs = self.usb/'Logs-Install-USB'
        self.assertEqual(self.resolve_install(logs), 'korea.projection.usblogs')
        self.assertEqual((logs/'KP_USB_EXPORT.txt').read_bytes(), (self.usb/'KP_USB_EXPORT.txt').read_bytes())
        a = hashlib.sha256((logs/'packages/korea.projection.usblogs.zip').read_bytes()).digest()
        b = hashlib.sha256((self.usb/'packages/korea.projection.usblogs.zip').read_bytes()).digest()
        self.assertEqual(a, b)

    def test_missing_local_logs_package_does_not_create_a_broken_installer(self):
        (self.usb/'packages/korea.projection.usblogs.zip').unlink()
        with self.assertRaises(FileNotFoundError):
            build.write_offline_entrypoints(self.usb)
        self.assertFalse((self.usb/'NEMESIS.data').exists())
        self.assertFalse((self.usb/'Logs-Install-USB').exists())
