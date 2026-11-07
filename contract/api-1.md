# The thin app contract, API 1

A thin app is a small native launcher and a Python server. The launcher owns the windows. The server runs headless as the launcher's child. The Python packages do not ship in the app: they come from a signed environment lock, which has its own number and its own channel. A new lock reaches people without a new app build.

This file is the contract between the three parts: the launcher (`swift/`, later Rust on Windows), the lock tools (`kavacha.lock`) and the server (`kavacha.host`). Each part reads the same fixtures in `contract/fixtures/`, so a change to one side that the others do not follow fails a test.

In the names below, `<Name>` is the app's name (`Leela`), `<name>` is its lower case form (`leela`), and `<PREFIX>` is its variable prefix (`LEELA_`). All of them come from the app's `Thin` spec.

## The spec and kavacha.json

The app describes itself once, in `packaging/kavacha.toml` or `[tool.kavacha.thin]` in `pyproject.toml`. `contract/fixtures/leela/kavacha.toml` is a full example. `Thin.config()` writes `kavacha.json`. The launcher reads every name from that file and has no app name in its code.

| Key | Meaning |
|---|---|
| `api` | the contract version; a launcher refuses a file with a higher `api` than its own |
| `name`, `identifier` | the app name and bundle id |
| `support` | the folder name in Application Support and Caches |
| `marker` | the env marker file name, such as `.leela-env.json` |
| `sig_ns` | the SSHSIG namespace, such as `leela-lock` |
| `env_prefix` | the prefix of every variable the launcher sets or reads |
| `server`, `health` | the console script in the env's `bin`, and the route that says the server is ready |
| `lock_project` | the pinned project's name, left out of the package changes |
| `python` | the Python minor, for the setup window |
| `channel` | the base URL of the GitHub release downloads |
| `extras` | the extras a person can add |
| `bridge` | `{handler, flag, methods, js_global}`: the page's native bridge |
| `sites` | `{list, go}`: the routes of a server that gives each site a port of its own; empty for one window |
| `routes` | `{open, grant, recent}`: the server routes the launcher calls |
| `capabilities` | the control routes the launcher answers |
| `menus`, `menu_action_js` | the menu bar route, and the JavaScript an action row runs (`{action}` is filled in) |
| `window` | `{size, min_size, home, title_prefix}` |
| `titlebar` | `{style, query, drag_class}`: the window's title bar; see below |
| `cask`, `debug_env` | the Homebrew cask, and the variable that turns on the web inspector |

## What is in the bundle

```
<Name>.app/Contents/
  MacOS/<Name>              kavacha's launcher
  Helpers/uv                the pinned uv, signed with the app
  Resources/Lock/           the bootstrap lock: manifest.json, manifest.sig, pyproject.toml, uv.lock, .python-version
  Resources/lock-keys.pub   the public keys that may sign a lock (main and emergency)
  Resources/childenv.json   the clean child environment, flat, for this OS
  Resources/kavacha.json    the names above
  Resources/AppIcon.icns
  Info.plist                from Thin.info_plist, with NSAllowsLocalNetworking
```

A Linux launcher holds the same files beside its binary: `uv`, `Lock/`, `lock-keys.pub`, `childenv.json` and `kavacha.json`.

## Where the launcher keeps its files

The layout is the same on every OS; only the two base folders differ.

| OS | `<support>` | `<caches>` |
|---|---|---|
| macOS | `~/Library/Application Support/<support>` | `~/Library/Caches/<support>` |
| Linux | `$XDG_DATA_HOME/<name>` (`~/.local/share/<name>`) | `$XDG_CACHE_HOME/<name>` (`~/.cache/<name>`) |
| Windows | the Linux layout inside WSL, where the server runs | |

```
<support>/
  locks/<n>/                each lock the launcher accepted
  envs/<hash16>/            one env per lock hash; <marker> is written last
  python/                   the managed Pythons uv downloads
  bin/                      the links to the env's agent tools
  state.json                {current, previous, pending, highest_n, bad, locks, extras, early_crashes, proven, held, pruned}
  logs/                     sync-<hash16>.log, server.log, setup.log, windows.log
  run.lock                  flock: one launcher at a time
<caches>/uv                 the uv cache
```

