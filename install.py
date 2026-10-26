#!/usr/bin/python3
"""Per-user installation; no account credentials are distributed or modified."""
import argparse
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile
import time

SOURCE = Path(__file__).resolve().parent
HOME = Path.home()
DEST = HOME / '.local/lib/crd-wayland-monitor'
STATE = Path(os.environ.get('XDG_STATE_HOME', str(HOME / '.local/state'))) / 'crd-wayland-monitor'
CONFIG = Path(os.environ.get('XDG_CONFIG_HOME', str(HOME / '.config')))
DATA = Path(os.environ.get('XDG_DATA_HOME', str(HOME / '.local/share')))
UNIT = 'app-local.crd.WaylandMonitor.service'
APP = 'local.crd.WaylandMonitor.desktop'
ENV = os.environ.copy()
ENV.update(XDG_RUNTIME_DIR='/run/user/' + str(os.getuid()), DBUS_SESSION_BUS_ADDRESS='unix:path=/run/user/' + str(os.getuid()) + '/bus')

def run(args, **kwargs):
    return subprocess.run(args, env=ENV, check=True, **kwargs)

def userctl(*args, **kwargs):
    return run(['systemctl', '--user', *args], **kwargs)

def atomic_write(path, content, mode=0o600):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
        tmp = Path(handle.name)
        handle.write(content.encode() if isinstance(content, str) else content)
        handle.flush()
        os.fsync(handle.fileno())
    tmp.chmod(mode)
    tmp.replace(path)

def host_config(argument):
    paths = [Path(argument).expanduser()] if argument else sorted((HOME / '.config/chrome-remote-desktop').glob('host#*.json'))
    valid = []
    for path in paths:
        try:
            data = json.loads(path.read_text())
            if data.get('host_id') and data.get('host_name') and data.get('private_key'):
                valid.append((path.resolve(), data))
        except (OSError, ValueError):
            continue
    if len(valid) != 1:
        sys.exit('One existing CRD registration is required. Register through https://remotedesktop.google.com/headless first; for multiple registrations use --host-config PATH.')
    return valid[0]

def build(output):
    flags = shlex.split(run(['pkg-config', '--cflags', '--libs', 'gio-unix-2.0'], capture_output=True, text=True).stdout)
    run(['cc', '-Wall', '-Wextra', '-Werror', '-O2', '-fPIC', '-shared',
         str(SOURCE / 'portal-monitor.c'), '-o', str(output), *flags, '-ldl'])

def verify_requirements():
    if os.geteuid() == 0:
        sys.exit('Run as the desktop user, not root.')
    if not Path('/etc/arch-release').exists():
        sys.exit('This installer currently targets Arch Linux and Arch derivatives.')
    if 'KDE' not in ENV.get('XDG_CURRENT_DESKTOP', '').upper() or ENV.get('XDG_SESSION_TYPE') != 'wayland':
        sys.exit('Run from the existing KDE Plasma Wayland desktop session.')
    missing = [name for name in ('cc', 'pkg-config', 'systemctl', 'busctl') if not shutil.which(name)]
    if missing:
        sys.exit('Missing: ' + ', '.join(missing) + '. Install dependencies first: sudo pacman -S --needed base-devel glib2 python')
    if not Path('/opt/google/chrome-remote-desktop/chrome-remote-desktop-host').exists():
        sys.exit('Install the chrome-remote-desktop host package first. Google binaries are not bundled.')
    result = run(['busctl', '--user', 'get-property', 'org.freedesktop.portal.Desktop',
        '/org/freedesktop/portal/desktop', 'org.freedesktop.portal.RemoteDesktop', 'version'], capture_output=True, text=True)
    if int(result.stdout.split()[-1]) < 2:
        sys.exit('RemoteDesktop portal version 2 or newer is required.')

def stop_previous_system_host():
    name = 'chrome-remote-desktop@' + __import__('getpass').getuser() + '.service'
    previous = {}
    for operation in ('is-enabled', 'is-active'):
        result = subprocess.run(['systemctl', operation, name], env=ENV, capture_output=True, text=True)
        previous[operation] = result.stdout.strip()
    statefile = STATE / 'previous-system-service.json'
    if not statefile.exists():
        atomic_write(statefile, json.dumps({'unit': name, **previous}) + '\n')
    if previous['is-active'] == 'active' or previous['is-enabled'] == 'enabled':
        print('Stopping the separate CRD desktop service. Authentication may be requested by the system.', flush=True)
        run(['systemctl', 'disable', '--now', name])

def install(args):
    verify_requirements()
    config, data = host_config(args.host_config)
    with tempfile.TemporaryDirectory(prefix='crd-wayland-build-') as temp:
        library = Path(temp) / 'portal-monitor.so'
        build(library)
        STATE.mkdir(parents=True, mode=0o700, exist_ok=True)
        DEST.mkdir(parents=True, mode=0o700, exist_ok=True)
        for name in ('launch.py', 'portal-monitor.c'):
            atomic_write(DEST / name, (SOURCE / name).read_bytes())
        atomic_write(DEST / 'portal-monitor.so', library.read_bytes(), 0o700)
    atomic_write(DEST / 'settings.json', json.dumps({'host_config': str(config), 'host_id': data['host_id']}) + '\n')
    atomic_write(CONFIG / 'systemd/user' / UNIT, (SOURCE / UNIT).read_bytes(), 0o644)
    atomic_write(DATA / 'applications' / APP, (SOURCE / APP).read_bytes(), 0o644)
    userctl('daemon-reload')
    if shutil.which('update-desktop-database'):
        run(['update-desktop-database', str(DATA / 'applications')])
    stop_previous_system_host()
    try:
        userctl('enable', UNIT)
        userctl('restart', UNIT)
        time.sleep(2)
        userctl('is-active', '--quiet', UNIT)
    except subprocess.CalledProcessError:
        print('Installation did not finish. Use ./install.sh --uninstall --restore-previous to restore the earlier system service.', file=sys.stderr)
        raise
    print('Installed. Approve the first physical-screen sharing prompt if shown. Future starts reuse that permission. Google account authentication is unchanged.')

def uninstall(args):
    userctl('disable', '--now', UNIT)
    for path in (CONFIG / 'systemd/user' / UNIT, DATA / 'applications' / APP):
        path.unlink(missing_ok=True)
    userctl('daemon-reload')
    if args.restore_previous and (STATE / 'previous-system-service.json').exists():
        data = json.loads((STATE / 'previous-system-service.json').read_text())
        if data['is-enabled'] == 'enabled':
            run(['systemctl', 'enable', data['unit']])
        if data['is-active'] == 'active':
            run(['systemctl', 'start', data['unit']])
    print('Disabled and uninstalled the user service and application entry. Local library and private state are retained for recovery.')

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host-config')
    parser.add_argument('--uninstall', action='store_true')
    parser.add_argument('--restore-previous', action='store_true')
    parser.add_argument('--status', action='store_true')
    args = parser.parse_args()
    if args.status:
        userctl('status', UNIT, '--no-pager')
    elif args.uninstall:
        uninstall(args)
    else:
        install(args)

if __name__ == '__main__':
    try:
        main()
    except subprocess.CalledProcessError as error:
        sys.exit('A setup command failed (exit %d). See the message above.' % error.returncode)
