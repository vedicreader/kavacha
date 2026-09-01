"One square image to the assets a bundle wants."
import sys
import pytest
from pathlib import Path
from kavacha.icons import ICNS_SIZES, ICO_SIZES, favicon, ico, iconset

PIL = pytest.importorskip('PIL')
from PIL import Image

def mkpng(path, size=1024, colour=(20, 20, 30, 255)):
    Image.new('RGBA', (size, size), colour).save(path)
    return path

def test_an_iconset_carries_every_size_macos_draws(tmp_path):
    src = mkpng(tmp_path/'logo.png')
    out = iconset(src, tmp_path/'Demo.iconset')
    got = sorted(p.stem for p in out.glob('*.png'))
    assert got == sorted(name for _, name in ICNS_SIZES)
    assert Image.open(out/'icon_512x512@2x.png').size == (1024, 1024)
    assert Image.open(out/'icon_16x16.png').size == (16, 16)

def test_a_non_square_image_is_refused_before_it_is_drawn_wrongly(tmp_path):
    p = tmp_path/'wide.png'
    Image.new('RGBA', (800, 400)).save(p)
    with pytest.raises(ValueError, match='has to be square'): iconset(p, tmp_path/'x.iconset')

def test_an_image_too_small_to_upscale_well_is_refused(tmp_path):
    "macOS draws icons at 1024. Accepting a 128px source means shipping a blurred app icon."
    p = mkpng(tmp_path/'small.png', size=128)
    with pytest.raises(ValueError, match='1024'): iconset(p, tmp_path/'x.iconset')

def test_an_ico_holds_every_size_in_the_one_file(tmp_path):
    src = mkpng(tmp_path/'logo.png')
    out = ico(src, tmp_path/'out'/'Demo.ico')
    assert out.exists()
    with Image.open(out) as im:
        assert (16, 16) in im.info['sizes'] and (256, 256) in im.info['sizes']
        assert len(im.info['sizes']) == len(ICO_SIZES)

def test_a_favicon_is_small_because_a_tab_is_small(tmp_path):
    src = mkpng(tmp_path/'logo.png')
    out = favicon(src, tmp_path/'web'/'favicon.png')
    assert Image.open(out).size == (64, 64)

def test_transparency_survives_every_step(tmp_path):
    "An icon on a plate the OS draws needs its alpha; flattening it puts a black square on the Dock."
    src = tmp_path/'logo.png'
    Image.new('RGBA', (1024, 1024), (10, 20, 30, 0)).save(src)
    out = iconset(src, tmp_path/'Demo.iconset')
    assert Image.open(out/'icon_256x256.png').getpixel((0, 0))[3] == 0

@pytest.mark.skipif(sys.platform != 'darwin', reason='iconutil is macOS only')
def test_an_icns_is_built_where_iconutil_exists(tmp_path):
    from kavacha.icons import icns
    src = mkpng(tmp_path/'logo.png')
    assert icns(src, tmp_path/'Demo.icns').exists()

@pytest.mark.skipif(sys.platform == 'darwin', reason='here iconutil exists')
def test_asking_for_an_icns_elsewhere_says_why_it_cannot(tmp_path):
    from kavacha.icons import icns
    src = mkpng(tmp_path/'logo.png')
    with pytest.raises(RuntimeError, match='iconutil'): icns(src, tmp_path/'Demo.icns')
