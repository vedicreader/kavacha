"The environment lock of a thin app: the checks that refuse a lock, the pinned project, the test record, the refusals of publish, and signing. A Leela-shaped spec drives it."
import json, os, shutil, subprocess, tomllib
from datetime import datetime, timedelta, timezone
from pathlib import Path
import pytest
from kavacha import lock as K
from kavacha.thin import Thin

FIX = Path(__file__).resolve().parent.parent/'contract'/'fixtures'
DL = 'https://github.com/vedicreader/leela/releases/download'
LL = dict(name='llama-cpp-python', version='0.3.30', sha256='4f5b385f31dbda502d7118aff0c07c9e98961fa0402c025b89ff3250db843eb3',
          url='https://github.com/abetlen/llama-cpp-python/releases/download/v0.3.30-metal/llama_cpp_python-0.3.30-py3-none-macosx_11_0_arm64.whl')
MARKER = "sys_platform == 'darwin' and platform_machine == 'arm64'"

@pytest.fixture
def L(tmp_path):
    "The lock tool for the Leela spec, in a root of its own with no hooks."
    root = tmp_path/'root'; (root/'packaging').mkdir(parents=True)
    (root/'packaging'/'kavacha.toml').write_text((FIX/'leela'/'kavacha.toml').read_text().replace('hooks = "tools/lock_hooks.py"\n', ''))
    (root/'packaging'/'uv.version').write_text('0.13.6\n')
    return K.Lock(Thin.load(root))

def _lock(d, extras=('mlx', 'llama', 'langserver'), pkgs=(), env=True, deps=('leela',), llama_in_base=False):
    "A small lock folder: the pinned project and a uv.lock with `pkgs` beside leela-lock and leela."
    d = Path(d); d.mkdir(parents=True, exist_ok=True)
    req = f'required-environments = ["{MARKER}"]' if env else ''
    (d/'pyproject.toml').write_text(f'[project]\nname = "leela-lock"\n[tool.uv]\n{req}\n')
    (d/'.python-version').write_text('3.13.18\n')
    whl = lambda n, v: f'{{ url = "https://files.pythonhosted.org/x/{n}-{v}-py3-none-any.whl", hash = "sha256:00", size = 10 }}'
    root_deps = ', '.join(f'{{ name = "{n}" }}' for n in deps)
    opt = '\n'.join(f'{x} = [{{ name = "{x}-pkg" }}]' for x in extras)
    rows = [f'[[package]]\nname = "leela-lock"\nversion = "0"\nsource = {{ virtual = "." }}\ndependencies = [{root_deps}]\n[package.optional-dependencies]\n{opt}\n',
            f'[[package]]\nname = "leela"\nversion = "0.1.23"\nsource = {{ url = "{DL}/0.1.23/leela-0.1.23-py3-none-any.whl" }}\n'
            f'dependencies = [{"{ name = " + chr(34) + LL["name"] + chr(34) + " }" if llama_in_base else ""}]\nwheels = [{whl("leela", "0.1.23")}]\n']
    rows += [f'[[package]]\nname = "{x}-pkg"\nversion = "1.0"\nsource = {{ registry = "https://pypi.org/simple" }}\nwheels = [{whl(x, "1.0")}]\n' for x in extras]
    rows += list(pkgs)
    (d/'uv.lock').write_text('version = 1\n[options]\nexclude-newer = "2026-10-30T00:00:00Z"\n\n' + '\n'.join(rows))
    return d

def _pkg(name, source='{ registry = "https://pypi.org/simple" }', wheels=True, fn=None):
    w = f'wheels = [{{ url = "https://x/{fn or name + "-1.0-py3-none-any.whl"}", hash = "sha256:00", size = 5 }}]\n' if wheels else 'sdist = { url = "https://x/a.tar.gz" }\n'
    return f'[[package]]\nname = "{name}"\nversion = "1.0"\nsource = {source}\n{w}'

def test_a_good_lock_passes(L, tmp_path): assert L.check(_lock(tmp_path/'l')) == []

