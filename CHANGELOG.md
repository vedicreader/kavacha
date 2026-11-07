# Release notes

<!-- do not remove -->

## 0.0.17

- Thin apps. A thin app is kavacha's native launcher and the app's Python server, whose packages come from a signed environment lock with its own channel. `contract/api-1.md` is the contract, and `contract/fixtures/` holds the cases the Python and Swift sides both check.
- `Thin` describes a thin app once, in `packaging/kavacha.toml` or `[tool.kavacha.thin]`. `Thin.config()` writes `kavacha.json`, the launcher's only source of names; `Thin.info_plist()` writes the bundle's `Info.plist`; `childenv()` gives the clean child environment per OS.
- `kavacha.host.HostClient` is the server's side: the token from stdin, the control routes, `scrub` of launcher 1.0.0's build settings, and `link_tools` (a `.cmd` shim on Windows).
- `kavacha lock make|hash|check|test|diff|publish|promote|verify|key|dev-lock|fetch|wheel|fixtures|verify-app` makes, tests, signs and publishes a lock. An app adds its own checks in a hooks file (`Thin.hooks`); the test record's code hash covers the hooks too.
- `kavacha ship mac` builds, signs and checks a bundle; `--release V` also notarizes, staples, uploads to `app-v<V>` and writes the cask.
- `swift/` is the launcher, from Leela 1.0, with its history: `KavachaCore`, `KavachaApp` and the `kavacha-launcher` executable, configured by `kavacha.json`, and the same code as SwiftPM libraries (`Package.swift` at the root). `kavacha-launcher --check-menu <menu.json>` checks a menu bar with no window. `make -C swift test` runs the Swift tests.
- The launcher's title bar is a spec setting (`titlebar = "mac-unified"` or `native`). Unified: transparent with a hidden title over a full-size content view and an empty unified toolbar, the style in the first URL (`?titlebar=mac-unified`) and from the `titlebar` bridge call, and a mouse-down on an element with the class `pywebview-drag-region` drags the window (a double-click does what `AppleActionOnDoubleClick` says). The window title is still set.
- Every file panel of the launcher is a sheet on the window that asked, so a tiling window manager does not move the app away.
- `launcher_json()` gives `LAUNCHER_ROWS` as menu rows.
- Keys off a Mac: `pc_key(row)` gives the chord a `Std` row takes on Linux or Windows. Full Screen is F11, Close Window is Ctrl+Shift+W and Quit is Ctrl+Q. Hide, Hide Others, Minimize, Zoom and Bring All to Front get `None`, so the row is not shown. Before, ⌃⌘F for Full Screen became Ctrl+F, which is Find. `pc_chord` writes any chord with `mod` as Control.
- `LINUX_RESERVED` and `pc_reserved` list the chords a Linux desktop keeps (Regolith and GNOME): every Super chord, Alt+Tab, Alt+F2, Alt+F4, Ctrl+Alt+T, Ctrl+Alt+Delete, Ctrl+Alt+L and Ctrl+Alt+arrows.
- `menu_json(bar, lookup, mac=False, native=())` builds the menu bar for a GTK launcher. A row carries a `chord` label, and a GTK `accel` only for Quit, Close Window, Full Screen and the actions in `native`. GTK runs window accelerators before the focused widget, so the editing keys stay labels only and Ctrl+C still reaches a terminal. `mac=None` uses the platform the code runs on. `gtk_accel` writes a chord as a GTK accelerator.
- `chord_glyph` writes a Super chord as `Super+D` off a Mac.

## 0.0.16

- `unified_titlebar(window)`, turned on by `shell_api().unified = True`: on macOS the title bar is transparent, the title is hidden and the page fills the window under the traffic lights (52 px band); on Windows the caption takes the theme's colours. The title is still set, so the Window menu and Sanketa read it. The page learns the mode from a `titlebar=<mode>` query on the first URL and from `ShellApi.titlebar()`.

## 0.0.15

- `sign` retries a file up to 3 times when Apple's timestamp server does not answer, so a short outage no longer fails a ship.

## 0.0.14

- `ShellApi.pick_path()` shows one chooser for a file or a folder, and `open_path(path)` opens a folder as `open_folder` does and a file as a Finder open does.
- A file or folder dropped on the window from Finder opens as a Finder open (`dropped`, `arm_drops`). Drops the page handles itself (tabs, cells) stay the page's.
- `exact_bar`: a menu row fires only when its chord matches exactly. Before, a row without Shift also caught Shift with keys such as Return, so ⌥⇧↩ ran ⌥↩'s row.
- The page can no longer call `ShellApi`'s host callbacks (`on_…`). Before, a page script could call `pywebview.api.on_open_folder(path)` and open any folder with no question.

## 0.0.13

- A menu key with Shift is written as the shifted character with no Shift flag, as AppKit expects: ⇧⌘P is `P` with ⌘, ⇧⌘/ is `?`. Before, 42 such rows never ran from the menu. Named keys (arrows, Return) keep the Shift flag.
- `mac_key` refuses Hyper chords, and `menu_chord` refuses `RESERVED` chords (macOS system chords and the window manager's). A scoped row shows its chord only when no other scope uses it, and the menu takes the first chord it may show.
- New: `menu_json(bar, lookup)` builds the menu bar for any launcher, `LAUNCHER_ROWS` lists the rows a launcher adds (Quit, Hide, Close Window, Undo, Redo, Minimize, Full Screen), and `chord_glyph` writes a chord as ⌃⌥⇧⌘ glyphs on a Mac and as `Ctrl+Shift+P` elsewhere.

## 0.0.12

- `strip_zip` also deletes unreachable paths that sit unzipped beside the archive, and `link_duplicates` makes relative symlinks on macOS, so a zipped app keeps one copy of a duplicate driver.

## 0.0.11

- `ShellApi.on_picked(paths)` runs after the person picks a folder in the native folder picker. A host uses it to grant that one folder, for a short time, without a second question.
- `ShellApi.on_page_folder(path)` runs when page JavaScript asks to open a folder through the window's API. Before, the host could not tell such a call from a folder that the person dropped on the Dock, so the host trusted it. Now the host can ask the person first.

## 0.0.10

- `App.build` sets `CFBundleVersion`, which Launch Services compares numerically to choose among copies of one app; `CFBundleShortVersionString` stays `version`. Before, both were `version`, so every local build of one release looked identical and macOS could open an old copy.

## 0.0.9

- A file Finder opens, by double-click or Open With, reaches the app through `run_shell(on_open_file=...)`, warm or cold. Before, only folders got through and a file was dropped. The `App` delegate answers `application:openFiles:` and replies success or failure; the raw `odoc` handler also passes files. `open_paths` sends each path to the folder or file callback once within `OPEN_TTL` seconds, so the two routes never deliver one open twice.
- `open_window` brings the app forward, and a reused window hidden to the Dock is shown again, through `bring_forward`.

## 0.0.8

- The interpreter probes, `uv export`, `git`, `iconutil`, `install_name_tool` and `codesign` calls get `/dev/null` as stdin, so a child can neither read the terminal it was started from nor leave it non-blocking. `run`, which a developer watches in the foreground, still shares it.

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
