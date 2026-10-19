"What happens to a bundle after the freezer wrote it."
import os, shutil, subprocess, sys, zipfile
from pathlib import Path
import pytest
from kavacha.bundle import _lib_dir, corrupt, graft, link_duplicates, macho, mend_frameworks, sign, strip_zip
from kavacha.probe import backend, is_framework, py_version, running_from, shell_ready, wait_for_http

def mkapp(tmp_path, version=None):
    "A bundle shaped the way py2app leaves one, without running py2app."
    v = version or 'python%d.%d' % sys.version_info[:2]
    lib = tmp_path/'Demo.app'/'Contents'/'Resources'/'lib'/v
    lib.mkdir(parents=True)
    return tmp_path/'Demo.app', lib

def test_the_lib_directory_is_found_on_either_layout(tmp_path):
    app, lib = mkapp(tmp_path)
    assert _lib_dir(app) == lib
    with pytest.raises(SystemExit): _lib_dir(tmp_path/'nothing')

def test_grafting_refuses_a_bundle_built_on_another_python(tmp_path):
    """The package carries compiled modules built for the interpreter doing the grafting, so a
    bundle on another version would take a wrong-ABI `.so` and fail at import with nothing to
    point at it."""
    app, _ = mkapp(tmp_path, version='python3.99')
    with pytest.raises(SystemExit, match='bundle is python3.99'): graft(app, 'json')

def test_grafting_a_package_that_is_not_here_says_so(tmp_path):
    app, _ = mkapp(tmp_path)
    with pytest.raises(SystemExit, match='not installed'): graft(app, 'no_such_package_xyz')

def test_the_flattened_extension_module_is_removed_before_the_real_one_lands(tmp_path):
    """A freezer flattens a package whose `__init__` is the extension module down to a lone `.so`,
    which then shadows the directory that replaces it."""
    app, lib = mkapp(tmp_path)
    (lib/'fastcore.cpython-312-darwin.so').write_text('the flattened one')
    graft(app, 'fastcore')
    assert not list(lib.glob('fastcore.*so')) and (lib/'fastcore'/'__init__.py').exists()

def test_a_grafted_package_is_compiled_and_importing_it_writes_nothing(tmp_path):
    """A signed bundle that writes `__pycache__` on first import no longer verifies."""
    app, lib = mkapp(tmp_path)
    graft(app, 'json')
    pys, pycs = list((lib/'json').rglob('*.py')), list((lib/'json').rglob('*.pyc'))
    assert len(pycs) == len(pys), 'one compiled file per source'
    assert {int.from_bytes(f.read_bytes()[4:8], 'little') for f in pycs} == {1}, 'hash-based, the source never checked'
    before = {f: f.stat().st_mtime_ns for f in lib.rglob('*')}
    src = f"import sys; sys.dont_write_bytecode = False; sys.path.insert(0, {str(lib)!r}); import json.decoder, json.tool; assert json.__file__.startswith({str(lib)!r})"
    subprocess.run([sys.executable, '-I', '-c', src], check=True)
    assert {f: f.stat().st_mtime_ns for f in lib.rglob('*')} == before

def test_stripping_drops_only_the_prefixes_it_was_given(tmp_path):
    app, lib = mkapp(tmp_path)
    z = lib.parent/'python312.zip'
    with zipfile.ZipFile(z, 'w') as f:
        f.writestr('keep/a.py', 'x' * 5000)
        f.writestr('drop/b.py', 'y' * 5000)
    strip_zip(app, ('drop/',))
    with zipfile.ZipFile(z) as f: assert f.namelist() == ['keep/a.py']

def test_stripping_nothing_rewrites_nothing(tmp_path):
    app, lib = mkapp(tmp_path)
    z = lib.parent/'python312.zip'
    with zipfile.ZipFile(z, 'w') as f: f.writestr('keep/a.py', 'x')
    before = z.stat().st_mtime_ns
    assert strip_zip(app, ('absent/',)) == 0 and strip_zip(app, ()) == 0
    assert z.stat().st_mtime_ns == before

def test_a_bundle_with_no_archive_is_not_an_error(tmp_path):
    app, _ = mkapp(tmp_path)
    assert strip_zip(app, ('anything/',)) == 0

def test_identical_grafted_files_become_one_copy_on_disk(tmp_path):
    """A fork of a package ships the same large binary byte for byte, so grafting both writes it
    twice. These are read-only library files, so a hardlink cannot surprise anyone."""
    app, lib = mkapp(tmp_path)
    blob = b'z' * 2_000_000
    for name in ('one', 'two'):
        (lib/name).mkdir()
        (lib/name/'node').write_bytes(blob)
    saved = link_duplicates(app, ['one', 'two'], floor=1_000_000)
    assert saved == 2
    assert os.stat(lib/'one'/'node').st_ino == os.stat(lib/'two'/'node').st_ino
    assert (lib/'two'/'node').read_bytes() == blob, 'and both are still real, readable files'

def test_small_files_are_left_alone(tmp_path):
    app, lib = mkapp(tmp_path)
    for name in ('one', 'two'):
        (lib/name).mkdir(); (lib/name/'small').write_bytes(b'z' * 10)
    assert link_duplicates(app, ['one', 'two'], floor=1_000_000) == 0
    assert os.stat(lib/'one'/'small').st_ino != os.stat(lib/'two'/'small').st_ino

