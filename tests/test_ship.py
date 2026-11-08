"The release steps that talk to Apple and GitHub: the verdict is read, stapling is tried again, and a broken gh login stops the release before the slow steps."
import json
from types import SimpleNamespace as NS
import pytest
from kavacha import ship as S

def _run(stdout='', stderr='', calls=None):
    "A stand-in for subprocess.run that records the command; never reaches a real program."
    def run(cmd, **kw):
        calls.append(cmd) if calls is not None else None
        return NS(stdout=stdout(cmd) if callable(stdout) else stdout, stderr=stderr, returncode=0)
    return run

def test_notarize_returns_the_id_of_an_accepted_submission(monkeypatch):
    calls = []
    monkeypatch.setattr(S.subprocess, 'run', _run(json.dumps({'id': 'abc-1', 'status': 'Accepted'}), calls=calls))
    assert S.notarize('x.zip', ['--key', 'k']) == 'abc-1'
    assert calls[0][:3] == ['xcrun', 'notarytool', 'submit'] and '--output-format' in calls[0] and calls[0][-1] == 'json'

def test_notarize_stops_on_a_rejection_even_when_the_tool_exits_zero_and_shows_apples_log(monkeypatch):
    "`notarytool submit --wait` can exit 0 for an Invalid submission; stapling then fails with a code that names no cause."
    def out(cmd): return json.dumps({'id': 'abc-2', 'status': 'Invalid'}) if cmd[2] == 'submit' else 'issue: the signature of the binary is invalid'
    monkeypatch.setattr(S.subprocess, 'run', _run(out))
    with pytest.raises(SystemExit) as e: S.notarize('x.zip', [])
    assert 'abc-2' in str(e.value) and 'Invalid' in str(e.value) and 'signature of the binary is invalid' in str(e.value)

def test_notarize_names_what_it_got_when_there_is_no_verdict(monkeypatch):
    monkeypatch.setattr(S.subprocess, 'run', _run('', stderr='Error: invalid credentials'))
    with pytest.raises(SystemExit, match='no verdict: Error: invalid credentials'): S.notarize('x.zip', [])

def test_staple_tries_again_while_apples_ticket_service_catches_up(monkeypatch):
    sleeps, calls = [], []
    def sh(*cmd, **kw):
        calls.append(cmd[2])
        if cmd[2] == 'staple' and calls.count('staple') < 3: raise SystemExit('stapler staple failed: Error 73')
        return ''
    monkeypatch.setattr(S, 'sh', sh); monkeypatch.setattr(S.time, 'sleep', sleeps.append)
    S.staple('Leela.app', tries=6, wait=20)
    assert calls == ['staple', 'staple', 'staple', 'validate'] and sleeps == [20, 20]

def test_staple_gives_up_after_its_tries_with_the_tools_own_message(monkeypatch):
    sleeps = []
    monkeypatch.setattr(S, 'sh', lambda *a, **k: (_ for _ in ()).throw(SystemExit('stapler staple failed: Error 73')))
    monkeypatch.setattr(S.time, 'sleep', sleeps.append)
    with pytest.raises(SystemExit, match='Error 73'): S.staple('Leela.app', tries=3, wait=5)
    assert sleeps == [5, 5]

def test_a_broken_gh_login_stops_the_release_before_anything_is_built(tmp_path, monkeypatch):
    (keys := tmp_path/'keys.pub').write_text('ssh-ed25519 AAAA x')
    def gh(*a, **k): raise SystemExit('gh release list failed: To get started with GitHub CLI, please run: gh auth login')
    lk = NS(t=NS(build_dir='build', name='Leela'), keys_pub=keys, root=tmp_path, gh=gh)
    built = []
    monkeypatch.setattr(S, 'sh', lambda *a, **k: ''); monkeypatch.setattr(S, 'build_mac', lambda *a, **k: built.append(1))
    with pytest.raises(SystemExit, match='gh auth login'): S.ship_mac(lk, '1.0.1', 'Developer ID Application: X (T)')
    assert not built, 'no build, notarize or upload ran'