@pytest.mark.parametrize('pkg,why', [
    (_pkg('a', '{ editable = "../a" }'), 'editable'), (_pkg('b', '{ git = "https://github.com/x/b?rev=1#abc" }'), 'git'),
    (_pkg('c', '{ registry = "https://test.pypi.org/simple" }'), 'test.pypi.org'), (_pkg('d', '{ url = "https://example.com/d.whl" }'), 'URL'),
    (_pkg('e', '{ path = "/tmp/e.whl" }'), 'local path'), (_pkg('f', wheels=False), 'no wheel'),
    (_pkg('g', fn='g-1.0-cp313-cp313-manylinux_2_17_x86_64.whl'), 'no wheel'), (_pkg('g2', fn='g2-1.0-cp312-cp312-macosx_11_0_arm64.whl'), 'no wheel'),
    (_pkg(LL['name'], f'{{ url = "{LL["url"]}" }}'), 'not the pinned wheel')])
def test_a_lock_the_app_cannot_install_is_refused(L, tmp_path, pkg, why):
    got = L.check(_lock(tmp_path/'l', pkgs=[pkg]))
    assert any(why in w for w in got), got

def test_a_pinned_wheel_is_allowed_only_in_an_extra(L, tmp_path):
    llama = f'[[package]]\nname = "{LL["name"]}"\nversion = "{LL["version"]}"\nsource = {{ url = "{LL["url"]}" }}\nwheels = [{{ url = "{LL["url"]}", hash = "sha256:{LL["sha256"]}" }}]\n'
    assert L.check(_lock(tmp_path/'ok', pkgs=[llama])) == []
    assert any('base environment' in w for w in L.check(_lock(tmp_path/'base', pkgs=[llama], llama_in_base=True)))

def test_the_apps_package_from_a_local_wheel_is_only_for_a_test(L, tmp_path):
    d = _lock(tmp_path/'l')
    (d/'uv.lock').write_text((d/'uv.lock').read_text().replace(f'url = "{DL}/0.1.23/leela-0.1.23-py3-none-any.whl" }}\ndep', 'path = "/tmp/leela.whl" }\ndep'))
    assert any('local path' in w for w in L.check(d)) and L.check(d, local=True) == []

def test_extras_and_the_required_environment_must_be_there(L, tmp_path):
    assert any('extras missing' in w for w in L.check(_lock(tmp_path/'a', extras=('mlx',))))
    assert any('required-environments' in w for w in L.check(_lock(tmp_path/'b', env=False)))

def test_the_pinned_project_pins_extras_and_exempts_the_owners_packages(L, tmp_path):
    at = datetime(2026, 11, 6, tzinfo=timezone.utc)
    t = L.pyproject('0.1.23', f'{DL}/0.1.23/leela-0.1.23-py3-none-any.whl', {'mlx': ['mlx-lm>=0.31'], 'llama': ['llama-cpp-python==0.3.30'], 'langserver': ['basedpyright>=1.39']}, ['ramabana'], at)
    p = tomllib.loads(t)
    assert p['project']['requires-python'] == '==3.13.*' and p['project']['dependencies'] == ['leela==0.1.23'] and p['project']['name'] == 'leela-lock'
    assert p['tool']['uv']['required-environments'] == [MARKER] and p['tool']['uv']['exclude-newer'] == '2026-10-30T00:00:00Z'
    assert p['tool']['uv']['exclude-newer-package'] == {'ramabana': '2026-11-06T00:00:00Z'} and p['tool']['uv']['sources']['llama-cpp-python'] == {'url': LL['url']}
    (tmp_path/'uv.lock').write_text('version = 1\n[[package]]\nname = "mlx-lm"\nversion = "0.32.2"\n[[package]]\nname = "basedpyright"\nversion = "1.40.2"\n[[package]]\nname = "llama-cpp-python"\nversion = "0.3.30"\n')
    assert tomllib.loads(L.pin_extras(t, tmp_path))['project']['optional-dependencies'] == {'mlx': ['mlx-lm==0.32.2'], 'llama': ['llama-cpp-python==0.3.30'], 'langserver': ['basedpyright==1.40.2']}

def test_the_manifest_has_the_contract_keys(L, tmp_path):
    m = L.manifest(_lock(tmp_path/'l'), 4, '0.13.6')
    assert set(m) == {'n', 'hash', 'files', 'leela', 'python', 'uv_min', 'launcher_api_min', 'platform', 'macos_min', 'download_bytes'}
    assert set(m['files']) == set(K.FILES) and m['leela'] == '0.1.23' and m['platform'] == 'darwin-arm64'
    doc = (FIX.parent/'api-1.md').read_text()
    assert all(f'`{k}`' in doc for k in m if k != 'leela'), 'the contract names every manifest key'

