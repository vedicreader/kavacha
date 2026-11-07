"Write contract/fixtures: run `uv run python tests/regen_fixtures.py` after a change to the contract, then commit what changed."
import json, os, shutil, sys, tempfile
from pathlib import Path
from kavacha.thin import Thin, childenv
from kavacha.lock import Lock, lock_hash, fixtures, dumps

FIX = Path(__file__).resolve().parent.parent/'contract'/'fixtures'

def lock_vector():
    d = FIX/'lock_hash'; d.mkdir(parents=True, exist_ok=True)
    (d/'pyproject.toml').write_text('p'); (d/'uv.lock').write_text('l'); (d/'.python-version').write_text('3.12.16\n')
    (d/'vector.json').write_text(dumps(dict(uv='0.13.6', hash=lock_hash(d, '0.13.6'), others=[dict(uv='0.13.7', hash=lock_hash(d, '0.13.7'))])))

def _uv_env(s, parent, home, vals):
    "What the launcher's `uvEnv` gives: the kept names, HOME, the tool folders then the parent's PATH, `set` where empty, the uv keys."
    e = {k: v for k, v in parent.items() if k not in s['drop'] and not k.startswith(tuple(s['drop_prefixes']))} | {'HOME': home}
    path = [home + d[1:] if d.startswith('~/') else d for d in s['tool_dirs']] + parent.get('PATH', '').split(':')
    e['PATH'] = ':'.join(dict.fromkeys(p for p in path if p))
    return {k: v for k, v in s['set'].items() if k not in e} | e | {k: v.format(**vals) for k, v in s['uv'].items()}

def _server_env(s, parent, home, extra):
    e = _uv_env(s | dict(set={}, uv={}), parent, home, {})
    return e | s['server'] | extra

def childenv_cases():
    s = childenv('DEMO_', 'linux', ['--app', '--port', '{port}'])
    parents = [dict(PATH='/usr/bin:/x', HOME='/h', VIRTUAL_ENV='/v', PYTHONPATH='p', UV_INDEX_URL='x', CONDA_PREFIX='c', DEMO_HOST_TOKEN='t', DEMO_LOCK_CHANNEL='test', OPENAI_API_KEY='k'),
               dict(PATH='/usr/local/bin:/usr/bin', HOME='/h', LANG='de_DE.UTF-8', NO_COLOR='0')]
    vals = dict(cache='/c', python='/py', python_version='3.13.18', env='/e')
    out = [dict(spec=s, parent=p, home='/h', vals=vals, lock='/l', port=4567, extra={'DEMO_APP_VERSION': '1.0.0'},
                uv_env=_uv_env(s, p, '/h', vals), server_env=_server_env(s, p, '/h', {'DEMO_APP_VERSION': '1.0.0'}),
                sync=['sync', '--frozen', '--no-install-project', '--project', '/l', '--inexact', '--extra', 'a'], server_args=['--app', '--port', '4567']) for p in parents]
    (FIX/'childenv_cases.json').write_text(json.dumps(out, indent=1, sort_keys=True) + '\n')

BRIDGE = [
    ({'method': 'open_folder', 'args': ['/x']}, {'open_folder': '/x'}), ({'method': 'open_folder', 'args': ['']}, {'unknown': 'open_folder'}),
    ({'method': 'open_folder', 'args': []}, {'unknown': 'open_folder'}), ({'method': 'pick_folder'}, {'pick_folder': True}),
    ({'method': 'pick_path', 'args': []}, {'pick_path': True}), ({'method': 'open_path', 'args': ['/a/b.png']}, {'open_path': '/a/b.png'}),
    ({'method': 'recent', 'args': []}, {'recent': True}), ({'method': 'set_background', 'args': ['#1a2B3c']}, {'set_background': '#1a2B3c'}),
    ({'method': 'set_background', 'args': ['red; x']}, {'unknown': 'set_background'}),
    ({'method': 'set_title', 'args': ['a — x', 'http://127.0.0.1:5010/']}, {'set_title': 'a — x', 'url': 'http://127.0.0.1:5010/'}),
    ({'method': 'set_title', 'args': ['a']}, {'set_title': 'a'}), ({'method': 'eval', 'args': ['x']}, {'unknown': 'eval'})]

