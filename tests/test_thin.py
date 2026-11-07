"A thin app's spec: the golden Leela spec gives the names Leela 1.0 shipped with, and the shared fixtures hold on the Python side."
import json, os
from pathlib import Path
import pytest
from kavacha.thin import Thin, childenv, CHILDENV
from kavacha.lock import Lock, lock_hash
from kavacha.host import HostClient, owned

FIX = Path(__file__).resolve().parent.parent/'contract'/'fixtures'

def leela(tmp_path):
    (tmp_path/'packaging').mkdir(exist_ok=True)
    (tmp_path/'packaging'/'kavacha.toml').write_text((FIX/'leela'/'kavacha.toml').read_text())
    return Thin.load(tmp_path)

def test_the_leela_spec_gives_leelas_names(tmp_path):
    t = leela(tmp_path)
    assert (t.identifier, t.sig_ns, t.marker, t.env_prefix, t.server, t.lock_project, t.cask) == ('org.vedicreader.leela', 'leela-lock', '.leela-env.json', 'LEELA_', 'leela', 'leela-lock', 'leela')
    assert t.key_names == ['leela_lock_ed25519', 'leela_lock_emergency_ed25519'] and t.python == '3.13.18' and t.extras == ['mlx', 'llama', 'langserver']
    c = t.config()
    assert (c['support'], c['bridge']['handler'], c['bridge']['flag'], c['bridge']['js_global'], c['debug_env']) == ('Leela', 'leela', '__leela', 'pywebview', 'LEELA_WEBVIEW_DEBUG')
    assert c['channel'] == 'https://github.com/vedicreader/leela/releases/download' and c['window']['home'] == 'leela:home' and c['window']['size'] == [1440, 900]
    assert c['sites'] == {'list': '/app/sites', 'go': '/hub/go/'} and c['python'] == '3.13'

def test_the_leela_child_environment_is_the_one_leela_shipped(tmp_path):
    assert leela(tmp_path).spec_env('darwin') == json.loads((FIX/'leela'/'childenv.json').read_text())

def test_the_leela_config_fixture_is_current(tmp_path):
    "The Swift golden test reads contract/fixtures/leela/kavacha.json; regenerate it with tests/regen_fixtures.py."
    assert json.loads((FIX/'leela'/'kavacha.json').read_text()) == leela(tmp_path).config()

def test_the_plist_has_what_the_launcher_and_finder_need(tmp_path):
    p = leela(tmp_path).info_plist()
    assert (p['CFBundleExecutable'], p['CFBundleIdentifier'], p['CFBundleIconFile'], p['LSMinimumSystemVersion'], p['NSHumanReadableCopyright']) == ('Leela', 'org.vedicreader.leela', 'AppIcon', '14.0', 'Apache-2.0')
    assert p['NSAppTransportSecurity'] == {'NSAllowsLocalNetworking': True}

def test_the_host_names_are_leelas():
    assert owned('LEELA_') == ('LEELA_HOST_URL', 'LEELA_HOST_TOKEN', 'LEELA_APP_VERSION', 'LEELA_APP_BUNDLE', 'LEELA_LOCK_N', 'LEELA_ENV_HASH', 'LEELA_UV')
    assert HostClient('LEELA_', 'Leela').steered('PYTHONPATH')

def test_the_childenv_spec_has_both_os_sections():
    assert set(CHILDENV) >= {'darwin', 'win32'} and 'darwin' not in childenv('X_', 'win32')

# the fixtures shared with the Swift side

def test_the_lock_hash_vector():
    v = json.loads((FIX/'lock_hash'/'vector.json').read_text())
    assert lock_hash(FIX/'lock_hash', v['uv']) == v['hash']
    assert all(lock_hash(FIX/'lock_hash', o['uv']) == o['hash'] for o in v['others'])

def test_childenv_cases(tmp_path, monkeypatch):
    "The server's environment and the build command, as the launcher makes them; `uv_env` is checked on the Swift side."
    lk = Lock(Thin('Demo'), tmp_path)
    for c in json.loads((FIX/'childenv_cases.json').read_text()):
        monkeypatch.setenv('HOME', c['home']); lk.spec = lambda c=c: c['spec']
        assert lk.server_env(c['parent']) | c['extra'] == c['server_env']
        assert lk.sync_args(c['lock'], ['a'], inexact=True) == c['sync']

@pytest.mark.skipif(not Path('/usr/bin/ssh-keygen').exists(), reason='no ssh-keygen')
def test_sshsig_fixtures(tmp_path):
    lk, d = Lock(Thin('App'), tmp_path), FIX/'sshsig'
    got = {k: lk.verify_sig(d/'message.json', d/f'{k}.sig', d/'keys.pub') for k in ('main', 'emergency', 'stranger', 'wrongns')}
    assert got == {'main': True, 'emergency': True, 'stranger': False, 'wrongns': False}
