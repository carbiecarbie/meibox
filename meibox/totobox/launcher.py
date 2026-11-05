"""Builds and runs a game's command exactly the way EmulationStation does.

Totobox does not know emulators: it takes the system's <command> from
es_systems.cfg and fills in the four variables the R36S configs use.
"""
import os
import shlex
import signal
import subprocess
import time

GOVERNOR = "performance"  # what ES fcamod passes (GlobalPerformanceGovernor default)


def pick_emulator(emulators, game_emulator=None, game_core=None):
    """(emulator, core) for a game: the game's own choice, else the system's first listed."""
    emulator, core = game_emulator, game_core
    if not emulator and emulators:
        emulator = emulators[0][0]
    if not core:
        for name, cores in emulators:
            if name == emulator and cores:
                core = cores[0]
                break
    return emulator or "", core or ""


def build_command(template, rom_path, emulators, game_emulator=None, game_core=None, governor=GOVERNOR):
    emulator, core = pick_emulator(emulators, game_emulator, game_core)
    return (template.replace("%ROM%", shlex.quote(rom_path))
            .replace("%EMULATOR%", emulator)
            .replace("%CORE%", core)
            .replace("%GOVERNOR%", governor))


def _signal_group_except(pgid, sig):
    out = subprocess.run(["pgrep", "-g", str(pgid)], capture_output=True, text=True).stdout.split()
    for pid in map(int, out):
        if pid != pgid:
            try:
                os.kill(pid, sig)
            except ProcessLookupError:
                pass


def run(command, log_path=None, test_timeout=None):
    """Run a game command and wait. Returns (exit_code, seconds).

    test_timeout (development only): after N seconds the game's processes are asked
    to quit, so the shell still runs the trailing `sudo perfnorm`.
    """
    t0 = time.time()
    log = open(log_path, "ab") if log_path else subprocess.DEVNULL
    try:
        env = dict(os.environ, TERM=os.environ.get("TERM") or "linux")  # ES runs games with TERM=linux
        proc = subprocess.Popen(["bash", "-c", command], stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                                start_new_session=True, env=env)
        if test_timeout:
            try:
                proc.wait(timeout=test_timeout)
            except subprocess.TimeoutExpired:
                # The game is a grandchild (wrapper script -> real emulator), so signal every
                # process in the game's group except the shell, which still has to run perfnorm.
                _signal_group_except(proc.pid, signal.SIGTERM)
                try:
                    proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    os.killpg(proc.pid, signal.SIGKILL)
                    proc.wait()
        else:
            proc.wait()
        return proc.returncode, time.time() - t0
    finally:
        if log_path:
            log.close()
