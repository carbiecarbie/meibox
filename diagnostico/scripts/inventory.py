#!/usr/bin/env python3
"""Read-only supplementary inventory; run on the console, emit JSON."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess


def run(args):
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=8)
        return {'exit_code': result.returncode, 'stdout': result.stdout.strip(), 'stderr': result.stderr.strip()}
    except (OSError, subprocess.TimeoutExpired) as error:
        return {'error': str(error)}


paths = ['/etc/os-release', '/proc/cpuinfo', '/proc/cmdline', '/proc/mounts',
         '/etc/systemd/system/emulationstation.service', '/opt/inttools/keys.gptk',
         '/sys/devices/system/cpu/cpu0/cpufreq/scaling_available_frequencies',
         '/sys/class/graphics/fb0/virtual_size', '/sys/class/graphics/fb0/bits_per_pixel',
         '/sys/class/graphics/fb0/stride']
files = {}
for name in paths:
    try:
        files[name] = Path(name).read_text(errors='replace')
    except OSError:
        files[name] = None
hashes = {}
for path in Path('/boot').glob('*'):
    if path.is_file() and (path.suffix == '.dtb' or path.name in ('logo.bmp', 'boot.ini')):
        hashes[str(path)] = hashlib.sha256(path.read_bytes()).hexdigest()
commands = [ ['id'], ['uname', '-a'], ['python3', '--version'], ['dialog', '--version'],
             ['nmcli', '-g', 'VERSION', 'general'], ['findmnt', '/opt/system/Tools'],
             ['ls', '-l', '/dev/input/by-path'], ['ls', '-l', '/dev/tty1', '/dev/uinput', '/dev/fb0'],
             ['systemctl', 'is-active', 'emulationstation', 'ssh', 'NetworkManager'],
             ['ls', '-ld', '/opt/system', '/opt/inttools', '/roms/tools'],
             ['ls', '/home/ark/.config/retroarch/cores'] ]
result = {'collected_at': datetime.now(timezone.utc).isoformat(), 'files': files,
          'boot_sha256': hashes,
          'commands': [{'argv': args, **run(args)} for args in commands],
          'dependencies': {name: shutil.which(name) for name in
                           ('bash', 'python3', 'dialog', 'flock', 'pgrep', 'ip', 'nmcli', 'lsusb', 'rfkill')},
          'menu_entries': sorted(path.name for path in Path('/opt/system').glob('*'))}
print(json.dumps(result, indent=2))
