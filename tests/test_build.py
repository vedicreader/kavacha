"The build driver: what it would do, and the stamp it leaves behind."
import json, subprocess, sys
from pathlib import Path
import pytest
from kavacha.build import (STAMP, git_stamp, lock_requirements, read_stamp, stamp_path,
                           write_stamp, check)
from kavacha.spec import App

def app(): return App(name='Demo', entry='demo_app.py', version='2.0.1')

def mkrepo(tmp_path):
    "A git checkout with one commit in it, which is what a stamp reads."
    def git(*a): subprocess.run(['git', *a], cwd=tmp_path, capture_output=True, check=True)
    git('init', '-q')
    git('config', 'user.email', 'a@b.c'); git('config', 'user.name', 'T')
    (tmp_path/'x.txt').write_text('one')
    git('add', '-A'); git('commit', '-qm', 'first')
    return tmp_path

def test_the_stamp_sits_where_each_platform_keeps_it(tmp_path):
    assert stamp_path(tmp_path/'Demo.app') == tmp_path/'Demo.app'/'Contents'/'Resources'/STAMP
    assert stamp_path(tmp_path/'Demo') == tmp_path/'Demo'/STAMP

def test_a_stamp_records_the_commit_and_whether_the_tree_was_dirty(tmp_path):
    """A bundle is derived from the tree and nothing else compares them, so an app built before a
    fix installs over one built after it and reports the version it always did."""
    repo = mkrepo(tmp_path)
    st = git_stamp(repo, version='2.0.1')
    assert len(st['commit']) == 40 and st['dirty'] is False and st['version'] == '2.0.1'
    (repo/'x.txt').write_text('changed')
    assert git_stamp(repo)['dirty'] is True

def test_outside_a_checkout_there_is_no_commit_to_record(tmp_path):
    assert git_stamp(tmp_path) is None

def test_a_stamp_round_trips_through_a_built_bundle(tmp_path):
    repo = mkrepo(tmp_path)
    bundle = tmp_path/'dist'/'Demo.app'/'Contents'/'Resources'
    bundle.mkdir(parents=True)
    written = write_stamp(tmp_path/'dist'/'Demo.app', repo, '2.0.1')
    got = read_stamp(tmp_path/'dist'/'Demo.app')
    assert got == written and got['version'] == '2.0.1'

def test_a_bundle_with_no_stamp_reads_as_none(tmp_path):
    assert read_stamp(tmp_path/'Demo.app') is None

def test_a_stamp_is_still_written_outside_a_checkout(tmp_path):
    "A build from a tarball has no commit, and that is a fact to record rather than a failure."
    d = tmp_path/'Demo'; d.mkdir()
    st = write_stamp(d, tmp_path, '2.0.1')
    assert st['commit'] == '' and st['version'] == '2.0.1'
    assert read_stamp(d)['built']

def test_no_lock_means_no_pinned_requirements(tmp_path):
    "Falling back to resolving from pyproject is the documented behaviour, not an error."
    assert lock_requirements(tmp_path) is None

def test_check_answers_on_a_platform_that_cannot_build(tmp_path):
    """`check` exists to be runnable anywhere: a person on Linux asking what a macOS build needs
    should get an answer, not a SystemExit."""
    rows = check(app(), tmp_path)
    assert rows['app'] == 'Demo' and rows['out'].endswith(app().bundle_name)
    assert rows['platform'] == sys.platform and rows['running'] == []
    assert 'freezer' in rows and rows['pywebview'] in ('installed', 'MISSING')
    if sys.platform not in ('darwin', 'win32'): assert 'builds nothing' in rows['freezer']
