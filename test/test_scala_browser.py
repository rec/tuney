from tuney.scale.ratios import Ratios
from tuney.scale.scala_browser import build_trie, scala_scales, scales_zip_path


def test_scala_scales_load_from_zipped_toml() -> None:
    scales = scala_scales()

    assert scales_zip_path().name == 'scales.toml.zip'
    assert len(scales) == 5401
    assert scales['zwolle'].name == 'zwolle.scl'
    assert scales['zwolle'].desc == 'Henri Arnaut De Zwolle. Pythagorean on G flat.'


def test_scala_trie_navigates_prefixes() -> None:
    ratios = {
        'abc': Ratios(text='2', name='abc.scl', desc='first'),
        'abd': Ratios(text='3', name='abd.scl', desc='second'),
        'b': Ratios(text='4', name='b.scl', desc='third'),
    }
    trie = build_trie(ratios)

    assert trie.choices('') == ['a', 'b']
    assert trie.choices('ab') == ['c', 'd']
    assert trie.terminal('ab') is None
    assert trie.terminal('abc') == ratios['abc']
    assert trie.first('ab') == ratios['abc']