def test_a_running_bundle_is_found_by_its_executable_not_its_command_line(tmp_path):
    """The check itself names the bundle in its own arguments, and so does every grep, editor and
    shell that has the path in it."""
    app = tmp_path/'Demo.app'
    ps = ('  PID COMMAND\n'
          f'  101 {app}/Contents/MacOS/Demo --serve\n'
          f'  102 /usr/bin/grep {app}\n'
          f'  103 /bin/zsh\n')
    assert running_from(app, ps) == [101]

def test_nothing_running_is_an_empty_list(tmp_path):
    assert running_from(tmp_path/'Demo.app', '  PID COMMAND\n  1 /sbin/launchd\n') == []

def test_the_platform_says_whether_a_window_is_even_possible():
    assert backend('darwin') == 'cocoa' and backend('win32') == 'edgechromium'
    assert backend('sunos') is None
    ok, why = shell_ready('sunos')
    assert ok is False and 'sunos' in why

def test_an_interpreter_that_will_not_answer_is_none_rather_than_a_guess():
    assert py_version('/definitely/not/a/python') is None
    assert py_version(sys.executable) == tuple(sys.version_info[:2])

def test_a_standalone_build_is_not_a_framework_build():
    "uv's and pyenv's interpreters are python-build-standalone, which py2app cannot embed."
    assert is_framework('/definitely/not/a/python') is False

def test_waiting_for_a_server_that_never_comes_gives_up(tmp_path):
    assert wait_for_http('http://127.0.0.1:1/nothing', timeout=.3, interval=.05) is False

needs_cc = pytest.mark.skipif(not all(map(shutil.which, ('cc', 'codesign', 'install_name_tool'))), reason='needs cc, codesign and install_name_tool')

def dylib(d, src, name='liblzma.5.dylib'):
    "A small dylib built from C `src` into `d`."
    d.mkdir(parents=True, exist_ok=True)
    (c := d/'x.c').write_text(src)
    subprocess.run(['cc', '-dynamiclib', '-o', d/name, c, '-install_name', str(d/name)], check=True)
    return d/name

@needs_cc
def test_a_library_with_the_header_of_its_namesake_is_mended_from_a_clean_copy(tmp_path):
    """py2app copies Frameworks libraries by basename and rewrites headers per node, so Homebrew's
    `liblzma.5.dylib` and Pillow's left one file holding the first's load commands over the second's
    body, and `codesign` refused it with 'main executable failed strict validation'."""
    small = dylib(tmp_path/'brew', 'int f(void){return 1;}')
    big = dylib(tmp_path/'pil', 'static const char pad[200000]={1};int f(void){return pad[7];}')
    app, _ = mkapp(tmp_path)
    (fw := app/'Contents'/'Frameworks').mkdir()
    end = macho(small)[0]['cmds_end']
    (bad := fw/small.name).write_bytes(small.read_bytes()[:end] + big.read_bytes()[end:])
    assert corrupt(bad) and not corrupt(small) and not corrupt(big)
    assert subprocess.run(['codesign', '--force', '-s', '-', bad], capture_output=True).returncode != 0
    got = mend_frameworks(app, search=[tmp_path/'brew', tmp_path/'pil'])
    assert got['mended'] == {small.name: str(big.resolve())}, 'the copy whose size matches the body'
    assert got['clashes'] == {small.name: sorted(str(p.resolve()) for p in (small, big))}
    assert not corrupt(bad) and macho(bad)[0]['id'] == '@executable_path/../Frameworks/liblzma.5.dylib'
    subprocess.run(['codesign', '--force', '-s', '-', bad], check=True)
    assert mend_frameworks(app, search=[tmp_path/'brew', tmp_path/'pil'])['mended'] == {}, 'and a second pass finds nothing'

@needs_cc
def test_a_corrupt_library_with_no_clean_copy_is_reported_not_skipped(tmp_path):
    small = dylib(tmp_path/'a', 'int f(void){return 1;}')
    big = dylib(tmp_path/'b', 'static const char pad[200000]={1};int f(void){return pad[7];}')
    app, _ = mkapp(tmp_path)
    (fw := app/'Contents'/'Frameworks').mkdir()
    end = macho(small)[0]['cmds_end']
    (fw/small.name).write_bytes(small.read_bytes()[:end] + big.read_bytes()[end:])
    assert mend_frameworks(app)['mended'] == {small.name: None}

@needs_cc
def test_signing_keeps_hardlinked_copies_one_file(tmp_path):
    """`codesign --force` writes a new file, so signing each path split the hardlinks `link_duplicates`
    made, and the bundle carried the same 121MB browser driver twice."""
    app = tmp_path/'Demo.app'
    (mac := app/'Contents'/'MacOS').mkdir(parents=True)
    (app/'Contents'/'Info.plist').write_text('<?xml version="1.0" encoding="UTF-8"?><plist version="1.0"><dict>'
        '<key>CFBundleExecutable</key><string>Demo</string><key>CFBundleIdentifier</key><string>org.example.demo</string>'
        '<key>CFBundlePackageType</key><string>APPL</string></dict></plist>')
    (c := tmp_path/'m.c').write_text('int main(void){return 0;}')
    subprocess.run(['cc', '-o', mac/'Demo', c], check=True)
    lib = app/'Contents'/'Resources'/'lib'
    for n in ('one', 'two'): (lib/n).mkdir(parents=True)
    shutil.copy(mac/'Demo', lib/'one'/'node'); os.link(lib/'one'/'node', lib/'two'/'node')
    sign(app, '-', run=lambda *a: subprocess.run([str(x) for x in a], check=True, capture_output=True))
    assert os.stat(lib/'one'/'node').st_ino == os.stat(lib/'two'/'node').st_ino
    subprocess.run(['codesign', '--verify', '--strict', lib/'two'/'node'], check=True)
