import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location('diagnostics', Path(__file__).parents[1] / 'src/r36s_diagnostics.py')
d = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(d)


class DiagnosticsTests(unittest.TestCase):
    def test_connection_requires_nm_and_address(self):
        self.assertEqual(d.wifi_status(30, ['192.168.1.2']), 'Disconnected')
        self.assertEqual(d.wifi_status(100, []), 'Associated, no IPv4')
        self.assertEqual(d.wifi_status(100, ['192.168.1.2']), 'Connected')
        self.assertIn('NM unavailable', d.wifi_status(None, ['192.168.1.2']))

    def test_ssid_escaping_and_terminal_controls(self):
        self.assertEqual(d.nmcli_fields(r'*:casa\:sala\\wifi:85'), ['*', 'casa:sala\\wifi', '85'])
        self.assertNotIn('\x1b', d.clean('SSID\x1b[2J\nmalicioso'))
        self.assertNotIn('\n', d.clean('SSID\x1b[2J\nmalicioso'))

    def test_missing_hardware_is_reported_without_crashing(self):
        with tempfile.TemporaryDirectory() as root:
            snapshot = d.Collector(Path(root), runner=lambda args: None).collect()
            self.assertEqual(snapshot['storage'], [])
            self.assertEqual(snapshot['resources']['temperatures'], [])
            self.assertFalse(snapshot['network']['internet_tested'])
            self.assertIn('No Wi-Fi interface found.', snapshot['observations'])
            self.assertIn('N/A', d.page(snapshot, 'all'))

    def test_realistic_sysfs_units_and_realtek_modes(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            def put(path, value):
                target = root / path.lstrip('/')
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(value)
            for path, value in {
                '/sys/class/power_supply/battery/type': 'Battery',
                '/sys/class/power_supply/battery/capacity': '85',
                '/sys/class/power_supply/battery/voltage_now': '3811000',
                '/sys/class/power_supply/battery/current_now': '97000',
                '/sys/class/thermal/thermal_zone0/type': 'soc-thermal',
                '/sys/class/thermal/thermal_zone0/temp': '45200',
                '/sys/class/thermal/thermal_zone1/temp': '-999000',
                '/sys/bus/usb/devices/usb1/idVendor': '1d6b',
                '/sys/bus/usb/devices/usb1/idProduct': '0002',
                '/sys/bus/usb/devices/1-1/idVendor': '0bda',
                '/sys/bus/usb/devices/1-1/idProduct': '1a2b',
                '/sys/class/net/wlan0/operstate': 'up',
                '/proc/uptime': 'unavailable',
            }.items():
                put(path, value)
            (root / 'sys/class/net/wlan0/wireless').mkdir()
            def runner(args):
                if args[:4] == ['ip', '-j', '-4', 'address']:
                    return json.dumps([{'ifname': 'wlan0', 'addr_info': [{'scope': 'global', 'local': '192.168.15.13'}]}])
                if 'GENERAL.STATE' in args:
                    return '30 (disconnected)'
                return None
            snapshot = d.Collector(root, runner).collect()
            battery = snapshot['resources']['batteries'][0]
            self.assertEqual(battery['voltage_v'], 3.811)
            self.assertEqual(battery['current_ma'], 97)
            self.assertEqual(snapshot['resources']['temperatures'], [{'sensor': 'thermal_zone0', 'type': 'soc-thermal', 'celsius': 45.2}])
            self.assertEqual(snapshot['network']['interfaces'][0]['status'], 'Disconnected')
            self.assertTrue(any('modeswitch' in note for note in snapshot['observations']))
            self.assertEqual(d.usb_kind('0bda', 'c820'), 'Realtek Wi-Fi/Bluetooth adapter')

    def test_saved_reports_are_private_and_equivalent(self):
        with tempfile.TemporaryDirectory() as root:
            snapshot = d.Collector(Path(root), runner=lambda args: None).collect()
            paths = d.save_report(snapshot, Path(root) / 'reports')
            self.assertEqual(json.loads(Path(paths[0]).read_text()), snapshot)
            self.assertIn('NETWORK', Path(paths[1]).read_text())
            self.assertEqual(os.stat(paths[0]).st_mode & 0o777, 0o600)
            self.assertEqual(os.stat(Path(root) / 'reports').st_mode & 0o777, 0o700)


if __name__ == '__main__':
    unittest.main()