- Every key of `state.json` is optional. A file from an older launcher still loads (`fixtures/state_cases.json`).
- The launcher writes `state.json.tmp`, then renames it.
- An env folder with no marker is a partial build, and garbage collection removes it.

## The lock hash

sha256 over the name and the bytes of `pyproject.toml`, `uv.lock` and `.python-version`, in that order, then the bytes `uv` and the uv version. `fixtures/lock_hash/vector.json` pins the value for the three files beside it.

## The child environment

`childenv.json` is one spec that the launcher and the lock tools both read. kavacha's default (`kavacha.thin.CHILDENV`) has common keys and a section per OS; the bundle holds the flat form for its OS.

- `drop` and `drop_prefixes`: names taken out of the launcher's environment. `{prefix}` in a prefix is `<PREFIX>`.
- `set`: names the launcher's own uv runs get when the person has none.
- `uv`: what the launcher's own uv runs get, with `{cache}`, `{python}`, `{python_version}` and `{env}` filled in.
- `server`: what the server also gets. The server gets the person's environment, less the dropped names, with `tool_dirs` first on `PATH`, and `HOME` set. It gets no `uv` key: every kernel, terminal and agent shell inherits the server's environment.
- `sync`, `extra`, `inexact`: the build command; `server_args`: the server's arguments, with `{port}` filled in.
- `fixtures/childenv_cases.json` gives a parent environment and what each side must make of it.

## The server's start (host mode)

The launcher starts `envs/<hash16>/bin/<server>` by its absolute path with these variables:

| Name | Value |
|---|---|
| `<PREFIX>HOST_URL` | `http://127.0.0.1:<port>` of the launcher's control server |
| `<PREFIX>APP_VERSION` | the app version |
| `<PREFIX>APP_BUNDLE` | the path of the app |
| `<PREFIX>LOCK_N` | the number of the lock the env came from |
| `<PREFIX>ENV_HASH` | the lock hash of the env |
| `<PREFIX>UV` | the path of the bundled uv |

The token is never in argv, the environment, a file or a log. The launcher writes one line `<token>` to the server's stdin right after the start, and closes its end. The server reads that line first (5 s at most), keeps it in memory, and reopens stdin on `/dev/null` (`HostClient.take`). No line, an empty line or a late line stops the server. A `<PREFIX>HOST_TOKEN` in the environment is ignored, with a warning. The server takes `<PREFIX>HOST_URL` out of its environment, so no child gets it. Launcher 1.0.0 gave its server uv's build settings; the server takes them out first (`kavacha.host.scrub`).

## The control routes of the launcher

Only the server calls them. Each request carries `Authorization: Bearer <token>`; a wrong token gets 401.

| Route | Body | Answer |
|---|---|---|
| `POST /confirm` | `{question}` | `{answer: bool}` from a native alert; any other answer means no window could ask, never a No |
| `POST /extras` | `{name}`, one of `extras` | `{ok}`; the state is in `/status` |
| `POST /update` | `{kind}`, `app` or `lock` | `{state, line}` |
| `GET /update` | | `{state, line}`; `state` is `idle`, `running`, `ready`, `same`, `unavailable`, `done` or `error` |
| `POST /restart` | `{}` | `{ok}`; the launcher stops the server, switches env if one is pending, and starts it again |
| `GET /status` | | `{app_version, api, brew, lock: {current_n, newest_n, newer, needs_app, changes}, extras: {name: {state, log}}, env}` |
| `POST /grant` | `{nonce, path}` | `{ok}`: true once, when the launcher issued `nonce` for `path` in the last minute |

## The server routes the launcher calls

| Route | Answer |
|---|---|
| `GET <health>` | `{status: "ok", version, lock_n}` |
| `POST <routes.open>?path=&grant=` | `{ok, url, id, name, root}`: the site that opens `path`; a grant makes the folder trusted |
| `POST <routes.grant>?path=&grant=` | `{ok, root}`: a folder picked in the launcher's dialog opens next with no question |
| `GET <menus>` | `{menus: [{title, items: [{title, action \| selector \| js, key, mask} \| {sep: true}]}], launcher: [...]}` (`kavacha.window.menu_json`, `launcher_json`) |
| `GET <routes.recent>` | `{recent: [path]}` for the Dock menu |
| `GET <sites.list>` | `{sites: [{id, name, root, url}], port}` |
| `GET <sites.go><id>` | 307 to that site's own port |

