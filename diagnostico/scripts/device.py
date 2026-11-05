#!/usr/bin/env python3
"""Run through WSL: python3 scripts/device.py deploy|survey|run COMMAND.

Uses an already authenticated, host-key-pinned SSH master; never stores passwords.
"""
import hashlib
import os
import json
from pathlib import Path
import shlex
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
APP = '/home/ark/.local/share/r36s-diagnostics'
MENU = '/opt/system/R36S Diagnostics.sh'
# Device from the environment: R36S_HOST=ark@<ip> (required), R36S_KNOWN_HOSTS (optional).
SSH = (['ssh', '-S', '/tmp/r36s-diag-dev-ssh', '-o', 'BatchMode=yes']
       + (['-o', 'StrictHostKeyChecking=yes', '-o', 'UserKnownHostsFile=' + os.environ['R36S_KNOWN_HOSTS']]
          if os.environ.get('R36S_KNOWN_HOSTS') else [])
       + [os.environ.get('R36S_HOST', 'ark@r36s')])


def remote(command, data=None):
    result = subprocess.run(SSH + [command], input=data, capture_output=True)
    if result.returncode:
        raise RuntimeError(result.stderr.decode(errors='replace') + result.stdout.decode(errors='replace'))
    return result.stdout


def deploy():
    mapping = {'src/r36s_diagnostics.py': APP + '/r36s_diagnostics.py',
               'device-launcher.sh': APP + '/launcher.sh',
               'keys.gptk': APP + '/keys.gptk', 'menu-entry.sh': MENU}
    files = []
    for source, destination in mapping.items():
        content = (ROOT / source).read_text(encoding='utf-8').replace('\r\n', '\n')
        files.append({'path': destination, 'content': content,
                      'mode': 0o644 if source == 'keys.gptk' else 0o755})
    installer = r'''
import hashlib,json,os,pathlib,tempfile
files=json.loads(__import__('sys').stdin.read())
app=pathlib.Path('/home/ark/.local/share/r36s-diagnostics')
menu=pathlib.Path('/opt/system/R36S Diagnostics.sh')
old_menu=pathlib.Path('/opt/system/Diagnostico R36S.sh')
for entry in (menu,old_menu):
    if entry.exists() and '/home/ark/.local/share/r36s-diagnostics/launcher.sh' not in entry.read_text():
        raise SystemExit('Existing menu entry belongs to another application; nothing changed.')
if app.exists() and not (app/'r36s_diagnostics.py').exists():
    raise SystemExit('Existing directory has no recognized application; nothing changed.')
app.mkdir(parents=True,exist_ok=True)
receipt=[]
for item in files:
    target=pathlib.Path(item['path'])
    data=item['content'].encode()
    if target.exists() and target.read_bytes()!=data:
        backup=target.with_name(target.name+'.previous')
        backup.write_bytes(target.read_bytes())
        backup.chmod(target.stat().st_mode & 0o777)
    fd,name=tempfile.mkstemp(prefix='.r36s-diag-',dir=target.parent)
    with os.fdopen(fd,'wb') as output:
        output.write(data)
    os.chmod(name,item['mode'])
    os.replace(name,target)
    receipt.append({'path':str(target),'sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'mode':oct(item['mode'])})
if old_menu.exists():
    old_menu.unlink()
print(json.dumps({'files':receipt,'removed_legacy_menu':not old_menu.exists()},indent=2))
'''
    receipt = json.loads(remote('python3 -c ' + shlex.quote(installer), json.dumps(files).encode()))
    (ROOT / 'artifacts').mkdir(exist_ok=True)
    for entry, (source, _) in zip(receipt['files'], mapping.items()):
        expected = hashlib.sha256((ROOT / source).read_text().replace('\r\n', '\n').encode()).hexdigest()
        assert entry['sha256'] == expected
    (ROOT / 'artifacts/deployment-receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt, indent=2))


def survey():
    output = remote('python3 ' + shlex.quote(APP + '/r36s_diagnostics.py') + ' --json')
    json.loads(output)
    (ROOT / 'docs').mkdir(exist_ok=True)
    (ROOT / 'docs/system-survey.json').write_bytes(output)
    print(output.decode())


if __name__ == '__main__':
    action = sys.argv[1]
    if action == 'deploy':
        deploy()
    elif action == 'survey':
        survey()
    elif action == 'run':
        print(remote(sys.argv[2]).decode(), end='')
    else:
        raise SystemExit('Use deploy, survey ou run COMANDO.')
