#!/usr/bin/env python3
"""Passive diagnostics for R36S/dArkOSRE. Python standard library only."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import re
import shutil
import struct
import subprocess
import tempfile
import textwrap
import unicodedata

VERSION = '0.1.2'
APP_DIR = Path(__file__).resolve().parent


def clean(value):
    """Prevent device names/SSIDs from injecting terminal control sequences."""
    return ''.join(c if unicodedata.category(c)[0] != 'C' else ' ' for c in str(value)).strip()


def read_text(path, default=None):
    try:
        return path.read_text(encoding='utf-8', errors='replace').strip().strip('\0')
    except (OSError, ValueError):
        return default


def number(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def nmcli_fields(line):
    fields, current, escaped = [], [], False
    for char in line:
        if escaped:
            current.append(char)
            escaped = False
        elif char == '\\':
            escaped = True
        elif char == ':':
            fields.append(''.join(current))
            current = []
        else:
            current.append(char)
    if escaped:
        current.append('\\')
    fields.append(''.join(current))
    return fields


def wifi_status(state, addresses):
    """Radio enabled/link UP alone never means a working connection."""
    if state == 100 and addresses:
        return 'Connected'
    if state == 100:
        return 'Associated, no IPv4'
    if state is not None and 40 <= state < 100:
        return 'Connecting'
    if state is None and addresses:
        return 'Interface has IP (NM unavailable)'
    return 'Disconnected'


def usb_kind(vendor, product):
    if vendor == '1d6b':
        return 'Internal controller'
    if (vendor, product) == ('0bda', '1a2b'):
        return 'Realtek in storage mode'
    if (vendor, product) == ('0bda', 'c820'):
        return 'Realtek Wi-Fi/Bluetooth adapter'
    return 'USB peripheral'


class Collector:
    def __init__(self, root=Path('/'), runner=None):
        self.root = Path(root)
        self.runner = runner or self.command

    def path(self, path):
        return self.root / path.lstrip('/')

    @staticmethod
    def command(args):
        if not shutil.which(args[0]):
            return None
        try:
            result = subprocess.run(args, capture_output=True, text=True, timeout=4,
                                    env=dict(os.environ, LC_ALL='C', LANG='C'))
            return result.stdout.strip() if result.returncode == 0 else None
        except (OSError, subprocess.TimeoutExpired, UnicodeError):
            return None

    def json_command(self, args, default):
        try:
            return json.loads(self.runner(args) or '')
        except (ValueError, TypeError):
            return default

    def system(self):
        release = {}
        for line in (read_text(self.path('/etc/os-release'), '')).splitlines():
            if '=' in line:
                key, value = line.split('=', 1)
                release[key] = value.strip('"')
        uptime = read_text(self.path('/proc/uptime'), '').split()
        try:
            uptime_seconds = int(float(uptime[0])) if uptime else None
        except (ValueError, OverflowError):
            uptime_seconds = None
        return {'os': release.get('PRETTY_NAME', 'Unavailable'),
                'os_version': release.get('DEBIAN_VERSION_FULL', release.get('VERSION_ID')),
                'kernel': platform.release(), 'architecture': platform.machine(),
                'hostname': platform.node(),
                'device_tree_model': read_text(self.path('/proc/device-tree/model')),
                'uptime_seconds': uptime_seconds}

    def resources(self):
        memory = {}
        for line in read_text(self.path('/proc/meminfo'), '').splitlines():
            key, _, raw = line.partition(':')
            value = number(raw.strip().split()[0]) if raw.strip() else None
            if value is not None:
                memory[key] = value * 1024
        total, available = memory.get('MemTotal'), memory.get('MemAvailable')
        if available is None and total is not None:
            available = sum(memory.get(key, 0) for key in ('MemFree', 'Buffers', 'Cached'))
        thermal = []
        for zone in sorted(self.path('/sys/class/thermal').glob('thermal_zone*')):
            raw = number(read_text(zone / 'temp'))
            if raw is not None and -40000 <= raw <= 150000:
                thermal.append({'sensor': zone.name, 'type': read_text(zone / 'type', zone.name),
                                'celsius': round(raw / 1000, 1)})
        batteries = []
        power = []
        for supply in sorted(self.path('/sys/class/power_supply').glob('*')):
            kind = read_text(supply / 'type', '')
            if kind.lower() == 'battery' or (supply / 'capacity').exists():
                voltage = number(read_text(supply / 'voltage_now'))
                current = number(read_text(supply / 'current_now'))
                batteries.append({'name': supply.name, 'percent': number(read_text(supply / 'capacity')),
                                  'status': read_text(supply / 'status'),
                                  'voltage_v': round(voltage / 1e6, 3) if voltage is not None else None,
                                  'current_ma': round(current / 1000, 1) if current is not None else None})
            else:
                power.append({'name': supply.name, 'type': kind,
                              'online': number(read_text(supply / 'online'))})
        frequency = number(read_text(self.path('/sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq')))
        loads = read_text(self.path('/proc/loadavg'), '').split()[:3]
        return {'cpu_count': os.cpu_count(), 'load_average': loads,
                'cpu_mhz': round(frequency / 1000) if frequency is not None else None,
                'governor': read_text(self.path('/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor')),
                'memory_total_bytes': total, 'memory_available_bytes': available,
                'memory_used_bytes': max(total - available, 0) if total is not None and available is not None else None,
                'swap_total_bytes': memory.get('SwapTotal'), 'swap_free_bytes': memory.get('SwapFree'),
                'temperatures': thermal, 'batteries': batteries, 'power_sources': power}

    def network(self):
        addresses = self.json_command(['ip', '-j', '-4', 'address', 'show'], [])
        routes = self.json_command(['ip', '-j', '-4', 'route', 'show', 'default'], [])
        interfaces = []
        for device in sorted(self.path('/sys/class/net').glob('*')):
            if device.name == 'lo':
                continue
            name = device.name
            ipv4 = [entry['local'] for row in addresses if row.get('ifname') == name
                    for entry in row.get('addr_info', []) if entry.get('scope') == 'global' and entry.get('local')]
            wireless = (device / 'wireless').exists() or name.startswith(('wlan', 'wl'))
            state_raw = self.runner(['nmcli', '-g', 'GENERAL.STATE', 'device', 'show', name])
            state_match = re.match(r'\s*(\d+)', state_raw or '')
            state = int(state_match.group(1)) if state_match else None
            ssid, signal = None, None
            if wireless:
                scan = self.runner(['nmcli', '--colors', 'no', '-t', '-e', 'yes', '-f',
                                    'IN-USE,SSID,SIGNAL', 'device', 'wifi', 'list', 'ifname', name, '--rescan', 'no'])
                for line in (scan or '').splitlines():
                    fields = nmcli_fields(line)
                    if len(fields) >= 3 and fields[0] == '*':
                        ssid, signal = fields[1], number(fields[2])
                        break
            driver_link = device / 'device/driver'
            driver = driver_link.resolve().name if driver_link.is_symlink() else None
            interfaces.append({'name': name, 'wireless': wireless, 'ipv4': ipv4,
                               'link_state': read_text(device / 'operstate'), 'nm_state': state,
                               'status': wifi_status(state, ipv4), 'ssid': ssid, 'signal_percent': signal,
                               'driver': driver})
        ssh = self.runner(['systemctl', 'is-active', 'ssh'])
        return {'interfaces': interfaces, 'default_routes': routes, 'ssh_service': ssh or 'inactive/unavailable',
                'internet_tested': False}

    def usb(self):
        devices = []
        for device in sorted(self.path('/sys/bus/usb/devices').glob('*')):
            vendor, product = read_text(device / 'idVendor'), read_text(device / 'idProduct')
            if not vendor or not product:
                continue
            drivers = []
            for interface in device.glob(device.name + ':*'):
                if (interface / 'driver').is_symlink():
                    drivers.append((interface / 'driver').resolve().name)
            # Sysfs also exposes interface nodes as siblings.
            for interface in device.parent.glob(device.name + ':*'):
                if (interface / 'driver').is_symlink():
                    drivers.append((interface / 'driver').resolve().name)
            devices.append({'path': device.name, 'id': vendor + ':' + product,
                            'kind': usb_kind(vendor, product), 'product': read_text(device / 'product'),
                            'manufacturer': read_text(device / 'manufacturer'),
                            'speed_mbps': read_text(device / 'speed'), 'drivers': sorted(set(drivers))})
        return devices

    def storage(self):
        mounts = {}
        for line in read_text(self.path('/proc/mounts'), '').splitlines():
            fields = line.split()
            if len(fields) >= 3:
                mounts[fields[1].replace('\\040', ' ')] = (fields[0], fields[2])
        result = []
        for path in ('/', '/boot', '/roms', '/roms2'):
            if path not in mounts:
                continue
            try:
                stats = os.statvfs(self.path(path))
            except OSError:
                continue
            result.append({'mount': path, 'device': mounts[path][0], 'filesystem': mounts[path][1],
                           'total_bytes': stats.f_blocks * stats.f_frsize,
                           'free_bytes': stats.f_bavail * stats.f_frsize,
                           'used_bytes': (stats.f_blocks - stats.f_bfree) * stats.f_frsize})
        return result

    def collect(self):
        result = {'schema_version': 1, 'tool_version': VERSION,
                  'collected_at': datetime.now(timezone.utc).isoformat(timespec='seconds'),
                  'system': self.system(), 'resources': self.resources(), 'network': self.network(),
                  'usb': self.usb(), 'storage': self.storage()}
        warnings = []
        if any(device['id'] == '0bda:1a2b' for device in result['usb']):
            warnings.append('Realtek adapter in storage mode; modeswitch may be needed.')
        if not any(device['kind'] != 'Internal controller' for device in result['usb']):
            warnings.append('No external USB peripherals found in this snapshot.')
        if not any(row['wireless'] for row in result['network']['interfaces']):
            warnings.append('No Wi-Fi interface found.')
        for row in result['storage']:
            if row['total_bytes'] and row['free_bytes'] / row['total_bytes'] < .1:
                warnings.append('Low free space on ' + row['mount'])
        result['observations'] = warnings
        return result


def size(value):
    if value is None:
        return 'N/A'
    return f'{value / 1024**3:.1f} GiB' if value >= 1024**3 else f'{value / 1024**2:.0f} MiB'


def value(raw, suffix=''):
    return 'N/A' if raw is None else clean(raw) + suffix


def page(snapshot, section):
    system, resources, network = (snapshot[name] for name in ('system', 'resources', 'network'))
    lines = []
    if section in ('summary', 'all'):
        wifi = next((row for row in network['interfaces'] if row['wireless']), None)
        battery = next(iter(resources['batteries']), {})
        cpu_temp = next((row for row in resources['temperatures'] if 'soc' in row['type'] or 'cpu' in row['type']), None)
        roms = next((row for row in snapshot['storage'] if row['mount'] == '/roms'), None)
        lines += ['R36S Diagnostics ' + VERSION, system['os'], 'Kernel: ' + system['kernel'], '',
                  'Wi-Fi: ' + (wifi['status'] if wifi else 'No interface'),
                  'IP: ' + (', '.join(wifi['ipv4']) if wifi and wifi['ipv4'] else 'N/A'),
                  'Battery: ' + value(battery.get('percent'), '%'),
                  'CPU: ' + value(cpu_temp['celsius'] if cpu_temp else None, ' C'),
                  'RAM: ' + size(resources['memory_used_bytes']) + ' / ' + size(resources['memory_total_bytes']),
                  'Games storage free: ' + (size(roms['free_bytes']) if roms else 'N/A')]
        lines += ['', *snapshot['observations']]
    if section in ('network', 'all'):
        lines += ['NETWORK', 'SSH: ' + network['ssh_service']]
        for row in network['interfaces']:
            lines += ['', row['name'] + ': ' + row['status'], 'SSID: ' + value(row['ssid']),
                      'IPv4: ' + (', '.join(row['ipv4']) or 'N/A'), 'Signal: ' + value(row['signal_percent'], '%'),
                      'Driver: ' + value(row['driver'])]
        for route in network['default_routes']:
            lines.append('Gateway: ' + value(route.get('gateway')) + ' (' + value(route.get('dev')) + ')')
        lines += ['', 'USB']
        for row in snapshot['usb']:
            lines += [row['id'] + ' - ' + row['kind'], value(row['product']),
                      'Drivers: ' + (', '.join(row['drivers']) or 'N/A')]
        lines += ['', 'IP/SSID show local network status.', 'Internet access has not been tested.']
    if section in ('resources', 'all'):
        lines += ['CPU AND MEMORY', 'Cores: ' + value(resources['cpu_count']),
                  'Current frequency: ' + value(resources['cpu_mhz'], ' MHz'),
                  'Governor: ' + value(resources['governor']),
                  'Load (1/5/15 min): ' + ' / '.join(resources['load_average']),
                  'RAM used: ' + size(resources['memory_used_bytes']),
                  'RAM available: ' + size(resources['memory_available_bytes']),
                  'RAM total: ' + size(resources['memory_total_bytes']),
                  'Swap total: ' + size(resources['swap_total_bytes']), '', 'TEMPERATURES']
        for row in resources['temperatures']:
            lines.append(row['type'] + ': ' + value(row['celsius'], ' C'))
        if not resources['temperatures']:
            lines.append('Sensors unavailable.')
        lines += ['', 'BATTERY']
        for row in resources['batteries']:
            lines += ['Charge: ' + value(row['percent'], '%'), 'Status: ' + value(row['status']),
                      'Voltage: ' + value(row['voltage_v'], ' V'), 'Current: ' + value(row['current_ma'], ' mA')]
        lines += ['', 'Values reported by the system.', 'This tool cannot diagnose short circuits.']
    if section in ('storage', 'all'):
        lines += ['STORAGE']
        for row in snapshot['storage']:
            lines += ['', row['mount'] + ' (' + row['filesystem'] + ')', row['device'],
                      'Used: ' + size(row['used_bytes']), 'Free: ' + size(row['free_bytes']),
                      'Total: ' + size(row['total_bytes'])]
        if not any(row['mount'] == '/roms2' for row in snapshot['storage']):
            lines += ['', 'TF2: no partition mounted at /roms2.']
    if section in ('about', 'all'):
        lines += ['ABOUT THIS TOOL', 'Version: ' + VERSION,
                  'Model reported by the device tree:', value(system['device_tree_model']),
                  'The DTB model does not verify the board.', '',
                  'Reads system, network, USB and sensors.',
                  'Does not install drivers, change Wi-Fi,',
                  'update the OS or read network passwords.',
                  'Save report writes JSON/TXT files only',
                  'to the tool\'s reports directory.', '',
                  'Snapshot UTC: ' + snapshot['collected_at']]
    return '\n'.join(clean(line) for line in lines)


def save_report(snapshot, directory):
    directory = Path(directory)
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    base = directory / ('r36s-diagnostics-' + stamp)
    paths = []
    for suffix, content in (('.json', json.dumps(snapshot, ensure_ascii=False, indent=2)),
                            ('.txt', page(snapshot, 'all'))):
        path = base.with_suffix(suffix)
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, 'w', encoding='utf-8') as output:
            output.write(content + '\n')
        paths.append(str(path))
    return paths


class DialogUI:
    def __init__(self, tty_path, reports):
        self.terminal = open(tty_path, 'rb+', buffering=0)
        if not os.isatty(self.terminal.fileno()):
            self.terminal.close()
            raise RuntimeError('The interface requires a terminal.')
        self.reports = reports
        import fcntl
        import termios
        rows, columns, _, _ = struct.unpack('HHHH', fcntl.ioctl(self.terminal.fileno(), termios.TIOCGWINSZ, b'\0' * 8))
        self.height, self.width = min(20, max(rows - 2, 12)), min(58, max(columns - 2, 38))
        self.env = dict(os.environ, TERM='linux', LANG='C.UTF-8', LC_ALL='C.UTF-8')
        # Keep screen rendering on stderr/TTY for EVERY widget. Without this,
        # dialog's textbox renders to our captured stdout instead of the screen.
        self.base = ['dialog', '--stdout', '--backtitle', 'R36S | Diagnostics ' + VERSION, '--title', 'R36S Diagnostics']

    def dialog(self, arguments):
        return subprocess.run(self.base + arguments, stdin=self.terminal, stdout=subprocess.PIPE,
                              stderr=self.terminal, text=True, env=self.env)

    def display(self, title, content):
        with tempfile.TemporaryDirectory(prefix='r36s-diag-') as temporary:
            path = Path(temporary) / 'page.txt'
            wrapped = '\n'.join(textwrap.fill(line, width=self.width - 6,
                                              replace_whitespace=False) if line else ''
                                for line in content.splitlines())
            path.write_text(title + '\n\n' + wrapped + '\n', encoding='utf-8')
            self.dialog(['--exit-label', 'Back', '--textbox', str(path), str(self.height), str(self.width)])

    def run(self):
        try:
            while True:
                result = self.dialog(['--cancel-label', 'Exit', '--ok-label', 'Open',
                                      '--menu', 'A: open | SELECT: back\nView system information.',
                                      str(self.height), str(self.width), str(min(7, self.height - 9)),
                                      '1', 'Device summary', '2', 'Network and USB devices',
                                      '3', 'CPU, memory and battery', '4', 'Storage space',
                                      '5', 'Save report (JSON/TXT)', '6', 'About and limitations', '0', 'Exit'])
                if result.returncode != 0 or result.stdout.strip() == '0':
                    return
                choice = result.stdout.strip()
                if choice not in {'1', '2', '3', '4', '5', '6'}:
                    continue
                snapshot = Collector().collect()
                if choice == '5':
                    paths = save_report(snapshot, self.reports)
                    self.display('REPORT SAVED', '\n\n'.join(paths) + '\n\nFiles are stored on this device and can be copied over SSH/SFTP.')
                else:
                    section = {'1': 'summary', '2': 'network', '3': 'resources', '4': 'storage', '6': 'about'}[choice]
                    self.display('A: back | B/SELECT: back', page(snapshot, section))
        finally:
            self.terminal.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--version', action='version', version=VERSION)
    parser.add_argument('--json', action='store_true', help='Print a JSON snapshot and exit.')
    parser.add_argument('--section', choices=('summary', 'network', 'resources', 'storage', 'about', 'all'), default='summary')
    parser.add_argument('--save', action='store_true', help='Save JSON/TXT without opening the interface.')
    parser.add_argument('--reports-dir', type=Path, default=APP_DIR / 'reports')
    parser.add_argument('--ui', action='store_true')
    parser.add_argument('--tty', default='/dev/tty1')
    args = parser.parse_args()
    if args.ui:
        if not shutil.which('dialog'):
            parser.error('dialog is not installed.')
        DialogUI(args.tty, args.reports_dir).run()
        return
    snapshot = Collector().collect()
    if args.save:
        paths = save_report(snapshot, args.reports_dir)
        print(json.dumps({'reports': paths}, ensure_ascii=False))
    elif args.json:
        print(json.dumps(snapshot, ensure_ascii=False, indent=2))
    else:
        print(page(snapshot, args.section))


if __name__ == '__main__':
    main()
