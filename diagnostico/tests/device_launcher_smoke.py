#!/usr/bin/env python3
"""Briefly open the installed menu entry on tty1, then restore EmulationStation."""
import json
import os
from pathlib import Path
import subprocess
import time


def command(args):
    return subprocess.run(args, check=True, capture_output=True, text=True).stdout


assert command(['systemctl', 'is-active', 'emulationstation']).strip() == 'active'
# No game should be running when temporarily taking over the display.
for name in ('retroarch', 'retroarch32', 'PPSSPPSDL', 'drastic'):
    assert subprocess.run(['pgrep', '-x', name], capture_output=True).returncode != 0, name + ' ativo'
before = command(['pgrep', '-x', 'gptokeyb']) if subprocess.run(['pgrep', '-x', 'gptokeyb'], capture_output=True).returncode == 0 else ''
process = None
missing_runtime = '/tmp/r36s-diagnostics-regression-missing-runtime'
assert not Path(missing_runtime).exists()
command(['sudo', '-n', 'systemctl', 'stop', 'emulationstation'])
try:
    process = subprocess.Popen(['timeout', '--kill-after=3s', '8s', '/bin/bash',
                                '/opt/system/R36S Diagnostics.sh'],
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                               env=dict(os.environ, XDG_RUNTIME_DIR=missing_runtime))
    time.sleep(2)
    assert process.poll() is None, process.communicate()
    helpers = command(['pgrep', '-af', '^/opt/inttools/gptokeyb -c /home/ark/.local/share/r36s-diagnostics/keys.gptk'])
    screen = subprocess.run(['sudo', '-n', 'cat', '/dev/vcs1'], check=True,
                            capture_output=True).stdout.decode('cp437', errors='replace')
    assert 'Device summary' in screen, screen
    assert 'Save report (JSON/TXT)' in screen, screen
    assert not Path(missing_runtime).exists(), 'Nao criar a pasta externa de sessao'
    assert (Path('/home/ark/.local/share/r36s-diagnostics/state/runtime')).is_dir()
    stdout, stderr = process.communicate(timeout=12)
    assert process.returncode == 124, (process.returncode, stdout, stderr)
    assert 'Traceback' not in stderr, stderr
    assert subprocess.run(['pgrep', '-af', '^/opt/inttools/gptokeyb -c /home/ark/.local/share/r36s-diagnostics/keys.gptk'], capture_output=True).returncode != 0
    print(json.dumps({'status': 'passed', 'native_tty_menu_visible': True,
                      'own_gamepad_helper_started_and_cleaned': True,
                      'missing_xdg_runtime_regression': True,
                      'physical_buttons_tested': False, 'shared_helper_before': before.strip()}))
finally:
    try:
        if process is not None and process.poll() is None:
            process.wait(timeout=12)
    finally:
        command(['sudo', '-n', 'systemctl', 'start', 'emulationstation'])
