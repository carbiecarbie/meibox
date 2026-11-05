#!/usr/bin/env python3
"""Execute on the R36S over SSH. Exercises real dialog with a private PTY.

Does not take over the screen or inject keys into the user's active console.
"""
import errno
import fcntl
import json
import os
from pathlib import Path
import pty
import select
import struct
import subprocess
import tempfile
import termios
import time

APP = Path('/home/ark/.local/share/r36s-diagnostics')
master, slave = pty.openpty()
fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack('HHHH', 24, 64, 0, 0))
transcript = bytearray()
with tempfile.TemporaryDirectory(prefix='r36s-diag-ui-test-') as report_dir:
    debug_log = Path(report_dir) / 'dialog-debug.txt'
    wrapper = """import sys
sys.path.insert(0, '/home/ark/.local/share/r36s-diagnostics')
import r36s_diagnostics as d
original = d.DialogUI.dialog
log_path = sys.argv[1]
def trace(self,args):
    result = original(self,args)
    with open(log_path, 'a') as output:
        output.write(repr((args,result.returncode,result.stdout))+'\\n')
    return result
d.DialogUI.dialog=trace
sys.argv.pop(1)
d.main()
"""
    process = subprocess.Popen(['python3', '-c', wrapper, str(debug_log), '--ui',
                                '--tty', os.ttyname(slave), '--reports-dir', report_dir],
                               stdin=slave, stdout=slave, stderr=slave, start_new_session=True)
    def expect(marker, timeout=15):
        current = bytearray()
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if select.select([master], [], [], .1)[0]:
                try:
                    chunk = os.read(master, 65536)
                except OSError as error:
                    if error.errno == errno.EIO:
                        break
                    raise
                current.extend(chunk)
                transcript.extend(chunk)
                if marker.encode() in current:
                    return
            if process.poll() is not None:
                break
        raise AssertionError('Tela nao encontrada: ' + marker + '\nprocess=' + str(process.poll())
                             + '\n' + (debug_log.read_text() if debug_log.exists() else '')
                             + '\n' + current.decode(errors='replace'))
    def send(data):
        # The first matching label can be emitted before dialog enables input.
        # Wait for the rest of that screen to settle before sending a key.
        time.sleep(.2)
        while select.select([master], [], [], .05)[0]:
            transcript.extend(os.read(master, 65536))
        os.write(master, data)
    try:
        expect('Device summary')
        send(b'\r')
        expect('Kernel:')
        send(b'\r')
        expect('Device summary')
        send(b'2\r')
        expect('SSID:')
        send(b'\r')
        expect('Device summary')
        send(b'3\r')
        expect('Current frequency:')
        send(b'\r')
        expect('Device summary')
        send(b'4\r')
        expect('STORAGE')
        send(b'\r')
        expect('Device summary')
        send(b'5\r')
        expect('REPORT SAVED')
        saved = list(Path(report_dir).glob('*.json'))
        assert len(saved) == 1
        report = json.loads(saved[0].read_text())
        assert report['system']['architecture'] == 'aarch64'
        assert len(list(Path(report_dir).glob('r36s-diagnostics-*.txt'))) == 1
        send(b'\r')
        expect('Device summary')
        send(b'6\r')
        expect('ABOUT THIS TOOL')
        send(b'\r')
        expect('Device summary')
        send(b'0\r')
        process.wait(timeout=5)
        assert process.returncode == 0
        assert b'Traceback' not in transcript
        print(json.dumps({'status': 'passed', 'terminal': '24x64',
                          'pages': ['summary', 'network', 'resources', 'storage', 'save', 'about'],
                          'report_json_txt': True, 'physical_buttons_tested': False}))
    finally:
        if process.poll() is None:
            process.terminate()
            process.wait(timeout=5)
        os.close(master)
        os.close(slave)