A later API adds `POST /app/quit` with the token, so a launcher that cannot send a signal (a Windows launcher and a server in WSL) can stop the server; today the launcher sends SIGTERM and the server stops within its grace time. All of them answer only on loopback. The launcher sends the server nothing secret: a process that takes the server's port first gets only a nonce for one path, good once.

## The window bridge

The launcher injects `window.<js_global>.api` into each page of the server, with one function per name in `bridge.methods`, and fires `<js_global>ready`. Each call posts `{method, args}` to the script message handler `bridge.handler` and gets one reply. `fixtures/bridge_cases.json` gives each body and the action it is. A path in a call or a reply is the server's path. A launcher whose server runs elsewhere (Windows with WSL) translates it at the bridge, in one place, as `wslpath` does. A call from a frame that is not the main frame of a server page is refused. Every file panel the launcher opens is a sheet on the window that asked, never a free panel: a free panel can hide the app under a tiling window manager.

## The title bar

`titlebar.style` is `mac-unified` or `native`.

- `mac-unified` (macOS): the title bar is transparent, the title is hidden, the content view is full size, and an empty unified toolbar makes the bar 52 pt with the traffic lights in its centre. The launcher still sets the window title from `set_title`, so the Window menu and other apps can read it. The first URL of a window gets `?<query>=mac-unified`, and the `titlebar` bridge call answers the same. The page reserves 94 px on the left for the traffic lights and drops it in full screen. A mouse-down on an element whose own class is `drag_class` drags the window; a double-click on it zooms or minimizes, as the system setting `AppleActionOnDoubleClick` says.
- `native` (Linux, WSL, and any launcher that cannot draw into its title bar): the launcher keeps the native title bar, sends `?<query>=native`, and the page reserves no gap.

## The manifest

`manifest.json` is signed into `manifest.sig`.

| Key | Meaning |
|---|---|
| `n` | the lock number; the launcher refuses a number it already passed |
| `hash` | the lock hash |
| `files` | `{name: sha256}` for the three lock files |
| `<name>` | the app version in the lock, under the app's package name |
| `python` | the exact Python |
| `uv_min` | the uv the lock was tested with; a lower bundled uv needs a newer app |
| `launcher_api_min` | the lowest launcher API that can run it |
| `platform` | such as `darwin-arm64` or `linux-x64` |
| `macos_min` | the lowest macOS |
| `download_bytes` | about how much a first install downloads |

The launcher refuses a lock when the signature or a hash is wrong, when `n` is not above `highest_n`, when the platform or the OS is wrong, or when the hash failed before. It says the app is too old when `uv_min` or `launcher_api_min` is above its own. `fixtures/manifest_cases.json` gives each case.

## The channel

Each lock is a release `lock-<n>` with the three lock files (`.python-version` is the asset `python-version`), `manifest.json`, `manifest.sig` and `tested.json`. The release `lock-channel` holds the pointers `channel.json` + `channel.sig` (stable) and `channel-test.json` + `channel-test.sig` (test). `<PREFIX>LOCK_CHANNEL=test` points a launcher at the test pointer.

A pointer is `{n, manifest_sha256, published, channel}`. The launcher refuses a pointer whose `channel` is not the one it asked for. Pointers do not expire; an old `expires` field is ignored.

## Signing

SSH Ed25519 keys, SSHSIG (`ssh-keygen -Y sign -n <sig_ns>`). The tools check with `ssh-keygen -Y verify`. The launcher checks SSHSIG itself: the key must be one of the embedded keys, the namespace must be `sig_ns`, the hash `sha512` or `sha256`, and the Ed25519 signature must hold over the SSHSIG signed data. `fixtures/sshsig` has a message signed by the main key, the emergency key, a stranger's key, and the main key under another namespace; only the first two are good.

## Changing this contract

A change that an older launcher cannot read raises `api`. Run `uv run python tests/regen_fixtures.py` after a change, then run the Python tests and `make -C swift test`.