def test_the_child_env_drops_the_parents_python_and_uv_settings(L):
    e = L.child_env(dict(PATH='/usr/bin', VIRTUAL_ENV='/v', UV_INDEX_URL='x', PYTHONPATH='p', LEELA_HOST_TOKEN='t', HOME='/h'), cache='/c', python='/py', python_version='3.12.16', env='/e')
    assert not {'VIRTUAL_ENV', 'UV_INDEX_URL', 'PYTHONPATH', 'LEELA_HOST_TOKEN'} & set(e) and e['UV_PROJECT_ENVIRONMENT'] == '/e' and e['HOME'] == '/h'
    s = L.server_env(dict(PATH='/usr/bin:/x', VIRTUAL_ENV='/v', UV_INDEX_URL='x', OPENAI_API_KEY='k'))
    assert not [k for k in s if k.startswith('UV_')] and 'VIRTUAL_ENV' not in s and 'NO_COLOR' not in s and s['OPENAI_API_KEY'] == 'k'
    assert s['PATH'].startswith(os.path.expanduser('~/.local/bin') + ':/opt/homebrew/bin') and s['PATH'].endswith(':/x')
    o = L.server_env_old('/e', dict(PATH='/usr/bin'), cache='/c', python='/py', python_version='3.12.16')
    assert o['PATH'].startswith('/e/bin:') and o['VIRTUAL_ENV'] == '/e' and o['PYTHONNOUSERSITE'] == '1'

def _record(L, d, h, **kw):
    (d/'tested').mkdir(exist_ok=True)
    (d/'tested'/f'{h}.json').write_text(json.dumps(dict(hash=h, passed=True, uv=L.pinned_version(), test_code=L.test_code_hash(), time=K.iso(K.now())) | kw))

@pytest.mark.parametrize('kw,why', [({}, ''), ({'passed': False}, 'did not pass'), ({'uv': '0.1.0'}, 'not the pinned'), ({'test_code': 'x'}, 'changed since the test'),
                                    ({'time': K.iso(K.now() - timedelta(days=8))}, 'days old')])
def test_a_test_record_must_pass_be_fresh_and_match_uv_and_the_test_code(L, tmp_path, kw, why):
    _record(L, tmp_path, 'h', **kw)
    r, msg = L.record_for('h', tmp_path)
    assert (r is not None) == (not why) and why in msg and L.record_for('other', tmp_path)[1].startswith('no test record')

def test_the_test_code_hash_covers_the_hooks_file(L):
    a = L.test_code_hash()
    (L.root/'hooks.py').write_text('def smoke(s): pass\n'); L.t.hooks = 'hooks.py'
    assert L.test_code_hash() != a

def test_publish_refuses_an_untested_lock_a_dirty_tree_and_a_downgrade(L, tmp_path, monkeypatch):
    d = _lock(tmp_path/'lock')
    monkeypatch.setattr(L, 'tree_clean', lambda: 'the git tree has changes that are not committed')
    monkeypatch.setattr(L, 'key_paths', lambda home=None: [tmp_path/'none'])
    why = L.refusals(d, {'leela': '0.2.0'}, keys_pub=tmp_path/'none.pub')
    assert any('not committed' in w for w in why) and any('no test record' in w for w in why) and any('lower than the published' in w for w in why) and any('lock key' in w for w in why)
    assert not any('lower than' in w for w in L.refusals(d, {'leela': '0.2.0'}, allow_downgrade=True))

def test_publish_stops_before_any_network_call_when_refused(L, tmp_path, monkeypatch):
    monkeypatch.setattr(L, 'channel', lambda *a, **kw: pytest.fail('no network before the local refusals pass'))
    monkeypatch.setattr(L, 'tree_clean', lambda: 'dirty')
    with pytest.raises(SystemExit, match='lock publish refuses'): L.publish(_lock(tmp_path/'lock'), keys_pub=tmp_path/'k.pub')

def test_a_failed_build_writes_no_passing_record(L, tmp_path, monkeypatch):
    fake = tmp_path/'uv'
    fake.write_text('#!/bin/sh\nif [ "$1" = "--version" ]; then echo "uv 0.13.6"; exit 0; fi\necho "no network" >&2; exit 2\n'); fake.chmod(0o755)
    monkeypatch.setenv('LEELA_UV', str(fake))
    rec = L.lock_test(_lock(tmp_path/'lock'), fresh=True, record_dir=tmp_path/'records')
    assert not rec['passed'] and rec['results'][0]['step'] == 'uv sync' and 'no network' in rec['results'][0]['error'] and not (tmp_path/'records').exists()

