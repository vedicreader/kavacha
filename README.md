# kavacha

A *kavaca* is armour — a shell fitted around a body. kavacha wraps a local web app in a native
window and packages it as a Mac or Windows application.

It does not reimplement py2app or py2exe. It is the wrapper around them that solves the five
things they leave to you, each of which is a day lost the first time you meet it.

## Install

```sh
pip install kavacha              # describe an app, and check what a build would do
pip install "kavacha[window]"    # + the native window
pip install "kavacha[macapp]"    # + py2app and the icon tooling
pip install "kavacha[windows]"   # + py2exe
```

The spec, the build driver and the bundle surgery need nothing but fastcore, so you can describe
an app and ask what building it would take on a machine that cannot build one.

## Describe the app once

```python
from kavacha import App, tree, doc_types, mypyc_modules

app = App(
    name     = 'Demo',
    entry    = 'demo_app.py',
    version  = '1.2.3',
    icon     = 'assets/Demo.icns',
    packages = ['demo', 'fasthtml', 'uvicorn', 'numpy'],   # copied whole, not scanned
    includes = ['demo.cli', *mypyc_modules()],             # single modules nothing references
    grafted  = ['apsw', 'playwright'],                     # an archive cannot hold these
    data     = tree('demo/static', 'demo/static'),
    extras   = ['desktop'],                                # what the build environment installs
    doc_types= doc_types(['.py', '.rs', '.md']),
)
app.py2app_options()   # or .py2exe_options() — same spec, either freezer
```

**`packages` is the part nobody can guess.** A freezer's scanner cannot see an import made inside a
function, which is most of any real application. Naming a package copies it whole. `includes` does
the same for single modules — including mypyc accelerators, which sit *beside* a package under a
name that is a hash of the build, so nothing references them and no scanner finds them.

The `Info.plist` you get carries what every local web app needs and would otherwise be silently
broken without: `NSAllowsLocalNetworking`, or WKWebView refuses `http://127.0.0.1`;
`NSRequiresAquaSystemAppearance: false`, or a dark UI renders on a white window; and `PYTHONUTF8`,
which has to be set before the interpreter starts. Your own entries override any of it.

## Build it

```python
from kavacha import build, check

check(app, root)    # what a build would do here, on any platform, building nothing
build(app, root, setup_py='packaging/macos/setup.py')
```

`build` handles the four things that go wrong:

- **The interpreter.** py2app needs a *framework* Python, and neither uv's nor pyenv's qualifies —
  both are python-build-standalone, `PYTHONFRAMEWORK` is empty, and their stdlib extension modules
  are not files. `build` finds one, makes a venv on it, and re-execs into it.
- **The pins.** pip resolves `>=` against whatever it finds and keeps whatever it has, so a build
  environment goes on shipping the versions it was first made with while the repository moves. The
  environment is installed from `uv.lock`, which is the set your tests ran against.
- **The stamp.** A bundle is derived from the tree and nothing compares them, so an app built
  before a fix installs over one built after it and reports the version it always did. Every build
  writes the commit it came from; `read_stamp` reads it back.
- **The live app.** py2app writes the bundle in place, and `python313.zip` is the running app's
  standard library. Replacing it under a live process makes every later import fail with
  `bad local file header`, raised by whatever imports next and naming nothing that leads back to
  the build. `build` refuses unless you pass `force`.

## After the freezer

```python
from kavacha import finish, graft, strip_zip, link_duplicates
finish(bundle, app)     # graft, strip, link, and install the modern icon
```

Some packages an archive simply cannot hold. `apsw` has the extension module for its own
`__init__`, so a flattened copy loses `apsw.ext`; `playwright` carries a Node binary it has to
*execute*, and a file inside an archive cannot be executed. `graft` puts the real directory in
place, removing the flattened `.so` that would otherwise shadow it, and refuses outright if the
bundle was built on a different Python than the one doing the grafting — the wrong ABI fails at
import with nothing to point at it.

`strip_zip` then drops what nothing can read: anything grafted is in the archive twice over, and a
package that finds its own data with `Path(__file__).parent` gets `False` from `.exists()` for
every path inside an archive. `link_duplicates` hardlinks identical large files across grafted
packages — a fork ships the same 121MB binary byte for byte, and these are read-only library files,
so nothing can write through one and surprise the other.

## Icons

```python
from kavacha.icons import icns, ico, favicon, icons_for
icons_for('assets/logo.png', 'assets', 'Demo')
```

One square image, at least 512px, to every asset a bundle wants. A non-square or too-small source
is refused rather than quietly upscaled — macOS draws icons at 1024, and a blurred app icon is the
kind of thing nobody notices until it ships.

`install_modern_icon` adds a macOS 26 Icon Composer document to a built bundle, after the freezer
and before anything signs it. A machine without Xcode 26 still builds a working app, with the ICNS.

## The window

```python
from kavacha import MenuItem, Std
from kavacha.window import run_shell, shell_ready, use_app

use_app('demo', prefix='DEMO_')          # window titles, config dir, and $DEMO_WINDOW_SIZE
if (ok := shell_ready())[0]:
    run_shell(['http://127.0.0.1:8000/'], titles=['Demo'],
              bar=[('File', [MenuItem('save'), Std('Close', 'performClose:', 'w')])],
              lookup=keymap.get, on_action=dispatch, on_recent=recent_folders)
```

A pywebview window over your loopback server, with the macOS menu bar, the Dock menu of recent
folders, real key equivalents, and the `odoc` Apple Event that opens a folder in a running app.

`use_app` names the application: window titles, the splash, the configuration directory, and the
prefix its environment variables carry. `bar` is the menu table. Its rows are `MenuItem` for your
own actions, `Std` for the rows AppKit implements itself, and `Js` for an expression to evaluate.
`lookup` maps an action to a `Binding`, which is where labels and key equivalents come from.
`on_action` runs a picked row. `on_recent` answers the recent-folder list, for the page through
`window.pywebview.api.recent()` and for the Dock menu. kavacha decides none of them.

## Status

The spec, build driver, bundle surgery and icons are covered by tests that run anywhere. The window
and menus are ported working code, but the platform they matter on is not one CI can exercise here
— treat that module as needing a real run on macOS before you rely on it.
