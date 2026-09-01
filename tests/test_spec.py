"One app described once, and the freezer options that follow from it."
import sys
import pytest
from kavacha.spec import App, DEFAULT_EXCLUDES, GUI_MODULE, doc_types, mypyc_modules, tree

def app(**kw):
    return App(name='Demo', entry='demo_app.py', version='1.2.3', **kw)

def test_an_app_names_its_bundle_and_where_it_lands(tmp_path):
    a = app()
    assert a.bundle_name == ('Demo.app' if sys.platform == 'darwin' else 'Demo')
    assert a.out(tmp_path) == tmp_path/'dist'/a.bundle_name

def test_a_bundle_identifier_is_derived_but_can_be_given():
    assert app().identifier == 'org.demo.demo'
    assert app(identifier='com.example.demo').identifier == 'com.example.demo'

def test_the_plist_carries_what_every_local_web_app_needs():
    """Loopback HTTP, the dark appearance, and UTF-8 before the interpreter starts. Each of these
    is a thing an app is silently broken without, and none is discoverable from a failure."""
    p = app(summary='a demo').info_plist()
    assert p['NSAppTransportSecurity'] == {'NSAllowsLocalNetworking': True}, 'or WKWebView refuses 127.0.0.1'
    assert p['NSRequiresAquaSystemAppearance'] is False, 'or a dark UI renders on a white window'
    assert p['LSEnvironment']['PYTHONUTF8'] == '1'
    assert p['CFBundleVersion'] == '1.2.3' and p['CFBundleGetInfoString'] == 'a demo'

def test_the_callers_own_plist_entries_win():
    p = app(plist={'CFBundleName': 'Other', 'NSMicrophoneUsageDescription': 'why'}).info_plist()
    assert p['CFBundleName'] == 'Other' and p['NSMicrophoneUsageDescription'] == 'why'
    assert p['CFBundleIdentifier'] == 'org.demo.demo', 'and the rest is still there'

def test_document_types_are_only_added_when_there_are_some():
    assert 'CFBundleDocumentTypes' not in app().info_plist()
    assert app(doc_types=doc_types(['.py'])).info_plist()['CFBundleDocumentTypes']

def test_an_editor_owns_its_files_and_only_alternates_for_folders():
    "Finder is the right default for a folder; this is what puts Open With on it all the same."
    rows = doc_types(['.py', '.rs', '.svg', '.pdf'])
    folder, files = rows
    assert folder['LSHandlerRank'] == 'Alternate' and folder['LSItemContentTypes'] == ['public.folder']
    assert files['LSHandlerRank'] == 'Owner'
    assert files['CFBundleTypeExtensions'] == ['py', 'rs'], 'a browser renders svg and pdf better'

def test_the_backends_this_build_is_not_using_are_excluded():
    "Shipping three webview backends is about 100MB of libraries the app will never load."
    ex = app().excluded('darwin')
    assert GUI_MODULE['win32'] in ex and GUI_MODULE['linux'] in ex
    assert GUI_MODULE['darwin'] not in ex
    assert set(DEFAULT_EXCLUDES) <= set(ex)

def test_a_callers_own_exclusions_are_added_not_replaced():
    ex = app(excludes=['mlx', 'torch']).excluded('darwin')
    assert 'mlx' in ex and 'torch' in ex and 'tkinter' in ex

def test_the_py2app_options_say_what_the_scanner_cannot_find():
    """A freezer's scanner cannot see an import made inside a function, which is most of any real
    app, so packages are named rather than discovered."""
    o = app(packages=['demo', 'numpy'], includes=['demo.cli'], icon='x.icns').py2app_options()
    assert o['packages'] == ['demo', 'numpy'] and o['includes'] == ['demo.cli']
    assert o['iconfile'] == 'x.icns'
    assert o['argv_emulation'] is False, 'it costs a visible Apple Event wait at every launch'
    assert o['site_packages'] is True and o['plist']['CFBundleName'] == 'Demo'

def test_an_app_with_no_icon_does_not_claim_one():
    assert 'iconfile' not in app().py2app_options()

def test_the_py2exe_options_carry_the_same_lists():
    o = app(packages=['demo'], excludes=['mlx']).py2exe_options()
    assert o['packages'] == ['demo'] and 'mlx' in o['excludes']
    assert GUI_MODULE['darwin'] in o['excludes']

def test_a_data_tree_is_walked_into_the_pairs_a_freezer_wants(tmp_path):
    src = tmp_path/'static'
    (src/'js').mkdir(parents=True); (src/'img').mkdir()
    (src/'app.css').write_text('a{}'); (src/'js'/'app.js').write_text('//')
    (src/'img'/'logo.png').write_text('x'); (src/'.hidden').write_text('no')
    (src/'__pycache__').mkdir(); (src/'__pycache__'/'x.pyc').write_text('no')
    got = dict(tree(src, 'demo/static'))
    assert set(got) == {'demo/static', 'demo/static/js', 'demo/static/img'}
    assert [p.split('/')[-1] for p in got['demo/static']] == ['app.css'], 'no dotfiles, no pycache'

def test_a_tree_can_skip_a_folder_by_name(tmp_path):
    src = tmp_path/'static'; (src/'js').mkdir(parents=True)
    (src/'a.css').write_text('a{}'); (src/'js'/'a.js').write_text('//')
    assert set(dict(tree(src, 'd', skip={'js'}))) == {'d'}

def test_mypyc_accelerators_beside_a_package_are_found_by_shape(tmp_path):
    """`chardet` is built with mypyc, so importing it imports a top-level extension whose name is a
    build hash. Nothing references it by name, so no scanner finds it and the package looks whole."""
    (tmp_path/'chardet__mypyc.cpython-312-darwin.so').write_text('')
    (tmp_path/'other.so').write_text('')
    assert mypyc_modules(tmp_path) == ['chardet__mypyc']