STATES = [
    dict(name='an old state.json with only some keys loads', json={'current': 'aa', 'highest_n': 3}, want=dict(current='aa', previous=None, pending=None, highest_n=3, bad=[], extras=[], early_crashes=0)),
    dict(name='an empty state is the first launch', json={}, want=dict(current=None, previous=None, pending=None, highest_n=-1, bad=[], extras=[], early_crashes=0))]

# what EnvStore does to state.json; `built` are the env hashes with a marker
MOVES = [
    dict(name='a pending env becomes current at launch', built=['a', 'b'], before=dict(current='a', pending='b', locks={'a': 1, 'b': 2}, highest_n=1), op='switch_at_launch', after=dict(current='b', previous='a', pending=None, highest_n=2)),
    dict(name='a bad pending env is not switched to', built=['a', 'b'], before=dict(current='a', pending='b', bad=['b']), op='switch_at_launch', after=dict(current='a', pending=None)),
    dict(name='rollback marks the current env bad', built=['a', 'b'], before=dict(current='b', previous='a'), op='rollback_bad', after=dict(current='a', previous=None, bad=['b'])),
    dict(name='use previous version holds the current env', built=['a', 'b'], before=dict(current='b', previous='a'), op='rollback_held', after=dict(current='a', previous='b', held=['b'])),
    dict(name='no previous env: no rollback', built=['b'], before=dict(current='b'), op='rollback_bad', after=dict(current='b', bad=[]))]

MANIFESTS = [  # a change to a signed manifest's field, and what the launcher says
    dict(name='good', set={}, want='ok'), dict(name='a lower lock number is a replay', set={}, highest=7, want='replay'),
    dict(name='another platform', set={'platform': 'win32-x64'}, want='platform'), dict(name='a newer macOS', set={'macos_min': '99.0'}, want='macOS'),
    dict(name='a newer uv needs a newer app', set={'uv_min': '0.99.0'}, want='needsApp', hash_uv='0.99.0'), dict(name='a newer launcher API needs a newer app', set={'launcher_api_min': 2}, want='needsApp'),
    dict(name='a wrong lock hash', set={'hash': '0' * 64}, want='lockHash'), dict(name='a wrong file hash', set={'files': {'uv.lock': '0' * 64}}, want='fileHash'),
    dict(name='a hash that failed before', set={}, bad=True, want='bad')]

POINTERS = [dict(name='a stable pointer', channel='channel', asked='channel', want='ok'), dict(name='a test pointer served as stable', channel='channel-test', asked='channel', want='pointer'),
            dict(name='an old expires field is ignored', channel='channel', asked='channel', extra={'expires': '2020-01-01T00:00:00Z'}, want='ok')]

def cases():
    (FIX/'bridge_cases.json').write_text(json.dumps([dict(body=b, action=a) for b, a in BRIDGE], indent=1, ensure_ascii=False) + '\n')
    (FIX/'state_cases.json').write_text(json.dumps(dict(load=STATES, moves=MOVES), indent=1) + '\n')
    (FIX/'manifest_cases.json').write_text(json.dumps(dict(manifests=MANIFESTS, pointers=POINTERS), indent=1) + '\n')

def leela():
    tmp = Path(tempfile.mkdtemp()); (tmp/'packaging').mkdir()
    shutil.copy(FIX/'leela'/'kavacha.toml', tmp/'packaging'/'kavacha.toml')
    (FIX/'leela'/'kavacha.json').write_text(json.dumps(Thin.load(tmp).config(), indent=1, sort_keys=True, ensure_ascii=False) + '\n')

if __name__ == '__main__':
    lock_vector(); childenv_cases(); cases(); leela()
    if '--sshsig' in sys.argv: fixtures(FIX/'sshsig', 'demo-lock')
    print(f'fixtures in {FIX}')
