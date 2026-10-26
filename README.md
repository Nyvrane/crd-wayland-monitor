# Chrome Remote Desktop — Existing Wayland Monitor

[Türkçe](README.tr.md)

Use an existing Chrome Remote Desktop registration to share your **current KDE Plasma Wayland desktop**, instead of creating a separate desktop or routing the screen through RDP.

This is an independent, experimental compatibility helper, not an official Google or KDE product. It is currently tested on one Arch-derived KDE Plasma Wayland installation with CRD **157.0.8103.19**. It is not a general promise of compatibility with every Arch desktop or future host release.

## What it does

- Runs Google's unmodified persistent host binary inside your logged-in Wayland session.
- Preloads a small library **only in that process**. It changes the screen-source request from a virtual monitor to a physical monitor.
- Requests a persistent RemoteDesktop portal grant, stores the returned token privately, and rotates it when reused.
- Keeps your existing Google registration, PIN and paired clients.
- Adds a desktop application identity so KDE displays **Chrome Remote Desktop (Wayland)** instead of “Unknown application”.
- Starts when your Plasma desktop session starts. It does **not** log you into Linux, unlock the lock screen, or provide access before a local desktop session exists.
- Keeps KDE's sharing indicator and permission controls intact. No RDP server, firewall rule, or global portal pre-authorization is added.

## Requirements

- Arch Linux or a derivative, KDE Plasma on Wayland.
- A working `xdg-desktop-portal` / KDE backend with RemoteDesktop interface version 2, PipeWire and EIS support.
- The `chrome-remote-desktop` host installed separately and already registered to your Google account.
- `python`, `base-devel`, `glib2`, and `pkgconf`. To install build requirements using your normal package-management workflow:

```sh
sudo pacman -S --needed base-devel glib2 python pkgconf
```

Google binaries and your registration credentials are not included. For first-time registration use [Google's setup page](https://remotedesktop.google.com/headless), then return to this installer. Registration and the first screen-sharing approval require user interaction.

## Install

Download the repository's source archive from GitHub, extract it, and open **Install.desktop** from that extracted folder. KDE may ask you to trust/allow the launcher. Alternatively, from that folder:

```sh
sh install.sh
```

Run as your desktop user, **not with sudo**. The installer compiles the helper locally and installs a per-user service. If a separate CRD system service is enabled, it disables/stops it using your system's normal authorization prompt; it records its earlier state for rollback.

Approve the screen-sharing dialog once, choosing the physical display you want. The portal's remembered permission is reused at future starts. Existing grants made under “Unknown application” may need approval once more after the new application identity is installed. If you revoke permission or a display becomes unavailable, the portal can request approval again.

Then connect to your existing device entry at [Chrome Remote Desktop](https://remotedesktop.google.com/access), including from your phone. Standard Google/PIN authentication still applies.

If multiple host configurations exist, select one explicitly:

```sh
sh install.sh --host-config /absolute/path/to/host-configuration.json
```

The repository provides a **single-launch installer for an already configured host**, not unattended Google account setup or a bundled AUR package installer.

## Status and recovery

```sh
sh install.sh --status
journalctl --user -u app-local.crd.WaylandMonitor.service -n 60 --no-pager
```

Successful startup includes `selecting the existing physical monitor`, `Portal remote desktop session initialization succeeded`, and on subsequent starts `restoring saved portal permission`.

```sh
sh install.sh --uninstall --restore-previous
```

This removes the user service and desktop entry, and restores the previous system-service state if requested. The helper library and private state are retained for recovery; Google account registration is unchanged.

Your state is stored under `$XDG_STATE_HOME/crd-wayland-monitor` (normally `~/.local/state/crd-wayland-monitor`) with private permissions. **Never publish this directory, `settings.json`, any host JSON, or portal tokens.** The source repository does not need any of these files.

## Sharing indicator

The indicator belongs to KDE's desktop portal. Hiding an entry using Plasma's system-tray visibility settings can remove it from the main panel while sharing continues; it may remain in the expanded tray. This project does not suppress the portal's indicator, disguise the application, or automatically change tray visibility.

## Development

```sh
python3 run_checks.py
```

Checks exercise request rewriting, isolation from unrelated D-Bus calls, malformed-message handling, private token storage and rotation, host selection, and installer failure behavior without changing your live services.

The helper relies on Google's GLib D-Bus implementation. A future CRD update can change that implementation; check logs and reconnect after upgrades. If injection no longer applies, do not assume that an online device entry means the desired physical monitor is captured.

## References

- [XDG RemoteDesktop persistence](https://flatpak.github.io/xdg-desktop-portal/docs/doc-org.freedesktop.portal.RemoteDesktop.html)
- [KDE portal application identification](https://develop.kde.org/docs/administration/portal-permissions/)
- [Chromium physical vs virtual monitor selection](https://chromium.googlesource.com/chromium/src/+/HEAD/remoting/host/linux/portal_capture_stream_manager.cc)

## License

MIT. Google Chrome Remote Desktop remains separately licensed and is not redistributed.