def test_the_pinned_uv_must_be_the_pinned_version(L, tmp_path, monkeypatch):
    fake = tmp_path/'uv'; fake.write_text('#!/bin/sh\necho "uv 0.0.1"\n'); fake.chmod(0o755)
    monkeypatch.setenv('LEELA_UV', str(fake))
    with pytest.raises(SystemExit, match='not the pinned'): L.pinned_uv()

needs_keygen = pytest.mark.skipif(not Path('/usr/bin/ssh-keygen').exists(), reason='no ssh-keygen')

@needs_keygen
def test_lock_key_makes_both_keys_refuses_to_overwrite_and_prints_them(L, tmp_path):
    home = tmp_path/'home'; home.mkdir()
    pubs = L.lock_key(home=home, keys_out=tmp_path/'keys.pub', passphrase=False, agent=False)
    main, emergency = L.key_paths(home)
    assert main.name == 'leela_lock_ed25519' and main.is_file() and emergency.is_file() and pubs.count('ssh-ed25519') == 2 and 'leela-lock-main' in pubs
    assert oct(main.stat().st_mode & 0o777) == '0o600' and oct(main.parent.stat().st_mode & 0o777) == '0o700'
    with pytest.raises(SystemExit, match='refusing to overwrite'): L.lock_key(home=home, passphrase=False, agent=False)

@needs_keygen
def test_a_signed_lock_verifies_and_a_changed_byte_or_another_key_does_not(L, tmp_path, monkeypatch):
    home = tmp_path/'home'; home.mkdir()
    L.lock_key(home=home, keys_out=tmp_path/'keys.pub', passphrase=False, agent=False)
    monkeypatch.setenv('HOME', str(home)); monkeypatch.setenv('SSH_AUTH_SOCK', str(tmp_path/'no-agent'))
    d = _lock(tmp_path/'lock')
    (d/'manifest.json').write_text(K.dumps(L.manifest(d, 3, '0.13.6')))
    L.sign(d/'manifest.json', L.key_paths(home)[0]).rename(d/'manifest.sig')
    assert L.check_lock_dir(d, tmp_path/'keys.pub')['n'] == 3
    with pytest.raises(SystemExit, match='not newer'): L.check_lock_dir(d, tmp_path/'keys.pub', highest=3)
    (d/'uv.lock').write_text((d/'uv.lock').read_text() + '\n')
    with pytest.raises(SystemExit, match='does not match the manifest'): L.check_lock_dir(d, tmp_path/'keys.pub')
    other = tmp_path/'other'; other.mkdir()
    L.lock_key(home=other, keys_out=tmp_path/'other.pub', passphrase=False, agent=False)
    assert not L.verify_sig(d/'manifest.json', d/'manifest.sig', tmp_path/'other.pub')

def test_a_pointer_names_its_channel_and_an_old_expires_field_is_ignored(L, tmp_path, monkeypatch):
    p = K.pointer(4, 'ab', 'channel-test')
    assert p['channel'] == 'channel-test' and 'expires' not in p
    monkeypatch.setattr(L, 'verify_sig', lambda *a: True)
    asked = []
    serve = lambda body: monkeypatch.setattr(K, 'fetch', lambda url, dst=None, **kw: (asked.append(kw), Path(dst).write_text(json.dumps(body)) if dst else None)[1])
    serve(p)
    with pytest.raises(SystemExit, match='pointer for channel-test'): L.channel('channel', tmp_path/'k')
    serve(p | {'expires': '2020-01-01T00:00:00Z'})
    assert L.channel('channel-test', tmp_path/'k')['n'] == 4
    assert asked and all(kw.get('fresh') for kw in asked), 'a pointer is replaced in place, so it is always read past the cache'

def test_the_lock_tests_refuse_the_app_the_person_runs(L, tmp_path, monkeypatch):
    (cfg := tmp_path/'.config'/'leela').mkdir(parents=True)
    (cfg/'serving.json').write_text(json.dumps({'pid': os.getpid(), 'port': 5999, 'ports': [6001]}))
    assert K.live_ports('Leela', tmp_path) == {5999, 6001}
    (cfg/'serving.json').write_text(json.dumps({'pid': 999999, 'port': 5999}))
    assert K.live_ports('Leela', tmp_path) == set(), 'a stale file names nobody'
    monkeypatch.setattr(K, 'live_ports', lambda name, home=None: {5999})
    fake = tmp_path/'uv'; fake.write_text('#!/bin/sh\necho "uv 0.13.6"\n'); fake.chmod(0o755); monkeypatch.setenv('LEELA_UV', str(fake))
    s = K.Smoke(L, tmp_path/'env', [])
    with pytest.raises(RuntimeError, match='the Leela you are running'): s.get('http://127.0.0.1:5999/health')

