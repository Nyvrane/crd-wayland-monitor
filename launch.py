#!/usr/bin/python3
"""Start the registered Google host on the existing Wayland desktop."""
import json
import os
from pathlib import Path
import socket
import stat
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent
STATE = Path(os.environ.get('XDG_STATE_HOME', str(Path.home() / '.local/state'))) / 'crd-wayland-monitor'
RUNTIME = Path('/run/user') / str(os.getuid())

def available(path):
    try:
        if not stat.S_ISSOCK(path.stat().st_mode):
            return False
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
            client.settimeout(1)
            client.connect(str(path))
        return True
    except OSError:
        return False

def main():
    settings = json.loads((ROOT / 'settings.json').read_text())
    config = Path(settings['host_config'])
    data = json.loads(config.read_text())
    if data.get('host_id') != settings['host_id']:
        sys.exit('Host registration changed. Run the installer again.')
    environment = os.environ.copy()
    environment.update(XDG_RUNTIME_DIR=str(RUNTIME), DBUS_SESSION_BUS_ADDRESS='unix:path=' + str(RUNTIME / 'bus'))
    display = None
    for _ in range(30):
        result = subprocess.run(['systemctl', '--user', 'show-environment'], env=environment, capture_output=True, text=True)
        values = dict(line.split('=', 1) for line in result.stdout.splitlines() if '=' in line)
        candidates = []
        if values.get('WAYLAND_DISPLAY'):
            candidates.append(RUNTIME / values['WAYLAND_DISPLAY'].strip("'\""))
        candidates.extend(sorted(RUNTIME.glob('wayland-*')))
        display = next((p for p in candidates if available(p)), None)
        if display:
            break
        time.sleep(1)
    if not display:
        sys.exit('No existing Wayland desktop. A separate desktop will not be started.')
    STATE.mkdir(parents=True, mode=0o700, exist_ok=True)
    environment.update(WAYLAND_DISPLAY=display.name, XDG_SESSION_TYPE='wayland',
        XDG_CURRENT_DESKTOP='KDE', LD_PRELOAD=str(ROOT / 'portal-monitor.so'),
        CRD_MONITOR_TOKEN_FILE=str(STATE / 'portal-token'))
    for name in ('DISPLAY', 'CHROME_REMOTE_DESKTOP_SESSION', 'PIPEWIRE_REMOTE',
                 'CHROME_REMOTE_DESKTOP_USE_WAYLAND', 'CHROME_REMOTE_DESKTOP_HOST_EXTRA_PARAMS'):
        environment.pop(name, None)
    binary = '/opt/google/chrome-remote-desktop/chrome-remote-desktop-host'
    print('Starting registered host on the existing local Wayland desktop ' + display.name, flush=True)
    os.execve(binary, [binary, '--host-config=' + str(config), '--enable-wayland'], environment)

if __name__ == '__main__':
    main()
