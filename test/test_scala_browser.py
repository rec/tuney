from tuney.scale import scala_browser
from tuney.scale.ratios import Ratios


def test_scala_scales_load_from_zipped_toml() -> None:
    scales = scala_browser.scala_scales()

    assert scala_browser.scales_zip_path().name == 'scales.toml.zip'
    assert len(scales) == 5401
    assert scales['zwolle'].name == 'zwolle.scl'
    assert scales['zwolle'].desc == 'Henri Arnaut De Zwolle. Pythagorean on G flat.'


def test_scales_zip_path_accepts_pyinstaller_nested_zip(tmp_path, monkeypatch) -> None:
    bundle_root = tmp_path / 'bundle'
    nested = bundle_root / scala_browser.SCALES_ZIP / scala_browser.SCALES_ZIP.name
    nested.parent.mkdir(parents=True)
    nested.write_bytes(b'zip')
    monkeypatch.setattr(scala_browser.sys, '_MEIPASS', str(bundle_root), raising=False)

    assert scala_browser.scales_zip_path() == nested


def test_scala_trie_navigates_prefixes() -> None:
    ratios = {
        'abc': Ratios(text='2', name='abc.scl', desc='first'),
        'abd': Ratios(text='3', name='abd.scl', desc='second'),
        'b': Ratios(text='4', name='b.scl', desc='third'),
    }
    trie = scala_browser.build_trie(ratios)

    assert trie.choices('') == ['a', 'b']
    assert trie.choices('ab') == ['c', 'd']
    assert trie.terminal('abc') is None
    assert trie.terminal('abc.scl') == ratios['abc']
    assert trie.first('ab') == ratios['abc']