def test_hooks_come_from_the_apps_file(L):
    (L.root/'hooks.py').write_text('def extra_reqs(): return {"mlx": ["mlx-lm"], "llama": [], "langserver": []}\n'); L.t.hooks = 'hooks.py'
    assert L.extra_reqs()['mlx'] == ['mlx-lm'] and L.hook('smoke') is None

def test_verify_app_refuses_a_bundle_that_is_not_this_spec(L, tmp_path):
    import plistlib
    c = tmp_path/'Leela.app'/'Contents'; (c/'Resources').mkdir(parents=True)
    (c/'Info.plist').write_bytes(plistlib.dumps(dict(CFBundleIdentifier='x')))
    with pytest.raises(SystemExit) as e: L.verify_app(tmp_path/'Leela.app')
    msg = str(e.value)
    assert "'org.vedicreader.leela'" in msg and 'no launcher' in msg and 'no kavacha.json' in msg and 'no Helpers/uv' in msg

def test_fetch_goes_past_the_cache_and_waits_out_a_new_releases_404(tmp_path, monkeypatch):
    "GitHub served a replaced channel pointer from its cache for minutes, so lock publish saw the old lock and stopped."
    import io, urllib.error
    urls, fails = [], [2]
    def opener(url, timeout=30):
        urls.append(url)
        if fails[0]: fails[0] -= 1; raise urllib.error.HTTPError(url, 404, 'not yet', {}, None)
        return io.BytesIO(b'{"n": 2}')
    monkeypatch.setattr(K.urllib.request, 'urlopen', opener); monkeypatch.setattr(K.time, 'sleep', lambda s: None)
    assert K.fetch('https://x/lock-channel/c.json', tmp_path/'c', fresh=True, tries=3, new=True) == b'{"n": 2}' and len(urls) == 3
    assert all('?t=' in u for u in urls) and (tmp_path/'c').read_bytes() == b'{"n": 2}'
    fails[0] = 1
    with pytest.raises(urllib.error.HTTPError): K.fetch('https://x/a', tries=3)   # a 404 is an answer, unless the release is new
    assert len(urls) == 4, 'one more try, not three'

def test_fetch_tries_again_on_a_server_error_and_a_dropped_connection(tmp_path, monkeypatch):
    "GitHub answered 504 for minutes on 8 Nov 2026, and `lock verify` stopped on the first one."
    import io, urllib.error
    seen, queue = [], [urllib.error.HTTPError('u', 504, 'Gateway Time-out', {}, None), urllib.error.URLError('connection reset'), TimeoutError()]
    def opener(url, timeout=30):
        seen.append(url)
        if queue: raise queue.pop(0)
        return io.BytesIO(b'ok')
    monkeypatch.setattr(K.urllib.request, 'urlopen', opener); monkeypatch.setattr(K.time, 'sleep', lambda s: None)
    assert K.fetch('https://x/a') == b'ok' and len(seen) == 4
    queue[:] = [urllib.error.HTTPError('u', 503, 'down', {}, None)] * 9
    with pytest.raises(urllib.error.HTTPError, match='503'): K.fetch('https://x/a', tries=3)
    queue[:] = [urllib.error.HTTPError('u', 403, 'forbidden', {}, None)]; seen.clear()
    with pytest.raises(urllib.error.HTTPError, match='403'): K.fetch('https://x/a')
    assert len(seen) == 1, 'a 403 is not retried'

def test_stale_says_why_the_test_record_cannot_be_used_and_is_empty_when_it_can(L, tmp_path):
    "`make ship` skips the lock test only for a lock whose record is usable; after a kavacha change the old record is stale."
    d = tmp_path/'lock'; _lock(d)
    assert L.stale(d).startswith('no test record')
    h = K.lock_hash(d, L.pinned_version()); _record(L, d, h)
    assert L.stale(d) == ''
    _record(L, d, h, test_code='old')
    assert 'changed since the test' in L.stale(d)
