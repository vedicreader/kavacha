# Release notes

<!-- do not remove -->

## 0.0.7

- `ShellApi.set_background` lets a page with themes give the native window its background, as `window.pywebview.api.set_background('#rrggbb')`. Every open window repaints on macOS, including what WebKit draws past the page during a resize, and later windows open on the colour. Anything but `#rrggbb` is refused.
- `run_shell` and `make_window` take `background`: one colour, or a `(light, dark)` pair that `window_background` picks from by the system's mode. The splash and the unreachable page draw on it, with dark text on a light colour.

## 0.0.6

- `kavacha.window` names five things a host reaches for: `dock_delegates`, `OpenHandler`, `RecentTarget`, `hidden_windows` and `keyed_windows`. The old private names stay as aliases for the same objects.
- `start_cdp` asks fossick's public `debug_ready`, which needs fossick 0.1.19 or later.

## 0.0.5

- A forked child gets the default SIGTERM back and drops the parent's wakeup socket, so stopping a worker works and cannot quit the app.
- A multiprocessing child exits when its parent dies, so a Force Quit no longer leaves idle workers behind.
- `quit_cleanly` terminates every child, waits one shared second, kills the rest, and reaps again after the atexit handlers; it sets `quitting` first. A quit with 14 workers takes 0.07 s, where it took 28 s.
- `dev` is an extra, so CI and the docs build install Pillow. The Linux `menus` test passes the arguments `menus` now takes.

## 0.0.4

- `graft` byte-compiles the grafted package as unchecked-hash `.pyc`, so importing it never writes into a signed bundle.
- `quit_cleanly` stops the process's multiprocessing children, then runs its atexit handlers with a time limit. The Dock delegate calls it from `applicationWillTerminate_`, because the C `exit()` behind Cmd+Q skips both.
- `quit_on_sigterm` turns SIGTERM into a Cocoa quit. `run_shell` installs it on macOS.

## 0.0.3

- `mend_frameworks` replaces a Frameworks library left with one library's header over another's body when two share a basename, and reports every shared basename. `finish` runs it.
- `sign` signs every Mach-O file once per inode, so hardlinks made by `link_duplicates` survive.
- `is_macho`, `macho` and `corrupt` read Mach-O headers without macholib.

## 0.0.2
kavacha relese to package webapps as mac or windows app
