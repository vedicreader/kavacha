# Decisions

This page lists the decisions that a maintainer must know. Each entry gives the decision, the reason, the version, and the place in the code.
This repo has no CLAUDE.md. The house style and the rules of the package family are in Leela's CLAUDE.md. The changes of each release are in the [CHANGELOG](../CHANGELOG.md).

## What lives here, what does not

- **kavacha holds the native window, the menu vocabulary and the definitions for both freezers.** Leela and other local web apps import them. They do not keep their own copy. `nbs/04_window.ipynb`, `nbs/06_menus.ipynb`, `nbs/01_spec.ipynb`.
- **kavacha wraps py2app and py2exe. It does not replace them.** (1 Sep 2026)
- **The app keeps what is its own.** The package list, the artwork, the language map behind `doc_types` and the registry of recent folders stay in the host. kavacha takes them as arguments. (1 Sep 2026) `App`, `doc_types`, `keep_running_in_dock`.
- **The base package needs only fastcore.** A person can describe an app and check a build on any machine. The window, icons and freezers are extras. `pyproject.toml`.
- **The menu vocabulary is data.** `MenuItem`, `Std`, `Js` and `Binding` are frozen dataclasses. The host gives its menu bar from them. (2 Sep 2026) `nbs/06_menus.ipynb`.

## The spec

- **One `App` gives the options for both freezers.** `packages` are named, not found, because a scanner cannot see an import inside a function. (1 Sep 2026) `App`, `py2app_options`, `py2exe_options` in `nbs/01_spec.ipynb`.
- **The plist carries what a local web app needs.** `NSAllowsLocalNetworking`, or WKWebView refuses 127.0.0.1. `NSRequiresAquaSystemAppearance` false, or a dark UI shows on a white window. `PYTHONUTF8`, which must be set before Python starts. (1 Sep 2026) `App.info_plist`.
- **`CFBundleVersion` is the build, not only the version.** Launch Services compares it by number to choose among copies of one app. (0.0.10) `App.build`.

## Build and bundle

- **`build` finds a framework Python.** py2app needs one, and the Pythons of uv and pyenv are not. `build` makes a venv from it, pinned from `uv.lock`, and runs the build script again in it. (1 Sep 2026) `build`, `build_venv` in `nbs/03_build.ipynb`.
- **Do not build over a running app.** The build replaces the standard library that the live app imports from. Pass `force=True` to do it anyway. Each bundle records the git commit it came from. (1 Sep 2026) `build`, `running_from`, `git_stamp`.
- **`finish` repairs what py2app leaves.** It grafts the packages that cannot run from the zip, strips the zip, hardlinks large twin files, mends Frameworks libraries that two namesakes mixed up, and installs an Icon Composer icon. (1 Sep 2026, 0.0.3) `finish` in `nbs/02_bundle.ipynb`.
- **A grafted package is compiled as unchecked-hash `.pyc`.** An import must never write into a signed bundle. (0.0.4) `graft`.
- **`sign` signs each Mach-O file once per inode, deepest first, and never uses `--deep`.** Then the frameworks, then the bundle, then a strict verify. A hardlink survives. (0.0.3) `sign`.
- **Sign the real bundle only.** Signing the built app with the Apple Development identity of the owner is wanted, so a TCC grant lasts across builds. Never copy, rename or re-sign other binaries, and never fake `argv[0]`: the security agent on the Mac flags it. (24 Oct 2026)

## Window and processes

- **A headless CDP Chrome gets its own port and profile.** Port 9223 and `~/.cache/fastcdp/cdp-chrome` belong to the visible CDP Chrome of the user. A headless one uses `HEADLESS_PORT` (9224) and `HEADLESS_PROFILE`. (26 Oct 2026) `cdp_target` in `nbs/04_window.ipynb`.
- **Quit cleanly.** `quit_cleanly` stops every child, waits one shared second, kills the rest and runs the atexit handlers with a limit. Cmd+Q and SIGTERM go through it. A child dies with its parent. (0.0.4, 0.0.5) `quit_cleanly`, `quit_on_sigterm`.
- **A file that Finder opens reaches the app once.** Both routes go through `open_paths`, which drops a second open within `OPEN_TTL`. (0.0.9) `open_paths`.
- **Child processes get `/dev/null` as stdin.** `run`, which a developer watches, keeps the terminal. (0.0.8)

## Tests

- **CI cannot open a macOS window.** The spec, build, bundle and icon code have tests that run anywhere. Try the window and menu code on a Mac. (1 Sep 2026) `tests/`, README "Status".
